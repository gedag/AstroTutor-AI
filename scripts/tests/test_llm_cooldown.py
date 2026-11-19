"""llm.Gemini yoğunluk beklemesi (busy_cooldown_minutes) testi — API çağrısı YOK (sahte istemci).

Kontrol edilenler: 503 / zaman aşımı veren model bekleme süresince denenmez, süre dolunca yeniden denenir (unutulmaz);
DNS/SSL hataları beklemeye sokmaz; bütün modeller beklemedeyken istek gönderilmez ve hata "geçici" sayılır (kota
bitti sayılmaz); yalnız bütün modellerin kotası dolunca QuotaExhausted; yargıç gibi tek modele zorlanan çağrı.

    python scripts/tests/test_llm_cooldown.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")   # sahte istemci kullanılır, ağa çıkılmaz
import llm  # noqa: E402

bad = 0
M = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash"]
E503 = "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'high demand'}}"
E429 = "429 RESOURCE_EXHAUSTED. quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'"
ETIMEOUT = "The read operation timed out"
EDNS = "[Errno 11001] getaddrinfo failed"
ESSL = "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate"


def check(name, ok, detail=""):
    global bad
    bad += not ok
    print(("ok   " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""), flush=True)


class Resp:
    parsed = {"ok": True}
    text = '{"ok": true}'
    usage_metadata = None


class FakeModels:
    def __init__(self):
        self.behavior = {}     # model -> hata mesajı (yoksa başarı)
        self.requests = []     # gerçekten gönderilen istekler (model adı)

    def generate_content(self, model, contents, config):
        self.requests.append(model)
        err = self.behavior.get(model)
        if err:
            raise Exception(err)
        return Resp()


def new_client():
    g = llm.Gemini(M, 0.0)
    g.min_interval = 0
    g._config = lambda system, schema: None     # SDK yapılandırması gerekmez
    fake = FakeModels()
    g.client = type("C", (), {"models": fake})()
    return g, fake


def call(g, exclude=None):
    try:
        g.generate_json("s", "p", dict, exclude=exclude)
        return "ok"
    except llm.QuotaExhausted:
        return "quota"
    except llm.TransientError:
        return "transient"


check("varsayılan bekleme 15 dk", llm.Gemini(M, 0.0).cooldown_seconds == 15 * 60)

# 1) 503 veren model bekleme süresince denenmez
g, f = new_client()
f.behavior = {M[0]: E503}
check("ilk çağrı: 3.6 503 -> 3.5 ile başarı", call(g) == "ok" and f.requests == [M[0], M[1]], str(f.requests))
f.requests.clear()
f.behavior = {}
check("ikinci çağrı: beklemedeki 3.6 denenmez", call(g) == "ok" and f.requests == [M[1]], str(f.requests))
check("3.6 beklemede", g.cooling == {M[0]})

# 2) süre dolunca model unutulmaz, yeniden denenir
g._busy_at[M[0]] -= g.cooldown_seconds + 1
g.last_model = None          # yapışkan seçim olmadan sıra: önce 3.6
f.requests.clear()
check("süre dolunca 3.6 yeniden denenir", call(g) == "ok" and f.requests == [M[0]], str(f.requests))
check("bekleme listesi boş", g.cooling == set())

# 3) bütün modeller 503: ilk çağrıda 4 istek, sonraki çağrıda hiç istek yok, hata geçici (iş atlanmaz)
g, f = new_client()
f.behavior = {m: E503 for m in M}
check("hepsi 503: geçici hata", call(g) == "transient")
check("hepsi 503: her model bir kez denendi", f.requests == M, str(f.requests))
f.requests.clear()
check("hepsi beklemede: yine geçici (kota bitti DEĞİL)", call(g) == "transient")
check("hepsi beklemede: hiç istek gönderilmedi", f.requests == [], str(f.requests))

# 4) ikisi kota (429), ikisi beklemede -> geçici; kota hatası sayılmaz
g, f = new_client()
f.behavior = {M[0]: E429, M[1]: E429, M[2]: E503, M[3]: E503}
check("2 kota + 2 yoğun: geçici", call(g) == "transient")
f.requests.clear()
check("2 kota + 2 beklemede: geçici, istek yok", call(g) == "transient" and f.requests == [], str(f.requests))
# beklemedekilerin süresi dolunca yeniden denenir ve kotaları kullanılır
for m in (M[2], M[3]):
    g._busy_at[m] -= g.cooldown_seconds + 1
f.behavior = {M[0]: E429, M[1]: E429}
f.requests.clear()
check("süre dolunca 3.7 kullanılır (kotası boşa gitmez)", call(g) == "ok" and f.requests == [M[2]],
      str(f.requests))

# 5) bütün modellerin kotası dolu -> QuotaExhausted
g, f = new_client()
f.behavior = {m: E429 for m in M}
check("hepsi kota: QuotaExhausted", call(g) == "quota")
f.requests.clear()
check("hepsi kota (tekrar): QuotaExhausted, istek yok", call(g) == "quota" and f.requests == [], str(f.requests))

# 6) zaman aşımı beklemeye sokar; DNS / SSL sokmaz
g, f = new_client()
f.behavior = {M[0]: ETIMEOUT, M[1]: EDNS, M[2]: ESSL}
check("zaman aşımı + DNS + SSL -> 3.8 ile başarı", call(g) == "ok" and f.requests == M, str(f.requests))
check("yalnız zaman aşımı veren beklemede", g.cooling == {M[0]}, str(g.cooling))
f.behavior = {}
f.requests.clear()
g.last_model = None
check("DNS/SSL veren modeller hemen yeniden denenir", call(g) == "ok" and f.requests == [M[1]], str(f.requests))

# 7) tek modele zorlanan çağrı (kalibrasyon / yargıç): o model beklemedeyse istek yok, geçici
g, f = new_client()
only = set(M) - {M[2]}
f.behavior = {M[2]: E503}
check("zorlanan model 503: geçici", call(g, exclude=only) == "transient" and f.requests == [M[2]], str(f.requests))
f.requests.clear()
check("zorlanan model beklemede: geçici, istek yok", call(g, exclude=only) == "transient" and f.requests == [])
f.requests.clear()
check("beklemedeki model başka çağrıyı engellemez", call(g, exclude={M[2]}) == "ok" and f.requests == [M[0]],
      str(f.requests))

# 8) süre aşımı (504 / zaman aşımı): toplu çağrı stop_on_deadline=True ile başka modele gitmez -> DeadlineError
E504 = "504 DEADLINE_EXCEEDED. {'error': {'code': 504, 'message': 'Deadline expired'}}"


def call_batch(g):
    try:
        g.generate_json("s", "p", dict, stop_on_deadline=True)
        return "ok"
    except llm.DeadlineError:
        return "deadline"
    except llm.QuotaExhausted:
        return "quota"
    except llm.TransientError:
        return "transient"


check("DeadlineError geçici hata sınıfından (eski yakalayıcılar bozulmaz)",
      issubclass(llm.DeadlineError, llm.TransientError))
g, f = new_client()
f.behavior = {M[0]: E504}
check("toplu + 504: DeadlineError, başka modele gidilmedi", call_batch(g) == "deadline" and f.requests == [M[0]],
      str(f.requests))
g, f = new_client()
f.behavior = {M[0]: E504}
check("tekli + 504: sıradaki modele geçilir", call(g) == "ok" and f.requests == [M[0], M[1]], str(f.requests))
g, f = new_client()
f.behavior = {M[0]: ETIMEOUT}
check("toplu + zaman aşımı: DeadlineError", call_batch(g) == "deadline" and f.requests == [M[0]], str(f.requests))
g, f = new_client()
f.behavior = {M[0]: E503}
check("toplu + 503 (süre aşımı değil): sıradaki modelle başarı", call_batch(g) == "ok" and f.requests == [M[0], M[1]],
      str(f.requests))
g, f = new_client()
f.behavior = {M[0]: EDNS, M[1]: E504}
check("DNS sonra 504: DeadlineError, üçüncü modele gidilmedi",
      call_batch(g) == "deadline" and f.requests == [M[0], M[1]], str(f.requests))
g, f = new_client()
f.behavior = {M[0]: E504}
call_batch(g)
f.requests.clear()
f.behavior = {}
check("süre aşımından sonraki normal çağrı etkilenmez", call(g) == "ok" and f.requests == [M[1]], str(f.requests))

print(f"\nhata: {bad}")
sys.exit(1 if bad else 0)
