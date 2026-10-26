"""Pipeline'daki tüm script'lerin ortak kullandığı yardımcılar.

- config.yaml okuma
- dosya + konsol log'u
- JSONL okuma/yazma
- SHA-256 metin hash'i
- nazik (rate-limited, retry'lı) HTTP oturumu
- elenen kayıtların nedenleriyle birlikte loglanması
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Windows konsolunda Türkçe karakterlerin bozulmaması için
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = load_config()


def p(key: str) -> Path:
    """config.yaml içindeki paths.<key> değerini mutlak yola çevirir ve klasörü oluşturur."""
    path = ROOT / CFG["paths"][key]
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    fh = logging.FileHandler(p("logs") / f"{name}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


_ONES = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]


def _last_word(num: str) -> str:
    """Sayının Türkçe okunuşundaki son kelime: '%16,9' -> dokuz, '100/100' -> yüz, '1.234' -> dört."""
    s = re.sub(r"[^\d,]", "", num.split("/")[-1].replace(".", ""))
    if "," in s:
        s = s.split(",")[-1]
    n = int(s or 0)
    if n == 0:
        return "sıfır"
    if n % 10:
        return _ONES[n % 10]
    if n % 100:
        return _TENS[(n % 100) // 10]
    if n % 1000:
        return "yüz"
    if n % 1_000_000:
        return "bin"
    return "milyon"


def tr_num(x) -> str:
    """Metin içindeki ondalık parametreyi Türkçe yazar (0.85 -> 0,85); tam sayıya dokunmaz."""
    return str(x).replace(".", ",") if isinstance(x, float) else str(x)


def tr_ek(num: str, form: str = "iyelik") -> str:
    """Sayıya kesme işaretiyle doğru Türkçe eki ekler.
    form: 'iyelik' (25'i, %36,6'sı, 100'ü), 'belirtme' (%15'i, %2'yi), 'iyelik_belirtme' (%16,9'unu, %2'sini)."""
    if not re.search(r"\d", num):  # ör. veri yokken "-"
        return num
    w = _last_word(num)
    v = next(c for c in reversed(w) if c in "aeıioöuü")
    h = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}[v]
    vowel_end = w[-1] in "aeıioöuü"
    if form == "iyelik":
        suf = ("s" if vowel_end else "") + h
    elif form == "belirtme":
        suf = ("y" if vowel_end else "") + h
    else:
        suf = ("s" if vowel_end else "") + h + "n" + h
    return f"{num}'{suf}"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> Iterator[dict]:
    if not Path(path).exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def append_jsonl(path: Path, row: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def rng(offset: int = 0) -> random.Random:
    return random.Random(CFG["project"]["random_seed"] + offset)


class RemovalLog:
    """Elenen her kaydı sessizce silmek yerine nedeniyle birlikte CSV'ye yazar."""

    FIELDS = ["id", "stage", "reason", "source", "detail"]

    def __init__(self, path: Path, stage: str, reset: bool = True):
        self.path = Path(path)
        self.stage = stage
        self.rows: list[dict] = []
        if not reset and self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self.rows = [r for r in csv.DictReader(f) if r["stage"] != stage]

    def add(self, id_: str, reason: str, source: str = "", detail: str = "") -> None:
        self.rows.append({"id": id_, "stage": self.stage, "reason": reason,
                          "source": source, "detail": str(detail)[:300]})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.FIELDS)
            w.writeheader()
            w.writerows(self.rows)


class PoliteSession:
    """İstekler arasında bekleyen, hata durumunda üstel geri çekilmeyle tekrar deneyen HTTP oturumu."""

    def __init__(self, delay: float | None = None):
        import requests

        self.s = requests.Session()
        self.s.headers["User-Agent"] = CFG["http"]["user_agent"]
        self.delay = CFG["http"]["delay_seconds"] if delay is None else delay
        self.timeout = CFG["http"]["timeout"]
        self.retries = CFG["http"]["max_retries"]
        self._last = 0.0

    def get(self, url: str, **kw):
        last_exc = None
        for attempt in range(self.retries):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.s.get(url, timeout=self.timeout, **kw)
                self._last = time.time()
                if r.status_code in (429, 500, 502, 503, 504):
                    retry_after = r.headers.get("Retry-After")
                    sleep_s = int(retry_after) if retry_after and retry_after.isdigit() else 5 * 2 ** attempt
                    time.sleep(min(sleep_s, 120))
                    last_exc = RuntimeError(f"HTTP {r.status_code}")
                    continue
                return r
            except Exception as e:  # ağ hatası
                self._last = time.time()
                last_exc = e
                time.sleep(5 * 2 ** attempt)
        raise RuntimeError(f"GET failed after retries: {url}: {last_exc}")


def fill(template: str, **values) -> str:
    """Prompt şablonundaki {ad} yer tutucularını TEK geçişte doldurur.
    str.format kullanılmaz: kaynak metinlerdeki süslü parantezler ({\rm J}, LaTeX) format hatasına yol açıyordu."""
    import re as _re

    return _re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), template)
