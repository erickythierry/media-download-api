#!/usr/bin/env python3
"""
Codifica um cookies.txt (Netscape) em Base64 de uma linha para YTDLP_COOKIES_B64.

Uso:
  python cookies_to_base64.py                    # lê youtube_cookies.txt no cwd
  python cookies_to_base64.py /caminho/cookies.txt
  python cookies_to_base64.py -o .env.b64        # grava só o valor (sem prefixo)
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Cookies.txt → Base64 (uma linha) para YTDLP_COOKIES_B64")
    p.add_argument(
        "path",
        nargs="?",
        default="youtube_cookies.txt",
        type=Path,
        help="arquivo de cookies (default: youtube_cookies.txt)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="escreve o Base64 neste arquivo em vez de stdout",
    )
    args = p.parse_args()

    path: Path = args.path
    if not path.is_file():
        print(f"erro: arquivo não encontrado: {path}", file=sys.stderr)
        return 1

    raw = path.read_bytes()
    if not raw.strip():
        print("erro: arquivo vazio", file=sys.stderr)
        return 1

    b64 = base64.standard_b64encode(raw).decode("ascii")

    if args.output:
        args.output.write_text(b64 + "\n", encoding="ascii")
        print(f"gravado em {args.output} ({len(b64)} caracteres)", file=sys.stderr)
    else:
        sys.stdout.write(b64 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
