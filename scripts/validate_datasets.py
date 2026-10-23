"""Teslim öncesi veri seti doğrulaması — "bu veri final döneminde eğitim için gerçekten kullanılabilir mi?"

Kontroller:
  1. Corpus JSONL şeması, document_id benzersizliği, split'ler arası doküman/grup çakışması = 0
  2. Instruction JSONL şeması, id benzersizliği, kaynak doküman birden fazla kümede değil
  3. Instruction ile corpus arasında küme tutarlılığı (corpus test dokümanından üretilen örnek train'de değil)
  4. Hugging Face `datasets` ile yüklenebilirlik
  5. Instruction örneklerine Qwen2.5-7B-Instruct chat template'inin hatasız uygulanması (SFT'ye hazır)
  6. Değerlendirme setleriyle 8-gram örtüşmesi (instruction'da 0 olmalı; corpus'ta raporlanır)
Sonuç: reports/validation_report.md ; hata varsa çıkış kodu 1
"""
from __future__ import annotations

import importlib
import re
import sys

from common import CFG, get_logger, p, read_jsonl

log = get_logger("validate_datasets")
CORPUS_FIELDS = ["document_id", "title", "source", "url", "language", "document_type", "publication_year", "subtopic",
                 "license", "retrieved_at", "split", "char_count", "word_count", "token_count", "text"]
INS_FIELDS = ["id", "source_document", "task_type", "level", "messages", "instruction", "response",
              "generation_method", "generator_model", "auto_verified", "human_verified", "split"]


def main() -> int:
    errors, lines = [], ["# Veri seti doğrulama raporu", ""]

    def check(name, ok, detail=""):
        lines.append(f"- [{'x' if ok else ' '}] {name}{' — ' + detail if detail else ''}")
        if not ok:
            errors.append(name)

    corpus = {s: list(read_jsonl(p("final") / f"{s}.jsonl")) for s in ("train", "validation", "test")}
    alld = [d for v in corpus.values() for d in v]
    check("Corpus boş değil", len(alld) > 0, f"{len(alld)} doküman")
    miss = [d["document_id"] for d in alld if any(f not in d for f in CORPUS_FIELDS)]
    check("Corpus şeması tam", not miss, f"eksik alanlı {len(miss)}")
    ids = [d["document_id"] for d in alld]
    check("document_id benzersiz", len(ids) == len(set(ids)))
    gs = {}
    clash = 0
    for s, v in corpus.items():
        for d in v:
            if gs.setdefault(d["group_key"], s) != s:
                clash += 1
    check("Corpus split'leri arasında grup çakışması yok", clash == 0, f"çakışma={clash}")
    doc_split = {d["document_id"]: d["split"] for d in alld}

    ins = list(read_jsonl(p("final") / "instruction_v1.0.jsonl"))
    if ins:
        miss = [x["id"] for x in ins if any(f not in x for f in INS_FIELDS)]
        check("Instruction şeması tam", not miss, f"{len(ins)} örnek, eksik alanlı {len(miss)}")
        check("Instruction id benzersiz", len({x["id"] for x in ins}) == len(ins))
        own, clash = {}, 0
        for x in ins:
            if own.setdefault(x["source_document"], x["split"]) != x["split"]:
                clash += 1
        check("Aynı kaynak dokümandan gelen örnekler tek kümede", clash == 0, f"çakışma={clash}")
        bad = sum(1 for x in ins if x["source_document"] in doc_split and doc_split[x["source_document"]] != x["split"])
        check("Instruction kümesi = kaynak dokümanın corpus kümesi (CPT↔SFT sızıntısı yok)", bad == 0, f"uyumsuz={bad}")
        for s in ("train", "validation", "test"):
            n = sum(1 for _ in read_jsonl(p("final") / "instruction" / f"{s}.jsonl"))
            check(f"instruction/{s}.jsonl mevcut", n > 0, f"{n} örnek")
    else:
        check("Instruction dataset mevcut", False, "data/final/instruction_v1.0.jsonl yok")

    try:
        from datasets import load_dataset

        ds = load_dataset("json", data_files={s: str(p("final") / f"{s}.jsonl") for s in corpus})
        check("Corpus HF datasets ile yükleniyor", True, str({k: v.num_rows for k, v in ds.items()}))
        if ins:
            di = load_dataset("json", data_files={s: str(p("final") / "instruction" / f"{s}.jsonl")
                                                  for s in ("train", "validation", "test")})
            check("Instruction HF datasets ile yükleniyor", True, str({k: v.num_rows for k, v in di.items()}))
    except Exception as e:
        check("HF datasets ile yükleme", False, str(e)[:200])

    if ins:
        try:
            from transformers import AutoTokenizer

            tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
            lens = [len(tok.apply_chat_template(x["messages"], tokenize=True)) for x in ins]
            lens.sort()
            check("Qwen2.5-7B-Instruct chat template uygulanabiliyor", True,
                  f"örnek token uzunluğu medyan={lens[len(lens) // 2]}, p95={lens[int(0.95 * (len(lens) - 1))]}, "
                  f"maks={lens[-1]}; 2048 token üzeri={sum(1 for x in lens if x > 2048)}")
        except Exception as e:
            check("Chat template", False, str(e)[:200])

    b9 = importlib.import_module("09_build_instruction_sources")
    n = CFG["instruction"]["decontam_ngram"]
    grams = b9.eval_ngrams(n)
    if ins:
        hit = sum(1 for x in ins if b9.overlaps(x["instruction"] + " " + x["response"], grams, n))
        check("Instruction ↔ değerlendirme setleri 8-gram örtüşmesi = 0", hit == 0, f"örtüşen={hit}")
    hitd = [d["document_id"] for d in alld if b9.overlaps(d["text"], grams, n) >= 3]
    lines.append(f"- [i] Corpus'ta değerlendirme setleriyle ≥3 adet 8-gram paylaşan doküman: {len(hitd)} "
                 f"(bilgi amaçlı; final değerlendirmesinde bu sorular ayrıca işaretlenecek)")
    (p("reports") / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for ln in lines:
        log.info(ln)
    log.info("BAŞARILI" if not errors else f"HATALAR: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
