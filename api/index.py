import logging
import time
import asyncio
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

# Impor dari file kamu
from config import BOT_TOKEN, CHANNEL_ID
from messages import *

app = Flask(__name__)

# Variabel penyimpanan sementara
user_requests = {}
user_state = {}
user_last_post = {}
POST_COOLDOWN = 3600
ALLOWED_TAGS = {"#wts", "#wtb", "#wtt"}

# Inisialisasi Application secara global
# Kita gunakan build() tapi jangan panggil initialize() di luar loop
application = Application.builder().token(BOT_TOKEN).build()

# --- FUNGSI HELPER ---

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

def main_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📩 Open Request", callback_data="open_request")]])

def post_action_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Request", callback_data="edit_request")],
        [InlineKeyboardButton("📤 Post to Channel", callback_data="post_request")]
    ])

def validate_hashtag(text: str) -> bool:
    if not text: return False
    first_word = text.split()[0].lower()
    return first_word in {tag.lower() for tag in ALLOWED_TAGS}

# --- HANDLER SECTION ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state.pop(user_id, None)
    user_requests.pop(user_id, None)
    await update.message.reply_text(MENU_TEXT, reply_markup=main_keyboard(), parse_mode="HTML")

async def open_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not await is_user_joined(context.bot, user_id):
        await query.message.reply_text("❌ Kamu belum bergabung di saluran kami.")
        return
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

    if not await is_admin(context.bot, user_id):
        last_post = user_last_post.get(user_id)
        now = time.time()
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
        await query.message.reply_text(f"❌ Gagal kirim: {str(e)}")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or (update.message.text and update.message.text.startswith("/")): return
    user_id = update.message.from_user.id
    
    if user_state.get(user_id) != "awaiting_message": return

    text = update.message.text or update.message.caption or ""
    if not validate_hashtag(text):
        await update.message.reply_text(MSG_INVALID_HASHTAG, parse_mode="HTML")
        return

    user_requests[user_id] = {"chat_id": update.message.chat_id, "message_id": update.message.message_id}
    await update.message.reply_text(MSG_REQUEST_RECEIVED, reply_markup=post_action_keyboard())

# Daftarkan handler SEKALI SAJA di luar route
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(open_request_callback, pattern="^(open_request|edit_request)$"))
application.add_handler(CallbackQueryHandler(post_request_callback, pattern="^post_request$"))
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

# --- VERCEL ROUTE ---

@app.route('/', methods=['POST', 'GET'])
def main_handler():
    if request.method == 'POST':
        try:
            update_data = request.get_json(force=True)
            # Menggunakan loop yang sudah ada atau buat baru jika tidak ada
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Jalankan inisialisasi dan proses update dalam satu sesi loop
            async def process():
                # Pastikan bot sudah terinisialisasi
                if not application.bot_data.get('initialized'):
                    await application.initialize()
                    application.bot_data['initialized'] = True
                
                update = Update.de_json(update_data, application.bot)
                await application.process_update(update)
            
            loop.run_until_complete(process())
            loop.close()
            return 'OK', 200
        except Exception as e:
            print(f"Error: {e}")
            return 'Error', 500
            
    return 'Bot is Running', 200
