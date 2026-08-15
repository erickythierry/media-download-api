"""Testes offline do fallback de download do TikTok."""
import app
from unittest.mock import patch


def _options():
    return {
        "outtmpl": "downloads/teste.%(ext)s",
        "cookiefile": "cookies.txt",
        "http_headers": {"User-Agent": "teste"},
    }


def test_sucesso_na_primeira_tentativa():
    calls = []
    with patch.object(app, "download_media", lambda url, options: calls.append(options) or "ok.mp4"):
        assert app._download_tiktok_with_retry("url", _options()) == "ok.mp4"
    assert len(calls) == 1
    assert calls[0]["cookiefile"] == "cookies.txt"


def test_fallback_sem_cookies():
    calls = []

    def fake_download(url, options):
        calls.append(options)
        if len(calls) == 1:
            raise RuntimeError("Unable to extract universal data for rehydration")
        return "ok.mp4"

    with (
        patch.object(app, "download_media", fake_download),
        patch.object(app, "_clean_request_files", lambda outtmpl: None),
        patch.object(app, "PROXY", None),
    ):
        assert app._download_tiktok_with_retry("url", _options()) == "ok.mp4"
    assert len(calls) == 2
    assert "cookiefile" not in calls[1]


def test_renova_cookies_em_segundo_plano_apos_falhas():
    calls = []
    refresh_calls = []

    def fake_download(url, options):
        calls.append(options)
        raise RuntimeError("Unexpected response from webpage request")

    with (
        patch.object(app, "download_media", fake_download),
        patch.object(app, "_trigger_cookie_refresh", lambda: refresh_calls.append(True)),
        patch.object(app, "_clean_request_files", lambda outtmpl: None),
        patch.object(app, "PROXY", None),
    ):
        try:
            app._download_tiktok_with_retry("url", _options())
            raise AssertionError("deveria propagar erro")
        except RuntimeError as error:
            assert "Unexpected response" in str(error)
    assert len(calls) == 2
    assert refresh_calls == [True]


def test_nao_repete_erro_de_download_de_midia():
    calls = []

    def fake_download(url, options):
        calls.append(options)
        raise RuntimeError("HTTP Error 403: Forbidden")

    with patch.object(app, "download_media", fake_download):
        try:
            app._download_tiktok_with_retry("url", _options())
            raise AssertionError("deveria propagar erro")
        except RuntimeError as error:
            assert "403" in str(error)
    assert len(calls) == 1


def test_tenta_proxy_depois_das_rotas_diretas():
    calls = []

    def fake_download(url, options):
        calls.append(options)
        if len(calls) < 3:
            raise RuntimeError("Unexpected response from webpage request")
        return "ok.mp4"

    with (
        patch.object(app, "download_media", fake_download),
        patch.object(app, "_clean_request_files", lambda outtmpl: None),
        patch.object(app, "PROXY", "http://proxy:3128"),
    ):
        assert app._download_tiktok_with_retry("url", _options()) == "ok.mp4"

    assert len(calls) == 3
    assert "cookiefile" not in calls[1]
    assert calls[2]["proxy"] == "http://proxy:3128"
    assert calls[2]["cookiefile"] == "cookies.txt"


if __name__ == "__main__":
    test_sucesso_na_primeira_tentativa()
    test_fallback_sem_cookies()
    test_renova_cookies_em_segundo_plano_apos_falhas()
    test_nao_repete_erro_de_download_de_midia()
    test_tenta_proxy_depois_das_rotas_diretas()
    print("PASS - fallback TikTok coberto")
