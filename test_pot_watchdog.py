"""Teste do watchdog do servidor POT e das rotas /info e /buscar.

Roda: python test_pot_watchdog.py
Cobre: reinício só após 2 pings seguidos sem resposta, nenhum reinício com
servidor vivo, formato do JSON de /buscar e /info.
"""
import app
import pot_manager

# ---- watchdog ----
def _roda_watchdog(respostas):
    """Executa _watchdog_loop com /ping simulado; devolve quantas vezes reiniciou."""
    pings = iter(respostas)
    reinicios = []

    class Fim(Exception):
        pass

    def fake_alive():
        try:
            return next(pings)
        except StopIteration:
            raise Fim

    pot_manager._is_server_alive = fake_alive
    pot_manager._kill_server = lambda: None
    pot_manager.start_pot_server = lambda: reinicios.append(1)
    pot_manager.time.sleep = lambda _: None
    try:
        pot_manager._watchdog_loop()
    except Fim:
        pass
    return len(reinicios)

assert _roda_watchdog([True, True, True]) == 0
assert _roda_watchdog([True, False, True, False, True]) == 0  # falha isolada não reinicia
assert _roda_watchdog([False, False, True]) == 1
assert _roda_watchdog([False, False, False, False, True]) == 2

# ---- /buscar e /info ----
client = app.app.test_client()

app._youtube_extract = lambda alvo, **kw: {"entries": [
    {"id": "abc", "title": "Musica", "duration": 3725, "view_count": 10,
     "thumbnails": [{"url": "http://t/1.jpg"}]},
    {"id": None},
    None,
]}
r = client.get("/buscar?text=musica").get_json()
assert r["success"] and len(r["data"]) == 1, r
item = r["data"][0]
assert item["id"] == "abc" and item["url"] == "https://youtube.com/watch?v=abc", item
assert item["duration"] == {"seconds": 3725, "time": "1:02:05"}, item
assert client.get("/buscar").status_code == 400

app._youtube_extract = lambda alvo, **kw: {
    "id": "abc", "title": "T", "duration": 214, "view_count": 5, "thumbnail": "http://t/1.jpg"}
r = client.get("/info?url=https://youtu.be/abc").get_json()
assert r == {"success": True, "title": "T", "videoid": "abc", "thumb": "http://t/1.jpg",
             "duration": 214, "views": 5}, r
assert client.get("/info?url=https://tiktok.com/x").status_code == 400

def falha(alvo, **kw):
    raise RuntimeError("Sign in to confirm your age")
app._youtube_extract = falha
r = client.get("/info?url=https://youtu.be/abc")
assert r.status_code == 500 and not r.get_json()["success"]

print("ok")
