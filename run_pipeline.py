"""Pipeline'ı baştan sona sırayla çalıştırır. Bir adım hata verirse durur.

    python run_pipeline.py --corpus | --instructions | --qc | --all
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ["01_download.py", "02_extract.py", "03_clean.py", "04_filter.py", "05_deduplicate.py", "06_split.py",
          "07_token_count.py", "08_statistics.py"]
# Ücretsiz Gemini katmanında günlerce süren üretim için run_instruction_loop.py kullanılır.
INSTR = ["09_build_instruction_sources.py --part se_ref", "09_build_instruction_sources.py --part doc",
         "10_generate_instructions.py", "11_verify_instructions.py", "12_split_instructions.py"]
QC = ["13_sample_for_review.py", "14_qc_report.py", "validate_datasets.py"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ("corpus", "instructions", "qc", "all"):
        g.add_argument(f"--{f}", action="store_true")
    a = ap.parse_args()
    steps = (CORPUS if a.corpus or a.all else []) + (INSTR if a.instructions or a.all else []) + \
            (QC if a.qc or a.all else [])
    for s in steps:
        t0 = time.time()
        print(f"\n===== {s} =====", flush=True)
        name, *args = s.split()
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], cwd=ROOT)
        if r.returncode != 0:
            sys.exit(f"{s} başarısız (çıkış kodu {r.returncode})")
        print(f"----- {s} tamam ({time.time() - t0:.0f} sn)")
