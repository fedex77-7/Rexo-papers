import os
import json
import random
import string
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase():
    if not firebase_admin._apps:
        cred_json = os.environ["FIREBASE_CREDENTIALS_JSON"]
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

KEYS = db.collection("keys")
USERS = db.collection("users")
USAGE = db.collection("usage_logs")

def _random_key(length=12):
    chars = string.ascii_uppercase + string.digits
    raw = "".join(random.choices(chars, k=length))
    return f"REXO-{raw[:4]}-{raw[4:8]}-{raw[8:12]}"

def create_key(entries: int, valid_days: int, tier: str = "standard", note: str = ""):
    key = _random_key()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=valid_days)
    KEYS.document(key).set({
        "key": key,
        "entries_total": entries,
        "entries_left": entries,
        "tier": tier,
        "created_at": firestore.SERVER_TIMESTAMP,
        "expires_at": expiry,
        "revoked": False,
        "note": note,
        "used_by": None,
    })
    return key

def revoke_key(key: str):
    doc = KEYS.document(key)
    if not doc.get().exists:
        return False
    doc.update({"revoked": True})
    return True

def list_keys(limit=50):
    docs = KEYS.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
    return [d.to_dict() for d in docs]

def validate_key(key: str):
    doc = KEYS.document(key).get()
    if not doc.exists:
        return False, "invalid", None
    data = doc.to_dict()
    if data.get("revoked"):
        return False, "revoked", data
    expires_at = data.get("expires_at")
    if expires_at and expires_at.replace(tzinfo=None) < datetime.datetime.utcnow():
        return False, "expired", data
    if data.get("entries_left", 0) <= 0:
        return False, "exhausted", data
    return True, "ok", data

def consume_key(key: str, telegram_user_id: int):
    doc_ref = KEYS.document(key)

    @firestore.transactional
    def _txn(transaction):
        snapshot = doc_ref.get(transaction=transaction)
        data = snapshot.to_dict()
        left = data.get("entries_left", 0)
        if left <= 0:
            return False
        transaction.update(doc_ref, {
            "entries_left": left - 1,
            "used_by": telegram_user_id,
        })
        return True

    transaction = db.transaction()
    ok = _txn(transaction)
    if ok:
        USAGE.add({
            "key": key,
            "telegram_user_id": telegram_user_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
    return ok

def key_usage_history(key: str, limit=20):
    docs = (USAGE.where("key", "==", key)
                 .order_by("timestamp", direction=firestore.Query.DESCENDING)
                 .limit(limit).stream())
    return [d.to_dict() for d in docs]

def get_user(telegram_user_id: int):
    doc = USERS.document(str(telegram_user_id)).get()
    if doc.exists:
        return doc.to_dict()
    default = {
        "telegram_user_id": telegram_user_id,
        "language": "en",
        "theme": "dark",
        "active_key": None,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    USERS.document(str(telegram_user_id)).set(default)
    return default

def update_user(telegram_user_id: int, **fields):
    USERS.document(str(telegram_user_id)).set(fields, merge=True)

def all_user_ids():
    return [int(d.id) for d in USERS.stream()]
