"""Instruction Dataset üretimini Gemini ücretsiz katmanında GÜNLER boyunca otomatik sürdürür.

Ücretsiz katman model başına günde 20 istek verir. Belgelere göre kota Pasifik saatiyle gece yarısı
yenilenir, ama gözlenen davranış kayan 24 saatlik pencere (23.10.2026: 13:51'de dolan model 14:20'de yanıt
verdi). Bu yüzden tüm modellerin kotası dolunca sabah beklenmez, saatte bir yeniden denenir. Bu script:
  1. 10_generate_instructions.py'yi çalıştırır
       çıkış 0 -> tüm işler bitti, 2. adıma geç
       çıkış 2 -> tüm modellerin kotası doldu, 60 dk (veya Pasifik gece yarısına kadar, hangisi önceyse) bekle
       çıkış 3 -> kalan iş var (503 yoğunluğu, reddedilen ya da Flash'a ertelenen işler), 45 dk bekle, tekrar dene
  2. 11_verify_instructions.py (kural + kanıt kontrolü + %10 LLM yargıç örneklemi), aynı bekleme mantığıyla
  3. 12_split_instructions.py ve 13_sample_for_review.py

Bilgisayar açık ve uyku modunda değilken çalışmalıdır. Kapanırsa aynı komutla yeniden başlatın;
her şey kaldığı yerden devam eder.

    python run_instruction_loop.py
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PY = sys.executable
LA, TR = ZoneInfo("America/Los_Angeles"), ZoneInfo("Europe/Istanbul")
LOG = ROOT / "logs" / "instruction_loop.log"


def say(msg: str) -> None:
    line = f"{datetime.now(TR):%Y-%m-%d %H:%M} | {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(script: str) -> int:
    say(f"çalıştırılıyor: {script}")
    return subprocess.run([PY, str(ROOT / "scripts" / script)], cwd=ROOT).returncode


def sleep_until_reset() -> None:
    now = datetime.now(LA)
    reset = (now + timedelta(days=1)).replace(hour=0, minute=10, second=0, microsecond=0)
    wake = min(reset, now + timedelta(minutes=60))
    say(f"tüm modellerin kotası doldu; yeniden deneme -> {wake.astimezone(TR):%d.%m %H:%M} (TR)")
    time.sleep(max(60, (wake - now).total_seconds()))


def loop(script: str) -> None:
    errors = 0
    while True:
        rc = run(script)
        if rc == 0:
            say(f"{script} tamamlandı")
            return
        if rc == 2:
            sleep_until_reset()
        elif rc == 3:
            say("kalan iş var (model yoğunluğu, reddedilip yeniden denenecek ya da Flash bekleyen işler); "
                "45 dk sonra tekrar")
            time.sleep(45 * 60)
        else:
            errors += 1
            if errors >= 5:
                sys.exit(f"{script} beklenmeyen hata ile 5 kez durdu; logs/ klasörüne bakın")
            say(f"{script} beklenmeyen çıkış kodu {rc}; 10 dk sonra tekrar ({errors}/5)")
            time.sleep(600)


LOCK = ROOT / "logs" / "instruction_loop.lock"
DONE = ROOT / "logs" / "instruction_loop.DONE"


def single_instance():
    """Aynı anda iki döngü çalışırsa aynı işleri iki kez üretip dosyalara birlikte yazarlar. Kilit, süreç
    ölünce işletim sistemi tarafından bırakılır (bayat kilit sorunu yok)."""
    LOCK.parent.mkdir(exist_ok=True)
    fh = open(LOCK, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Başka bir run_instruction_loop.py zaten çalışıyor; çıkılıyor.", flush=True)
        sys.exit(0)
    return fh  # açık kalmalı


def keep_awake() -> None:
    """Döngü çalıştıkça Windows'un kendiliğinden uykuya geçmesini engeller (SetThreadExecutionState).
    24.10.2026: bilgisayar gece 00:38–09:33 arası uykuda kaldı ve bekleme sayacı da durdu. Kullanıcının
    Başlat > Uyku ile verdiği açık komut bununla engellenmez."""
    if os.name != "nt":
        return
    import ctypes

    es_continuous, es_system, es_away = 0x80000000, 0x00000001, 0x00000040
    k = ctypes.windll.kernel32
    if not k.SetThreadExecutionState(es_continuous | es_system | es_away):
        k.SetThreadExecutionState(es_continuous | es_system)  # "away mode" desteklenmiyorsa


if __name__ == "__main__":
    if DONE.exists():
        print(f"Döngü daha önce tamamlandı ({DONE.name}); yeniden çalıştırmak için bu dosyayı silin.")
        sys.exit(0)
    _lock = single_instance()
    keep_awake()
    if not (ROOT / "data/interim/instruction_jobs.jsonl").exists():
        sys.exit("Önce scripts/09_build_instruction_sources.py çalıştırılmalı (Corpus v1.0 bittikten sonra).")
    loop("10_generate_instructions.py")
    import json

    kinds = {json.loads(l)["kind"] for l in open(ROOT / "data/interim/instruction_jobs.jsonl", encoding="utf-8")}
    if "doc" not in kinds:
        say("SE ve kapsam dışı işleri bitti. Doküman işleri henüz eklenmedi: Corpus v1.0 bitince "
            "'python scripts/09_build_instruction_sources.py --part doc' çalıştırıp bu script'i yeniden başlatın.")
        sys.exit(0)
    loop("11_verify_instructions.py")
    for s in ("12_split_instructions.py", "13_sample_for_review.py"):
        if run(s) != 0:
            sys.exit(f"{s} başarısız")
    say("Instruction Dataset v1.0 hazır. Sıradaki adım: reports/qc/instruction_review.csv manuel kontrolü.")
    DONE.write_text(datetime.now(TR).isoformat(), encoding="utf-8")
