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

from common import CFG, get_logger, instruction_file, p, read_jsonl, rng

log = get_logger("13_sample_for_review")
CORPUS_CRIT = ["okunabilir", "dogru_domain", "extraction_dogru", "header_footer_temiz", "bozuk_karakter_yok",
               "metadata_dogru"]
INS_CRIT = ["talimat_anlasilir", "kaynakla_tutarli", "talimati_karsiliyor", "gorev_turu_dogru", "ingilizce_akici"]
CLAUDE_TAIL = ["claude_karar", "claude_hata_turu", "claude_gerekce"]
HUMAN = ["son_karar", "son_hata_turu", "insan_notu"]


def stratified(rows: list[dict], key: str, n: int, seed_off: int) -> list[dict]:
    r = rng(seed_off)
    by = defaultdict(list)
    for x in rows:
        by[x[key]].append(x)
    keys = sorted(by)
    take = {k: max(1, round(n * len(by[k]) / len(rows))) for k in keys}
    # Yuvarlamalar toplamı n'nin altına düşürürse en büyük küsuratlı türlerden tamamlanır (örneklem tam n olsun).
    # Toplam zaten n veya üstündeyse hiçbir şey değişmez (corpus örneklemi bu yüzden aynı kalır).
    short = n - sum(take.values())
    for k in sorted(keys, key=lambda k: -(n * len(by[k]) / len(rows) - take[k]))[: max(0, short)]:
        take[k] += 1
    out = []
    for k in keys:
        r.shuffle(by[k])
        out += by[k][: take[k]]
    r.shuffle(out)
    return out[:n]


def already_filled(path) -> bool:
    if not path.exists():
        return False
    with open(path, encoding="utf-8-sig") as f:
        return any((row.get("claude_karar") or row.get("son_karar") or "").strip() for row in csv.DictReader(f))


def corpus_topup(docs: list[dict], n: int) -> None:
    """Corpus v2.0 (09.11.2026): v1.0 örnekleminden corpus'ta artık olmayan satırları (Türkçe dokümanlar) çıkarır,
    incelenmiş satırlara dokunmaz ve örneklemi kaynak oranlarına göre n dokümana tamamlar (yeni satırlar boş)."""
    out = p("qc") / "corpus_review.csv"
    with open(out, encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        cols, rows = rd.fieldnames, list(rd)
    ids = {d["document_id"] for d in docs}
    kept = [x for x in rows if x["document_id"] in ids]
    log.info(f"corpus_review.csv: {len(rows) - len(kept)} satır corpus'ta olmadığı için çıkarıldı "
             f"({sorted(x['document_id'] for x in rows if x['document_id'] not in ids)})")
    # hedef: kaynak oranında n doküman (en büyük küsurat yöntemi); mevcut satırlar hedeften düşülür
    by = defaultdict(list)
    for d in docs:
        by[d["source"]].append(d)
    exact = {k: n * len(v) / len(docs) for k, v in by.items()}
    want = {k: int(v) for k, v in exact.items()}
    for k in sorted(exact, key=lambda k: -(exact[k] - want[k]))[: n - sum(want.values())]:
        want[k] += 1
    have = defaultdict(int)
    for x in kept:
        have[x["source"]] += 1
    r = rng(16)
    in_sample = {x["document_id"] for x in kept}
    new = []
    for k in sorted(by):
        pool = sorted((d for d in by[k] if d["document_id"] not in in_sample), key=lambda d: d["document_id"])
        r.shuffle(pool)
        new += pool[: max(0, want[k] - have[k])]
    blank = {c: "" for c in cols}
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(kept)
        for d in new:
            w.writerow({**blank, "document_id": d["document_id"], "source": d["source"], "language": d["language"],
                        "subtopic": d["subtopic"], "document_type": d["document_type"],
                        "publication_year": d["publication_year"], "title": d["title"], "url": d["url"],
                        "token_count": d["token_count"], "metin_ilk_1500": d["text"][:1500]})
    log.info(f"corpus_review.csv: {len(kept)} incelenmiş + {len(new)} yeni satır; hedef {dict(want)}; "
             f"yeni: {[d['document_id'] for d in new]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", choices=["corpus", "instruction"], default=None)
    ap.add_argument("--corpus-topup", action="store_true",
                    help="corpus örneklemini yeni corpus sürümüne uyarla ve qc.corpus_sample'a tamamla")
    a = ap.parse_args()
    q = CFG["qc"]
    docs = []
    for s in ("train", "validation", "test"):
        docs += list(read_jsonl(p("final") / f"{s}.jsonl"))
    if a.corpus_topup:
        corpus_topup(docs, q["corpus_sample"])
        return

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
        ins = list(read_jsonl(instruction_file())) if instruction_file().exists() else []
        if not ins:
            log.warning(f"{instruction_file().name} yok; instruction örneklemi atlandı")
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
            w.writerow(["id", "raw_example_id", "task_type", "level", "source_document", "source_url", "kaynak_metin", "talimat",
                        "cevap", "destekleyen_alinti"] + [f"claude_{c}" for c in INS_CRIT] + CLAUDE_TAIL + HUMAN)
            for x in sample:
                src = doc_text.get(x["source_document"]) or se_text.get(x["source_document"]) or "(kaynak yok)"
                w.writerow([x["id"], x["raw_example_id"], x["task_type"], x["level"], x["source_document"], x["source_url"], src[: CFG["instruction"]["source_doc_max_chars"]],
                            x["instruction"], x["response"], x.get("supporting_evidence")]
                           + [""] * (len(INS_CRIT) + len(CLAUDE_TAIL) + len(HUMAN)))
        log.info(f"instruction_review.csv: {len(sample)} örnek")


if __name__ == "__main__":
    main()
