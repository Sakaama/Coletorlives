import os
import datetime
import uuid
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from google.cloud import storage, firestore

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_123')

# Configurações do GCP
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0812651894')
BUCKET_NAME = os.environ.get('BUCKET_NAME', f"{PROJECT_ID}-tutuco-media")
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
PASSWORD = "S@kamaForce1"

try:
    db = firestore.Client(project=PROJECT_ID)
    storage_client = storage.Client(project=PROJECT_ID)
except Exception as e:
    print(f"Aviso: Firestore/Storage não puderam ser inicializados localmente. Erro: {e}")
    db = None
    storage_client = None

def require_auth(f):
    def wrap(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('ai_dashboard'))
        else:
            flash("Senha incorreta!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@require_auth
def index():
    return redirect(url_for('ai_dashboard'))

@app.route('/ai')
@require_auth
def ai_dashboard():
    clips = []
    if db:
        docs = db.collection('raw_clips').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        clips = [doc.to_dict() for doc in docs]
    return render_template('ai_dashboard.html', clips=clips)

@app.route('/editor', methods=['GET', 'POST'])
@require_auth
def editor_dashboard():
    if request.method == 'POST':
        title = request.form.get('title')
        notes = request.form.get('notes')
        file = request.files.get('video_file')
        
        if file and file.filename:
            file_id = str(uuid.uuid4())
            blob_name = f"edited/{file_id}_{file.filename}"
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(blob_name)
            blob.upload_from_file(file, content_type=file.content_type)
            blob.make_public()
            
            video_url = blob.public_url
            created_at = datetime.datetime.utcnow()
            expires_at = created_at + datetime.timedelta(days=30)
            
            doc_ref = db.collection('edited_clips').document(file_id)
            doc_ref.set({
                'id': file_id,
                'title': title,
                'notes': notes,
                'video_url': video_url,
                'created_at': created_at,
                'expires_at': expires_at,
                'blob_name': blob_name
            })
            flash("Vídeo editado salvo com sucesso! Expira em 30 dias.")
            return redirect(url_for('editor_dashboard'))

    clips = []
    if db:
        docs = db.collection('edited_clips').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        clips = [doc.to_dict() for doc in docs]
    
    return render_template('editor_dashboard.html', clips=clips)

@app.route('/api/webhook/radar', methods=['POST'])
def webhook_radar():
    """Recebe dados dos radares (Twitch/YT/Kick)"""
    data = request.json
    # data: {'channel': 'gabepeixe', 'category': '...', 'hook': '...', 'context': '...', 'platform': 'twitch'}
    clip_id = str(uuid.uuid4())
    created_at = datetime.datetime.utcnow()
    expires_at = created_at + datetime.timedelta(days=14)
    
    doc_ref = db.collection('raw_clips').document(clip_id)
    doc_ref.set({
        'id': clip_id,
        'channel': data.get('channel'),
        'platform': data.get('platform'),
        'category': data.get('category'),
        'hook': data.get('hook'),
        'context': data.get('context'),
        'created_at': created_at,
        'expires_at': expires_at
    })
    return jsonify({"status": "success", "id": clip_id}), 201

@app.route('/send_telegram/<clip_id>', methods=['POST'])
@require_auth
def send_telegram(clip_id):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        flash("Configurações do Telegram ausentes.")
        return redirect(url_for('editor_dashboard'))
        
    doc = db.collection('edited_clips').document(clip_id).get()
    if not doc.exists:
        flash("Clipe não encontrado.")
        return redirect(url_for('editor_dashboard'))
        
    data = doc.to_dict()
    video_url = data['video_url']
    caption = f"🎬 *{data['title']}*\n📝 {data['notes']}"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "video": video_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    
    r = requests.post(url, json=payload)
    if r.status_code == 200:
        flash("Vídeo enviado para o Telegram com sucesso!")
    else:
        flash(f"Erro ao enviar: {r.text}")
        
    return redirect(url_for('editor_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
