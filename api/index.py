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

application = Application.builder().token(BOT_TOKEN).build()

user_requests = {}   # Menyimpan request aktif user
user_state = {}      # Menyimpan state user, misal 'awaiting_message'
user_last_post = {}  # Untuk cooldown post
POST_COOLDOWN = 3600
ALLOWED_TAGS = {"#wts", "#wtb", "#wtt"}

# =========================
# UTIL
# =========================
async def is_user_joined(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

# =========================
# HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state.pop(user_id, None)
    user_requests.pop(user_id, None)

    joined = await is_user_joined(context.bot, user_id)
    if not joined:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/yourchannel")]
        ])
        await update.message.reply_text(
            "Kamu harus join channel terlebih dahulu untuk menggunakan bot.", 
            reply_markup=keyboard
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Open Request", callback_data="open_request")]
    ])
    await update.message.reply_text(MENU_TEXT, reply_markup=keyboard, parse_mode="HTML")

async def open_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Cek join channel
    joined = await is_user_joined(context.bot, user_id)
    if not joined:
        await query.message.reply_text(
            f"⚠️ Kamu harus join channel terlebih dahulu: t.me/yourchannel"
        )
        return

    # Set state menunggu pesan
    user_state[user_id] = "awaiting_message"
    await query.message.reply_text(MSG_SEND_REQUEST)

async def post_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    request_data = user_requests.get(user_id)

    if not request_data:
        await query.message.reply_text(MSG_ERROR_NO_REQUEST)
        return

    # Cek Admin bypass cooldown
    is_admin = False
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        is_admin = member.status in ("administrator", "creator")
    except: 
        pass

    if not is_admin:
        now = time.time()
        last_post = user_last_post.get(user_id)
        if last_post and now - last_post < POST_COOLDOWN:
            remaining = int((POST_COOLDOWN - (now - last_post)) / 60)
            await query.message.reply_text(f"💬 Tunggu {remaining} menit lagi.")
            return

    try:
        await context.bot.copy_message(
            chat_id=CHANNEL_ID, 
            from_chat_id=request_data["chat_id"], 
            message_id=request_data["message_id"]
        )
        user_last_post[user_id] = time.time()
        await query.edit_message_text(MSG_POST_SUCCESS, reply_markup=None)
        user_requests.pop(user_id, None)
        user_state.pop(user_id, None)
    except Exception as e:
        await query.message.reply_text(f"❌ Gagal: {str(e)}")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or (update.message.text and update.message.text.startswith("/")): 
        return

    user_id = update.message.from_user.id

    # Hanya lanjutkan jika user sedang dalam state menunggu pesan
    if user_state.get(user_id) != "awaiting_message": 
        return

    # Diam jika user sudah punya request aktif
    if user_requests.get(user_id):
        return

    text = update.message.text or update.message.caption or ""
    first_word = text.split()[0].lower() if text.split() else ""

    if first_word not in {tag.lower() for tag in ALLOWED_TAGS}:
        await update.message.reply_text(MSG_INVALID_HASHTAG, parse_mode="HTML")
        return

    # Simpan request baru
    user_requests[user_id] = {
        "chat_id": update.message.chat_id,
        "message_id": update.message.id
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Request", callback_data="open_request")],
        [InlineKeyboardButton("📤 Post to Channel", callback_data="post_request")]
    ])
    await update.message.reply_text(MSG_REQUEST_RECEIVED, reply_markup=keyboard)

# =========================
# REGISTRASI HANDLER
# =========================
if not application.handlers:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(open_request_callback, pattern="^open_request$"))
    application.add_handler(CallbackQueryHandler(post_request_callback, pattern="^post_request$"))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

# =========================
# OPTIMASI FLASK/VERCEL
# =========================
@app.route('/', methods=['POST', 'GET'])
def main():
    if request.method == 'POST':
        update_data = request.get_json(force=True)
        
        async def process():
            async with application:
                update = Update.de_json(update_data, application.bot)
                await application.process_update(update)
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process())
            loop.close()
        except Exception:
            pass
            
        return 'OK', 200
    return 'Bot is Running', 200
