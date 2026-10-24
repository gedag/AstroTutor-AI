"""Kusurlu üretim işlerini yeniden kuyruğa alır (bakım script'i).

Bir işin çıktısındaki örneklerin en az JOB_REJECT_RATIO'su Türkçe karakter eksikliği taşıyorsa
(bkz. scripts/turkish_check.py) o işin örnekleri instructions_raw.jsonl'den ARŞİVE taşınır ve iş
"tamamlanmış" listesinden çıkarılır; 10_generate_instructions.py işi bir sonraki çalışmada yeniden üretir.
Hiçbir örnek sessizce silinmez: arşiv data/interim/archive/ altında, iş listesi reports/removed_instructions.csv'de
(stage=regen).

    python scripts/requeue_jobs.py --dry-run   # yalnız rapor
    python scripts/requeue_jobs.py
    python scripts/requeue_jobs.py --reason mcq --prompt-version v1.1   # soru/şık/cevabı talimatta veren işler

Üretim döngüsü çalışırken KULLANILMAZ (instructions_raw.jsonl ve iş listesi yeniden yazılır).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime

from common import RemovalLog, get_logger, p, read_jsonl, write_jsonl
from mcq_check import job_mcq_leak_ratio
from turkish_check import JOB_REJECT_RATIO, job_defect_ratio

log = get_logger("requeue_jobs")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reason", choices=["turkce", "mcq"], default="turkce")
    ap.add_argument("--prompt-version", help="yalnız bu prompt sürümüyle üretilmiş işler")
    a = ap.parse_args()
    raw_f = p("interim") / "instructions_raw.jsonl"
    done_f = p("interim") / "instruction_jobs_done.jsonl"
    raw = list(read_jsonl(raw_f))
    done = list(read_jsonl(done_f))
    by_job = defaultdict(list)
    for r in raw:
        by_job[r["job_id"]].append(r)
    ratio = job_defect_ratio if a.reason == "turkce" else job_mcq_leak_ratio
    bad = {j: ratio(rs) for j, rs in by_job.items()
           if not a.prompt_version or rs[0].get("prompt_version") == a.prompt_version}
    bad = {j: v for j, v in bad.items() if v >= JOB_REJECT_RATIO}
    n_rows = sum(len(by_job[j]) for j in bad)
    models = defaultdict(int)
    for j in bad:
        models[by_job[j][0].get("generator_model")] += 1
    log.info(f"Kusurlu iş: {len(bad)} ({n_rows} örnek); modeller: {dict(models)}")
    if a.dry_run or not bad:
        for j, v in sorted(bad.items()):
            log.info(f"  {j}: %{100 * v:.0f} kusurlu, {len(by_job[j])} örnek, {by_job[j][0].get('generator_model')}")
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = "turkce_karakter_eksik" if a.reason == "turkce" else "mcq_talimatta_soru"
    arch = p("interim") / "archive" / f"{tag}_{stamp}.jsonl"
    arch.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(arch, [r for j in sorted(bad) for r in by_job[j]])
    write_jsonl(raw_f, [r for r in raw if r["job_id"] not in bad])
    write_jsonl(done_f, [d for d in done if d["job_id"] not in bad])
    csv_path = p("reports") / "removed_instructions.csv"
    removed = RemovalLog(csv_path, "regen", reset=False)
    # RemovalLog aynı aşamanın eski satırlarını atar (yeniden çalıştırmada tekrar olmasın diye); "regen"
    # kayıtları ise birikmeli, bu yüzden geri eklenir.
    import csv
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            removed.rows += [r for r in csv.DictReader(f) if r["stage"] == "regen"]
    prev = {r["id"] for r in removed.rows if r["stage"] == "regen"}
    for j in sorted(bad):
        if j not in prev:  # aynı iş ikinci kez yeniden kuyruğa alınırsa satır tekrarlanmaz
            removed.add(j, "turkish_chars_missing_job_regenerated" if a.reason == "turkce" else
                        "mcq_answer_in_instruction_job_regenerated", by_job[j][0]["source_name"],
                        f"kusurlu oran={bad[j]:.2f} örnek={len(by_job[j])} model={by_job[j][0].get('generator_model')} "
                        f"arşiv={arch.name}")
    removed.save()
    log.info(f"{len(bad)} iş yeniden kuyruğa alındı; {n_rows} örnek arşivlendi: {arch}")


if __name__ == "__main__":
    main()
