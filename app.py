import threading
import uuid
import secrets
import os
from flask import Flask, render_template_string, redirect, url_for, session, request, jsonify
import telebot
import firebase_admin
from firebase_admin import credentials, db
from github import Github

# --- КОНФИГУРАЦИЯ (Берем из переменных окружения Render) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = "linkgenjjjbot"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "zggfds/database"
FIREBASE_URL = os.environ.get("FIREBASE_URL")

# Путь к секретному файлу Firebase на Render или локально
cred_path = '/etc/secrets/firebase-sdk.json' if os.path.exists('/etc/secrets/firebase-sdk.json') else 'firebase-sdk.json'

# Инициализация Firebase
try:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
except Exception as e:
    print(f"Firebase Error: {e}")

ref = db.reference('/users')
auth_ref = db.reference('/auth_tokens')

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

bot = telebot.TeleBot(BOT_TOKEN)

# Инициализация GitHub
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
except Exception as e:
    print(f"GitHub Error: {e}")

# --- HTML ШАБЛОН (Твой дизайн) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ data.name or 'Welcome' }}</title>
    <style>
        body { background: #000; color: #fff; font-family: 'Segoe UI', Tahoma, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { 
            background: #111; border-radius: 30px; padding: 40px 20px; text-align: center; 
            width: 340px; border: 2px solid {{ data.frame_color or '#333' }};
            box-shadow: 0 10px 40px rgba(0,0,0,0.8);
        }
        .avatar { 
            width: 140px; height: 140px; border-radius: 50%; 
            border: 4px solid {{ data.frame_color or '#0088cc' }}; 
            object-fit: cover; margin-bottom: 20px; background: #222;
        }
        h1 { margin: 10px 0; font-size: 1.8rem; }
        .stars { color: #ffd700; font-size: 1.5rem; font-weight: bold; margin-bottom: 20px; }
        .btn { 
            background: #0088cc; color: white; padding: 14px 25px; border-radius: 15px; 
            text-decoration: none; display: inline-block; font-weight: bold; margin-top: 10px; border: none; cursor: pointer; width: 80%;
        }
        .input-group { margin-top: 15px; text-align: left; padding: 0 20px; }
        input { width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: white; border-radius: 10px; box-sizing: border-box; margin-top: 5px; }
        .links a { color: #0088cc; display: block; margin: 10px 0; text-decoration: none; font-weight: 600; }
    </style>
</head>
<body>
    <div class="card">
        {% if mode == 'login' %}
            <h1>Добро пожаловать</h1>
            <p style="color: #888;">Чтобы создать профиль, нажми кнопку ниже и запусти бота.</p>
            <a href="https://t.me/{{ bot_username }}" class="btn">ВОЙТИ ЧЕРЕЗ TELEGRAM</a>
        {% else %}
            <img src="{{ data.avatar_url or 'https://ui-avatars.com/api/?name=' + data.name }}" class="avatar">
            <h1>{{ data.name }}</h1>
            <div class="stars">⭐ {{ data.stars or 0 }}</div>
            
            <div class="links">
                {% if data.steam %}<a href="{{ data.steam }}" target="_blank">🎮 Steam Profile</a>{% endif %}
                {% if data.tg_channel %}<a href="{{ data.tg_channel }}" target="_blank">📢 Telegram Channel</a>{% endif %}
            </div>

            <button class="btn" style="background: #28a745;" onclick="copyLink()">🔗 ПОДЕЛИТЬСЯ</button>

            {% if is_owner %}
                <hr style="border: 0.5px solid #333; margin: 25px 0;">
                <form action="/save" method="POST" enctype="multipart/form-data">
                    <div class="input-group"><input type="text" name="frame_color" placeholder="Цвет рамки (#hex)" value="{{ data.frame_color }}"></div>
                    <div class="input-group"><input type="text" name="steam" placeholder="Steam URL" value="{{ data.steam or '' }}"></div>
                    <div class="input-group"><input type="file" name="avatar" accept="image/*"></div>
                    <button type="submit" class="btn">СОХРАНИТЬ</button>
                </form>
                <a href="/logout" style="color: #555; font-size: 12px; display: block; margin-top: 20px; text-decoration: none;">Выйти</a>
            {% endif %}
        {% endif %}
    </div>

    <script>
    function copyLink() {
        const link = window.location.origin + "/profile/{{ data.id }}";
        navigator.clipboard.writeText(link).then(() => {
            alert("Ссылка скопирована! Отправь её друзьям.");
        });
    }
    </script>
</body>
</html>
"""

# --- ЛОГИКА ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(f'/profile/{session["user_id"]}')
    return render_template_string(HTML_TEMPLATE, mode='login', data={}, bot_username=BOT_USERNAME)

@app.route('/profile/<uid>')
def profile(uid):
    user_data = ref.child(uid).get()
    if not user_data: return "User not found", 404
    
    is_owner = (session.get('user_id') == str(uid))
    
    # Начисляем звезду при просмотре профиля гостем
    if not is_owner:
        current_stars = user_data.get('stars', 0)
        ref.child(uid).update({"stars": current_stars + 1})
        user_data['stars'] = current_stars + 1

    return render_template_string(HTML_TEMPLATE, data=user_data, is_owner=is_owner, mode='profile')

@app.route('/auth/<token>')
def auth(token):
    auth_data = auth_ref.child(token).get()
    if auth_data:
        uid = auth_data['uid']
        session['user_id'] = uid
        auth_ref.child(token).delete() # Одноразовый токен

        if not ref.child(uid).get():
            ref.child(uid).set({
                "id": uid, "name": auth_data['name'], 
                "stars": 0, "frame_color": "#0088cc"
            })
        return redirect(f'/profile/{uid}')
    return "Invalid or expired token", 403

@app.route('/save', methods=['POST'])
def save():
    uid = session.get('user_id')
    if not uid: return redirect('/')
    
    upd = {
        "frame_color": request.form.get('frame_color'),
        "steam": request.form.get('steam')
    }
    
    file = request.files.get('avatar')
    if file and file.filename != '':
        path = f"avatars/{uid}.png"
        content = file.read()
        try:
            curr = repo.get_contents(path)
            repo.update_file(path, "update", content, curr.sha)
        except:
            repo.create_file(path, "create", content)
        # Важно: ветка main или master
        upd["avatar_url"] = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}"

    ref.child(uid).update(upd)
    return redirect(f'/profile/{uid}')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- БОТ ---

@bot.message_handler(commands=['start'])
def bot_welcome(message):
    uid = str(message.from_user.id)
    token = secrets.token_urlsafe(16)
    
    auth_ref.child(token).set({
        "uid": uid,
        "name": message.from_user.first_name
    })
    
    # Ссылка должна вести на твой URL на Render!
    base_url = "https://database-project.onrender.com" # ЗАМЕНИ НА СВОЙ
    login_url = f"{base_url}/auth/{token}"
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("ВОЙТИ В ПРОФИЛЬ 🛡️", url=login_url))
    
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}! Твоя секретная ссылка готова:", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    print(f"Бот получил сообщение: {message.text}") # Это отобразится в логах Render
    bot.reply_to(message, "Я тебя вижу! Пробую создать ссылку...")
    welcome(message) # Вызывает твою основную функцию


if __name__ == "__main__":
    # Локальный запуск (python main.py)
    threading.Thread(target=lambda: bot.infinity_polling(timeout=10, long_polling_timeout=5), daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
else:
    # Запуск на Render через Gunicorn
    threading.Thread(target=lambda: bot.infinity_polling(timeout=10, long_polling_timeout=5), daemon=True).start()