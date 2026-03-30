# -------- STAGE 1: binário Deno (yt-dlp EJS — mínimo Deno 2.0) --------
# Versões antigas (ex.: 1.42.x) são ignoradas pelo yt-dlp; veja MIN_SUPPORTED_VERSION em yt_dlp.
ARG DENO_VERSION=2.7.9
FROM denoland/deno:bin-${DENO_VERSION} AS deno

# -------- STAGE 2: app Python --------
FROM python:3.11-slim

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# ffmpeg: merge de streams; curl/ca-certificates: yt-dlp / componentes remotos
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deno /deno /usr/local/bin/deno
RUN chmod +x /usr/local/bin/deno && deno --version

# Alinha com config.get_ytdlp_js_runtimes() (auto = node → bun → deno; no container só Deno entra).
# Para forçar só Deno: YTDLP_JS_RUNTIMES=deno
ENV YTDLP_JS_RUNTIMES=auto \
    YTDLP_USE_EJS=1

# Opcional: YTDLP_COOKIES_FILE + volume, ou YTDLP_COOKIES_B64 (Base64 do cookies.txt) sem volume.
# ENV YTDLP_COOKIES_FILE=
# ENV YTDLP_COOKIES_B64=

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p downloads && chmod +x start.sh

EXPOSE 5000

ENV PORT=5000
CMD ["sh", "start.sh"]
