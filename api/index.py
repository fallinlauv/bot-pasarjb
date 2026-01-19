import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Import dari file lokal kamu
from config import BOT_TOKEN, CHANNEL_ID
from messages import *

app = Flask(__name__)

# Inisialisasi Bot
application = Application.builder().token(BOT_TOKEN).build()

# Handler Utama
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📩 Open Request", callback_data="open_request")]])
    await update.message.reply_text(MENU_TEXT, reply_markup=keyboard, parse_mode="HTML")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "open_request":
        await query.message.reply_text(MSG_SEND_REQUEST)

# Daftarkan handler ke application
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_callback))

@app.route('/', methods=['POST', 'GET'])
def is_running():
    if request.method == 'POST':
        # Proses pesan yang masuk dari Telegram
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        update = Update.de_json(request.get_json(force=True), application.bot)
        loop.run_until_complete(application.process_update(update))
        return "OK", 200
    return "Bot is Running", 200
