"""Instruction kaynak dokümanlarının kapsam incelemesi tablosu (Instruction v2.0, 11.11.2026).

Tam üretimden sonra yapılan denetimde bazı kaynak dokümanların Tasarım raporunun kapsamı dışında olduğu görüldü
(ör. Wikipedia "Chuseok" — Kore hasat bayramı, corpus'ta "planets_moons" etiketiyle; uzay şirketleri; mikrobiyoloji
haberleri; ileri matematiksel fizik). LLM yargıcın ölçütleri "alan içi mi?" sorusunu içermediği için bu örnekler sete
girebilirdi. Bu script, instruction kaynağı olan HER dokümanı (iş listesindeki doküman işleri) tabloya çıkarır;
yapay zekâ destekli ön karar ve gerekçe (claude_karar / claude_gerekce) yazılır, son kararı grup üyesi verir.
11_verify_instructions.py yalnız son_karar = "cikar" olan kaynakların örneklerini eler (neden: out_of_scope_source).

Kullanım: python scripts/instruction_source_review.py   (dolu kararlar korunur; yeni kaynak yalnız eklenir)
"""
from __future__ import annotations

import csv
from collections import defaultdict

from common import CFG, ROOT, get_logger, p, read_jsonl

log = get_logger("instruction_source_review")
COLS = ["document_id", "source", "title", "subtopic", "url", "ornek_sayisi", "ornek_talimatlar",
        "claude_karar", "claude_gerekce", "son_karar", "insan_notu"]


def review_file():
    return ROOT / CFG["instruction"]["source_review_file"]


def excluded_sources() -> dict[str, str]:
    """son_karar = 'cikar' olan kaynak dokümanlar -> başlık (11 kullanır)."""
    f = review_file()
    if not f.exists():
        return {}
    with open(f, encoding="utf-8-sig") as fh:
        return {r["document_id"]: r["title"] for r in csv.DictReader(fh) if (r.get("son_karar") or "").strip() == "cikar"}


def main() -> None:
    out = review_file()
    prev = {}
    if out.exists():
        with open(out, encoding="utf-8-sig") as f:
            prev = {r["document_id"]: r for r in csv.DictReader(f)}
    docs = {}
    for s in ("train", "validation", "test"):
        for d in read_jsonl(p("final") / f"{s}.jsonl"):
            docs[d["document_id"]] = d
    ex = defaultdict(list)
    for r in read_jsonl(p("interim") / "instructions_raw.jsonl"):
        if r.get("generation_method") == "llm_synthetic_from_source_document":
            ex[r["source_document"]].append(r["instruction"])
    rows = []
    for j in read_jsonl(p("interim") / "instruction_jobs.jsonl"):
        if j["kind"] != "doc":
            continue
        d = docs[j["source_document"]]
        old = prev.get(d["document_id"], {})
        ins = sorted(set(ex[d["document_id"]]))
        rows.append({"document_id": d["document_id"], "source": d["source"], "title": d["title"],
                     "subtopic": d["subtopic"], "url": d["url"], "ornek_sayisi": len(ex[d["document_id"]]),
                     "ornek_talimatlar": " || ".join(x[:160].replace("\n", " ") for x in ins[:4]),
                     **{c: old.get(c, "") for c in ("claude_karar", "claude_gerekce", "son_karar", "insan_notu")}})
    rows.sort(key=lambda x: (x["source"], x["title"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    log.info(f"{out.name}: {len(rows)} kaynak doküman; önceki kararlar korundu ({len(prev)})")


if __name__ == "__main__":
    main()
