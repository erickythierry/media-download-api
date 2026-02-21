# Media Download API

API unificada para download de mídia (vídeo e áudio) de vários sites usando **yt-dlp**.  
Integra em um único projeto as APIs de: YouTube/geral, Pinterest, Twitter/X e Facebook.

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Health check |
| POST/GET | `/download` | Baixar mídia. Use `type=audio` para áudio (apenas YouTube, formato m4a). |
| GET | `/files/<filename>` | Baixar arquivo final |

## Configuração

Copie `.env.example` para `.env` e ajuste se precisar:

- `PROXY` ou `YTDLP_PROXY`: proxy para o yt-dlp
- `DOWNLOAD_DIR`: pasta de downloads (default: `downloads`)
- `CLEANUP_MAX_AGE_MINUTES`: idade máxima dos arquivos antes de limpar (default: 5)
- `PORT`: porta do servidor (default: 5000)
- `AUTO_EXPIRE_SECONDS`: opcional; agenda exclusão do arquivo após N segundos
- `YTDLP_USE_EJS`: `1` (default) usa Deno + EJS para `js_runtimes`; use `0` se não tiver Deno instalado

## Executar

**Com Docker (recomendado)** — inclui Deno para `js_runtimes` do yt-dlp (igual ao repo yt-dlp):

```bash
docker build -t media-download-api .
docker run -p 5000:5000 --env-file .env media-download-api
```

**Localmente:**

```bash
pip install -r requirements.txt
# Deno instalado no PATH para js_runtimes (ou defina YTDLP_USE_EJS=0 para desativar)
python app.py
```

Resposta típica: `{"file": "http://.../files/xxx.mp4"}` — use essa URL para baixar o arquivo.
