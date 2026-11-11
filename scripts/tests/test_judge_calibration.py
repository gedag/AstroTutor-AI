"""judge_calibration.py testi — SAHTE Gemini, gerçek veriye DOKUNMAZ.

Gerçek ham örnekler geçici bir klasöre kopyalanır (interim/reports orada; corpus ve kapsam tablosu yalnız okunur).
Şu anda yeterli tamamlanmış doküman işi olmadığı için test kopyasında doküman örneklerinin üretici modeli tek modele
çevrilir ve üçlü sayısı küçültülür (yalnız bu testte).

    python scripts/tests/test_judge_calibration.py
"""
import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="astrotutor_calib_"))
cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
for k in ("interim", "reports", "logs"):
    cfg["paths"][k] = str(TMP / k)
cfg["paths"]["final"] = str(ROOT / "data" / "final")          # yalnız okunur
(TMP / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
os.environ["ASTROTUTOR_CONFIG"] = str(TMP / "config.yaml")
(TMP / "interim").mkdir(parents=True)
(TMP / "reports").mkdir()
for f in ("instruction_jobs.jsonl", "instruction_jobs_done.jsonl"):
    shutil.copy(ROOT / "data" / "interim" / f, TMP / "interim" / f)
GEN = "gemini-3.7-flash"
with open(ROOT / "data" / "interim" / "instructions_raw.jsonl", encoding="utf-8") as fin, \
        open(TMP / "interim" / "instructions_raw.jsonl", "w", encoding="utf-8") as fout:
    for line in fin:
        r = json.loads(line)
        if r["job_id"].startswith(("JOB_DOC_", "JOB_REF_")):
            r["generator_model"] = GEN      # yalnız test kopyası: tek üretici -> üçlü kurulabilsin
        fout.write(json.dumps(r, ensure_ascii=False) + "\n")

sys.path.insert(0, str(ROOT / "scripts"))
import llm  # noqa: E402

bad = 0


def check(name, ok, detail=""):
    global bad
    bad += not ok
    print(("ok   " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""), flush=True)


class FakeGemini:
    """Kararı örneğin metninden belirleyen sahte yargıç: iki modda da aynı örneğe aynı karar (uyum %100 beklenir)."""
    calls: list = []
    quota_after = None   # bu kadar çağrıdan sonra kota hatası (devam testi)

    def __init__(self, models, temperature, thinking=None):
        self.models = list(models)
        self.last_model = None
        self.exhausted = set()

    def generate_json(self, system, prompt, schema, exclude=None):
        if FakeGemini.quota_after is not None and len(FakeGemini.calls) >= FakeGemini.quota_after:
            raise llm.QuotaExhausted("fake quota")
        import re

        cands = [m for m in self.models if m not in (exclude or set())]
        self.last_model = cands[0]
        groups = re.search(r"Below are (\d+) GROUPS", prompt)
        FakeGemini.calls.append((int(groups.group(1)) if groups else 1, self.last_model))
        out = []
        blocks = re.split(r"^\[(\d+)\] \(task type: [^)]*\)\nINSTRUCTION:\n", prompt, flags=re.M)[1:]
        for i in range(0, len(blocks), 2):
            idx, body = int(blocks[i]), blocks[i + 1]
            fail = sum(map(ord, body.split("\nRESPONSE:\n")[0][:60])) % 7 == 0
            out.append({"index": idx, "supported": not fail, "correct": True, "follows_instruction": True,
                        "instruction_clear": True, "fluent_english": True, "level": "intermediate",
                        "verdict": "fail" if fail else "pass", "issues": "fake" if fail else ""})
        return out


llm.Gemini = FakeGemini
cal = importlib.import_module("judge_calibration")
cal.PLAN = {"DOC": 1, "REF": 1, "SE": 1}
cal.CRITERIA = {**cal.CRITERIA, "min_single_fails": 1}

# 1) kota: 2 çağrıdan sonra kota dolar -> çıkış 2, kaldığı yerden devam
FakeGemini.quota_after = 2
check("kota dolunca çıkış 2", cal.main() == 2)
sel = json.loads((TMP / "interim" / "judge_calibration" / "selection.json").read_text(encoding="utf-8"))
check("seçim sabitlendi (3 üçlü)", len(sel["triples"]) == 3, str([t["jobs"] for t in sel["triples"]]))
check("üçlüler 3'er iş, tür karışmıyor",
      all(len(t["jobs"]) == 3 and len({j.split("_")[1] for j in t["jobs"]}) == 1 for t in sel["triples"]))
check("yargıç modeli üreticiden farklı", all(t["judge_model"] != GEN for t in sel["triples"]
                                              if not t["jobs"][0].startswith("JOB_SE_")))
FakeGemini.quota_after = None
check("devam: tamamlandı (çıkış 0)", cal.main() == 0)
n_calls = len(FakeGemini.calls)
check("çağrı sayısı = 9 tekli + 3 toplu", n_calls == 12, str(n_calls))
check("toplu çağrılar 3 grup", sorted(n for n, _ in FakeGemini.calls).count(3) == 3)
res = json.loads((TMP / "reports" / "judge_calibration.json").read_text(encoding="utf-8"))
check("bütün seçili örnekler karşılaştırıldı", res["examples_compared"] == res["examples_selected"] > 0,
      f"{res['examples_compared']}/{res['examples_selected']}")
check("aynı karar -> uyum %100", res["agreement"] == 1.0 and res["fail_recall"] == 1.0, str(res["agreement"]))
check("otomatik ölçüt sağlandı", res["automatic_criteria_met"] is True)
check("markdown rapor yazıldı", (TMP / "reports" / "judge_calibration.md").exists())
rec = [json.loads(x) for f in ("single", "batch") for x in open(TMP / "interim" / "judge_calibration" / f"{f}.jsonl",
                                                                  encoding="utf-8")]
model_of = {t: tr["judge_model"] for t, tr in enumerate(sel["triples"])}
check("iki mod da üçlünün yargıç modeliyle", all(r["judge_model"] == model_of[r["triple"]] for r in rec))
check("resmî yargıç dosyası yazılmadı", not (TMP / "interim" / "instruction_judgments.jsonl").exists())

# 2) yeniden çalıştırma: yeni çağrı yok
check("tekrar çalıştırma çıkış 0", cal.main() == 0)
check("tekrar çalıştırmada yeni çağrı yok", len(FakeGemini.calls) == n_calls)

# 3) toplu yargıç gevşek olsaydı: ölçüt 2 sağlanmamalı
by_job = {}
rows, _ = cal.v11.prepare_rows(cal.RemovalLog(TMP / "x.csv", "t"))
for r in rows:
    by_job.setdefault(r["job_id"], []).append(r)
judged = {m: {r["raw_example_id"]: r for r in rec if r["mode"] == m} for m in ("single", "batch")}
lenient = {k: {**v, "supported": True, "verdict": "pass"} for k, v in judged["batch"].items()}
cal.report(sel, by_job, {"single": judged["single"], "batch": lenient})
res2 = json.loads((TMP / "reports" / "judge_calibration.json").read_text(encoding="utf-8"))
check("gevşek toplu yargıç: yakalama 0", res2["fail_recall"] == 0.0, str(res2["fail_recall"]))
check("gevşek toplu yargıç: ölçüt sağlanmadı", res2["automatic_criteria_met"] is False)
check("uyuşmayanlar listelendi", len(res2["disagreements"]) == res2["single_fail"] > 0)

print(f"\nhata: {bad}")
if not bad:
    shutil.rmtree(TMP, ignore_errors=True)
else:
    print(f"İnceleme için geçici klasör bırakıldı: {TMP}")
sys.exit(1 if bad else 0)
