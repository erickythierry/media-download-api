import glob
import copy
import os
import threading
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
    TIKTOK_UA,
    USE_DENO_EJS,
    YOUTUBE_PROXY_RETRIES,
    get_ytdlp_js_runtimes,
    YTDLP_COOKIE_PATH,
)
from cookie_refresher import refresh_now, start_scheduler

app = Flask(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Sobe o renovador de cookies (idempotente; respeita COOKIE_REFRESH_ENABLED).
start_scheduler()


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
def _ydl_base_opts(outtmpl, proxy=None, user_agent=None, use_global_proxy=True):
    opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
    }

    if user_agent:
        # http_headers (e não user_agent): o impersonate do yt-dlp sobrescreve
        # o param user_agent, mas headers explícitos têm prioridade final.
        opts["http_headers"] = {"User-Agent": user_agent}

    if proxy:
        opts["proxy"] = proxy
    elif PROXY and use_global_proxy:
        opts["proxy"] = PROXY

    if USE_DENO_EJS:
        jsr = get_ytdlp_js_runtimes()
        if jsr:
            opts["js_runtimes"] = jsr
        opts["remote_components"] = ["ejs:github"]

    if YTDLP_COOKIE_PATH and os.path.isfile(YTDLP_COOKIE_PATH):
        opts["cookiefile"] = YTDLP_COOKIE_PATH

    return opts


def _get_tmpl_base(outtmpl) -> str:
    raw = outtmpl.get("default", "") if isinstance(outtmpl, dict) else str(outtmpl)
    return os.path.splitext(os.path.basename(raw))[0]


def download_media(url: str, options: dict) -> str:
    outtmpl = options["outtmpl"]  # salva antes — o yt-dlp muta o dict de opts
    with YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)
    # yt-dlp 2026.07 não preenche ext/filepath no info de algumas plataformas
    # (ex.: Twitter devolve info vazio pós-download) — resolve pelo template do
    # uuid, que é único por request. Mais novo por segurança (arquivos parciais).
    base = _get_tmpl_base(outtmpl)
    matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{base}.*"))
    if not matches:
        raise RuntimeError("download não gerou arquivo")
    return max(matches, key=os.path.getmtime)


_TIKTOK_RETRY_ERRORS = (
    "Unable to extract universal data for rehydration",
    "Unexpected response from webpage request",
    "Unable to extract challenge data",
    "Unable to solve JS challenge",
    "Site Maintenance",
)


def _clean_request_files(outtmpl) -> None:
    base = _get_tmpl_base(outtmpl)
    for path in glob.glob(os.path.join(DOWNLOAD_DIR, f"{base}.*")):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def _trigger_cookie_refresh() -> None:
    threading.Thread(
        target=refresh_now,
        name="tiktok-cookie-refresh",
        daemon=True,
    ).start()


def _download_tiktok_with_retry(url: str, options: dict) -> str:
    """Alterna sessão e rota de saída; renova cookies após esgotar fallbacks."""
    anonymous_options = copy.deepcopy(options)
    anonymous_options.pop("cookiefile", None)

    attempts = [
        ("direto com cookies", copy.deepcopy(options)),
        ("direto sem cookies", anonymous_options),
    ]
    if PROXY:
        proxy_options = copy.deepcopy(options)
        proxy_options["proxy"] = PROXY
        anonymous_proxy_options = copy.deepcopy(anonymous_options)
        anonymous_proxy_options["proxy"] = PROXY
        attempts.extend([
            ("proxy com cookies", proxy_options),
            ("proxy sem cookies", anonymous_proxy_options),
        ])

    last_error = None
    for index, (label, attempt_options) in enumerate(attempts):
        try:
            return download_media(url, attempt_options)
        except Exception as error:
            if not any(message in str(error) for message in _TIKTOK_RETRY_ERRORS):
                raise
            last_error = error
            _clean_request_files(options["outtmpl"])
            if index + 1 < len(attempts):
                print(
                    f"[download] TikTok falhou via {label}; tentando {attempts[index + 1][0]}: {error}",
                    flush=True,
                )

    print(
        f"[download] TikTok esgotou fallbacks; agendando renovação: {last_error}",
        flush=True,
    )
    _trigger_cookie_refresh()
    raise last_error


def _download_with_proxy_retry(url: str, options: dict) -> str:
    """
    YouTube roda atrás do proxy V6 rotativo (porta aleatória). O YouTube
    bloqueia parte dos IPs de saída — stream de áudio cai com 403 em ~50% das
    portas. A cada falha 403, re-sorteia a porta e tenta de novo.
    """
    for attempt in range(YOUTUBE_PROXY_RETRIES):
        try:
            return download_media(url, options)
        except Exception as e:
            is_last = attempt == YOUTUBE_PROXY_RETRIES - 1
            if is_last or "403" not in str(e) or not options.get("proxy"):
                raise
            options["proxy"] = get_youtube_proxy()
    raise RuntimeError("unreachable")


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

        platform = "youtube"
        proxy = get_youtube_proxy()

        youtube_opts = {
            **_ydl_base_opts(outtmpl, proxy),
            "extractor_args": {"youtube": {"player_client": ["web_embedded", "web", "tv"]}},
        }

        if is_audio:
            options = {
                **youtube_opts,
                "format": "bestaudio[ext=m4a]",
            }

        else:
            options = {
                **youtube_opts,
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
            }
            # options = {
            #     **_ydl_base_opts(outtmpl, proxy),
            #     "format": "bestvideo[vcodec^=vp9]+bestaudio/best[vcodec^=vp9]/best[vcodec!^=av01]",
            #     "merge_output_format": "mp4",
            # }

    # ---------- TIKTOK ----------
    elif is_tiktok:

        platform = "tiktok"
        options = {
            # UA fixo obrigatório: o WAF ata o token anti-bot ao UA que gerou
            # os cookies (cookie_refresher). Sem ele → "Site Maintenance".
            # Sem proxy: o TikTok devolve 403 no IP do proxy (o YouTube é o
            # contrário — só passa via proxy). Conexão direta funciona.
            **_ydl_base_opts(outtmpl, user_agent=TIKTOK_UA, use_global_proxy=False),
            "format": "best[vcodec=h264][acodec=aac][ext=mp4]/best[vcodec=h264][ext=mp4]",
            "merge_output_format": "mp4",
        }

    # ---------- PINTEREST ----------
    elif "pinterest" in url:

        platform = "pinterest"
        options = {
            **_ydl_base_opts(outtmpl),
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
        }

    # ---------- TWITTER / X / FACEBOOK ----------
    elif "x.com" in url or "twitter.com" in url or "facebook.com" in url or "fb.watch" in url:

        platform = "facebook" if ("facebook.com" in url or "fb.watch" in url) else "twitter"
        if "x.com" in url:
            url = url.replace("x.com", "twitter.com")

        options = {
            **_ydl_base_opts(outtmpl),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }

    # ---------- GENERIC ----------
    else:

        platform = "generic"
        options = {
            **_ydl_base_opts(outtmpl),
        }

    print(f"[download] plataforma={platform} type={download_type} url={url}", flush=True)

    try:

        if is_youtube and options.get("proxy"):
            # proxy V6 rotativo: re-sorteia a porta se o YouTube devolver 403
            file_path = _download_with_proxy_retry(url, options)
        elif is_tiktok:
            file_path = _download_tiktok_with_retry(url, options)
        else:
            file_path = download_media(url, options)
        filename = os.path.basename(file_path)

        base_url = request.host_url.rstrip("/")
        download_url = f"{base_url}/files/{filename}"

        print(f"[download] OK plataforma={platform} arquivo={filename}", flush=True)

        return jsonify({
            "success": True,
            "file": download_url,
            "type": download_type,
            "platform": platform
        })

    except Exception as e:
        print(f"[download] ERRO plataforma={platform} url={url}: {e}", flush=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------- Cookie refresh (manual) ----------
@app.route("/admin/refresh-cookies", methods=["POST"])
def admin_refresh_cookies():
    try:
        result = refresh_now()
        status = 200 if result.get("ok") else 409
        return jsonify(result), status
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
