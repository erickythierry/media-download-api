import os
import time
import uuid
import random

from flask import Flask, request, jsonify, send_from_directory
from yt_dlp import YoutubeDL

from config import (
    DOWNLOAD_DIR,
    PROXY,
    PROXY_V6,
    PROXY_V6_PORT_START,
    PROXY_V6_PORT_END,
    CLEANUP_MAX_AGE_MINUTES,
    USE_DENO_EJS
)

app = Flask(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ---------- Proxy Resolver ----------
def get_youtube_proxy():
    """
    Retorna proxy para YouTube:
    - Usa PROXY_V6 com porta aleatória se disponível
    - Caso contrário usa PROXY normal
    """

    if PROXY_V6 and PROXY_V6_PORT_START and PROXY_V6_PORT_END:
        try:
            start = int(PROXY_V6_PORT_START)
            end = int(PROXY_V6_PORT_END)

            port = random.randint(start, end)

            # garante schema
            if not PROXY_V6.startswith("http"):
                proxy = f"http://{PROXY_V6}:{port}"
            else:
                proxy = f"{PROXY_V6}:{port}"

            return proxy

        except Exception as e:
            print(f"[proxy_v6] erro ao montar proxy: {e}")

    return PROXY


# ---------- Cleanup ----------
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


# ---------- yt-dlp base ----------
def _ydl_base_opts(outtmpl, proxy=None):
    opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
    }

    if proxy:
        opts["proxy"] = proxy
    elif PROXY:
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


# ---------- Download ----------
@app.route("/download", methods=["POST", "GET"])
def download():

    clean_old_files()

    url = _get_url_from_request()

    if not url:
        return jsonify({"error": "URL não fornecida"}), 400

    data = request.get_json(silent=True) or {}
    download_type = request.args.get("type") or data.get("type", "video")

    is_audio = download_type == "audio"

    file_id = str(uuid.uuid4())
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    is_youtube = "youtube.com" in url or "youtu.be" in url
    is_tiktok = "tiktok.com" in url

    if is_audio and not is_youtube:
        return jsonify({"error": "Download de áudio disponível apenas para YouTube"}), 400

    # ---------- YOUTUBE ----------
    if is_youtube:

        proxy = get_youtube_proxy()

        if is_audio:
            options = {
                **_ydl_base_opts(outtmpl, proxy),
                "format": "bestaudio[ext=m4a]",
            }

        else:
            options = {
                **_ydl_base_opts(outtmpl, proxy),
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
                "js_runtimes": {"deno": {}},
                "remote_components": ["ejs:github"]
            }

    # ---------- TIKTOK ----------
    elif is_tiktok:

        options = {
            **_ydl_base_opts(outtmpl),
            "format": "best[vcodec=h264][acodec=aac][ext=mp4]/best[vcodec=h264][ext=mp4]",
            "merge_output_format": "mp4",
        }

    # ---------- PINTEREST ----------
    elif "pinterest" in url:

        options = {
            **_ydl_base_opts(outtmpl),
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
        }

    # ---------- TWITTER / X / FACEBOOK ----------
    elif "x.com" in url or "twitter.com" in url or "facebook.com" in url or "fb.watch" in url:

        if "x.com" in url:
            url = url.replace("x.com", "twitter.com")

        options = {
            **_ydl_base_opts(outtmpl),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }

    # ---------- GENERIC ----------
    else:

        options = {
            **_ydl_base_opts(outtmpl),
        }

    try:

        file_path = download_media(url, options)
        filename = os.path.basename(file_path)

        base_url = request.host_url.rstrip("/")
        download_url = f"{base_url}/files/{filename}"

        return jsonify({
            "success": True,
            "file": download_url,
            "type": download_type,
            "platform": "youtube" if is_youtube else "tiktok" if is_tiktok else "generic"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------- File server ----------
@app.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):

    clean_old_files()

    return send_from_directory(DOWNLOAD_DIR, filename)


if __name__ == "__main__":

    from config import PORT

    app.run(
        debug=True,
        host="0.0.0.0",
        port=PORT,
        use_reloader=False
    )