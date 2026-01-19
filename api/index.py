import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Mengambil variabel dari file config dan pesan milikmu
from config import BOT_TOKEN, CHANNEL_ID
from messages import *

app = Flask(__name__)

# Inisialisasi Bot secara global
application = Application.builder().token(BOT_TOKEN).build()

# --- HANDLER SECTION ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Gunakan MENU_TEXT dari file messages.py kamu
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📩 Open Request", callback_data="open_request")]])
    await update.message.reply_text(MENU_TEXT, reply_markup=keyboard, parse_mode="HTML")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "open_request":
        await query.message.reply_text(MSG_SEND_REQUEST)

# --- SETUP HANDLERS ---
# Kita buat fungsi untuk mendaftarkan handler agar tidak duplikat
def setup_handlers(app_tg):
    if not app_tg.handlers:
        app_tg.add_handler(CommandHandler("start", start))
        app_tg.add_handler(CallbackQueryHandler(handle_callback))

# --- VERCEL ROUTE ---

@app.route('/', methods=['POST', 'GET'])
def main_handler():
    if request.method == 'POST':
        setup_handlers(application)
        
        # Proses update dari Telegram secara sinkron untuk Flask
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(application.initialize())
            loop.run_until_complete(application.process_update(update))
        finally:
            loop.close()
            
        return "OK", 200
    return "Bot is Running", 200
