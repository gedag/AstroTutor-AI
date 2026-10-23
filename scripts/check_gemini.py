"""Gemini anahtarını, erişilebilir modelleri ve pipeline'ın kullandığı JSON-şemalı çağrıyı test eder.
Anahtarı ASLA ekrana yazdırmaz.

    python scripts/check_gemini.py                 # config'teki üretici model
    python scripts/check_gemini.py gemini-3.5-flash-lite
"""
import re
import sys
import time

from dotenv import dotenv_values
from pydantic import BaseModel

from common import CFG, ROOT

raw = (ROOT / ".env").read_bytes()
key = dotenv_values(ROOT / ".env").get("GEMINI_API_KEY") or ""
print("anahtar bulundu:", bool(key), "| uzunluk:", len(key), "| BOM:", raw.startswith(b"\xef\xbb\xbf"),
      "| boşluk/tırnak:", bool(re.search(r"[\s\"']", key)))
if not key:
    sys.exit(1)

from llm import Gemini  # noqa: E402


class Item(BaseModel):
    instruction: str
    response: str


model = sys.argv[1] if len(sys.argv) > 1 else CFG["instruction"]["generator_model"]
g = Gemini(model, 0.7, CFG["instruction"].get("generator_thinking_budget"))
t = time.time()
res = g.generate_json("Türkçe eğitim verisi üretirsin.",
                      "Şu bilgiden 1 soru-cevap örneği üret: 'Işık yılı, ışığın bir yılda aldığı yoldur.'", list[Item])
print(f"{model}: {time.time() - t:.1f} sn, {len(res)} örnek, token={g.usage}")
print(res[0].model_dump() if hasattr(res[0], "model_dump") else res[0])
