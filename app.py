import os
from flask import Flask, render_template, request, jsonify, send_file, abort
from yt_dlp import YoutubeDL
import requests
from dotenv import load_dotenv

# --- Configuração inicial ---
load_dotenv()
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
if not YOUTUBE_API_KEY:
    raise RuntimeError("Defina a variável YOUTUBE_API_KEY no .env")

# Pasta de downloads
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Caminho dos cookies (coloca cookies.txt nesta pasta)
COOKIES_FILE = os.path.join(os.path.dirname(__file__), 'cookies.txt')
if not os.path.exists(COOKIES_FILE):
    print("⚠️ cookies.txt não encontrado. Algumas músicas podem falhar.")

# Configurações do Flask
app = Flask(__name__, static_folder='static', template_folder='templates')

# yt-dlp opções com cookies
ydl_stream_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'cookiefile': COOKIES_FILE
}
ydl_download_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'cookiefile': COOKIES_FILE,
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
}

# Memória em tempo de execução
favoritos = []
historico = []

# --- Funções auxiliares ---

def youtube_search(query, max_results=15):
    params = {
        'key': YOUTUBE_API_KEY,
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'maxResults': max_results,
    }
    r = requests.get('https://www.googleapis.com/youtube/v3/search', params=params)
    r.raise_for_status()
    return [
        {
            'id': item['id']['videoId'],
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['default']['url'],
        }
        for item in r.json().get('items', [])
    ]

# --- Rotas Flask ---

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
        return jsonify({'status': 'success', 'data': results})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
            historico.append({'id': video_id, 'title': title or info.get('title', '')})
            return jsonify({'status': 'success', 'data': {'audio_url': audio_url}})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Erro ao obter áudio: {e}'}), 500

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
            filename = f"{info.get('title', video_id)}.mp3"
            return send_file(filepath, as_attachment=True, download_name=filename, mimetype='audio/mpeg')
    except Exception as e:
        abort(500, f'Erro ao baixar áudio: {e}')

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
        return jsonify({'status': 'success'})
    if request.method == 'DELETE':
        favoritos[:] = [f for f in favoritos if f.get('id') != data.get('id')]
        return jsonify({'status': 'success'})

@app.route('/historico')
def get_historico():
    return jsonify({'status': 'success', 'data': historico[-20:][::-1]})

# --- Execução ---
if __name__ == '__main__':
    app.run(debug=True)

