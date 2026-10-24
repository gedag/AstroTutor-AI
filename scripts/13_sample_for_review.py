"""13 — Kalite kontrolü için rastgele örneklem tabloları üretir (Vize Rehberi §12).

reports/qc/corpus_review.csv       : qc.corpus_sample (100) rastgele corpus dokümanı (kaynak oranında tabakalı)
reports/qc/instruction_review.csv  : qc.instruction_sample (150) rastgele instruction örneği (görev türü oranında)

İnceleme iki aşamalıdır ve raporda AYRI gösterilir:
  1) claude_* sütunları  : yapay zekâ destekli ön inceleme (Claude). Ölçüt başına 1/0, genel karar, hata türü, gerekçe.
  2) son_karar sütunu    : grup üyesinin NİHAİ kararı (uygun / sorunlu). Claude'un kararına katılıyorsa aynısını,
                           katılmıyorsa kendi kararını yazar; gerekirse son_hata_turu ve insan_notu doldurur.
Dolu bir tablo varsa üzerine yazılmaz (--force ile yazılır).
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict

from common import CFG, get_logger, p, read_jsonl, rng

log = get_logger("13_sample_for_review")
CORPUS_CRIT = ["okunabilir", "dogru_domain", "extraction_dogru", "header_footer_temiz", "bozuk_karakter_yok",
               "metadata_dogru"]
INS_CRIT = ["talimat_anlasilir", "kaynakla_tutarli", "talimati_karsiliyor", "gorev_turu_dogru", "turkce_akici"]
CLAUDE_TAIL = ["claude_karar", "claude_hata_turu", "claude_gerekce"]
HUMAN = ["son_karar", "son_hata_turu", "insan_notu"]


def stratified(rows: list[dict], key: str, n: int, seed_off: int) -> list[dict]:
    r = rng(seed_off)
    by = defaultdict(list)
    for x in rows:
        by[x[key]].append(x)
    out = []
    for k in sorted(by):
        r.shuffle(by[k])
        out += by[k][: max(1, round(n * len(by[k]) / len(rows)))]
    r.shuffle(out)
    return out[:n]


def already_filled(path) -> bool:
    if not path.exists():
        return False
    with open(path, encoding="utf-8-sig") as f:
        return any((row.get("claude_karar") or row.get("son_karar") or "").strip() for row in csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", choices=["corpus", "instruction"], default=None)
    a = ap.parse_args()
    q = CFG["qc"]
    docs = []
    for s in ("train", "validation", "test"):
        docs += list(read_jsonl(p("final") / f"{s}.jsonl"))

    if a.only in (None, "corpus"):
        out = p("qc") / "corpus_review.csv"
        if already_filled(out) and not a.force:
            log.info("corpus_review.csv dolu, atlandı")
        else:
            sample = stratified(docs, "source", q["corpus_sample"], 13)
            with open(out, "w", encoding="utf-8-sig", newline="") as f:  # BOM: Excel Türkçe karakterleri doğru açsın
                w = csv.writer(f)
                w.writerow(["document_id", "source", "language", "subtopic", "document_type", "publication_year",
                            "title", "url", "token_count", "metin_ilk_1500"]
                           + [f"claude_{c}" for c in CORPUS_CRIT] + CLAUDE_TAIL + HUMAN)
                for d in sample:
                    w.writerow([d["document_id"], d["source"], d["language"], d["subtopic"], d["document_type"],
                                d["publication_year"], d["title"], d["url"], d["token_count"], d["text"][:1500]]
                               + [""] * (len(CORPUS_CRIT) + len(CLAUDE_TAIL) + len(HUMAN)))
            log.info(f"corpus_review.csv: {len(sample)} doküman")

    if a.only in (None, "instruction"):
        ins = list(read_jsonl(p("final") / "instruction_v1.0.jsonl"))
        if not ins:
            log.warning("instruction_v1.0.jsonl yok; instruction örneklemi atlandı")
            return
        doc_text = {d["document_id"]: d["text"] for d in docs}
        se_text = {}
        for j in read_jsonl(p("interim") / "instruction_jobs.jsonl"):
            for it in j.get("items", []):
                se_text[it["rid"]] = f"Q: {it['question']}\n\nA: {it['answer']}"
        out = p("qc") / "instruction_review.csv"
        if already_filled(out) and not a.force:
            log.info("instruction_review.csv dolu, atlandı")
            return
        sample = stratified(ins, "task_type", q["instruction_sample"], 14)
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "task_type", "level", "source_document", "source_url", "kaynak_ilk_3000", "talimat",
                        "cevap", "destekleyen_alinti"] + [f"claude_{c}" for c in INS_CRIT] + CLAUDE_TAIL + HUMAN)
            for x in sample:
                src = doc_text.get(x["source_document"]) or se_text.get(x["source_document"]) or "(kaynak yok)"
                w.writerow([x["id"], x["task_type"], x["level"], x["source_document"], x["source_url"], src[:3000],
                            x["instruction"], x["response"], x.get("supporting_evidence")]
                           + [""] * (len(INS_CRIT) + len(CLAUDE_TAIL) + len(HUMAN)))
        log.info(f"instruction_review.csv: {len(sample)} örnek")


if __name__ == "__main__":
    main()
