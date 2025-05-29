import os
from flask import Flask, render_template, request, jsonify, send_file, abort
from yt_dlp import YoutubeDL
import requests
from dotenv import load_dotenv

# --- Configuração inicial ---
load_dotenv()
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
if not YOUTUBE_API_KEY:
    raise RuntimeError("Defina a variável de ambiente YOUTUBE_API_KEY no seu .env")

# Pasta de downloads
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Caminho do ficheiro de cookies
COOKIES_FILE = '/tmp/cookies.txt'

# Configuração do Flask
app = Flask(__name__, static_folder='static', template_folder='templates')

# Opções yt_dlp
ydl_stream_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
}
ydl_download_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
}

# Se cookies existirem, usar
if os.path.exists(COOKIES_FILE):
    ydl_stream_opts['cookiefile'] = COOKIES_FILE
    ydl_download_opts['cookiefile'] = COOKIES_FILE

# Dados em memória
favoritos = []
historico = []

YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'

# --- Funções auxiliares ---

def youtube_search(query, max_results=15):
    params = {
        'key': YOUTUBE_API_KEY,
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'maxResults': max_results,
    }
    resp = requests.get(YOUTUBE_SEARCH_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            'id': item['id']['videoId'],
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['default']['url'],
        }
        for item in data.get('items', [])
    ]

# --- Rotas ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': 'error', 'message': 'Termo de pesquisa obrigatório'}), 400
    try:
        results = youtube_search(q)
    except requests.HTTPError as e:
        return jsonify({'status': 'error', 'message': f'Erro na API do YouTube: {e}'}), 500
    return jsonify({'status': 'success', 'data': results})

@app.route('/audio_url')
def audio_url():
    video_id = request.args.get('video_id', '').strip()
    title = request.args.get('title', '').strip()
    if not video_id:
        return jsonify({'status': 'error', 'message': 'video_id é obrigatório'}), 400

    url = f'https://www.youtube.com/watch?v={video_id}'
    try:
        with YoutubeDL(ydl_stream_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Erro ao obter áudio: {e}'}), 500

    historico.append({'id': video_id, 'title': title or info.get('title', '')})
    return jsonify({'status': 'success', 'data': {'audio_url': audio_url, 'title': title}})

@app.route('/download')
def download():
    video_id = request.args.get('video_id', '').strip()
    if not video_id:
        abort(400, 'video_id é obrigatório')

    url = f'https://www.youtube.com/watch?v={video_id}'
    try:
        with YoutubeDL(ydl_download_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
    except Exception as e:
        abort(500, f'Erro ao baixar áudio: {e}')

    filename = f"{info.get('title', video_id)}.mp3"
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='audio/mpeg'
    )

@app.route('/favoritos', methods=['GET', 'POST', 'DELETE'])
def manage_favoritos():
    if request.method == 'GET':
        return jsonify({'status': 'success', 'data': favoritos})

    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Dados JSON esperados'}), 400

    if request.method == 'POST':
        if data not in favoritos:
            favoritos.append(data)
        return jsonify({'status': 'success', 'message': 'Adicionado aos favoritos'})

    if request.method == 'DELETE':
        vid = data.get('id')
        if not vid:
            return jsonify({'status': 'error', 'message': 'id é obrigatório para remover'}), 400
        favoritos[:] = [f for f in favoritos if f.get('id') != vid]
        return jsonify({'status': 'success', 'message': 'Removido dos favoritos'})

@app.route('/historico')
def get_historico():
    data = historico[-20:][::-1]
    return jsonify({'status': 'success', 'data': data})

@app.route('/upload_cookies', methods=['POST'])
def upload_cookies():
    file = request.files.get('file')
    if not file or not file.filename.endswith('.txt'):
        return jsonify({'status': 'error', 'message': 'Envie um ficheiro .txt com cookies'}), 400

    try:
        file.save(COOKIES_FILE)
        return jsonify({'status': 'success', 'message': 'Cookies guardados com sucesso'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Erro ao guardar cookies: {e}'}), 500

# --- Inicialização ---

if __name__ == '__main__':
    app.run(debug=True)

