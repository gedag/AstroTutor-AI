"""10 — Instruction örneklerini üretir (Instruction v2.0, İngilizce).

Üç iş türü (09'da hazırlanır):
  doc     : Domain Corpus dokümanından, atanmış görev türleri ve seviyelerle örnekler (Gemini, LLM destekli sentetik)
  se      : Stack Exchange soru-cevap çiftleri; v2.0'da Gemini KULLANILMAZ, orijinal İngilizce metin olduğu gibi
            kaydedilir (seviye "unassigned"; seviyeyi 11'deki LLM yargıç atar)
  refusal : kapsam dışı / bilgi yetersizliği örnekleri (Gemini)

Model, sıcaklık ve prompt sürümü config.yaml'dadır; prompt metinleri prompts/<sürüm>/ altındadır.
Kaldığı yerden devam eder: tamamlanan işler data/interim/instruction_jobs_done.jsonl'de tutulur.
(v1.0'daki Türkçe karakter kontrolü ve "yalnız Flash ile yeniden dene" kuralı v2.0'da gerekmez; Git etiketi v1.0.)

Kullanım:
  python scripts/10_generate_instructions.py --limit 4      # pilot deneme (iş türlerinden dengeli)
  python scripts/10_generate_instructions.py                # tüm işler
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
from mcq_check import JOB_REJECT_RATIO, job_mcq_leak_ratio

log = get_logger("10_generate_instructions")
I = CFG["instruction"]
PD = ROOT / CFG["paths"]["prompts"] / I["prompt_version"]
SE_UNASSIGNED_LEVEL = "unassigned"   # 11'de yargıç beginner / intermediate / advanced atar


class Example(BaseModel):
    task_type: str
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
    tl = "\n".join(f"{i + 1}. task_type={t}, level={lv}" for i, (t, lv) in enumerate(zip(job["task_types"], job["levels"])))
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
                    "generation_method": "llm_synthetic_from_source_document"})
    return out


def run_se(job: dict) -> list[dict]:
    """Gemini yok: soru ve cevap 09'da seçildiği gibi, metin değiştirilmeden örneğe dönüşür."""
    out = []
    for k, it in enumerate(job["items"]):
        out.append({"task_type": "question_answering", "level": SE_UNASSIGNED_LEVEL,
                    "instruction": it["question"], "response": it["answer"], "supporting_evidence": "",
                    "raw_example_id": f"{job['job_id']}_{k:02d}", "job_id": job["job_id"],
                    "source_document": it["rid"], "source_url": it["url"], "source_name": "stackexchange_space_qa",
                    "split_hint": None, "planned_task_type": "question_answering",
                    "generation_method": "stackexchange_original_verbatim",
                    # lisans sürümü cevabın tarihinden (09); kaynak veri setinde yazar adı yok
                    "source_license": it.get("license"), "source_answer_date": it.get("answer_date")})
    return out


def run_refusal(job: dict, llm: Gemini) -> list[dict]:
    prompt = fill(load_prompt("generate_refusal.txt"), n=job["n"], themes="; ".join(job["themes"]))
    res = llm.generate_json(load_prompt("system_generate.txt"), prompt, list[Example])
    out = []
    for k, ex in enumerate(res):
        ex = ex.model_dump() if hasattr(ex, "model_dump") else ex
        rid = f"{job['job_id']}_{k:02d}"
        out.append({**ex, "task_type": "out_of_scope_refusal", "raw_example_id": rid,
                    "job_id": job["job_id"], "source_document": f"NOSRC_{rid}", "source_url": None,
                    "source_name": "none", "split_hint": None, "themes": job["themes"],
                    "planned_task_type": "out_of_scope_refusal",
                    "generation_method": "llm_synthetic_out_of_scope"})
    return out


def record_failure(job: dict, msg: str, fails: Counter) -> None:
    """Kalıcı hata (bozuk JSON, çoktan seçmeli sızıntısı vb.): 3 denemeden sonra iş atlanır, her gün kota yakmasın."""
    append_jsonl(p("interim") / "instruction_jobs_failed.jsonl", {"job_id": job["job_id"], "error": msg[:300],
                                                                  "at": now_iso()})
    fails[job["job_id"]] += 1
    if fails[job["job_id"]] >= 3:
        append_jsonl(p("interim") / "instruction_jobs_done.jsonl",
                     {"job_id": job["job_id"], "n": 0, "failed": True, "at": now_iso()})
        log.error(f"{job['job_id']} 3 kez başarısız oldu, atlandı")


def main() -> int:
    """Çıkış kodu: 0 = tüm işler bitti, 2 = günlük kota doldu, 3 = model yoğunluğu (503) nedeniyle durdu / iş kaldı."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="en fazla bu kadar iş çalıştır (pilot)")
    ap.add_argument("--kind", choices=["doc", "se", "refusal"], default=None)
    a = ap.parse_args()
    jobs = list(read_jsonl(p("interim") / "instruction_jobs.jsonl"))
    done = {r["job_id"] for r in read_jsonl(p("interim") / "instruction_jobs_done.jsonl")}
    fails = Counter(r["job_id"] for r in read_jsonl(p("interim") / "instruction_jobs_failed.jsonl"))
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
    # Stack Exchange işleri Gemini kullanmaz; istemci yalnız gerekiyorsa kurulur (anahtar yoksa SE işleri yine çalışır)
    llm = Gemini(I["generator_models"], I["temperature"], I.get("generator_thinking_budget")) \
        if any(j["kind"] != "se" for j in todo) else None
    docs = doc_texts()
    n_ex = 0
    busy_streak = 0
    code = 0
    for i, job in enumerate(todo, 1):
        try:
            if job["kind"] == "doc":
                rows = run_doc(job, docs, llm)
            elif job["kind"] == "se":
                rows = run_se(job)
            else:
                rows = run_refusal(job, llm)
        except QuotaExhausted as e:
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
        model = None if job["kind"] == "se" else llm.last_model
        # Çoktan seçmeli örneklerde soru/şık/cevap talimatın içine yazılmışsa (bkz. mcq_check.py) iş yeniden denenir
        leak = job_mcq_leak_ratio(rows)
        if leak >= JOB_REJECT_RATIO:
            log.warning(f"{job['job_id']} reddedildi ({model}): çoktan seçmeli örneklerin %{100 * leak:.0f}'inde "
                        f"soru/şık/cevap talimatta; yeniden denenecek")
            record_failure(job, f"mcq_question_in_instruction ratio={leak:.2f} model={model}", fails)
            continue
        for r in rows:
            r.update({"generator_model": model, "prompt_version": None if model is None else I["prompt_version"],
                      "temperature": None if model is None else I["temperature"], "generated_at": now_iso()})
            append_jsonl(p("interim") / "instructions_raw.jsonl", r)
        append_jsonl(p("interim") / "instruction_jobs_done.jsonl", {"job_id": job["job_id"], "n": len(rows),
                                                                    "model": model, "at": now_iso()})
        n_ex += len(rows)
        if i % 10 == 0:
            log.info(f"{i}/{len(todo)} iş, {n_ex} örnek" + (f", çağrı={llm.calls}, token={llm.usage}" if llm else ""))
    log.info(f"Bu çalıştırmada {n_ex} örnek üretildi"
             + (f"; çağrı={llm.calls} {llm.calls_by_model}; 503={llm.busy}; token={llm.usage}" if llm else ""))
    if code == 0 and not a.limit:
        done = {r["job_id"] for r in read_jsonl(p("interim") / "instruction_jobs_done.jsonl")}
        left = sum(1 for j in jobs if j["job_id"] not in done)
        log.info(f"Kalan iş: {left}")
        code = 0 if left == 0 else 3
    return code


if __name__ == "__main__":
    sys.exit(main())
