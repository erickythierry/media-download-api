"""Configurações centralizadas da API de download de mídia."""
import os
from dotenv import load_dotenv

load_dotenv()

# Diretório de downloads
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

# Proxy opcional (usado pelo yt-dlp quando definido)
PROXY = os.getenv("PROXY") or os.getenv("YTDLP_PROXY")

# Idade máxima dos arquivos em minutos antes de serem removidos
CLEANUP_MAX_AGE_MINUTES = int(os.getenv("CLEANUP_MAX_AGE_MINUTES", "5"))

# Porta do servidor
PORT = int(os.getenv("PORT", "5000"))

# Usar Deno para js_runtimes do yt-dlp (EJS). Default True; use 0 quando rodar sem Deno instalado.
USE_DENO_EJS = os.getenv("YTDLP_USE_EJS", "1").strip().lower() not in ("0", "false", "no")
