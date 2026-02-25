import asyncio
import threading
import os
import secrets
from flask import Flask, render_template_string, redirect, url_for, session, request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import firebase_admin
from firebase_admin import credentials, db
from github import Github

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "zggfds/database"
FIREBASE_URL = os.environ.get("FIREBASE_URL")
BOT_USERNAME = "linkgenjjjbot"

# Инициализация Firebase (с проверкой пути для Render)
cred_path = '/etc/secrets/firebase-sdk.json' if os.path.exists('/etc/secrets/firebase-sdk.json') else 'firebase-sdk.json'
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
    except Exception as e:
        print(f"Firebase Init Error: {e}")

ref = db.reference('/users')
auth_ref = db.reference('/auth_tokens')

# Инициализация Flask
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Инициализация Aiogram & GitHub
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
except Exception as e:
    print(f"GitHub Init Error: {e}")

# --- ДИЗАЙН (HTML) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ data.name or 'Профиль' }}</title>
    <style>
        body { background: #000; color: #fff; font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #111; border-radius: 35px; padding: 40px 20px; text-align: center; width: 340px; border: 2px solid {{ data.frame_color or '#333' }}; box-shadow: 0 10px 40px rgba(0,0,0,0.8); }
        .avatar { width: 140px; height: 140px; border-radius: 50%; border: 4px solid {{ data.frame_color or '#0088cc' }}; object-fit: cover; margin-bottom: 20px; background: #222; }
        .stars { color: #ffd700; font-size: 1.8rem; font-weight: bold; margin-bottom: 20px; }
        .btn { background: #0088cc; color: white; padding: 14px; border-radius: 15px; text-decoration: none; display: inline-block; font-weight: bold; margin-top: 10px; border: none; cursor: pointer; width: 85%; }
        .input-group { margin-top: 15px; text-align: left; padding: 0 20px; }
        input { width: 100%; padding: 12px; background: #222; border: 1px solid #444; color: white; border-radius: 10px; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="card">
        {% if mode == 'login' %}
            <h1>👋 Привет!</h1>
            <p style="color: #888;">Для создания профиля нажми на кнопку ниже:</p>
            <a href="https://t.me/{{ bot_username }}" class="btn">ВОЙТИ ЧЕРЕЗ БОТА</a>
        {% else %}
            <img src="{{ data.avatar_url or 'https://ui-avatars.com/api/?name=' + data.name }}" class="avatar">
            <h1>{{ data.name }}</h1>
            <div class="stars">⭐ {{ data.stars or 0 }}</div>
            
            <button class="btn" style="background: #28a745;" onclick="copyLink()">🔗 ПОДЕЛИТЬСЯ</button>

            {% if is_owner %}
                <hr style="border: 0.5px solid #333; margin: 25px 0;">
                <form action="/save" method="POST" enctype="multipart/form-data">
                    <div class="input-group"><input type="text" name="frame_color" placeholder="Цвет рамки (#hex)" value="{{ data.frame_color }}"></div>
                    <div class="input-group"><input type="text" name="steam" placeholder="Ссылка на Steam" value="{{ data.steam or '' }}"></div>
                    <div class="input-group"><input type="file" name="avatar" accept="image/*"></div>
                    <button type="submit" class="btn">СОХРАНИТЬ</button>
                </form>
                <a href="/logout" style="color: #444; font-size: 12px; display: block; margin-top: 20px; text-decoration: none;">Выход</a>
            {% endif %}
        {% endif %}
    </div>
    <script>
    function copyLink() {
        const link = window.location.origin + "/profile/{{ data.id }}";
        navigator.clipboard.writeText(link).then(() => alert("Ссылка скопирована!"));
    }
    </script>
</body>
</html>
"""

# --- БОТ (AIOGRAM) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = str(message.from_user.id)
    token = secrets.token_urlsafe(16)
    auth_ref.child(token).set({"uid": uid, "name": message.from_user.first_name})
    
    # Ссылка для входа (замени на свой домен Render)
    base_url = "https://database-project.onrender.com" 
    login_url = f"{base_url}/auth/{token}"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="ВОЙТИ НА САЙТ ✅", url=login_url))
    await message.answer(f"Привет, {message.from_user.first_name}! Твоя ссылка для входа готова:", reply_markup=builder.as_markup())

def run_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # handle_signals=False — это КЛЮЧЕВОЙ момент для работы в потоке
    loop.run_until_complete(dp.start_polling(bot, skip_updates=True, handle_signals=False))

# --- САЙТ (FLASK) ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('profile', uid=session['user_id']))
    return render_template_string(HTML_TEMPLATE, mode='login', data={}, bot_username=BOT_USERNAME)

@app.route('/auth/<token>')
def auth(token):
    auth_data = auth_ref.child(token).get()
    if auth_data:
        uid = auth_data['uid']
        session['user_id'] = uid
        auth_ref.child(token).delete()
        if not ref.child(uid).get():
            ref.child(uid).set({"id": uid, "name": auth_data['name'], "stars": 0, "frame_color": "#0088cc"})
        return redirect(url_for('profile', uid=uid))
    return "Ошибка: токен недействителен", 403

@app.route('/profile/<uid>')
def profile(uid):
    user_data = ref.child(uid).get()
    if not user_data: return "Пользователь не найден", 404
    is_owner = (session.get('user_id') == str(uid))
    if not is_owner:
        ref.child(uid).update({"stars": user_data.get('stars', 0) + 1})
        user_data['stars'] = user_data.get('stars', 0) + 1
    return render_template_string(HTML_TEMPLATE, data=user_data, is_owner=is_owner, mode='profile')

@app.route('/save', methods=['POST'])
def save():
    uid = session.get('user_id')
    if not uid: return redirect('/')
    upd = {"frame_color": request.form.get('frame_color'), "steam": request.form.get('steam')}
    file = request.files.get('avatar')
    if file and file.filename != '':
        path = f"avatars/{uid}.png"
        content = file.read()
        try:
            curr = repo.get_contents(path)
            repo.update_file(path, "upd", content, curr.sha)
        except:
            repo.create_file(path, "new", content)
        upd["avatar_url"] = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}"
    ref.child(uid).update(upd)
    return redirect(url_for('profile', uid=uid))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- ЗАПУСК ---
if __name__ == "__main__":
    # Запуск бота в фоне
    threading.Thread(target=run_bot_thread, daemon=True).start()
    # Запуск Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
else:
    # Для Gunicorn на Render
    threading.Thread(target=run_bot_thread, daemon=True).start()