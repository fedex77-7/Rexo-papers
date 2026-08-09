"""
Rexo Papers — Firestore data layer.
Handles: license keys, user profiles, usage logs, broadcast targets.
"""
import random
import string
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------------------------------------------------------------------
# Init — expects GOOGLE_APPLICATION_CREDENTIALS_JSON env var (see README)
# ---------------------------------------------------------------------------
import os
import json
import base64

def init_firebase():
    if not firebase_admin._apps:
        # Preferred: build the credentials dict from individual small env
        # vars — far less error-prone on mobile than pasting one huge
        # base64/JSON blob (each field is short and single-line except
        # private_key, which just needs its literal \n sequences kept).
        project_id = os.environ.get("FIREBASE_PROJECT_ID")
        if project_id:
            private_key = os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n")
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key_id": os.environ["FIREBASE_PRIVATE_KEY_ID"],
                "private_key": private_key,
                "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
                "client_id": os.environ.get("FIREBASE_CLIENT_ID", ""),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_CERT_URL", ""),
                "universe_domain": "googleapis.com",
            }
        else:
            # Fallbacks: base64 blob, or raw JSON blob.
            b64 = os.environ.get("FIREBASE_CREDENTIALS_B64")
            if b64:
                cleaned = "".join(b64.split())
                missing_padding = len(cleaned) % 4
                if missing_padding:
                    cleaned += "=" * (4 - missing_padding)
                cred_json = base64.b64decode(cleaned).decode("utf-8")
            else:
                cred_json = os.environ["FIREBASE_CREDENTIALS_JSON"]
            cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

KEYS = db.collection("keys")
USERS = db.collection("users")
USAGE = db.collection("usage_logs")

# ---------------------------------------------------------------------------
# Key system
# ---------------------------------------------------------------------------
def _random_key(length=12):
    chars = string.ascii_uppercase + string.digits
    raw = "".join(random.choices(chars, k=length))
    return f"REXO-{raw[:4]}-{raw[4:8]}-{raw[8:12]}"

TIER_DEFAULTS = {
    "standard": {"suggested_entries": 10, "watermark": True},
    "a_plus": {"suggested_entries": 50, "watermark": False},
    "first_class": {"suggested_entries": None, "watermark": False},  # unlimited entries
}

def normalize_tier(raw: str) -> str:
    """Accepts common ways someone might type a tier name and maps it to
    the canonical value, so a typo/casing difference never silently falls
    back to 'standard' and leaves a watermark that shouldn't be there."""
    t = (raw or "").lower().replace("-", "").replace("_", "").replace(" ", "")
    if t in ("aplus", "a+"):
        return "a_plus"
    if t in ("firstclass", "fc", "first1st", "1stclass"):
        return "first_class"
    return "standard"

def create_key(entries: int, valid_days: int, tier: str = "standard", note: str = ""):
    """Admin: create a new license key.
    tier is one of: standard, a_plus, first_class (first_class = unlimited entries)."""
    tier = normalize_tier(tier)
    unlimited = TIER_DEFAULTS[tier]["suggested_entries"] is None
    key = _random_key()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=valid_days)
    KEYS.document(key).set({
        "key": key,
        "entries_total": entries,
        "entries_left": entries,
        "unlimited": unlimited,
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
    """Returns (ok: bool, reason: str, key_data: dict|None)."""
    doc = KEYS.document(key).get()
    if not doc.exists:
        return False, "invalid", None
    data = doc.to_dict()
    if data.get("revoked"):
        return False, "revoked", data
    expires_at = data.get("expires_at")
    if expires_at and expires_at.replace(tzinfo=None) < datetime.datetime.utcnow():
        return False, "expired", data
    if not data.get("unlimited") and data.get("entries_left", 0) <= 0:
        return False, "exhausted", data
    return True, "ok", data

def consume_key(key: str, telegram_user_id: int):
    """Deduct one entry from a key after a successful paper generation.
    First Class (unlimited) keys are never decremented."""
    doc_ref = KEYS.document(key)

    @firestore.transactional
    def _txn(transaction):
        snapshot = doc_ref.get(transaction=transaction)
        data = snapshot.to_dict()
        if data.get("unlimited"):
            transaction.update(doc_ref, {"used_by": telegram_user_id})
            return True
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

# ---------------------------------------------------------------------------
# Users (language, theme, active key)
# ---------------------------------------------------------------------------
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

def add_known_key(telegram_user_id: int, key: str):
    """Remember a key this user has entered before, so they can switch
    back to it later without retyping (Settings -> My Keys)."""
    USERS.document(str(telegram_user_id)).set(
        {"known_keys": firestore.ArrayUnion([key])}, merge=True
    )

def list_known_keys(telegram_user_id: int):
    """Returns full key_data dicts for every key this user has used before."""
    user = get_user(telegram_user_id)
    known = user.get("known_keys", []) or []
    results = []
    for k in known:
        doc = KEYS.document(k).get()
        if doc.exists:
            results.append(doc.to_dict())
    return results

def all_user_ids():
    """For broadcast."""
    return [int(d.id) for d in USERS.stream()]
