import os
import secrets
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask, render_template_string, redirect, url_for, session, request, jsonify
from github import Github

# --- КОНФИГУРАЦИЯ ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "zggfds/database"
FIREBASE_URL = os.environ.get("FIREBASE_URL")
API_SECRET = os.environ.get("API_SECRET", "default_secret_123")
BOT_USERNAME = "linkgenjjjbot"

# Firebase
cred_path = '/etc/secrets/firebase-sdk.json' if os.path.exists('/etc/secrets/firebase-sdk.json') else 'firebase-sdk.json'
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
    except Exception as e:
        print(f"Firebase Init Error: {e}")

ref = db.reference('/users')
auth_ref = db.reference('/auth_tokens')

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# GitHub
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
except Exception as e:
    repo = None
    print(f"GitHub Error: {e}")

# --- HTML ШАБЛОН ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ data.name or 'Профиль' }}</title>
    <style>
        body { background: #0b0b0b; color: #fff; font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #161616; border-radius: 30px; padding: 40px 20px; text-align: center; width: 350px; border: 2px solid {{ data.frame_color or '#333' }}; box-shadow: 0 15px 35px rgba(0,0,0,0.7); }
        .avatar { width: 130px; height: 130px; border-radius: 50%; border: 4px solid {{ data.frame_color or '#0088cc' }}; object-fit: cover; margin-bottom: 15px; background: #222; }
        h1 { margin: 10px 0; font-size: 1.6rem; }
        .stars { color: #ffd700; font-size: 1.4rem; font-weight: bold; margin-bottom: 20px; }
        .btn { background: #0088cc; color: white; padding: 12px; border-radius: 12px; text-decoration: none; display: block; font-weight: bold; margin: 10px auto; border: none; cursor: pointer; width: 80%; }
        .input-group { margin-top: 15px; text-align: left; padding: 0 20px; font-size: 0.9rem; }
        input { width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: white; border-radius: 8px; margin-top: 5px; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="card">
        {% if mode == 'login' %}
            <h1>🔑 Вход</h1>
            <p style="color: #888;">Чтобы создать свой профиль или редактировать его, перейди в нашего бота:</p>
            <a href="https://t.me/{{ bot_username }}" class="btn">ОТКРЫТЬ TELEGRAM</a>
        {% else %}
            <img src="{{ data.avatar_url or 'https://ui-avatars.com/api/?name=' + data.name }}" class="avatar">
            <h1>{{ data.name }}</h1>
            <div class="stars">⭐ {{ data.stars or 0 }}</div>
            
            <button class="btn" style="background: #28a745;" onclick="copyLink()">🔗 ССЫЛКА НА ПРОФИЛЬ</button>

            {% if is_owner %}
                <hr style="border: 0.5px solid #333; margin: 25px 0;">
                <form action="/save" method="POST" enctype="multipart/form-data">
                    <div class="input-group">Цвет рамки:<input type="text" name="frame_color" placeholder="#0088cc" value="{{ data.frame_color }}"></div>
                    <div class="input-group">Steam URL:<input type="text" name="steam" placeholder="https://steam..." value="{{ data.steam or '' }}"></div>
                    <div class="input-group">Аватар:<input type="file" name="avatar" accept="image/*"></div>
                    <button type="submit" class="btn" style="margin-top:20px;">ОБНОВИТЬ</button>
                </form>
                <a href="/logout" style="color: #555; font-size: 11px; text-decoration: none; display: block; margin-top: 15px;">Выйти из сессии</a>
            {% endif %}
        {% endif %}
    </div>
    <script>
    function copyLink() {
        const url = window.location.origin + "/profile/{{ data.id }}";
        navigator.clipboard.writeText(url).then(() => alert("Ссылка скопирована!"));
    }
    </script>
</body>
</html>
"""

# --- API ДЛЯ БОТА ---
@app.route('/api/create_token', methods=['POST'])
def create_token():
    if request.headers.get("X-API-Key") != API_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    uid = str(data.get("uid"))
    token = secrets.token_urlsafe(16)
    auth_ref.child(token).set({"uid": uid, "name": data.get("name")})
    return jsonify({"token": token})

# --- РОУТЫ САЙТА ---
@app.route('/')
def index():
    if 'user_id' in session: return redirect(url_for('profile', uid=session['user_id']))
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
    return "Срок действия ссылки истек", 403

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
    if not uid or not repo: return redirect('/')
    upd = {"frame_color": request.form.get('frame_color'), "steam": request.form.get('steam')}
    file = request.files.get('avatar')
    if file and file.filename != '':
        path = f"avatars/{uid}.png"
        content = file.read()
        try:
            curr = repo.get_contents(path); repo.update_file(path, "upd", content, curr.sha)
        except: repo.create_file(path, "new", content)
        upd["avatar_url"] = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}"
    ref.child(uid).update(upd)
    return redirect(url_for('profile', uid=uid))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))