"""Teste do retry do proxy V6 do YouTube.

Roda: python test_proxy_retry.py
Cobre: re-sorteio de porta no 403, sucesso após falhas, sem retry para outros
erros, exaustão de tentativas.
"""
import sys

import app


def _mock(attempts_to_fail, error_msg):
    calls = []

    def fake_download(url, options):
        calls.append(options.get("proxy"))
        if len(calls) <= attempts_to_fail:
            raise RuntimeError(error_msg)
        return "ok.mp4"

    app.download_media = fake_download
    app.get_youtube_proxy = lambda: f"http://proxy:{len(calls) + 1}"
    return calls


# 1. duas falhas 403, sucesso na terceira
calls = _mock(2, "ERROR: unable to download video data: HTTP Error 403: Forbidden")
r = app._download_with_proxy_retry("u", {"proxy": "http://proxy:0", "outtmpl": "x.%(ext)s"})
assert r == "ok.mp4", r
assert calls == ["http://proxy:0", "http://proxy:2", "http://proxy:3"], calls

# 2. falha não-403 → levanta sem retry
calls = _mock(9, "ERROR: [TikTok] 123: Unexpected response")
try:
    app._download_with_proxy_retry("u", {"proxy": "http://proxy:0", "outtmpl": "x.%(ext)s"})
    raise AssertionError("deveria ter levantado")
except RuntimeError as e:
    assert "Unexpected response" in str(e), e
assert len(calls) == 1, calls  # sem retry

# 3. 403 sempre → esgota as tentativas (YOUTUBE_PROXY_RETRIES)
calls = _mock(99, "ERROR: HTTP Error 403: Forbidden")
try:
    app._download_with_proxy_retry("u", {"proxy": "http://proxy:0", "outtmpl": "x.%(ext)s"})
    raise AssertionError("deveria ter levantado")
except RuntimeError as e:
    assert "403" in str(e), e
assert len(calls) == app.YOUTUBE_PROXY_RETRIES, (len(calls), app.YOUTUBE_PROXY_RETRIES)

print("PASS — retry re-sorteia porta, respeita exceção e limite")
