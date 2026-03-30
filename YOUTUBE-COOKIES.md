# Cookies do YouTube para o yt-dlp (anti-bot)

Quando o YouTube responde com **“Sign in to confirm you’re not a bot”**, o `yt-dlp` precisa enviar cookies de uma sessão em que você já passou por essa verificação (em geral, estando **logado** no navegador). Isso é comum em IPs de datacenter, VPN ou hospedagem.

O aviso **`No title found in player responses; falling back to title from initial data`** costuma aparecer no mesmo contexto (respostas do player limitadas); com cookies válidos costuma melhorar junto com o download.

Este repositório envia cookies ao `yt-dlp` assim:

- **`YTDLP_COOKIES_FILE`**: caminho para um `cookies.txt` no disco.
- **`YTDLP_COOKIES_B64`**: o **mesmo** arquivo em **Base64** (uma linha). Na inicialização o processo decodifica e grava um arquivo temporário em `/tmp` (útil em Docker **sem** montar volume).

**Prioridade:** se `YTDLP_COOKIES_FILE` apontar para um arquivo que **existe**, ele é usado; caso contrário usa-se `YTDLP_COOKIES_B64` (se definido). Veja `config.py`.

---

## Antes de começar (segurança)

- O arquivo de cookies **é credencial**: quem tiver o arquivo pode agir como sua sessão no YouTube. **Não commite** no Git e não compartilhe.
- Exporte cookies **só do domínio necessário** (`youtube.com`), não o perfil inteiro do navegador.
- Se vazar ou duvidar, **troque a senha Google** e **encerre sessões** em [segurança da conta Google](https://myaccount.google.com/security).
- Cookies **expiram**; se o erro voltar, exporte de novo.

Documentação oficial do yt-dlp:

- [Como passar cookies ao yt-dlp (FAQ)](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [Exportar cookies do YouTube (extractors)](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)

---

## Formato aceito

O yt-dlp espera um arquivo no **formato Netscape** (`cookies.txt`), com linhas típicas começando por domínio, flag, caminho, etc.

---

## Opção A — Extensão do navegador (recomendado para esta API)

Funciona bem para rodar a app em Docker/servidor: você exporta no PC onde o navegador está logado e copia o arquivo para o servidor.

### 1. Faça login no YouTube

Abra [https://www.youtube.com](https://www.youtube.com) no Chrome, Edge, Firefox ou Brave e conclua qualquer verificação (“não sou um robô”) se aparecer.

### 2. Instale uma extensão compatível

Use uma extensão que exporte **cookies.txt no formato Netscape** e que permita exportar **por site**.

Extensão frequentemente indicada na documentação do yt-dlp:

- **“Get cookies.txt LOCALLY”** (Chrome / Firefox — verifique a loja oficial da sua plataforma e instale a extensão correta; existem forks com nomes parecidos).

Siga as recomendações da [wiki do yt-dlp sobre exportação](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies): evite extensões antigas que geram formato incompatível.

### 3. Exporte só o YouTube

Com a aba do **YouTube** aberta (`youtube.com`), use a extensão para exportar cookies **somente para esse site** (ou filtre domínios `youtube.com` / `.youtube.com` conforme a extensão permitir).

Salve o arquivo, por exemplo, como `youtube_cookies.txt`.

### 4. Use na aplicação

**Local (.env na raiz do projeto):**

```env
YTDLP_COOKIES_FILE=/caminho/absoluto/para/youtube_cookies.txt
```

**Docker** (monte o arquivo só leitura e aponte a variável):

```bash
docker run \
  -e YTDLP_COOKIES_FILE=/config/youtube_cookies.txt \
  -v /caminho/no/host/youtube_cookies.txt:/config/youtube_cookies.txt:ro \
  -p 5000:5000 \
  sua-imagem
```

Reinicie o container ou o processo Flask após trocar o arquivo.

**Docker / CI sem volume — `YTDLP_COOKIES_B64`:**

No host, gere Base64 em **uma linha** (conteúdo idêntico ao `youtube_cookies.txt`):

```bash
base64 -w0 youtube_cookies.txt
# macOS: base64 -i youtube_cookies.txt | tr -d '\n'
```

Ou use o script do repositório (Python 3, mesmo resultado que o `config` espera):

```bash
python cookies_to_base64.py youtube_cookies.txt
# gravar em arquivo (ex.: colar no painel de secrets): -o cookies.b64.txt
```

Passe o resultado como variável de ambiente (cuidado: string longa; evite logar o valor):

```bash
docker run -p 5000:5000 \
  -e "YTDLP_COOKIES_B64=$(base64 -w0 youtube_cookies.txt)" \
  sua-imagem
```

Em painéis (Coolify, Railway, etc.), crie um secret com esse Base64 e mapeie para `YTDLP_COOKIES_B64`. O app cria um arquivo em `/tmp` ao subir; ao trocar os cookies, **reimplante** ou reinicie para recarregar a env.

**Segurança:** Base64 **não** é criptografia — trate `YTDLP_COOKIES_B64` como segredo (não commitar em repositório).

---

## Opção B — Linha de comando (`yt-dlp` no seu computador)

Se você tem o `yt-dlp` instalado localmente **e** o navegador no mesmo sistema, pode testar se os cookies resolvem antes de gerar o `cookies.txt`:

```bash
yt-dlp --cookies-from-browser chrome "https://www.youtube.com/watch?v=VIDEO_ID"
```

Substitua `chrome` por `firefox`, `brave`, `edge`, etc., conforme o [FAQ do yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp).

**Dentro de um container Linux sem navegador**, `--cookies-from-browser` em geral **não** está disponível da mesma forma; por isso a **Opção A** (arquivo exportado) costuma ser a prática para esta API.

---

## Conferir se está funcionando

1. Defina `YTDLP_COOKIES_FILE` **ou** `YTDLP_COOKIES_B64` (conforme a seção anterior).
2. Chame o endpoint de download com uma URL de vídeo público.
3. Se ainda falhar: confira se o arquivo não está vazio, se você está logado no YouTube no momento da exportação e se não passou muitos dias (exporte de novo).

---

## Problemas frequentes

| Sintoma | O que tentar |
|--------|----------------|
| Continua pedindo login | Exportar de novo após abrir o YouTube e passar pela verificação; garantir que o volume/env no Docker está correto. |
| Cookie inválido / formato | Gerar de novo com extensão recomendada na wiki do yt-dlp; arquivo deve ser Netscape. |
| Funciona no PC e não no servidor | Normal: IP do servidor é diferente; use cookies recém-exportados e, se precisar, teste sem proxy ou com IP residencial (política do YouTube). |

---

## Resumo

1. Entre no YouTube no navegador e resolva anti-bot se aparecer.  
2. Exporte **cookies Netscape** só para `youtube.com`.  
3. Configure **`YTDLP_COOKIES_FILE`** ou **`YTDLP_COOKIES_B64`** no `.env` ou no Docker.  
4. Trate o arquivo como **segredo** e **não** versionamento no repositório.

Adicione `youtube_cookies.txt` e pastas de secrets ao `.gitignore` se ainda não estiverem ignorados.
