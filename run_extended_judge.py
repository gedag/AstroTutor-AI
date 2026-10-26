"""Ek LLM yargıcı (Instruction v1.1 hazırlığı): örneklem dışındaki lite üretimi işleri, v1.0 dosyalarına DOKUNMADAN
ayrı bir çalışma klasöründe değerlendirir.

Neden ayrı klasör: 11_verify_instructions.py --extended doğrudan çalışırsa v1.0 ile commit edilmiş
`reports/removed_instructions.csv` ve `reports/instruction_verification_summary.json` değişir ve final setle
uyuşmaz hâle gelir. Bu script 11'i aynı kodla ama `data/interim/extended_judge/` altındaki kopyalar üzerinde çalıştırır.
Yargıç kararları orada birikir (kaldığı yerden devam eder); kota dolunca 60 dk bekleyip yeniden dener.

    python run_extended_judge.py              # tümü bitene kadar döngü
    python run_extended_judge.py --once       # tek tur

v1.1'i oluşturmak için (bitince): çalışma klasöründeki instruction_judgments.jsonl ve instruction_judge_attempts.jsonl
dosyalarını data/interim/ altına kopyalayıp 11 → 12 → 14 → 08 → 15 → 16 → validate_datasets zincirini çalıştırın.
"""
from __future__ import annotations

import importlib
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "data" / "interim" / "extended_judge"
LOG = ROOT / "logs" / "extended_judge.log"
DONE = WORK / "DONE"
SEED_FILES = {"interim": ["instructions_raw.jsonl", "instruction_jobs.jsonl", "instruction_judge_sample.json",
                          "instruction_judgments.jsonl", "instruction_judge_attempts.jsonl"],
              "reports": ["removed_instructions.csv"]}
# Her turda v1.0 kaynağından tazelenen (salt okunur) dosyalar; kararlar ve denemeler çalışma klasöründe birikir
REFRESH = {"interim": ["instructions_raw.jsonl", "instruction_jobs.jsonl", "instruction_judge_sample.json"]}


def say(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M} | {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def prepare() -> None:
    for sub, files in SEED_FILES.items():
        (WORK / sub).mkdir(parents=True, exist_ok=True)
        src_dir = ROOT / ("data/interim" if sub == "interim" else "reports")
        for name in files:
            dst = WORK / sub / name
            if not dst.exists() or name in REFRESH.get(sub, []):
                shutil.copy(src_dir / name, dst)


def once() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    import common

    real_p = common.p

    def work_p(key: str) -> Path:
        return WORK / key if key in ("interim", "reports") else real_p(key)

    common.p = work_p
    log = logging.getLogger("extended_judge")
    if not log.handlers:
        h = logging.FileHandler(LOG, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    b9 = importlib.import_module("09_build_instruction_sources")
    b9.log = log
    m = importlib.import_module("11_verify_instructions")
    m.p, m.log = work_p, log
    sys.argv = ["11_verify_instructions.py", "--extended"]
    return m.main()


def keep_awake() -> None:
    import os

    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)


if __name__ == "__main__":
    if "--once" in sys.argv:
        sys.exit(once())
    if DONE.exists():
        sys.exit(f"Ek yargıç daha önce tamamlandı ({DONE}).")
    keep_awake()
    prepare()
    errors = 0
    while True:
        say("ek yargıç turu başlıyor")
        rc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--once"], cwd=ROOT).returncode
        if rc == 0:
            say("ek yargıç tamamlandı")
            DONE.write_text(datetime.now().isoformat(), encoding="utf-8")
            break
        if rc == 2:
            say("kota doldu veya bekleyen iş var; 60 dk sonra tekrar")
            time.sleep(3600)
            continue
        errors += 1
        say(f"beklenmeyen çıkış kodu {rc} ({errors}/5); 10 dk sonra tekrar")
        if errors >= 5:
            sys.exit("ek yargıç 5 kez beklenmeyen hatayla durdu; logs/extended_judge.log'a bakın")
        time.sleep(600)
