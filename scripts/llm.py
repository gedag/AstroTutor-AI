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


NETWORK_ERR = re.compile(r"10054|10053|10060|connection (reset|aborted|refused)|remote ?(end|host|disconnected)|"
                         r"timed? ?out|ReadTimeout|ConnectTimeout|RemoteProtocolError|ConnectError|"
                         r"Server disconnected|EOF occurred", re.I)


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
        # Çağıranın geçici olarak dışladığı modeller (ör. lite'ta iki kez Türkçe karakter kusuru veren iş
        # yalnız Flash ile denenir)
        self.force_exclude: set[str] = set()

    @property
    def exhausted(self) -> set[str]:
        now = time.time()
        return {m for m, t in self._exhausted_at.items() if now - t < self.recheck_seconds}

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

    def generate_json(self, system: str, prompt: str, schema, exclude: set | None = None) -> object:
        """exclude: bu çağrıda kullanılmayacak modeller (ör. yargıç için örneği üreten model)."""
        config = self._config(system, schema)
        self._last_err = None
        self._permanent_err = False  # bu çağrıda içerikle ilgili (geçici olmayan) hata görüldü mü
        excl = set(exclude or ()) | self.force_exclude
        avail = [m for m in self.models if m not in self.exhausted and m not in excl]
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
        if all(m in self.exhausted for m in avail):
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
                        log.warning(f"{model}: geçici yoğunluk (503), sıradaki modele geçiliyor")
                        self.busy[model] = self.busy.get(model, 0) + 1
                        break
                    if NETWORK_ERR.search(msg) or isinstance(e, (ConnectionError, TimeoutError)):
                        log.warning(f"{model}: bağlantı hatası ({msg[:80]}), sıradaki modele geçiliyor")
                        self.busy[model] = self.busy.get(model, 0) + 1
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
