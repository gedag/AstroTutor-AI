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
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1)))
        self.models = [models] if isinstance(models, str) else list(models)
        self.model = self.models[0]
        self.last_model = None
        self.exhausted: set[str] = set()
        self.temperature = temperature
        self.thinking = thinking  # Gemini 2.x: token bütçesi (int); Gemini 3+: seviye ("low"/"medium"/"high")
        self.min_interval = 60.0 / CFG["instruction"]["requests_per_minute"]
        self._last = 0.0
        self.calls = 0
        self.calls_by_model: dict[str, int] = {}
        self.busy: dict[str, int] = {}  # model başına 503 sayısı
        self.usage = {"prompt_tokens": 0, "output_tokens": 0}

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
        last_err = None
        usable = [m for m in self.models if m not in self.exhausted and m not in (exclude or set())]
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
                            log.warning(f"{model}: günlük kota doldu, sıradaki modele geçiliyor")
                            self.exhausted.add(model)
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
                    if isinstance(e, (json.JSONDecodeError, ValueError)):
                        log.warning(f"{model}: geçersiz JSON, tekrar deneniyor")
                        continue
                    raise
        if not usable or all(m in self.exhausted for m in usable):
            raise QuotaExhausted(f"Tüm modellerin günlük kotası doldu: {self.models}")
        raise RuntimeError(f"Gemini çağrısı başarısız: {last_err}")
