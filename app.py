import threading
import uuid
import secrets  # <--- Добавь эту строчку сюда!
from flask import Flask, render_template_string, redirect, url_for, session, request, flash
import telebot
import firebase_admin
from firebase_admin import credentials, db
from github import Github
# --- КОНФИГУРАЦИЯ (ЗАПОЛНИ СВОИ ДАННЫЕ) ---
BOT_TOKEN = "8601680131:AAHQv3SpgjxAbNdB52B3kghcILT8n7H7UEc"
BOT_USERNAME = "linkgenjjjbot" # Без @
GITHUB_TOKEN = "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"
GITHUB_REPO = "zggfds/database"
FIREBASE_URL = "https://qrcod-8ada6-default-rtdb.firebaseio.com/"


cred = credentials.Certificate("firebase-sdk.json")
try:
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
except: pass
ref = db.reference('/users')
auth_ref = db.reference('/auth_tokens') # Для безопасного входа

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

bot = telebot.TeleBot(BOT_TOKEN)
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

# --- УЛУЧШЕННЫЙ HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>{{ data.name or 'Профиль' }}</title>
    <style>
        body { background: #0f0f0f; color: white; font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #1a1a1a; padding: 30px; border-radius: 25px; text-align: center; width: 350px; border: 4px solid {{ data.frame_color or '#444' }}; box-shadow: 0 15px 35px rgba(0,0,0,0.5); }
        .avatar { width: 130px; height: 130px; border-radius: 50%; border: 4px solid {{ data.frame_color or '#0088cc' }}; object-fit: cover; margin-bottom: 15px; }
        .btn { background: #0088cc; color: white; padding: 12px 20px; border-radius: 12px; text-decoration: none; display: inline-block; font-weight: bold; margin: 5px; border: none; cursor: pointer; }
        .share-btn { background: #28a745; }
        .stars { color: #ffd700; font-size: 1.5rem; margin-bottom: 20px; }
        .links a { color: #0088cc; display: block; margin: 10px 0; text-decoration: none; font-weight: bold; font-size: 1.1rem; }
        input { width: 100%; padding: 10px; margin-top: 8px; background: #2a2a2a; border: 1px solid #444; color: white; border-radius: 8px; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="card">
        {% if mode == 'login' %}
            <h2>Вход в систему</h2>
            <p>Нажмите кнопку в боте для безопасного входа.</p>
            <a href="https://t.me/{{ bot_username }}" class="btn">ОТКРЫТЬ ТЕЛЕГРАМ</a>
        
        {% else %}
            <img src="{{ data.avatar_url or 'https://ui-avatars.com/api/?name='+data.name }}" class="avatar">
            <h1>{{ data.name }}</h1>
            <div class="stars">⭐ {{ data.stars or 0 }}</div>

            <div class="links">
                {% if data.tg_channel %}<a href="{{ data.tg_channel }}" target="_blank">📢 Telegram Канал</a>{% endif %}
                {% if data.steam %}<a href="{{ data.steam }}" target="_blank">🎮 Steam Profile</a>{% endif %}
            </div>

            <button class="btn share-btn" onclick="copyLink()">🔗 ПОДЕЛИТЬСЯ ПРОФИЛЕМ</button>

            {% if is_owner %}
                <hr style="border: 0.5px solid #333; margin: 20px 0;">
                <form action="/save" method="POST" enctype="multipart/form-data">
                    <input type="text" name="frame_color" placeholder="Цвет рамки (#hex)" value="{{ data.frame_color }}">
                    <input type="text" name="steam" placeholder="Steam URL" value="{{ data.steam or '' }}">
                    <input type="text" name="tg_channel" placeholder="ТГ Канал" value="{{ data.tg_channel or '' }}">
                    <input type="file" name="avatar" style="margin-top: 10px;">
                    <button type="submit" class="btn" style="width:100%; background: #555;">СОХРАНИТЬ</button>
                </form>
                <a href="/logout" style="color: #666; font-size: 12px; text-decoration: none; display: block; margin-top: 10px;">Выйти</a>
            {% endif %}
        {% endif %}
    </div>

    <script>
    function copyLink() {
        const link = window.location.origin + "/profile/{{ data.id }}";
        navigator.clipboard.writeText(link);
        alert("Ссылка скопирована! Отправь её друзьям, чтобы получить звёзды.");
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
    # Добавляем data={}, чтобы CSS не падал
    return render_template_string(HTML_TEMPLATE, data={}, mode='login', bot_username=BOT_USERNAME)

@app.route('/profile/<uid>')
def profile(uid):
    user_data = ref.child(uid).get()
    if not user_data: 
        return "Профиль не найден", 404
    
    is_owner = (session.get('user_id') == str(uid))
    
    # Начисляем звезду, если зашел гость
    if not is_owner:
        current_stars = user_data.get('stars', 0)
        ref.child(uid).child('stars').set(current_stars + 1)
        user_data['stars'] = current_stars + 1 # Обновляем для отображения
    
    return render_template_string(HTML_TEMPLATE, data=user_data, is_owner=is_owner, mode='profile')
@app.route('/auth/<token>')
def safe_auth(token):
    # Проверяем секретный токен в Firebase
    auth_data = auth_ref.child(token).get()
    if auth_data:
        uid = auth_data['uid']
        session['user_id'] = uid
        # Удаляем токен, чтобы его нельзя было использовать второй раз
        auth_ref.child(token).delete()
        
        if not ref.child(uid).get():
            ref.child(uid).set({"id": uid, "name": auth_data['name'], "stars": 0, "frame_color": "#0088cc"})
        return redirect(f'/profile/{uid}')
    return "Ошибка безопасности: токен недействителен или просрочен", 403

@app.route('/save', methods=['POST'])
def save():
    uid = session.get('user_id')
    if not uid: return redirect('/')
    
    upd = {
        "frame_color": request.form.get('frame_color'),
        "steam": request.form.get('steam'),
        "tg_channel": request.form.get('tg_channel')
    }
    
    file = request.files.get('avatar')
    if file and file.filename != '':
        path = f"avatars/{uid}.png"
        content = file.read()
        try:
            curr = repo.get_contents(path); repo.update_file(path, "upd", content, curr.sha)
        except: repo.create_file(path, "new", content)
        upd["avatar_url"] = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}"

    ref.child(uid).update(upd)
    return redirect(f'/profile/{uid}')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- БОТ ---

@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.from_user.id)
    # Генерируем случайный длинный токен
    secure_token = secrets.token_urlsafe(32)
    
    # Сохраняем его в Firebase временно
    auth_ref.child(secure_token).set({
        "uid": uid,
        "name": message.from_user.first_name
    })
    
    # Ссылка на вход (на Render замени адрес)
    login_url = f"http://127.0.0.1:5000/auth/{secure_token}"
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("ВОЙТИ В АККАУНТ 🛡️", url=login_url))
    
    bot.send_message(message.chat.id, "Ваша секретная ссылка для входа готова. Она одноразовая!", reply_markup=markup)

# В самом низу файла:
if __name__ == "__main__":
    threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)