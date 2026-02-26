import os
import asyncio
import secrets
import firebase_admin
from firebase_admin import credentials, db
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.environ.get("BOT_TOKEN")
FIREBASE_URL = os.environ.get("FIREBASE_URL")
SITE_URL = os.environ.get("SITE_URL") # https://твой-сайт.onrender.com

# Firebase Init
cred_path = '/etc/secrets/firebase-sdk.json' if os.path.exists('/etc/secrets/firebase-sdk.json') else 'firebase-sdk.json'
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})

auth_ref = db.reference('/auth_tokens')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    token = secrets.token_urlsafe(16)
    # Пишем токен напрямую в Firebase
    auth_ref.child(token).set({
        "uid": message.from_user.id,
        "name": message.from_user.first_name
    })
    
    login_url = f"{SITE_URL}/auth/{token}"
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="ВХОД ✅", url=login_url))
    await message.answer(f"Привет! Ссылка для входа:", reply_markup=kb.as_markup())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())