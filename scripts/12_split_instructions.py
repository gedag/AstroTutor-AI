"""12 — Instruction Dataset v1.0'ı oluşturur ve train/validation/test olarak ayırır (Vize Rehberi §11).

Sızıntı önleme:
  - Corpus dokümanından üretilen örnekler, kaynak dokümanın CORPUS'taki kümesini miras alır.
    -> Aynı dokümandan gelen tüm örnekler tek kümede kalır VE corpus test dokümanından üretilen bir örnek
       instruction train'e giremez (CPT ile SFT arasında da sızıntı yok).
  - StackExchange örnekleri soru kimliğine (qid), kapsam dışı örnekler kendi kimliğine göre gruplanır ve
    seed 42 ile %90/%5/%5 ayrılır.
Çıktı: data/final/instruction_v1.0.jsonl (tamamı, split alanıyla)
       data/final/instruction/{train,validation,test}.jsonl
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from common import CFG, get_logger, p, read_jsonl, rng, write_jsonl

log = get_logger("12_split_instructions")
S = CFG["split"]


def main() -> None:
    rows = list(read_jsonl(p("interim") / "instructions_verified.jsonl"))
    rows.sort(key=lambda r: r["raw_example_id"])
    doc_license = {}
    for s in ("train", "validation", "test"):
        for d in read_jsonl(p("final") / f"{s}.jsonl"):
            doc_license[d["document_id"]] = d["license"]
    # SE ve kapsam dışı örnekler için grup bazlı rastgele ayrım
    groups = sorted({r["source_document"] for r in rows if not r.get("split_hint")})
    r = rng(12)
    r.shuffle(groups)
    n = len(groups)
    n_test, n_val = round(n * S["test"]), round(n * S["validation"])
    gsplit = {g: ("test" if i < n_test else "validation" if i < n_test + n_val else "train") for i, g in enumerate(groups)}
    out = []
    for i, x in enumerate(rows, 1):
        split = x.get("split_hint") or gsplit[x["source_document"]]
        if x["source_name"] == "stackexchange_space_qa":
            lic = "CC BY-SA 4.0 (Stack Exchange içeriğinin Türkçe türevi)"
        elif x["source_name"] == "none":
            lic = "Proje tarafından üretildi (kaynak doküman yok)"
        else:
            lic = doc_license.get(x["source_document"])
        out.append({
            "id": f"INS_{i:05d}", "source_document": x["source_document"], "source_url": x.get("source_url"),
            "source_name": x["source_name"], "task_type": x["task_type"], "level": x["level"],
            "messages": [{"role": "user", "content": x["instruction"].strip()},
                         {"role": "assistant", "content": x["response"].strip()}],
            "instruction": x["instruction"].strip(), "response": x["response"].strip(),
            "supporting_evidence": x.get("supporting_evidence"), "generation_method": x["generation_method"],
            "generator_model": x["generator_model"], "prompt_version": x["prompt_version"],
            "auto_verified": x.get("auto_verified", False), "judge_model": (x.get("judge") or {}).get("judge_model"),
            "human_verified": None, "verified_by": "kural_kontrolleri+llm_yargic" if x.get("auto_verified") else None,
            "license": lic, "split": split, "raw_example_id": x["raw_example_id"]})
    write_jsonl(p("final") / "instruction_v1.0.jsonl", out)
    by = defaultdict(list)
    for x in out:
        by[x["split"]].append(x)
    for s in ("train", "validation", "test"):
        write_jsonl(p("final") / "instruction" / f"{s}.jsonl", by[s])
    # sızıntı kontrolü: bir kaynak doküman yalnız bir kümede
    owner = {}
    for x in out:
        assert owner.setdefault(x["source_document"], x["split"]) == x["split"], x["source_document"]
    summary = {"total": len(out), "splits": {s: len(v) for s, v in by.items()},
               "task_types": dict(Counter(x["task_type"] for x in out)),
               "levels": dict(Counter(x["level"] for x in out)),
               "sources": dict(Counter(x["source_name"] for x in out)),
               "methods": dict(Counter(x["generation_method"] for x in out)),
               "task_type_by_split": {s: dict(Counter(x["task_type"] for x in v)) for s, v in by.items()}}
    (p("reports") / "instruction_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                                           encoding="utf-8")
    log.info(f"Instruction v1.0: {len(out)} örnek; " + ", ".join(f"{s}={len(v)}" for s, v in by.items()))


if __name__ == "__main__":
    main()
