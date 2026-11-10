"""09'un tekrar üretilebilirlik testi (Rehber: "pipeline baştan çalıştırılınca aynı sonucu veriyor mu?").

09 üç farklı config SIRASIYLA (orijinal, alfabetik, ters) ve üç farklı PYTHONHASHSEED ile geçici klasörlerde çalıştırılır;
iş listeleri (instruction_jobs.jsonl) bit bit aynı olmalıdır. Gerçek data/interim'e DOKUNMAZ (corpus yalnız okunur).
10.11.2026: config'te satır sırası değişince doküman seçimi değişiyordu (287 / 283 iş); 09 sözlükleri artık sıralı okur.

    python scripts/tests/test_reproducibility.py
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="astrotutor_repro_"))
base = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def reorder(obj, mode: str):
    """Sözlüklerin anahtar sırasını değiştirir (içerik aynı)."""
    if isinstance(obj, dict):
        keys = list(obj)
        keys = sorted(keys) if mode == "alpha" else list(reversed(keys)) if mode == "reverse" else keys
        return {k: reorder(obj[k], mode) for k in keys}
    return obj


hashes = {}
for mode, seed in (("orijinal", "0"), ("alpha", "1"), ("reverse", "12345")):
    d = TMP / mode
    cfg = reorder(base, mode)
    for k in ("interim", "reports", "qc", "logs", "samples"):
        cfg["paths"][k] = str(d / k)
    d.mkdir(parents=True)
    (d / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    env = dict(os.environ, ASTROTUTOR_CONFIG=str(d / "config.yaml"), PYTHONHASHSEED=seed, PYTHONUTF8="1")
    for part in ("se_ref", "doc"):
        r = subprocess.run([sys.executable, str(ROOT / "scripts/09_build_instruction_sources.py"), "--part", part],
                           env=env, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    hashes[mode] = hashlib.sha256((d / "interim/instruction_jobs.jsonl").read_bytes()).hexdigest()
    print(mode, f"PYTHONHASHSEED={seed}", hashes[mode][:16])
ok = len(set(hashes.values())) == 1
print("ok   iş listesi config sırasından ve hash tohumundan bağımsız" if ok else "FAIL iş listeleri farklı")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if ok else 1)
