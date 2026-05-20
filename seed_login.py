"""
Script interativo para fazer login do YouTube/Google uma única vez.

Uso (no host, com DISPLAY disponível):

    pip install playwright
    python -m playwright install chromium
    python seed_login.py

Abre uma janela do Chromium usando o mesmo perfil persistente que o renovador
automático (`BROWSER_PROFILE_DIR`, default `./browser_profile/`). Faça login
normalmente na sua conta do Google/YouTube e, ao terminar, feche a janela.
A sessão fica salva no perfil; o renovador headless reusa-a.

Ao final, executa uma renovação imediata para gerar o cookies.txt.
"""
from __future__ import annotations

import os
import sys

from config import BROWSER_PROFILE_DIR


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "playwright não está instalado. Rode:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium",
            file=sys.stderr,
        )
        return 1

    profile_dir = os.path.abspath(BROWSER_PROFILE_DIR)
    os.makedirs(profile_dir, exist_ok=True)
    print(f"[seed_login] usando perfil persistente em: {profile_dir}")
    print("[seed_login] abra o navegador, faça login no Google/YouTube e feche a janela.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.goto("https://accounts.google.com/ServiceLogin?service=youtube", wait_until="domcontentloaded")
        print("[seed_login] aguardando você fechar o navegador...")
        try:
            # Bloqueia até o usuário fechar a janela.
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        try:
            context.close()
        except Exception:
            pass

    print("[seed_login] perfil salvo. Gerando cookies.txt inicial...")
    from cookie_refresher import refresh_now

    try:
        result = refresh_now(headless=True)
        print(f"[seed_login] renovação inicial: {result}")
        if not result.get("logged_in"):
            print(
                "[seed_login] AVISO: cookies de login não detectados. "
                "Verifique se o login foi concluído antes de fechar o navegador."
            )
            return 2
    except Exception as e:
        print(f"[seed_login] FALHA na renovação inicial: {e}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
