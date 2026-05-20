"""
Renovador automático de cookies do YouTube.

Estratégia:
- Mantém um perfil persistente do Chromium em `BROWSER_PROFILE_DIR`.
- O login é feito uma vez via `python seed_login.py` (janela aberta).
- A cada `COOKIE_REFRESH_INTERVAL_HOURS`, abre o navegador headless,
  navega no YouTube/Google, extrai os cookies da sessão logada e grava
  no formato Netscape em `COOKIE_REFRESH_OUTPUT` (mesmo path lido pelo yt-dlp).

O arquivo é sobrescrito atomicamente; o yt-dlp lê o cookiefile a cada
download, então a renovação não exige restart da API.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import Iterable

from config import (
    BROWSER_PROFILE_DIR,
    COOKIE_REFRESH_ENABLED,
    COOKIE_REFRESH_HEADLESS,
    COOKIE_REFRESH_INTERVAL_HOURS,
    COOKIE_REFRESH_OUTPUT,
)

_RELEVANT_DOMAIN_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "google.com",
    "googlevideo.com",
)

# Lock pra evitar duas renovações simultâneas (scheduler + chamada manual).
_refresh_lock = threading.Lock()

# Cabeçalho padrão do cookies.txt aceito pelo yt-dlp/curl.
_NETSCAPE_HEADER = (
    "# Netscape HTTP Cookie File\n"
    "# https://curl.se/rfc/cookie_spec.html\n"
    "# Gerado automaticamente por cookie_refresher.py — não editar manualmente.\n"
    "\n"
)


def _is_relevant(domain: str) -> bool:
    d = domain.lstrip(".").lower()
    return any(d == s or d.endswith("." + s) for s in _RELEVANT_DOMAIN_SUFFIXES)


def _format_cookie_line(cookie: dict) -> str | None:
    domain = cookie.get("domain") or ""
    if not domain or not _is_relevant(domain):
        return None

    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
    path = cookie.get("path") or "/"
    secure = "TRUE" if cookie.get("secure") else "FALSE"

    expires_raw = cookie.get("expires")
    try:
        expires = int(expires_raw) if expires_raw is not None else 0
    except (TypeError, ValueError):
        expires = 0
    if expires < 0:
        expires = 0

    name = cookie.get("name") or ""
    value = cookie.get("value") or ""
    if not name:
        return None

    domain_field = f"#HttpOnly_{domain}" if cookie.get("httpOnly") else domain
    return f"{domain_field}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}"


def _write_netscape(cookies: Iterable[dict], path: str) -> int:
    lines = [_NETSCAPE_HEADER]
    count = 0
    for c in cookies:
        line = _format_cookie_line(c)
        if line:
            lines.append(line + "\n")
            count += 1

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".cookies_",
        suffix=".tmp",
        dir=os.path.dirname(os.path.abspath(path)) or ".",
        text=False,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    return count


def _has_login_cookies(cookies: Iterable[dict]) -> bool:
    needed = {"SAPISID", "__Secure-3PAPISID", "LOGIN_INFO"}
    found = {c.get("name") for c in cookies}
    return bool(needed & found)


def refresh_now(headless: bool | None = None) -> dict:
    """
    Executa uma renovação de cookies. Retorna um dict com o resultado.
    Levanta exceção se Playwright não estiver instalado ou o perfil não existir.
    """
    if not _refresh_lock.acquire(blocking=False):
        return {"ok": False, "reason": "outra renovação em andamento"}

    try:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "playwright não está instalado. Rode `pip install playwright && python -m playwright install chromium`."
            ) from e

        use_headless = COOKIE_REFRESH_HEADLESS if headless is None else headless
        profile_dir = os.path.abspath(BROWSER_PROFILE_DIR)
        os.makedirs(profile_dir, exist_ok=True)

        print(
            f"[cookie_refresher] iniciando — headless={use_headless} profile={profile_dir}",
            flush=True,
        )
        started = time.time()

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=use_headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
                viewport={"width": 1280, "height": 800},
            )
            try:
                page = context.new_page()
                # Visita YouTube e Google para garantir que todos os cookies relevantes
                # estejam aquecidos e renovados pelo servidor.
                page.goto("https://www.youtube.com/", wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                page.goto("https://accounts.google.com/", wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                cookies = context.cookies()
            finally:
                context.close()

        if not _has_login_cookies(cookies):
            print(
                "[cookie_refresher] AVISO: cookies de login não encontrados. "
                "O perfil pode não estar logado. Rode `python seed_login.py`.",
                flush=True,
            )

        written = _write_netscape(cookies, COOKIE_REFRESH_OUTPUT)
        elapsed = time.time() - started
        print(
            f"[cookie_refresher] OK — {written} cookies gravados em {COOKIE_REFRESH_OUTPUT} ({elapsed:.1f}s)",
            flush=True,
        )

        return {
            "ok": True,
            "cookies": written,
            "logged_in": _has_login_cookies(cookies),
            "path": COOKIE_REFRESH_OUTPUT,
            "elapsed_s": round(elapsed, 2),
        }
    finally:
        _refresh_lock.release()


def _safe_refresh_job():
    try:
        refresh_now()
    except Exception as e:
        print(f"[cookie_refresher] FALHA na renovação agendada: {e}", flush=True)


def start_scheduler() -> bool:
    """
    Sobe o APScheduler com o job de renovação. Idempotente.
    Retorna True se o scheduler foi iniciado, False se desabilitado.
    """
    if not COOKIE_REFRESH_ENABLED:
        print("[cookie_refresher] desabilitado (COOKIE_REFRESH_ENABLED=0)", flush=True)
        return False

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        print(
            "[cookie_refresher] APScheduler não instalado — scheduler não iniciado",
            flush=True,
        )
        return False

    interval = max(0.25, float(COOKIE_REFRESH_INTERVAL_HOURS))
    scheduler = BackgroundScheduler(daemon=True, timezone="UTC")
    scheduler.add_job(
        _safe_refresh_job,
        trigger="interval",
        hours=interval,
        id="youtube_cookie_refresh",
        max_instances=1,
        coalesce=True,
        next_run_time=None,  # primeira execução é disparada manualmente abaixo
    )
    scheduler.start()
    print(
        f"[cookie_refresher] scheduler iniciado (intervalo: {interval}h)",
        flush=True,
    )

    # Primeira renovação em thread separada pra não bloquear o boot do Flask.
    threading.Thread(target=_safe_refresh_job, name="cookie-refresh-boot", daemon=True).start()
    return True
