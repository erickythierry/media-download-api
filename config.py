"""Configurações centralizadas da API de download de mídia."""
import base64
import binascii
import os
import shutil
import tempfile
from dotenv import load_dotenv

load_dotenv()

_VALID_YTDLP_JS = frozenset({"deno", "node", "bun", "quickjs"})


def get_ytdlp_js_runtimes():
    """
    Dict para a opção `js_runtimes` do yt-dlp (formato {runtime: {}}).

    - YTDLP_JS_RUNTIMES=auto (padrão): usa o primeiro executável encontrado no PATH
      nesta ordem: node, bun, deno, quickjs.
    - YTDLP_JS_RUNTIMES=node,bun: força a lista (útil para vários fallbacks).
    - YTDLP_NODE_PATH, YTDLP_BUN_PATH, YTDLP_DENO_PATH: caminho explícito do binário
      quando o PATH do processo não inclui o runtime (ex.: serviço systemd sem nvm).
    """
    raw = (os.getenv("YTDLP_JS_RUNTIMES") or "auto").strip().lower()

    path_overrides = {
        "node": os.getenv("YTDLP_NODE_PATH"),
        "bun": os.getenv("YTDLP_BUN_PATH"),
        "deno": os.getenv("YTDLP_DENO_PATH"),
        "quickjs": os.getenv("YTDLP_QUICKJS_PATH"),
    }

    def runtime_cfg(name):
        cfg = {}
        p = path_overrides.get(name)
        if p:
            cfg["path"] = p
        return cfg

    if raw != "auto":
        out = {}
        for part in raw.split(","):
            name = part.strip().lower()
            if name in _VALID_YTDLP_JS:
                out[name] = runtime_cfg(name)
        return out

    for name in ("node", "bun", "deno", "quickjs"):
        p = path_overrides.get(name)
        if p and os.path.isfile(p):
            return {name: runtime_cfg(name)}
        if shutil.which(name):
            return {name: runtime_cfg(name)}
    return {}

# Diretório de downloads
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

# Proxy opcional (usado pelo yt-dlp quando definido)
PROXY = os.getenv("PROXY") or os.getenv("YTDLP_PROXY")


# Proxy rotativo com IPv6
PROXY_V6 = os.getenv("PROXY_V6") # sem a porta no fim
PROXY_V6_PORT_START = os.getenv("PROXY_V6_PORT_START")
PROXY_V6_PORT_END = os.getenv("PROXY_V6_PORT_END")

# Idade máxima dos arquivos em minutos antes de serem removidos
CLEANUP_MAX_AGE_MINUTES = int(os.getenv("CLEANUP_MAX_AGE_MINUTES", "5"))

# Porta do servidor
PORT = int(os.getenv("PORT", "5000"))

# EJS do yt-dlp (YouTube): baixa componente remoto e exige um JS runtime (node/bun/deno…).
# Desative com YTDLP_USE_EJS=0 se não quiser rede extra / EJS.
USE_DENO_EJS = os.getenv("YTDLP_USE_EJS", "1").strip().lower() not in ("0", "false", "no")

# Cookies YouTube: caminho OU conteúdo em Base64 (útil em Docker sem volume).
_RAW_COOKIES_FILE = (os.getenv("YTDLP_COOKIES_FILE") or "").strip()
_RAW_COOKIES_B64 = os.getenv("YTDLP_COOKIES_B64")


def _decode_cookies_b64(b64: str) -> bytes | None:
    data = "".join(b64.split())
    if not data:
        return None
    pad = -len(data) % 4
    if pad:
        data += "=" * pad
    try:
        return base64.standard_b64decode(data)
    except binascii.Error:
        try:
            return base64.urlsafe_b64decode(data)
        except binascii.Error:
            print("[config] YTDLP_COOKIES_B64: base64 inválido", flush=True)
            return None


def _resolve_ytdlp_cookiefile() -> str | None:
    """
    Caminho absoluto do cookies.txt para o yt-dlp, ou None.

    Prioridade: YTDLP_COOKIES_FILE > YTDLP_COOKIES_B64 (grava em /tmp).
    Para YTDLP_COOKIES_FILE devolvemos o path mesmo se o arquivo ainda não
    existir: o renovador automático (cookie_refresher) cria/atualiza o arquivo
    e o `_ydl_base_opts` revalida com `os.path.isfile` antes de cada download.
    """
    if _RAW_COOKIES_FILE:
        if not os.path.isfile(_RAW_COOKIES_FILE):
            print(
                f"[config] YTDLP_COOKIES_FILE ainda não existe (será criado pelo refresher): {_RAW_COOKIES_FILE}",
                flush=True,
            )
        return _RAW_COOKIES_FILE

    if not _RAW_COOKIES_B64 or not str(_RAW_COOKIES_B64).strip():
        return None

    raw = _decode_cookies_b64(str(_RAW_COOKIES_B64))
    if raw is None:
        return None
    if not raw.strip():
        print("[config] YTDLP_COOKIES_B64 decodificado está vazio", flush=True)
        return None

    fd, tmp_path = tempfile.mkstemp(
        prefix="ytdlp_cookies_",
        suffix=".txt",
        text=False,
    )
    try:
        os.write(fd, raw)
    finally:
        os.close(fd)
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    print(f"[config] cookies do YouTube carregados de YTDLP_COOKIES_B64 → {tmp_path}", flush=True)
    return tmp_path


# Caminho efetivo para cookiefile do yt-dlp (resolvido na importação do módulo).
YTDLP_COOKIE_PATH = _resolve_ytdlp_cookiefile()


# ---------- Renovador automático de cookies (Playwright) ----------
def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


# Habilita/desabilita o renovador embutido no Flask.
COOKIE_REFRESH_ENABLED = _env_bool("COOKIE_REFRESH_ENABLED", True)

# Intervalo entre renovações (horas).
COOKIE_REFRESH_INTERVAL_HOURS = float(os.getenv("COOKIE_REFRESH_INTERVAL_HOURS", "6"))

# Pasta persistente do perfil do Chromium (sessão logada).
BROWSER_PROFILE_DIR = os.getenv("BROWSER_PROFILE_DIR", "browser_profile")

# Roda em headless? Em produção (Docker) deve ser True.
# No host, deixar False só ajuda em debug local.
COOKIE_REFRESH_HEADLESS = _env_bool("COOKIE_REFRESH_HEADLESS", True)

# Onde o renovador grava o cookies.txt quando YTDLP_COOKIES_FILE não está setado.
COOKIE_REFRESH_OUTPUT = (
    os.getenv("YTDLP_COOKIES_FILE")
    or os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_cookies.txt")
)

# Se o renovador está habilitado e nenhum cookiefile foi configurado via env,
# o yt-dlp deve ler exatamente o arquivo que o renovador grava.
if COOKIE_REFRESH_ENABLED and not YTDLP_COOKIE_PATH:
    YTDLP_COOKIE_PATH = COOKIE_REFRESH_OUTPUT
    print(
        f"[config] cookiefile do yt-dlp apontando para o renovador automático: {YTDLP_COOKIE_PATH}",
        flush=True,
    )
