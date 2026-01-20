import asyncio
import time
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config import BOT_TOKEN, CHANNEL_ID
from messages import *

app = Flask(__name__)

# Gunakan satu global application instance
application = Application.builder().token(BOT_TOKEN).build()

user_requests = {}
user_state = {}
user_last_post = {}
POST_COOLDOWN = 3600
ALLOWED_TAGS = {"#wts", "#wtb", "#wtt"}

# --- HELPER ---
async def is_user_joined(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except: return False

async def is_admin(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("administrator", "creator")
    except: return False

def validate_hashtag(text: str) -> bool:
    if not text: return False
    first_word = text.split()[0].lower()
    return first_word in {tag.lower() for tag in ALLOWED_TAGS}

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state.pop(user_id, None)
    user_requests.pop(user_id, None)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📩 Open Request", callback_data="open_request")]])
    await update.message.reply_text(MENU_TEXT, reply_markup=keyboard, parse_mode="HTML")

async def open_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Jawab instan
    user_id = query.from_user.id
    if not await is_user_joined(context.bot, user_id):
        await query.message.reply_text("❌ Kamu belum bergabung di saluran kami.")
        return
    user_state[user_id] = "awaiting_message"
    await query.message.reply_text(MSG_SEND_REQUEST)

async def post_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Jawab instan
    user_id = query.from_user.id
    request_data = user_requests.get(user_id)
    if not request_data:
        await query.message.reply_text(MSG_ERROR_NO_REQUEST)
        return

    if not await is_admin(context.bot, user_id):
        now = time.time()
        last_post = user_last_post.get(user_id)
        if last_post and now - last_post < POST_COOLDOWN:
            remaining = int((POST_COOLDOWN - (now - last_post)) / 60)
            await query.message.reply_text(f"💬 Tunggu {remaining} menit lagi.")
            return

    try:
        await context.bot.copy_message(chat_id=CHANNEL_ID, from_chat_id=request_data["chat_id"], message_id=request_data["message_id"])
        user_last_post[user_id] = time.time()
        await query.edit_message_text(MSG_POST_SUCCESS, reply_markup=None)
        user_requests.pop(user_id, None)
        user_state.pop(user_id, None)
    except Exception as e:
        await query.message.reply_text(f"❌ Gagal: {str(e)}")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or (update.message.text and update.message.text.startswith("/")): return
    user_id = update.message.from_user.id
    if user_state.get(user_id) != "awaiting_message": return
    text = update.message.text or update.message.caption or ""
    if not validate_hashtag(text):
        await update.message.reply_text(MSG_INVALID_HASHTAG, parse_mode="HTML")
        return
    user_requests[user_id] = {"chat_id": update.message.chat_id, "message_id": update.message.message_id}
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Edit Request", callback_data="edit_request")], [InlineKeyboardButton("📤 Post to Channel", callback_data="post_request")]])
    await update.message.reply_text(MSG_REQUEST_RECEIVED, reply_markup=keyboard)

# REGISTRASI HANDLER (Hanya sekali)
if not application.handlers:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(open_request_callback, pattern="^(open_request|edit_request)$"))
    application.add_handler(CallbackQueryHandler(post_request_callback, pattern="^post_request$"))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

# --- VERCEL ENTRY POINT ---
@app.route('/', methods=['POST', 'GET'])
def main():
    if request.method == 'POST':
        update_data = request.get_json(force=True)
        # Gunakan loop yang lebih efisien tanpa membuat baru terus menerus jika tidak perlu
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(application.initialize())
            update = Update.de_json(update_data, application.bot)
            loop.run_until_complete(application.process_update(update))
        finally:
            loop.close()
        return 'OK', 200
    return 'Bot is Running', 200
