import os
import time
import uuid

from flask import Flask, request, jsonify, send_from_directory

from yt_dlp import YoutubeDL

from config import DOWNLOAD_DIR, PROXY, CLEANUP_MAX_AGE_MINUTES, USE_DENO_EJS

app = Flask(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def clean_old_files(max_age_minutes=None):
    max_age = max_age_minutes if max_age_minutes is not None else CLEANUP_MAX_AGE_MINUTES
    now = time.time()
    max_age_seconds = max_age * 60
    if not os.path.isdir(DOWNLOAD_DIR):
        return
    for filename in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.isfile(path) and (now - os.path.getctime(path)) > max_age_seconds:
            try:
                os.remove(path)
                print(f"[cleanup] Removido: {filename}")
            except Exception as e:
                print(f"[cleanup] Erro ao remover {filename}: {e}")


def _ydl_base_opts(outtmpl):
    opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
    }
    if PROXY:
        opts["proxy"] = PROXY
    if USE_DENO_EJS:
        opts["js_runtimes"] = {"deno": {}}
        opts["remote_components"] = ["ejs:github"]
    return opts


def download_media(url: str, options: dict) -> str:
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def _get_url_from_request():
    url = request.args.get("url")
    if url:
        return url
    data = request.get_json(silent=True) or {}
    return data.get("url")


# ---------- Health ----------
@app.route("/", methods=["GET"])
def index():
    return "running ✅"


# ---------- Unified Download Endpoint ----------
@app.route("/download", methods=["POST", "GET"])
def download():
    """Identifica a plataforma e baixa a mídia usando a lógica correta."""
    clean_old_files()
    url = _get_url_from_request()
    
    if not url:
        return jsonify({"error": "URL não fornecida"}), 400

    # Verifica se o usuário quer apenas áudio
    data = request.get_json(silent=True) or {}
    download_type = request.args.get("type") or data.get("type", "video")
    is_audio = download_type == "audio"

    file_id = str(uuid.uuid4())
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")
    
    # Lógica de identificação e configuração de opções
    is_youtube = "youtube.com" in url or "youtu.be" in url

    if is_audio and not is_youtube:
        return jsonify({"error": "Download de áudio disponível apenas para YouTube"}), 400

    if is_youtube:
        # Requisito específico: Priorizar MP4 com áudio e usar Deno para vídeo, 
        # ou apenas áudio (M4A) se solicitado.
        if is_audio:
            options = {
                **_ydl_base_opts(outtmpl),
                "format": "bestaudio[ext=m4a]",
            }
        else:
            options = {
                **_ydl_base_opts(outtmpl),
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
                "js_runtimes": {"deno": {}},
                "remote_components": ["ejs:github"]
            }
    elif "pinterest" in url:
        options = {
            **_ydl_base_opts(outtmpl),
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
        }
    elif "x.com" in url or "twitter.com" in url or "facebook.com" in url or "fb.watch" in url:
        if "x.com" in url:
            url = url.replace("x.com", "twitter.com")
        
        options = {
            **_ydl_base_opts(outtmpl),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }
    else:
        # Download genérico
        options = {
            **_ydl_base_opts(outtmpl),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }

    try:
        file_path = download_media(url, options)
        filename = os.path.basename(file_path)
        
        # Consolidando a geração da URL de download
        base_url = request.host_url.rstrip("/")
        download_url = f"{base_url}/files/{filename}"
        
        return jsonify({
            "success": True, 
            "file": download_url,
            "type": download_type,
            "platform": "youtube" if "youtube.com" in url or "youtu.be" in url else "generic"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):
    clean_old_files()
    return send_from_directory(DOWNLOAD_DIR, filename)


if __name__ == "__main__":
    from config import PORT
    app.run(debug=True, host="0.0.0.0", port=PORT, use_reloader=False)
