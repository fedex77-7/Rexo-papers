"""
Rexo Papers — Telegram bot
Powered by Rexo International

Run: python bot.py  (needs env vars — see README.md)
"""
import os
import hashlib
import tempfile

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

import db
import ai_format
import pdf_maker
from languages import LANGUAGES, paginate
from keep_alive import start_keep_alive

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_PASSWORD_HASH = os.environ["ADMIN_PASSWORD_HASH"]  # sha256 hex — see README
ADMIN_TELEGRAM_IDS = {int(x) for x in os.environ.get("ADMIN_TELEGRAM_IDS", "").split(",") if x}

CONTACT = {
    "email": "teamrexo77@gmail.com",
    "instagram": "an_7x_n",
    "telegram": "akmflashh",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 New Question Paper", callback_data="new_paper")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("💬 Contact Admin / Developer", callback_data="contact")],
    ])

def settings_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Language", callback_data="set_lang_p0")],
        [InlineKeyboardButton("🎨 Theme (toggle)", callback_data="toggle_theme")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")],
    ])

def contact_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 Email", url=f"mailto:{CONTACT['email']}")],
        [InlineKeyboardButton("📷 Instagram", url=f"https://instagram.com/{CONTACT['instagram']}")],
        [InlineKeyboardButton("✈️ Telegram", url=f"https://t.me/{CONTACT['telegram']}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")],
    ])

def lang_kb(page=0):
    pages = paginate(LANGUAGES)
    page = max(0, min(page, len(pages) - 1))
    rows = [[InlineKeyboardButton(label, callback_data=f"lang_{code}")] for code, label in pages[page]]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"set_lang_p{page-1}"))
    if page < len(pages) - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"set_lang_p{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="settings")])
    return InlineKeyboardMarkup(rows)

# ---------------------------------------------------------------------------
# Basic commands
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.get_user(update.effective_user.id)
    await update.message.reply_text(
        "📄 *Rexo Papers*\nPowered by Rexo International\n\n"
        "Paste your exam questions, get a formatted PDF question paper — in seconds.",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id

    if data == "main_menu":
        await q.edit_message_text("📄 *Rexo Papers* — Main Menu", parse_mode="Markdown", reply_markup=main_menu_kb())

    elif data == "settings":
        await q.edit_message_text("⚙️ Settings", reply_markup=settings_kb())

    elif data == "contact":
        text = (
            "💬 *Contact Admin / Developer*\n\n"
            f"Email: `{CONTACT['email']}`\n"
            f"Instagram: @{CONTACT['instagram']}\n"
            f"Telegram: @{CONTACT['telegram']}"
        )
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=contact_kb())

    elif data.startswith("set_lang_p"):
        page = int(data.replace("set_lang_p", ""))
        await q.edit_message_text("🌐 Select your language:", reply_markup=lang_kb(page))

    elif data.startswith("lang_"):
        code = data.replace("lang_", "")
        db.update_user(uid, language=code)
        await q.edit_message_text(f"✅ Language set to {LANGUAGES.get(code, code)}.", reply_markup=settings_kb())

    elif data == "toggle_theme":
        user = db.get_user(uid)
        new_theme = "light" if user.get("theme") == "dark" else "dark"
        db.update_user(uid, theme=new_theme)
        await q.edit_message_text(f"🎨 Theme set to {new_theme}.", reply_markup=settings_kb())

    elif data == "new_paper":
        user = db.get_user(uid)
        active_key = user.get("active_key")
        ok = False
        if active_key:
            ok, reason, _ = db.validate_key(active_key)
        if not ok:
            context.user_data["state"] = "awaiting_key"
            await q.edit_message_text(
                "🔑 Please enter your Rexo access key to continue.\n"
                "(Don't have one? Contact the admin — see Contact menu.)"
            )
        else:
            context.user_data["state"] = "awaiting_meta"
            context.user_data["meta"] = {}
            await q.edit_message_text(
                "🏫 Send the exam details, one message, in this format:\n\n"
                "School Name | Exam Title | Class | Subject | Time | Full Marks\n\n"
                "Example:\nRexo International School | Term 1 Exam | 6 | Mathematics | 2:30 Hrs | 100"
            )

    elif data == "download_full":
        await send_final_pdf(update, context)

# ---------------------------------------------------------------------------
# Free-text flow: key entry -> exam meta -> questions
# ---------------------------------------------------------------------------
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    uid = update.effective_user.id
    text = update.message.text.strip()

    if state == "awaiting_key":
        ok, reason, data_ = db.validate_key(text)
        if not ok:
            reasons = {
                "invalid": "❌ That key doesn't exist.",
                "revoked": "❌ That key has been revoked.",
                "expired": "❌ That key has expired.",
                "exhausted": "❌ That key has no papers left.",
            }
            await update.message.reply_text(reasons.get(reason, "❌ Invalid key.") + "\nTry again, or contact admin.")
            return
        db.update_user(uid, active_key=text)
        context.user_data["state"] = "awaiting_meta"
        context.user_data["meta"] = {}
        await update.message.reply_text(
            f"✅ Key accepted. {data_['entries_left']} paper(s) available on this key.\n\n"
            "🏫 Now send exam details, one message:\n"
            "School Name | Exam Title | Class | Subject | Time | Full Marks"
        )
        return

    if state == "awaiting_meta":
        parts = [p.strip() for p in text.split("|")]
        keys = ["school_name", "exam_title", "cls", "subject", "time", "marks"]
        meta = dict(zip(keys, parts))
        context.user_data["meta"] = meta
        context.user_data["state"] = "awaiting_questions"
        await update.message.reply_text("✏️ Now paste all the exam questions (any language, any format).")
        return

    if state == "awaiting_questions":
        await update.message.reply_text("⏳ Formatting your paper with AI...")
        try:
            parsed = ai_format.format_paper(text)
        except Exception as e:
            await update.message.reply_text(f"⚠️ AI formatting failed: {e}\nTry again with shorter/cleaner input.")
            return

        context.user_data["parsed"] = parsed
        meta = context.user_data.get("meta", {})

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            preview_path = tmp.name
        pdf_maker.build_pdf(preview_path, parsed, meta, watermark=True)

        await update.message.reply_document(
            document=open(preview_path, "rb"),
            filename="rexo_preview.pdf",
            caption="👁 Preview (watermarked). Tap below for the clean download.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬇️ Download Full PDF", callback_data="download_full")]]),
        )
        context.user_data["state"] = None
        return

    # default: not in a flow
    await update.message.reply_text("Use /start to open the menu.", reply_markup=main_menu_kb())

async def send_final_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = db.get_user(uid)
    active_key = user.get("active_key")
    parsed = context.user_data.get("parsed")
    meta = context.user_data.get("meta", {})

    if not parsed or not active_key:
        await update.callback_query.message.reply_text("Session expired — start again with /start.")
        return

    ok, reason, key_data = db.validate_key(active_key)
    if not ok:
        await update.callback_query.message.reply_text("❌ Your key is no longer valid. Contact admin for a new one.")
        return

    consumed = db.consume_key(active_key, uid)
    if not consumed:
        await update.callback_query.message.reply_text("❌ No entries left on this key.")
        return

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        final_path = tmp.name
    watermark = key_data.get("tier") != "a_plus"
    pdf_maker.build_pdf(final_path, parsed, meta, watermark=watermark)

    _, _, refreshed = db.validate_key(active_key)
    left = refreshed["entries_left"] if refreshed else "?"

    await update.callback_query.message.reply_document(
        document=open(final_path, "rb"),
        filename="rexo_paper.pdf",
        caption=f"✅ Done! {left} paper(s) left on this key.",
    )

# ---------------------------------------------------------------------------
# Admin panel (inside the bot — password gated)
# ---------------------------------------------------------------------------
def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Create Key", callback_data="adm_create")],
        [InlineKeyboardButton("📋 List Keys", callback_data="adm_list")],
        [InlineKeyboardButton("🚫 Revoke Key", callback_data="adm_revoke")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")],
    ])

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "awaiting_admin_password"
    await update.message.reply_text("🔒 Enter admin password:")

async def admin_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if it handled the message (so text_router should stop)."""
    state = context.user_data.get("state")
    text = update.message.text.strip()

    if state == "awaiting_admin_password":
        if sha256(text) == ADMIN_PASSWORD_HASH:
            context.user_data["is_admin_session"] = True
            context.user_data["state"] = None
            await update.message.reply_text("✅ Admin verified.", reply_markup=admin_menu_kb())
        else:
            await update.message.reply_text("❌ Wrong password.")
        return True

    if not context.user_data.get("is_admin_session"):
        return False

    if state == "adm_awaiting_create":
        # format: entries days [tier] [note]
        parts = text.split()
        try:
            entries = int(parts[0])
            days = int(parts[1])
            tier = parts[2] if len(parts) > 2 else "standard"
            note = " ".join(parts[3:]) if len(parts) > 3 else ""
        except (IndexError, ValueError):
            await update.message.reply_text("Format: <entries> <valid_days> [tier] [note]\nExample: 50 30 standard \"Green Valley School\"")
            return True
        key = db.create_key(entries, days, tier, note)
        context.user_data["state"] = None
        await update.message.reply_text(f"✅ Key created:\n`{key}`\n{entries} entries, {days} days, tier={tier}", parse_mode="Markdown")
        return True

    if state == "adm_awaiting_revoke":
        ok = db.revoke_key(text)
        context.user_data["state"] = None
        await update.message.reply_text("✅ Revoked." if ok else "❌ Key not found.")
        return True

    if state == "adm_awaiting_broadcast":
        ids = db.all_user_ids()
        sent = 0
        for user_id in ids:
            try:
                await context.bot.send_message(chat_id=user_id, text=f"📢 {text}")
                sent += 1
            except Exception:
                pass
        context.user_data["state"] = None
        await update.message.reply_text(f"✅ Broadcast sent to {sent}/{len(ids)} users.")
        return True

    return False

async def admin_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not context.user_data.get("is_admin_session"):
        await q.answer("Not authorized.", show_alert=True)
        return
    await q.answer()
    data = q.data

    if data == "adm_create":
        context.user_data["state"] = "adm_awaiting_create"
        await q.message.reply_text("Send: <entries> <valid_days> [tier] [note]\nExample: 50 30 standard Green Valley School")

    elif data == "adm_list":
        keys = db.list_keys()
        if not keys:
            await q.message.reply_text("No keys yet.")
            return
        lines = [f"`{k['key']}` — {k['entries_left']}/{k['entries_total']} left, tier={k.get('tier')}, revoked={k.get('revoked')}" for k in keys]
        await q.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif data == "adm_revoke":
        context.user_data["state"] = "adm_awaiting_revoke"
        await q.message.reply_text("Send the key to revoke:")

    elif data == "adm_broadcast":
        context.user_data["state"] = "adm_awaiting_broadcast"
        await q.message.reply_text("Send the broadcast message text:")

# ---------------------------------------------------------------------------
# Combined text handler (admin flow takes priority)
# ---------------------------------------------------------------------------
async def combined_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handled = await admin_text_router(update, context)
    if not handled:
        await text_router(update, context)

# ---------------------------------------------------------------------------
def main():
    start_keep_alive()  # opens a port so Render's Web Service health check passes

    # Explicitly create and set an event loop for this thread before PTB
    # touches asyncio. Newer Python versions (3.14+) removed the automatic
    # "create one if missing" behaviour that asyncio.get_event_loop() used
    # to provide, which otherwise crashes python-telegram-bot's polling
    # startup with "There is no current event loop in thread 'MainThread'".
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(admin_callback_router, pattern="^adm_"))
    app.add_handler(CallbackQueryHandler(menu_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, combined_text_handler))

    print("Rexo Papers bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
