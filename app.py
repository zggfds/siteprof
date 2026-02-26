import os
import secrets
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask, render_template_string, redirect, url_for, session, request
from github import Github

# --- КОНФИГУРАЦИЯ ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "zggfds/database"
FIREBASE_URL = os.environ.get("FIREBASE_URL")
BOT_USERNAME = "linkgenjjjbot"

# Firebase Init
cred_path = '/etc/secrets/firebase-sdk.json' if os.path.exists('/etc/secrets/firebase-sdk.json') else 'firebase-sdk.json'
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
    except Exception as e:
        print(f"Firebase Error: {e}")

ref = db.reference('/users')
auth_ref = db.reference('/auth_tokens')

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# GitHub Init
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
except:
    repo = None

# --- HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ data.name or 'Профиль' }}</title>
    <style>
        body { background: #000; color: #fff; font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #111; border-radius: 30px; padding: 40px; text-align: center; width: 320px; border: 2px solid {{ data.frame_color or '#333' }}; }
        .avatar { width: 120px; height: 120px; border-radius: 50%; border: 3px solid {{ data.frame_color or '#0088cc' }}; object-fit: cover; }
        .stars { color: #ffd700; font-size: 1.5rem; margin: 15px 0; }
        .btn { background: #0088cc; color: #fff; padding: 12px; border-radius: 10px; text-decoration: none; display: block; margin: 10px 0; font-weight: bold; border: none; width: 100%; cursor: pointer; }
        input { width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 8px; margin-bottom: 10px; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="card">
        {% if mode == 'login' %}
            <h1>Вход</h1>
            <p>Перейдите в бота для авторизации:</p>
            <a href="https://t.me/{{ bot_username }}" class="btn">ОТКРЫТЬ БОТА</a>
        {% else %}
            <img src="{{ data.avatar_url or 'https://ui-avatars.com/api/?name=' + data.name }}" class="avatar">
            <h1>{{ data.name }}</h1>
            <div class="stars">⭐ {{ data.stars or 0 }}</div>
            <button class="btn" onclick="copyLink()">🔗 КОПИРОВАТЬ ССЫЛКУ</button>
            {% if is_owner %}
                <form action="/save" method="POST" enctype="multipart/form-data" style="margin-top: 20px;">
                    <input type="text" name="frame_color" placeholder="Цвет (#0088cc)" value="{{ data.frame_color }}">
                    <input type="text" name="steam" placeholder="Steam URL" value="{{ data.steam or '' }}">
                    <input type="file" name="avatar" accept="image/*">
                    <button type="submit" class="btn" style="background: #28a745;">СОХРАНИТЬ</button>
                </form>
                <a href="/logout" style="color: #666; font-size: 12px; text-decoration: none;">Выйти</a>
            {% endif %}
        {% endif %}
    </div>
    <script>
    function copyLink() {
        navigator.clipboard.writeText(window.location.origin + "/profile/{{ data.id }}");
        alert("Скопировано!");
    }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    if 'user_id' in session: return redirect(url_for('profile', uid=session['user_id']))
    return render_template_string(HTML_TEMPLATE, mode='login', data={}, bot_username=BOT_USERNAME)

@app.route('/auth/<token>')
def auth(token):
    auth_data = auth_ref.child(token).get()
    if auth_data:
        uid = str(auth_data['uid'])
        session['user_id'] = uid
        auth_ref.child(token).delete()
        if not ref.child(uid).get():
            ref.child(uid).set({"id": uid, "name": auth_data['name'], "stars": 0, "frame_color": "#0088cc"})
        return redirect(url_for('profile', uid=uid))
    return "Токен недействителен", 403

@app.route('/profile/<uid>')
def profile(uid):
    user_data = ref.child(uid).get()
    if not user_data: return "404", 404
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