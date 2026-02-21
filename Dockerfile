# -------- STAGE 1: Deno binário oficial (para yt-dlp js_runtimes / EJS) --------
FROM denoland/deno:bin-1.42.4 AS deno

# -------- STAGE 2: Python app --------
FROM python:3.11-slim

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# Dependências de sistema (ffmpeg para merge; curl/unzip para yt-dlp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas o binário do Deno (necessário para js_runtimes no yt-dlp)
COPY --from=deno /deno /usr/local/bin/deno
RUN chmod +x /usr/local/bin/deno && deno --version

# Python deps (inclui yt-dlp-ejs para remote_components)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p downloads && chmod +x start.sh

EXPOSE 5000

ENV PORT=5000
CMD ["sh", "start.sh"]
