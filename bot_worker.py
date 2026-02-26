import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_SECRET = os.environ.get("API_SECRET", "default_secret_123")
# Внутренний адрес на Render
API_URL = "http://0.0.0.0:10000" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = str(message.from_user.id)
    name = message.from_user.first_name
    
    headers = {"X-API-Key": API_SECRET}
    payload = {"uid": uid, "name": name}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{API_URL}/api/create_token", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("token")
                    # Внешний URL для пользователя (измени на свой адрес .onrender.com)
                    site_url = f"https://siteprof.onrender.com/auth/{token}"
                    
                    kb = InlineKeyboardBuilder()
                    kb.row(types.InlineKeyboardButton(text="ЛИЧНЫЙ КАБИНЕТ 🛡️", url=site_url))
                    await message.answer(f"Привет, {name}! Твоя ссылка для входа готова. Она одноразовая:", reply_markup=kb.as_markup())
                else:
                    await message.answer("Ошибка: Сайт временно недоступен.")
        except Exception as e:
            await message.answer(f"Не удалось связаться с сервером. Подожди 30 секунд, пока сайт проснется.")

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())