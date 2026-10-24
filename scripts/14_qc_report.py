"""14 — Kalite kontrol raporu (Vize Rehberi §12) -> reports/quality_control_report.md + reports/qc_summary.json

A) Otomatik kontroller (her çalıştırmada veriden hesaplanır)
B) Rastgele örneklem incelemesi (reports/qc/*_review.csv):
   - claude_* sütunları  : yapay zekâ destekli ön inceleme (Claude) -> ölçüt bazında oranlar
   - son_karar sütunu    : grup üyesinin nihai kararı -> nihai başarı oranı ve hata türleri
   - ikisinin uyuşma oranı
   Instruction örneklerinde nihai kararı 'sorunlu' olanlar setten ÇIKARILIR (removed_instructions.csv, stage=qc).
   İnsan kararı henüz yoksa Claude'un 'sorunlu' dedikleri ihtiyaten çıkarılır ve bu durum raporda belirtilir.
"""
from __future__ import annotations

import csv
import importlib
import json
import re
from collections import Counter

from common import CFG, RemovalLog, get_logger, p, read_jsonl, write_jsonl

log = get_logger("14_qc_report")
R = p("reports")
CORPUS_CRIT = ["okunabilir", "dogru_domain", "extraction_dogru", "header_footer_temiz", "bozuk_karakter_yok",
               "metadata_dogru"]
INS_CRIT = ["talimat_anlasilir", "kaynakla_tutarli", "talimati_karsiliyor", "gorev_turu_dogru", "turkce_akici"]
OK = {"1", "evet", "e", "true", "uygun", "x", "✓", "yes"}
BAD = {"0", "hayir", "hayır", "h", "false", "sorunlu", "no"}


def pct(a, b) -> str:
    return f"%{100 * a / b:.1f}".replace(".", ",") if b else "-"


def norm(v) -> str | None:
    v = (v or "").strip().lower()
    return "ok" if v in OK else "bad" if v in BAD else None


def is_approval(r: dict) -> bool:
    return (r.get("insan_notu") or "").strip().lower().startswith("onay")


def read_csv(path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def review_section(rows: list[dict], crit: list[str], title: str) -> tuple[list[str], dict]:
    pre = [r for r in rows if norm(r.get("claude_karar"))]
    hum = [r for r in rows if norm(r.get("son_karar"))]
    md = [f"### {title}", "", f"Örneklem: **{len(rows)}** · Claude ön incelemesi yapılan: {len(pre)} · "
                              f"grup üyesi nihai kararı verilen: **{len(hum)}**", ""]
    summ = {"sample": len(rows), "pre_reviewed": len(pre), "human_reviewed": len(hum)}
    if pre:
        md += ["**Ölçüt bazında sonuçlar (yapay zekâ destekli ön inceleme, Claude):**", "",
               "| Kontrol | Başarılı | Oran |", "| --- | --- | --- |"]
        for c in crit:
            ok = sum(1 for r in pre if norm(r.get(f"claude_{c}")) == "ok")
            md.append(f"| {c} | {ok}/{len(pre)} | {pct(ok, len(pre))} |")
            summ[f"pre_{c}"] = round(ok / len(pre), 4)
        pre_ok = sum(1 for r in pre if norm(r["claude_karar"]) == "ok")
        md += [f"| **Ön incelemede uygun** | {pre_ok}/{len(pre)} | **{pct(pre_ok, len(pre))}** |", ""]
        summ["pre_pass_rate"] = round(pre_ok / len(pre), 4)
    if hum:
        h_ok = sum(1 for r in hum if norm(r["son_karar"]) == "ok")
        md += ["**Nihai karar (grup üyesi):**", "", "| Sonuç | Adet | Oran |", "| --- | --- | --- |",
               f"| Uygun | {h_ok} | {pct(h_ok, len(hum))} |",
               f"| Sorunlu | {len(hum) - h_ok} | {pct(len(hum) - h_ok, len(hum))} |", ""]
        summ["human_pass_rate"] = round(h_ok / len(hum), 4)
        # insan_notu "onay" ile başlıyorsa: nihai karar, grup üyesinin ön inceleme kararını onaylamasıdır
        appr = sum(1 for r in hum if is_approval(r))
        summ["human_approved_pre"] = appr
        if appr:
            md += [f"Nihai kararların {appr}/{len(hum)}'i grup üyesinin ön inceleme kararlarını onaylamasıyla "
                   "verilmiştir.", ""]
        both = [r for r in hum if norm(r.get("claude_karar")) and not is_approval(r)]
        if both:  # yalnız ayrı verilmiş kararlar için anlamlı
            agree = sum(1 for r in both if norm(r["claude_karar"]) == norm(r["son_karar"]))
            md += [f"Claude ön incelemesi ile nihai kararın uyuşma oranı: **{agree}/{len(both)} ({pct(agree, len(both))})**", ""]
            summ["agreement"] = round(agree / len(both), 4)
    errs = Counter()
    for r in rows:
        dec = norm(r.get("son_karar")) or norm(r.get("claude_karar"))
        if dec == "bad":
            tag = (r.get("son_hata_turu") or r.get("claude_hata_turu") or "belirtilmedi").strip()
            for t in re.split(r"[;,]", tag):
                if t.strip():
                    errs[t.strip()] += 1
    if errs:
        md += ["**Hata türleri** (nihai karar, yoksa ön inceleme):", "", "| Hata türü | Adet | Örneklemdeki oranı |",
               "| --- | --- | --- |"]
        md += [f"| {k} | {v} | {pct(v, len(rows))} |" for k, v in errs.most_common()] + [""]
        summ["error_types"] = dict(errs)
    if not pre and not hum:
        md += ["*Henüz inceleme yapılmadı.*", ""]
    return md, summ


def main() -> None:
    docs = []
    for s in ("train", "validation", "test"):
        docs += list(read_jsonl(p("final") / f"{s}.jsonl"))
    ins = list(read_jsonl(p("final") / "instruction_v1.0.jsonl"))
    summary: dict = {}
    fp = CFG["filtering"]["min_chars"]
    ids = [d["document_id"] for d in docs]
    grp_clash = len({(d["group_key"], d["split"]) for d in docs}) - len({d["group_key"] for d in docs})
    auto_c = {
        "Doküman sayısı": len(docs),
        "Boş metin": sum(1 for d in docs if not d["text"].strip()),
        f"{fp} karakterden kısa": sum(1 for d in docs if len(d["text"]) < fp),
        "Benzersiz document_id": "evet" if len(ids) == len(set(ids)) else "HAYIR",
        "Kaynak / URL / lisans eksik": sum(1 for d in docs if not (d.get("source") and d.get("url") and d.get("license"))),
        "Dil en/tr dışında": sum(1 for d in docs if d["language"] not in ("en", "tr")),
        "Bozuk karakter (U+FFFD) içeren": sum(1 for d in docs if "�" in d["text"]),
        "token_count eksik": sum(1 for d in docs if not d.get("token_count")),
        "Aynı grup birden fazla kümede": grp_clash,
    }
    md = ["# Kalite Kontrol Raporu", "", "Bu rapor `scripts/14_qc_report.py` tarafından üretilir.", "",
          "## A. Otomatik kontroller — Domain Corpus v1.0", "", "| Kontrol | Sonuç |", "| --- | --- |"]
    md += [f"| {k} | {v} |" for k, v in auto_c.items()] + [""]
    summary["corpus_auto"] = auto_c

    removed_ins = read_csv(R / "removed_instructions.csv")
    vsum = json.loads((R / "instruction_verification_summary.json").read_text(encoding="utf-8")) \
        if (R / "instruction_verification_summary.json").exists() else {}
    if ins:
        v11 = importlib.import_module("11_verify_instructions")
        mcq = [x for x in ins if x["task_type"] == "coktan_secmeli_soru_uretimi"]
        own = {}
        clash = 0
        for x in ins:
            if own.setdefault(x["source_document"], x["split"]) != x["split"]:
                clash += 1
        auto_i = {
            "Örnek sayısı": len(ins),
            "Benzersiz id": "evet" if len({x["id"] for x in ins}) == len(ins) else "HAYIR",
            "messages biçimi hatalı": sum(1 for x in ins if not (len(x["messages"]) == 2
                                                               and [m["role"] for m in x["messages"]] == ["user", "assistant"]
                                                               and all(m["content"].strip() for m in x["messages"]))),
            "Kaynak bilgisi eksik": sum(1 for x in ins if not x.get("source_document")),
            "Çoktan seçmeli JSON geçerli": f"{sum(1 for x in mcq if v11.check_mcq(x['response']) is None)}/{len(mcq)}",
            "Aynı kaynak doküman birden fazla kümede": clash,
            "LLM yargıç örneklemi (örnek)": vsum.get("judged_examples"),
            "LLM yargıç başarısızlık oranı (tahmini hata oranı)": pct(vsum.get("judge_fail", 0), vsum.get("judged_examples") or 0),
        }
        md += ["## A. Otomatik kontroller — Instruction Dataset v1.0", "", "| Kontrol | Sonuç |", "| --- | --- |"]
        md += [f"| {k} | {v} |" for k, v in auto_i.items()] + [""]
        reasons = Counter(r["reason"].split(":")[0] for r in removed_ins if r["stage"] in ("verify", "qc"))
        md += ["Doğrulama ve kalite kontrolünde elenme nedenleri:", "", "| Neden | Adet |", "| --- | --- |"]
        md += [f"| {k} | {v} |" for k, v in reasons.most_common()] + [""]
        if vsum.get("judge_fail_by_criterion"):
            md += ["LLM yargıcın başarısız bulduğu ölçütler: " + ", ".join(
                f"{k}={v}" for k, v in vsum["judge_fail_by_criterion"].items()), ""]
        summary["instruction_auto"] = auto_i

    md += ["## B. Rastgele örneklem incelemesi", "",
           "İnceleme iki aşamalıdır: (1) yapay zekâ destekli ön inceleme (Claude; örneği üreten Gemini'den farklı bir "
           "model), her örneği kaynak metniyle karşılaştırıp ölçüt bazında karar ve gerekçe yazar; (2) grup üyesi "
           "ön incelemeyi gözden geçirip nihai kararı verir. İki aşama ayrı raporlanır.", ""]
    crow = read_csv(p("qc") / "corpus_review.csv")
    sec, s_c = review_section(crow, CORPUS_CRIT, "Domain Corpus")
    md += sec
    summary["corpus_review"] = s_c
    irow = read_csv(p("qc") / "instruction_review.csv")
    sec, s_i = review_section(irow, INS_CRIT, "Instruction Dataset")
    md += sec
    summary["instruction_review"] = s_i

    # nihai kararı (yoksa ön incelemesi) 'sorunlu' olan instruction örneklerini çıkar
    if ins and irow:
        # Eşleştirme raw_example_id ile yapılır: INS_ numaraları doğrulanmış küme değişince (yargıç, yeni örnek)
        # kayabilir, raw_example_id kaymaz. Eski tablolarda bu sütun yoksa id -> raw_example_id eşlemesi kullanılır.
        id2raw = {x["id"]: x["raw_example_id"] for x in ins}

        def rkey(r):
            return (r.get("raw_example_id") or "").strip() or id2raw.get(r["id"], r["id"])

        drop = {}
        for r in irow:
            dec = norm(r.get("son_karar"))
            src = "insan"
            if dec is None:
                dec, src = norm(r.get("claude_karar")), "claude_on_inceleme"
            if dec == "bad":
                drop[rkey(r)] = (src, r.get("son_hata_turu") or r.get("claude_hata_turu") or "")
        reviewed = {rkey(r): r for r in irow}
        rm = RemovalLog(R / "removed_instructions.csv", "qc", reset=False)
        kept = []
        for x in ins:
            r = reviewed.get(x["raw_example_id"])
            if r is not None:
                h = norm(r.get("son_karar"))
                x["human_verified"] = None if h is None else (h == "ok")
                x["verified_by"] = "kural+kanit+claude_on_inceleme" + ("+insan_karari" if h else "")
            if x["raw_example_id"] in drop:
                continue
            kept.append(x)
        # Çıkarılanların raw_example_id'leri kalıcı listeye eklenir: 12 yeniden çalışsa da geri gelmezler
        excl_f = p("interim") / "qc_excluded_raw_ids.json"
        excl = set(json.loads(excl_f.read_text(encoding="utf-8"))) if excl_f.exists() else set()
        excl |= set(drop)
        excl_f.write_text(json.dumps(sorted(excl), indent=0), encoding="utf-8")
        # 14 tekrar çalıştırılsa da (çıkarılan örnek artık sette olmasa da) kayıt eksiksiz kalır
        for i, (src, tag) in sorted(drop.items()):
            rm.add(i, f"qc_fail({src})", "", tag)
        rm.save()
        if len(kept) != len(ins) or any(x["raw_example_id"] in reviewed for x in ins):
            write_jsonl(p("final") / "instruction_v1.0.jsonl", kept)
            for s in ("train", "validation", "test"):
                write_jsonl(p("final") / "instruction" / f"{s}.jsonl", [x for x in kept if x["split"] == s])
        md += [f"Örneklem incelemesinde sorunlu bulunan **{len(drop)}** instruction örneği setten çıkarıldı "
               f"(kalan: {len(kept)}).", ""]
        summary["instruction_removed_in_qc"] = len(drop)
        summary["instruction_final_count"] = len(kept)

    nd = read_csv(p("qc") / "near_dup_pairs_review.csv")
    thr = CFG["dedup"]["jaccard_threshold"]
    nd_md = []
    for col, label, key in (("claude_tekrar_mi", "yapay zekâ destekli ön inceleme (Claude)", "pre"),
                            ("son_karar_tekrar_mi", "grup üyesinin nihai kararı", "human")):
        pr = [r for r in nd if norm(r.get(col))]
        if not pr:
            continue
        if key == "human" and all(is_approval(r) for r in pr):
            label = "nihai karar (grup üyesi onayı)"
            summary["near_dup_human_is_approval"] = True
        agree = sum(1 for r in pr if (r["above_threshold"] == "True") == (norm(r[col]) == "ok"))
        fp = sum(1 for r in pr if r["above_threshold"] == "True" and norm(r[col]) == "bad")
        fn = sum(1 for r in pr if r["above_threshold"] != "True" and norm(r[col]) == "ok")
        nd_md.append(f"| {label} | {len(pr)} | {agree}/{len(pr)} ({pct(agree, len(pr))}) | {fp} | {fn} |")
        summary[f"near_dup_threshold_agreement_{key}"] = round(agree / len(pr), 4)
        summary[f"near_dup_{key}"] = {"pairs": len(pr), "above": sum(1 for r in pr if r["above_threshold"] == "True"),
                                      "below": sum(1 for r in pr if r["above_threshold"] != "True"),
                                      "false_removals": fp, "missed": fn}
    if nd_md:
        md += ["### Near-duplicate eşiğinin doğrulanması", "",
               f"{len(nd)} aday çift (yarısı Jaccard ≥ {thr}, yarısı altı) incelendi. 'Eşik hatalı eledi' = eşik "
               f"üstü ama gerçekte tekrar değil; 'eşik kaçırdı' = eşik altı ama gerçekte tekrar.", "",
               "| İnceleme | Çift | Eşikle uyum | Eşik hatalı eledi | Eşik kaçırdı |", "| --- | --- | --- | --- | --- |",
               *nd_md, ""]
    (R / "quality_control_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (R / "qc_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log.info(f"quality_control_report.md yazıldı (corpus inceleme={len(crow)}, instruction inceleme={len(irow)})")


if __name__ == "__main__":
    main()
