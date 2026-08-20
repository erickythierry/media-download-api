"""
Gerenciador do servidor local de PO Token (BgUtils / BotGuard).
Inicia o servidor Deno em background em localhost:4416 (ou porta configurada).
"""
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from config import POT_SERVER_ENABLED, POT_SERVER_PORT, POT_SERVER_URL


_server_process = None
_server_lock = threading.Lock()


def _is_server_alive() -> bool:
    try:
        url = f"{POT_SERVER_URL.rstrip('/')}/ping"
        req = urllib.request.Request(url, headers={"User-Agent": "POT-HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _find_deno_binary() -> str | None:
    # 1. Path direto
    p = os.getenv("YTDLP_DENO_PATH")
    if p and os.path.isfile(p):
        return p
    # 2. Local bin / user home
    local_deno = os.path.expanduser("~/.deno/bin/deno")
    if os.path.isfile(local_deno):
        return local_deno
    # 3. PATH
    return shutil.which("deno")


def start_pot_server():
    """Inicia o servidor de PO Token se habilitado e não estiver rodando."""
    global _server_process
    if not POT_SERVER_ENABLED:
        return

    with _server_lock:
        if _is_server_alive():
            print(f"[pot_server] servidor PO Token já ativo em {POT_SERVER_URL}", flush=True)
            return

        deno_bin = _find_deno_binary()
        if not deno_bin:
            print("[pot_server] AVISO: binário do Deno não encontrado; PO Token server não iniciado", flush=True)
            return

        pot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pot_server")
        main_ts = os.path.join(pot_dir, "src", "main.ts")
        if not os.path.isfile(main_ts):
            print(f"[pot_server] AVISO: arquivo {main_ts} não encontrado", flush=True)
            return

        cmd = [
            deno_bin,
            "run",
            "--allow-env",
            "--allow-net",
            "--allow-ffi",
            "--allow-read",
            main_ts,
            "--port",
            str(POT_SERVER_PORT),
        ]

        try:
            _server_process = subprocess.Popen(
                cmd,
                cwd=pot_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Aguarda inicialização (até 4 segundos)
            for _ in range(20):
                time.sleep(0.2)
                if _is_server_alive():
                    print(f"[pot_server] servidor PO Token iniciado com sucesso em {POT_SERVER_URL} (PID: {_server_process.pid})", flush=True)
                    return
            print(f"[pot_server] AVISO: servidor iniciado (PID: {_server_process.pid}) mas ainda não respondeu /ping", flush=True)
        except Exception as e:
            print(f"[pot_server] ERRO ao iniciar servidor POT: {e}", flush=True)
