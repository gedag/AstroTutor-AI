"""14 — Kalite kontrol raporu (Vize Rehberi §12) -> reports/quality_control_report.md

A) Otomatik kontroller (her çalıştırmada veriden hesaplanır)
B) Manuel inceleme sonuçları: reports/qc/*_review.csv doldurulduysa oranlar ve hata türleri hesaplanır.
   Instruction incelemesinde 'kaynakla_tutarli' veya 'talimati_karsiliyor' = 0 olan örnekler setten ÇIKARILIR
   (reports/removed_instructions.csv, stage=human) ve incelenen örneklere human_verified=true/false yazılır.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter

from common import CFG, RemovalLog, get_logger, p, read_jsonl, write_jsonl

log = get_logger("14_qc_report")
R = p("reports")
CORPUS_COLS = ["okunabilir", "dogru_domain", "extraction_dogru", "header_footer_temiz", "bozuk_karakter_yok",
               "metadata_dogru"]
INS_COLS = ["talimat_anlasilir", "kaynakla_tutarli", "talimati_karsiliyor", "gorev_turu_dogru", "turkce_akici"]
TRUE = {"1", "evet", "e", "true", "x", "✓", "yes"}
FALSE = {"0", "hayir", "hayır", "h", "false", "no"}


def pct(a, b) -> str:
    return f"%{100 * a / b:.1f}".replace(".", ",") if b else "-"


def read_review(path, cols):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if all((r.get(c) or "").strip().lower() in TRUE | FALSE for c in cols)]


def review_table(rows, cols, title) -> list[str]:
    md = [f"### {title}", "", f"Değerlendirilen örnek: **{len(rows)}**", "", "| Kontrol | Başarılı | Oran |",
          "| --- | --- | --- |"]
    for c in cols:
        ok = sum(1 for r in rows if r[c].strip().lower() in TRUE)
        md.append(f"| {c} | {ok}/{len(rows)} | {pct(ok, len(rows))} |")
    allok = sum(1 for r in rows if all(r[c].strip().lower() in TRUE for c in cols))
    md += [f"| **Tüm kontrollerden geçen** | {allok}/{len(rows)} | **{pct(allok, len(rows))}** |", ""]
    err = Counter(t.strip() for r in rows for t in re.split(r"[;,]", r.get("hata_turu") or "") if t.strip())
    if err:
        md += ["Hata türleri:", "", "| Hata türü | Adet | Oran |", "| --- | --- | --- |"]
        md += [f"| {k} | {v} | {pct(v, len(rows))} |" for k, v in err.most_common()]
        md.append("")
    return md


def main() -> None:
    docs = []
    for s in ("train", "validation", "test"):
        docs += list(read_jsonl(p("final") / f"{s}.jsonl"))
    ins = list(read_jsonl(p("final") / "instruction_v1.0.jsonl"))
    md = ["# Kalite Kontrol Raporu", "", "Bu rapor `scripts/14_qc_report.py` tarafından üretilir.", "",
          "## A. Otomatik kontroller — Domain Corpus", "", "| Kontrol | Sonuç |", "| --- | --- |"]
    ids = [d["document_id"] for d in docs]
    md += [f"| Doküman sayısı | {len(docs)} |",
           f"| Boş metin | {sum(1 for d in docs if not d['text'].strip())} |",
           f"| {CFG['filtering']['min_chars']} karakterden kısa | {sum(1 for d in docs if len(d['text']) < CFG['filtering']['min_chars'])} |",
           f"| Benzersiz document_id | {'evet' if len(ids) == len(set(ids)) else 'HAYIR'} |",
           f"| Kaynak/URL/lisans eksik | {sum(1 for d in docs if not (d.get('source') and d.get('url') and d.get('license')))} |",
           f"| Dil en/tr dışında | {sum(1 for d in docs if d['language'] not in ('en', 'tr'))} |",
           f"| '\\ufffd' (bozuk karakter) içeren | {sum(1 for d in docs if chr(0xFFFD) in d['text'])} |",
           f"| Token sayısı eksik | {sum(1 for d in docs if not d.get('token_count'))} |",
           f"| Aynı grup birden fazla kümede | {len({d['group_key'] for d in docs}) - len({(d['group_key'], d['split']) for d in docs}) and 'VAR' or 0} |",
           ""]
    # ----- instruction otomatik
    removed_ins = []
    if (R / "removed_instructions.csv").exists():
        with open(R / "removed_instructions.csv", encoding="utf-8") as f:
            removed_ins = list(csv.DictReader(f))
    if ins:
        iid = [x["id"] for x in ins]
        bad_msgs = sum(1 for x in ins if not (len(x["messages"]) == 2 and x["messages"][0]["role"] == "user"
                                              and x["messages"][1]["role"] == "assistant"
                                              and all(m["content"].strip() for m in x["messages"])))
        mcq = [x for x in ins if x["task_type"] == "coktan_secmeli_soru_uretimi"]
        import importlib

        v11 = importlib.import_module("11_verify_instructions")
        mcq_ok = sum(1 for x in mcq if v11.check_mcq(x["response"]) is None)
        verify_rm = Counter(r["reason"].split(":")[0] for r in removed_ins if r["stage"] == "verify")
        judge_fail = sum(1 for r in removed_ins if r["stage"] == "verify" and r["reason"].startswith("judge_fail"))
        md += ["## A. Otomatik kontroller — Instruction Dataset", "", "| Kontrol | Sonuç |", "| --- | --- |",
               f"| Örnek sayısı | {len(ins)} |",
               f"| Benzersiz id | {'evet' if len(iid) == len(set(iid)) else 'HAYIR'} |",
               f"| messages biçimi hatalı | {bad_msgs} |",
               f"| Kaynak bilgisi eksik | {sum(1 for x in ins if not x.get('source_document'))} |",
               f"| Çoktan seçmeli JSON geçerli | {mcq_ok}/{len(mcq)} |",
               f"| Otomatik doğrulanmış (kural + LLM yargıç) | {sum(1 for x in ins if x['auto_verified'])}/{len(ins)} |",
               f"| LLM yargıç tarafından elenen | {judge_fail} |",
               f"| Aynı kaynak doküman birden fazla kümede | "
               f"{len({x['source_document'] for x in ins}) - len({(x['source_document'], x['split']) for x in ins}) and 'VAR' or 0} |",
               ""]
        md += ["Doğrulama aşamasında elenme nedenleri:", "", "| Neden | Adet |", "| --- | --- |"]
        md += [f"| {k} | {v} |" for k, v in verify_rm.most_common()]
        md.append("")

    # ----- manuel
    md += ["## B. Manuel inceleme", ""]
    crow = read_review(p("qc") / "corpus_review.csv", CORPUS_COLS)
    irow = read_review(p("qc") / "instruction_review.csv", INS_COLS)
    if crow:
        md += review_table(crow, CORPUS_COLS, "Domain Corpus (rastgele örneklem)")
        by_src = Counter(r["source"] for r in crow)
        ok_src = Counter(r["source"] for r in crow if all(r[c].strip().lower() in TRUE for c in CORPUS_COLS))
        md += ["Kaynak bazında tüm kontrollerden geçme oranı:", "", "| Kaynak | Oran |", "| --- | --- |"]
        md += [f"| {s} | {ok_src[s]}/{n} ({pct(ok_src[s], n)}) |" for s, n in by_src.most_common()] + [""]
    else:
        md += ["**Domain Corpus manuel incelemesi henüz doldurulmadı** — `reports/qc/corpus_review.csv` "
               "dosyasındaki kontrol sütunlarına 1/0 yazıp bu script'i tekrar çalıştırın.", ""]
    if irow:
        md += review_table(irow, INS_COLS, "Instruction Dataset (rastgele örneklem)")
        fail_ids = {r["id"]: r for r in irow if r["kaynakla_tutarli"].strip().lower() in FALSE
                    or r["talimati_karsiliyor"].strip().lower() in FALSE}
        reviewed = {r["id"] for r in irow}
        rm = RemovalLog(R / "removed_instructions.csv", "human", reset=False)
        kept = []
        for x in ins:
            if x["id"] in reviewed:
                x["human_verified"] = x["id"] not in fail_ids
                x["verified_by"] = "kural_kontrolleri+llm_yargic+manuel"
            if x["id"] in fail_ids:
                rm.add(x["id"], "human_fail", x["source_name"], fail_ids[x["id"]].get("hata_turu", ""))
                continue
            kept.append(x)
        rm.save()
        write_jsonl(p("final") / "instruction_v1.0.jsonl", kept)
        for s in ("train", "validation", "test"):
            write_jsonl(p("final") / "instruction" / f"{s}.jsonl", [x for x in kept if x["split"] == s])
        md += [f"Manuel incelemede kaynakla tutarsız veya talimatı karşılamayan **{len(fail_ids)}** örnek setten "
               f"çıkarıldı; kalan örnek: {len(kept)}.", ""]
    else:
        md += ["**Instruction manuel incelemesi henüz doldurulmadı** — `reports/qc/instruction_review.csv`.", ""]
    nd = R / "qc" / "near_dup_pairs_review.csv"
    if nd.exists():
        with open(nd, encoding="utf-8") as f:
            pr = [r for r in csv.DictReader(f) if (r.get("is_duplicate_human(evet/hayir)") or "").strip()]
        if pr:
            agree = sum(1 for r in pr if (r["above_threshold"] == "True") ==
                        (r["is_duplicate_human(evet/hayir)"].strip().lower() in TRUE))
            md += ["### Near-duplicate eşiği doğrulaması", "",
                   f"{len(pr)} aday çiftte insan kararı ile Jaccard ≥ {CFG['dedup']['jaccard_threshold']} eşiğinin "
                   f"uyumu: {agree}/{len(pr)} ({pct(agree, len(pr))}).", ""]
    (R / "quality_control_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log.info(f"quality_control_report.md yazıldı (manuel corpus={len(crow)}, manuel instruction={len(irow)})")


if __name__ == "__main__":
    main()
