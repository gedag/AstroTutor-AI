"""Gemini API istemcisi: hız sınırı (RPM), üstel geri çekilme ile tekrar deneme, JSON şema zorlaması.

Anahtar .env dosyasındaki GEMINI_API_KEY'den okunur (.env Git'e girmez).
Günlük kota bittiğinde QuotaExhausted fırlatılır; çağıran script kaldığı yerden devam edebilir.
"""
from __future__ import annotations

import json
import os
import re
import time

from dotenv import load_dotenv

from common import CFG, ROOT, get_logger

log = get_logger("llm")
load_dotenv(ROOT / ".env")


class QuotaExhausted(Exception):
    pass


class TransientError(RuntimeError):
    """Çağrı yalnız geçici nedenlerle başarısız oldu (503 yoğunluk, kota, dakikalık sınır, bağlantı kopması).
    İşin kendisiyle ilgili değildir; çağıran bunu kalıcı hata sayıp işi ATLAMAMALIDIR.
    (23.10.2026: bir işte iki model 503, iki model 429 verdi; yalnız son hata (429) bildirildiği için iş kalıcı
    hata sanılıp atlanmıştı.)"""


class DeadlineError(TransientError):
    """İstek sunucunun süre sınırını aştı (504 DEADLINE_EXCEEDED / okuma zaman aşımı) ve çağıran
    stop_on_deadline=True istedi. Toplu yargıç çağrısı büyükse çağıran işleri tek tek dener (19.11.2026: kalibrasyonda
    bir Stack Exchange toplu çağrısı taze kotada bile üç kez ~10 dk sonra 504 verdi; aynı isteği diğer modellere
    göndermek her biri için ~10 dk ve kota harcardı)."""


NETWORK_ERR = re.compile(r"10054|10053|10060|connection (reset|aborted|refused)|remote ?(end|host|disconnected)|"
                         r"timed? ?out|ReadTimeout|ConnectTimeout|RemoteProtocolError|ConnectError|"
                         r"Server disconnected|EOF occurred|getaddrinfo|Name or service not known|nodename|"
                         r"CERTIFICATE_VERIFY_FAILED|SSL|10051|10065|unreachable|erişilemeyen", re.I)


class Gemini:
    """models: [birincil, yedek1, ...]. Bir model geçici olarak yoğunsa (503) veya günlük kotası dolduysa
    sıradaki modele geçilir. Her çağrıda gerçekten kullanılan model `last_model` alanına yazılır."""

    def __init__(self, models: str | list[str], temperature: float, thinking: int | str | None = None):
        from google import genai

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise SystemExit("GEMINI_API_KEY bulunamadı. .env.example dosyasını .env olarak kopyalayıp anahtarı yazın.")
        from google.genai import types

        # SDK'nın kendi otomatik tekrar denemesi KAPALI: ücretsiz katmanda 503 alan her deneme de günlük
        # 20 istek hakkından düşüyor (22.10.2026'da gözlendi). Tekrar politikası aşağıda bizim kontrolümüzde.
        # Zaman aşımı: kütüphanenin varsayılanı sınırsız. 25.10.2026'da gemini-3.8-flash isteği 80 dk cevapsız kaldı
        # ve döngü durdu. Süresi dolan istek bağlantı hatası sayılır, sıradaki modele geçilir (iş atlanmaz).
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1),
            timeout=1000 * CFG["instruction"].get("request_timeout_seconds", 600)))
        self.models = [models] if isinstance(models, str) else list(models)
        self.model = self.models[0]
        self.last_model = None
        # Kotası dolan modeller ve zamanı. Google'ın günlük sınırı kayan 24 saatlik pencere gibi davranıyor:
        # 23.10 13:51'de "günlük kota doldu" diyen gemini-3.7-flash 14:20'de yeniden yanıt verdi. Bu yüzden
        # kotası dolan model belli bir süre sonra (quota_recheck_minutes) yeniden denenir; reddedilen (429)
        # istek kotadan düşmez.
        self._exhausted_at: dict[str, float] = {}
        self.recheck_seconds = 60 * CFG["instruction"].get("quota_recheck_minutes", 30)
        # 503 / zaman aşımı veren model bir süre (busy_cooldown_minutes) denenmez: bu istekler de kotadan düşüyor ve
        # yoğunluk genelde dakikalarca sürüyor (17.11.2026: üretimde ~28 istek 503 aldı, 8'i başarılı). Süre dolunca
        # model YENİDEN denenir (unutulmaz). DNS/SSL gibi Google'a ulaşmayan ağ hataları soğumaya sokmaz.
        self._busy_at: dict[str, float] = {}
        self.cooldown_seconds = 60 * CFG["instruction"].get("busy_cooldown_minutes", 15)
        self.temperature = temperature
        self.thinking = thinking  # Gemini 2.x: token bütçesi (int); Gemini 3+: seviye ("low"/"medium"/"high")
        self.min_interval = 60.0 / CFG["instruction"]["requests_per_minute"]
        self._last = 0.0
        self.calls = 0
        self.calls_by_model: dict[str, int] = {}
        self.busy: dict[str, int] = {}  # model başına 503 sayısı
        self.usage = {"prompt_tokens": 0, "output_tokens": 0}
        self._last_err: Exception | None = None
        self._permanent_err = False
        self._deadline = False
        self._stop_on_deadline = False
        # Çağıranın geçici olarak dışladığı modeller (ör. lite'ta iki kez Türkçe karakter kusuru veren iş
        # yalnız Flash ile denenir)
        self.force_exclude: set[str] = set()

    @property
    def exhausted(self) -> set[str]:
        now = time.time()
        return {m for m, t in self._exhausted_at.items() if now - t < self.recheck_seconds}

    @property
    def cooling(self) -> set[str]:
        """Yakın zamanda 503 / zaman aşımı veren, şimdilik denenmeyen modeller."""
        now = time.time()
        return {m for m, t in self._busy_at.items() if now - t < self.cooldown_seconds}

    def _config(self, system: str, schema):
        from google.genai import types

        cfg = dict(system_instruction=system, temperature=self.temperature,
                   max_output_tokens=CFG["instruction"]["max_output_tokens"],
                   response_mime_type="application/json", response_schema=schema)
        if isinstance(self.thinking, str):
            cfg["thinking_config"] = types.ThinkingConfig(thinking_level=self.thinking)
        elif isinstance(self.thinking, int):
            cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=self.thinking)
        return types.GenerateContentConfig(**cfg)

    def generate_json(self, system: str, prompt: str, schema, exclude: set | None = None,
                      stop_on_deadline: bool = False) -> object:
        """exclude: bu çağrıda kullanılmayacak modeller (ör. yargıç için örneği üreten model).
        stop_on_deadline: süre aşımında (504 / zaman aşımı) başka modele geçmeden DeadlineError fırlat."""
        config = self._config(system, schema)
        self._last_err = None
        self._permanent_err = False  # bu çağrıda içerikle ilgili (geçici olmayan) hata görüldü mü
        self._deadline = False       # bu çağrıda süre aşımı görüldü mü
        self._stop_on_deadline = stop_on_deadline
        excl = set(exclude or ()) | self.force_exclude
        cand = [m for m in self.models if m not in excl]
        cooling = self.cooling
        avail = [m for m in cand if m not in self.exhausted and m not in cooling]
        if not avail:
            if all(m in self.exhausted for m in cand):
                raise QuotaExhausted(f"Tüm modellerin günlük kotası doldu: {self.models}")
            # Kotası olan ama yoğunluk nedeniyle beklemedeki modeller var: geçici durum, iş atlanmaz
            raise TransientError(f"Gemini çağrısı geçici nedenlerle başarısız (503/kota/bağlantı): kullanılabilir "
                                 f"modeller yoğunluk beklemesinde {sorted(m for m in cand if m in cooling)}")
        # Kademeler: "lite" modeller daha kısa cevap üretiyor (23.10.2026 ölçümü: Stack Exchange işlerinde
        # kanıt kontrolü %68'e karşı Flash'ta %96; doküman işlerinde ikisi de %100, ort. cevap ~380'e karşı ~745
        # karakter). Bu yüzden lite YALNIZCA tüm Flash modellerinin günlük kotası bittiğinde kullanılır; anlık
        # yoğunlukta (503) lite'a düşülmez, çağıran bekleyip tekrar dener.
        primary = [m for m in avail if "lite" not in m]
        lite = [m for m in avail if "lite" in m]
        for tier in ([primary, lite] if primary else [lite]):
            out = self._try_tier(list(tier), config, prompt)
            if out is not None:
                return out
            # Kademede kotası bitmemiş (503 vb. ile başarısız) model varsa alt kademeye İNİLMEZ
            if not all(m in self.exhausted for m in tier):
                break
        if self._deadline and self._stop_on_deadline:
            raise DeadlineError(f"Gemini çağrısı sunucu süre sınırını aştı (504/zaman aşımı): {self._last_err}")
        # Yalnız kullanılabilecek BÜTÜN modellerin kotası dolduysa "kota bitti" denir; beklemedeki (503) bir model
        # varsa durum geçicidir (o model süre dolunca yeniden denenir).
        if all(m in self.exhausted for m in cand):
            raise QuotaExhausted(f"Tüm modellerin günlük kotası doldu: {self.models}")
        if not self._permanent_err:
            raise TransientError(f"Gemini çağrısı geçici nedenlerle başarısız (503/kota/bağlantı): {self._last_err}")
        raise RuntimeError(f"Gemini çağrısı başarısız: {self._last_err}")

    def _try_tier(self, usable: list[str], config, prompt: str):
        """Bir kademedeki modelleri sırayla dener; başarıda sonucu, aksi halde None döndürür."""
        last_err = None
        # "Yapışkan" seçim (yalnız aynı kademe içinde): son başarılı model önce denenir; yoğun modelleri
        # her işte yeniden denemek kota yakıyordu (503'ler de günlük 20 haktan düşüyor).
        if self.last_model in usable:
            usable.remove(self.last_model)
            usable.insert(0, self.last_model)
        for model in usable:
            if self._deadline and self._stop_on_deadline:
                break   # ağır istek başka modele gönderilmez; çağıran küçülterek dener
            for attempt in range(4):
                wait = self.min_interval - (time.time() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.time()
                try:
                    resp = self.client.models.generate_content(model=model, contents=prompt, config=config)
                    self.calls += 1
                    self.calls_by_model[model] = self.calls_by_model.get(model, 0) + 1
                    um = getattr(resp, "usage_metadata", None)
                    if um:
                        self.usage["prompt_tokens"] += um.prompt_token_count or 0
                        self.usage["output_tokens"] += (um.candidates_token_count or 0)
                    out = resp.parsed if resp.parsed is not None else json.loads(resp.text)
                    self.last_model = model
                    return out
                except Exception as e:
                    msg = str(e)
                    last_err = e
                    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                        if re.search(r"per ?day|PerDay|daily", msg, re.I):
                            log.warning(f"{model}: günlük kota doldu, sıradaki modele geçiliyor "
                                        f"({self.recheck_seconds // 60} dk sonra yeniden denenecek)")
                            # Teşhis için hatanın kota kısmı (anahtar içermez)
                            q = re.findall(r"quotaId': '[^']+'|quotaValue': '[^']+'", msg)
                            log.info(f"{model}: 429 ayrıntısı: {q}")
                            self._exhausted_at[model] = time.time()
                            break
                        m = re.search(r"retry in ([\d.]+)s|retryDelay': '(\d+)s", msg)
                        delay = float(next(g for g in m.groups() if g)) if m else 30 * (attempt + 1)
                        log.warning(f"{model}: dakikalık hız sınırı, {delay:.0f} sn bekleniyor")
                        time.sleep(min(delay + 2, 300))
                        continue
                    if any(x in msg for x in ("500", "503", "UNAVAILABLE", "INTERNAL", "DEADLINE")):
                        # Yoğunluk hatası da kotadan düşüyor: aynı modelde hemen tekrar deneme, sıradaki modele geç.
                        log.warning(f"{model}: geçici yoğunluk (503), sıradaki modele geçiliyor "
                                    f"({self.cooldown_seconds // 60} dk sonra yeniden denenecek)")
                        self.busy[model] = self.busy.get(model, 0) + 1
                        self._busy_at[model] = time.time()
                        if "DEADLINE" in msg or "504" in msg:
                            self._deadline = True
                        break
                    # Ağ hataları (DNS, SSL, erişilemeyen ağ) işin kusuru değildir. ssl.SSLError aynı zamanda ValueError
                    # olduğu için bu kontrol JSON kontrolünden ÖNCE yapılır (28.10.2026: Wi-Fi değişince 15 iş için SSL ve
                    # DNS hataları "geçersiz JSON"/işe özgü hata sayılıp deneme hakkı yaktı).
                    if NETWORK_ERR.search(msg) or isinstance(e, (ConnectionError, TimeoutError, OSError)):
                        log.warning(f"{model}: bağlantı hatası ({msg[:80]}), sıradaki modele geçiliyor")
                        self.busy[model] = self.busy.get(model, 0) + 1
                        # Zaman aşımı: istek Google'a ulaştı ve model cevap veremedi (yoğunluk) -> beklemeye al.
                        # DNS/SSL/bağlantı kopması: istek ulaşmadı, model beklemeye ALINMAZ.
                        if re.search(r"timed? ?out|ReadTimeout|DEADLINE", msg, re.I):
                            self._busy_at[model] = time.time()
                            self._deadline = True
                        break
                    if isinstance(e, (json.JSONDecodeError, ValueError)):
                        log.warning(f"{model}: geçersiz JSON, tekrar deneniyor")
                        if attempt == 3:
                            self._permanent_err = True
                        continue
                    raise
        if last_err is not None:
            self._last_err = last_err
        return None
