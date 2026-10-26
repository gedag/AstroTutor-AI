"""10 — Gemini ile Türkçe instruction örnekleri üretir (LLM destekli sentetik üretim).

Üç iş türü (09'da hazırlanır):
  doc     : Domain Corpus dokümanından, atanmış görev türleri ve seviyelerle 4-8 örnek
  se      : StackExchange Q&A çiftlerinin Türkçeleştirilip temizlenmesi (soru_cevap)
  refusal : kapsam dışı / bilgi yetersizliği örnekleri

Model, sıcaklık ve prompt sürümü config.yaml'dadır; prompt metinleri prompts/<sürüm>/ altındadır.
Kaldığı yerden devam eder: tamamlanan işler data/interim/instruction_jobs_done.jsonl'de tutulur.

Kullanım:
  python scripts/10_generate_instructions.py --limit 10      # pilot deneme
  python scripts/10_generate_instructions.py                 # tüm işler
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter

from pydantic import BaseModel

from common import CFG, ROOT, append_jsonl, fill, get_logger, now_iso, p, read_jsonl
from llm import Gemini, QuotaExhausted, TransientError
from mcq_check import job_mcq_leak_ratio
from turkish_check import JOB_REJECT_RATIO, job_defect_ratio

log = get_logger("10_generate_instructions")
I = CFG["instruction"]
PD = ROOT / CFG["paths"]["prompts"] / I["prompt_version"]
LEVEL_TR = {"baslangic": "başlangıç", "orta": "orta", "ileri": "ileri"}


class Example(BaseModel):
    task_type: str
    level: str
    instruction: str
    response: str
    supporting_evidence: str


class SeExample(BaseModel):
    source_id: str
    skip: bool
    skip_reason: str
    level: str
    instruction: str
    response: str
    supporting_evidence: str


def load_prompt(name: str) -> str:
    return (PD / name).read_text(encoding="utf-8")


def doc_texts() -> dict[str, dict]:
    out = {}
    for s in ("train", "validation", "test"):
        for d in read_jsonl(p("final") / f"{s}.jsonl"):
            out[d["document_id"]] = d
    return out


def excerpt(text: str) -> str:
    return text[: I["source_doc_max_chars"]]


def run_doc(job: dict, docs: dict, llm: Gemini) -> list[dict]:
    d = docs[job["source_document"]]
    defs = json.loads(load_prompt("task_types.json"))
    tl = "\n".join(f"{i + 1}. task_type={t}, level={lv} ({LEVEL_TR[lv]})"
                   for i, (t, lv) in enumerate(zip(job["task_types"], job["levels"])))
    used = sorted(set(job["task_types"]))
    prompt = fill(load_prompt("generate_doc.txt"),
        title=d["title"], source_name=d["source"], language=d["language"], text=excerpt(d["text"]),
        n=len(job["task_types"]), task_list=tl, task_defs="\n".join(f"- {t}: {defs[t]}" for t in used))
    res = llm.generate_json(load_prompt("system_generate.txt"), prompt, list[Example])
    out = []
    for k, ex in enumerate(res):
        ex = ex.model_dump() if hasattr(ex, "model_dump") else ex
        out.append({**ex, "raw_example_id": f"{job['job_id']}_{k:02d}", "job_id": job["job_id"],
                    "source_document": job["source_document"], "source_url": job["source_url"],
                    "source_name": job["source_name"], "split_hint": job["split"],
                    "planned_task_type": job["task_types"][k] if k < len(job["task_types"]) else None,
                    "generation_method": "llm_sentetik_kaynak_dokumandan"})
    return out


def run_se(job: dict, llm: Gemini) -> list[dict]:
    items = "\n\n".join(
        f"### source_id: {it['rid']}\nQUESTION:\n{it['question']}\n\nANSWER:\n{it['answer']}" for it in job["items"])
    res = llm.generate_json(load_prompt("system_generate.txt"), fill(load_prompt("generate_se.txt"), items=items),
                            list[SeExample])
    by = {it["rid"]: it for it in job["items"]}
    out = []
    for k, ex in enumerate(res):
        ex = ex.model_dump() if hasattr(ex, "model_dump") else ex
        it = by.get(ex["source_id"])
        if it is None:
            continue
        out.append({"task_type": "soru_cevap", "level": ex["level"], "instruction": ex["instruction"],
                    "response": ex["response"], "supporting_evidence": ex["supporting_evidence"],
                    "skip": ex["skip"], "skip_reason": ex["skip_reason"],
                    "raw_example_id": f"{job['job_id']}_{k:02d}", "job_id": job["job_id"],
                    "source_document": it["rid"], "source_url": it["url"], "source_name": "stackexchange_space_qa",
                    "split_hint": None, "planned_task_type": "soru_cevap",
                    "generation_method": "llm_ceviri_duzenleme_stackexchange"})
    return out


def run_refusal(job: dict, llm: Gemini) -> list[dict]:
    prompt = fill(load_prompt("generate_refusal.txt"), n=job["n"], themes="; ".join(job["themes"]))
    res = llm.generate_json(load_prompt("system_generate.txt"), prompt, list[Example])
    out = []
    for k, ex in enumerate(res):
        ex = ex.model_dump() if hasattr(ex, "model_dump") else ex
        rid = f"{job['job_id']}_{k:02d}"
        out.append({**ex, "task_type": "bilgi_yetersizligi_kapsam_disi", "raw_example_id": rid,
                    "job_id": job["job_id"], "source_document": f"NOSRC_{rid}", "source_url": None,
                    "source_name": "none", "split_hint": None, "themes": job["themes"],
                    "planned_task_type": "bilgi_yetersizligi_kapsam_disi",
                    "generation_method": "llm_sentetik_kapsam_disi"})
    return out


def record_failure(job: dict, msg: str, fails: Counter) -> None:
    """Kalıcı hata (bozuk JSON, Türkçe karakter eksikliği vb.): 3 denemeden sonra iş atlanır, her gün kota yakmasın."""
    append_jsonl(p("interim") / "instruction_jobs_failed.jsonl", {"job_id": job["job_id"], "error": msg[:300],
                                                                  "at": now_iso()})
    fails[job["job_id"]] += 1
    if fails[job["job_id"]] >= 3:
        append_jsonl(p("interim") / "instruction_jobs_done.jsonl",
                     {"job_id": job["job_id"], "n": 0, "failed": True, "at": now_iso()})
        log.error(f"{job['job_id']} 3 kez başarısız oldu, atlandı")


def main() -> int:
    """Çıkış kodu: 0 = tüm işler bitti, 2 = günlük kota doldu, 3 = model yoğunluğu (503) nedeniyle durdu."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="en fazla bu kadar iş çalıştır (pilot)")
    ap.add_argument("--kind", choices=["doc", "se", "refusal"], default=None)
    a = ap.parse_args()
    jobs = list(read_jsonl(p("interim") / "instruction_jobs.jsonl"))
    done = {r["job_id"] for r in read_jsonl(p("interim") / "instruction_jobs_done.jsonl")}
    failed_rows = list(read_jsonl(p("interim") / "instruction_jobs_failed.jsonl"))
    fails = Counter(r["job_id"] for r in failed_rows)
    # Lite'ta iki kez Türkçe karakter kusuru veren iş artık yalnız Flash ile denenir (Flash'ta bu kusur %0)
    tr_fails = Counter(r["job_id"] for r in failed_rows if str(r.get("error", "")).startswith("turkce_karakter_eksik"))
    todo = [j for j in jobs if j["job_id"] not in done and (a.kind is None or j["kind"] == a.kind)]
    if a.limit:
        # pilot: her türden dengeli örnek
        by = {}
        for j in todo:
            by.setdefault(j["kind"], []).append(j)
        todo = [j for i in range(a.limit) for k in ("doc", "se", "refusal") for j in by.get(k, [])[i:i + 1]][: a.limit]
    log.info(f"{len(jobs)} iş, {len(done)} tamamlanmış, {len(todo)} çalıştırılacak")
    if not todo:
        return 0
    llm = Gemini(I["generator_models"], I["temperature"], I.get("generator_thinking_budget"))
    docs = doc_texts()
    n_ex = 0
    busy_streak = 0
    code = 0
    deferred = 0
    lite_models = {m for m in llm.models if "lite" in m}
    for i, job in enumerate(todo, 1):
        flash_only = tr_fails[job["job_id"]] >= 2
        llm.force_exclude = lite_models if flash_only else set()
        try:
            if job["kind"] == "doc":
                rows = run_doc(job, docs, llm)
            elif job["kind"] == "se":
                rows = run_se(job, llm)
            else:
                rows = run_refusal(job, llm)
        except QuotaExhausted as e:
            if flash_only:
                # Yalnız Flash ile denenecek iş, Flash kotası şu an dolu: atlanmaz, sonraki çalıştırmaya ertelenir
                deferred += 1
                log.info(f"{job['job_id']}: yalnız Flash ile denenecek, Flash kotası şu an dolu; ertelendi")
                continue
            log.error(f"Günlük kota doldu, durduruldu (kaldığı yerden devam edilebilir): {str(e)[:200]}")
            code = 2
            break
        except Exception as e:
            msg = str(e)
            log.error(f"{job['job_id']} başarısız: {msg[:200]}")
            # Geçici hata (503 / kota / bağlantı): iş kalıcı hata sayılmaz, sonra yeniden denenir
            if isinstance(e, TransientError) or "503" in msg or "UNAVAILABLE" in msg:
                busy_streak += 1
                if busy_streak >= 3:
                    log.error("Üst üste 3 iş yoğunluk (503) nedeniyle başarısız; kota boşa harcanmasın diye "
                              "durduruldu. Birkaç saat sonra kaldığı yerden devam eder.")
                    code = 3
                    break
                time.sleep(120)
                continue
            record_failure(job, msg, fails)
            continue
        busy_streak = 0
        # Türkçe karakterleri düşürülmüş çıktı (lite modellerde çağrı düzeyinde görülüyor): kaydedilmez,
        # iş yeniden denenir. Tek tük kalan kusurlu örnekleri 11_verify_instructions.py eler.
        bad = job_defect_ratio(rows)
        if bad >= JOB_REJECT_RATIO:
            log.warning(f"{job['job_id']} reddedildi ({llm.last_model}): örneklerin %{100 * bad:.0f}'inde Türkçe "
                        f"karakterler eksik; yeniden denenecek")
            record_failure(job, f"turkce_karakter_eksik oran={bad:.2f} model={llm.last_model}", fails)
            tr_fails[job["job_id"]] += 1
            continue
        # Çoktan seçmeli örneklerde soru/şık/cevap talimatın içine yazılmışsa (bkz. mcq_check.py; v1.1 ile azaldı
        # ama iş düzeyinde sürüyor: 24.10'da 10 sızıntının 10'u 2 işten): iş yeniden denenir
        leak = job_mcq_leak_ratio(rows)
        if leak >= JOB_REJECT_RATIO:
            log.warning(f"{job['job_id']} reddedildi ({llm.last_model}): çoktan seçmeli örneklerin %{100 * leak:.0f}'inde "
                        f"soru/şık/cevap talimatta; yeniden denenecek")
            record_failure(job, f"mcq_talimatta_soru oran={leak:.2f} model={llm.last_model}", fails)
            continue
        for r in rows:
            r.update({"generator_model": llm.last_model, "prompt_version": I["prompt_version"],
                      "temperature": I["temperature"], "generated_at": now_iso()})
            append_jsonl(p("interim") / "instructions_raw.jsonl", r)
        append_jsonl(p("interim") / "instruction_jobs_done.jsonl", {"job_id": job["job_id"], "n": len(rows),
                                                                    "model": llm.last_model, "at": now_iso()})
        n_ex += len(rows)
        if i % 10 == 0:
            log.info(f"{i}/{len(todo)} iş, {n_ex} örnek, çağrı={llm.calls}, token={llm.usage}")
    log.info(f"Bu çalıştırmada {n_ex} örnek üretildi; çağrı={llm.calls} {llm.calls_by_model}; "
             f"503={llm.busy}; token={llm.usage}; Flash için ertelenen iş={deferred}")
    if code == 0 and not a.limit:
        done = {r["job_id"] for r in read_jsonl(p("interim") / "instruction_jobs_done.jsonl")}
        left = sum(1 for j in jobs if j["job_id"] not in done)
        log.info(f"Kalan iş: {left}")
        code = 0 if left == 0 else 3
    return code


if __name__ == "__main__":
    sys.exit(main())
