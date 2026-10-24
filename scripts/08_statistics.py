"""08 — Corpus istatistik raporu (Vize Rehberi §12).

Tüm aşama özetlerini (extraction, filter, dedup, split, token) birleştirip
reports/statistics.md ve reports/figures/*.png üretir. Rapor tablosu = grafiklerin tablo görünümü.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict

from common import CFG, get_logger, p, read_jsonl

log = get_logger("08_statistics")
R = p("reports")
FIG = R / "figures"
FIG.mkdir(exist_ok=True)

SURFACE, INK, INK2, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"


def j(name: str) -> dict:
    f = R / name
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def fmt(n) -> str:
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else str(n)


def pct(a, b) -> str:
    return f"%{100 * a / b:.1f}".replace(".", ",") if b else "-"


def hbar(labels: list[str], values: list[float], title: str, fname: str, xlabel: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 0.42 * len(labels) + 1.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=SERIES, height=0.6, edgecolor=SURFACE, linewidth=2)
    vmax = max(values) if values else 1
    for yi, v in zip(y, values):
        ax.text(v + vmax * 0.01, yi, fmt(int(v)) if float(v).is_integer() else f"{v:.1f}", va="center",
                fontsize=8, color=INK2)
    ax.set_yticks(list(y), labels, fontsize=8, color=INK)
    ax.set_xlabel(xlabel, fontsize=8, color=INK2)
    ax.set_title(title, fontsize=10, color=INK, loc="left")
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.set_xlim(0, vmax * 1.15)
    fig.tight_layout()
    fig.savefig(FIG / fname, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    ext, flt, ded, tok = j("extraction_summary.json"), j("filter_summary.json"), j("dedup_summary.json"), j("token_stats.json")
    d2 = j("dedup2_summary.json") if (R / "dedup2_summary.json").exists() else {}
    docs = []
    for s in ("train", "validation", "test"):
        docs += list(read_jsonl(p("final") / f"{s}.jsonl"))
    removed = []
    for f in ("extraction_failures.csv", "removed_documents.csv"):
        if (R / f).exists():
            with open(R / f, encoding="utf-8") as fh:
                removed += list(csv.DictReader(fh))
    reasons = Counter(r["reason"] for r in removed)

    n_download_err = reasons.get("download_error", 0)
    n_raw = ext["total"]["raw"] + n_download_err + reasons.get("non_content_section", 0)
    n_ext_ok = ext["total"]["ok"]
    n_ext_fail = ext["total"]["failed"] + n_download_err + reasons.get("non_content_section", 0)
    n_filtered = flt["kept"]
    words = sum(d["word_count"] for d in docs)
    tokens = sum(d["token_count"] for d in docs)
    lang_tok = Counter()
    for d in docs:
        lang_tok[d["language"]] += d["token_count"]
    src_names = sorted({d["source"] for d in docs})

    md = [f"# Domain Corpus v{CFG['project']['corpus_version']} — İstatistik Raporu", "",
          "Bu rapor `scripts/08_statistics.py` tarafından üretilir; elle düzenlenmez.", "",
          "## 1. Sayısal özet", "", "| Özellik | Değer |", "| --- | --- |",
          f"| Veri kaynağı sayısı (corpus) | {len(src_names)} |",
          f"| Ham doküman | {fmt(n_raw)} |",
          f"| Extraction başarılı | {fmt(n_ext_ok)} |",
          f"| Extraction başarısız (indirme hatası + boş/kısa çıktı + içerik dışı PDF bölümü) | {fmt(n_ext_fail)} |",
          f"| Filtering sonrası | {fmt(n_filtered)} |",
          f"| Exact duplicate | {fmt(ded.get('exact_duplicates', 0))} |",
          f"| Near duplicate (Jaccard ≥ {ded.get('threshold')}) | {fmt(ded.get('near_duplicates', 0))} |",
          f"| Yeniden yayın tekrarı (06b; APOD ve NASA Science, kimlik ve kümeler korunarak) | "
          f"{fmt(d2.get('repost_removed', 0))} |",
          f"| İletişim dizini sayfası / temizlik sonrası çok kısa (06b) | "
          f"{fmt(sum(d2.get('other_removed', {}).values()))} |",
          f"| Final doküman | {fmt(len(docs))} |",
          f"| Toplam kelime | {fmt(words)} |",
          f"| Toplam token ({tok.get('tokenizer')}) | {fmt(tokens)} |",
          f"| İngilizce içerik (token) | {pct(lang_tok.get('en', 0), tokens)} |",
          f"| Türkçe içerik (token) | {pct(lang_tok.get('tr', 0), tokens)} |", ""]

    md += ["## 2. Verinin aşamalar boyunca erimesi", "",
           f"{fmt(n_raw)} ham doküman → extraction sonrası {fmt(n_ext_ok)} → temizleme ve filtreleme sonrası "
           f"{fmt(n_filtered)} → tekrar ayıklama sonrası **{fmt(len(docs))}** doküman.", "",
           "![Veri erimesi](figures/funnel.png)", ""]
    hbar(["Ham", "Extraction sonrası", "Filtreleme sonrası", "Tekrar ayıklama sonrası (final)"],
         [n_raw, n_ext_ok, n_filtered, len(docs)], "Aşama başına doküman sayısı", "funnel.png", "doküman")

    md += ["## 3. Çıkarılma nedenleri", "", "| Çıkarma nedeni | Doküman | Aşama |", "| --- | --- | --- |"]
    stage_of = {}
    for r in removed:
        stage_of[r["reason"]] = r["stage"]
    for reason, n in reasons.most_common():
        md.append(f"| {reason} | {fmt(n)} | {stage_of[reason]} |")
    md += ["", "Ayrıntılı liste: `reports/extraction_failures.csv`, `reports/removed_documents.csv`.", ""]

    # kaynak tablosu
    by_src = defaultdict(lambda: Counter())
    for d in docs:
        c = by_src[d["source"]]
        c["docs"] += 1
        c["words"] += d["word_count"]
        c["tokens"] += d["token_count"]
    md += ["## 4. Kaynak dağılımı (final)", "", "| Kaynak | Dil | Doküman | Kelime | Token | Token payı |",
           "| --- | --- | --- | --- | --- | --- |"]
    for s, c in sorted(by_src.items(), key=lambda kv: -kv[1]["tokens"]):
        lang = Counter(d["language"] for d in docs if d["source"] == s).most_common(1)[0][0]
        md.append(f"| {s} | {lang} | {fmt(c['docs'])} | {fmt(c['words'])} | {fmt(c['tokens'])} | {pct(c['tokens'], tokens)} |")
    top_doc_share = max(c["docs"] for c in by_src.values()) / len(docs)
    md += ["", f"En büyük kaynağın doküman payı: {pct(max(c['docs'] for c in by_src.values()), len(docs))} "
               f"({'tek kaynak baskın değil' if top_doc_share < 0.5 else 'dengesizlik var, kartta gerekçelendirildi'}).",
           "", "![Kaynak dağılımı](figures/sources.png)", ""]
    srt = sorted(by_src.items(), key=lambda kv: -kv[1]["tokens"])
    hbar([s for s, _ in srt], [c["tokens"] / 1e6 for _, c in srt], "Kaynak başına token (milyon)", "sources.png",
         "milyon token")

    # alt konu
    sub = Counter(d["subtopic"] for d in docs)
    sub_tok = Counter()
    for d in docs:
        sub_tok[d["subtopic"]] += d["token_count"]
    md += ["## 5. Alt konu dağılımı", "", "| Alt konu | Doküman | Doküman payı | Token payı |", "| --- | --- | --- | --- |"]
    for s, n in sub.most_common():
        md.append(f"| {s} | {fmt(n)} | {pct(n, len(docs))} | {pct(sub_tok[s], tokens)} |")
    md += ["", "![Alt konular](figures/subtopics.png)", ""]
    hbar([s for s, _ in sub.most_common()], [n for _, n in sub.most_common()], "Alt konu başına doküman",
         "subtopics.png", "doküman")

    # dil, tür, yıl
    lang_docs = Counter(d["language"] for d in docs)
    md += ["## 6. Dil dağılımı", "", "| Dil | Doküman | Doküman payı | Token payı |", "| --- | --- | --- | --- |"]
    for l, n in lang_docs.most_common():
        md.append(f"| {l} | {fmt(n)} | {pct(n, len(docs))} | {pct(lang_tok[l], tokens)} |")
    dt = Counter(d["document_type"] for d in docs)
    md += ["", "## 7. Doküman türleri", "", "| Tür | Doküman |", "| --- | --- |"]
    md += [f"| {t} | {fmt(n)} |" for t, n in dt.most_common()]

    # token dağılımı
    td = tok.get("documents", {})
    md += ["", "## 8. Token uzunluk dağılımı (doküman başına)", "",
           "| Küme | Doküman | Toplam token | Min | Medyan | Ortalama | p95 | Maks |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, st in [("Tümü", td), *tok.get("per_split", {}).items()]:
        md.append(f"| {name} | {fmt(st['count'])} | {fmt(st['total'])} | {fmt(st['min'])} | {fmt(st['median'])} | "
                  f"{st['mean']} | {fmt(st['p95'])} | {fmt(st['max'])} |")
    md += ["", "| Kaynak | Min | Medyan | Ortalama | p95 | Maks |", "| --- | --- | --- | --- | --- | --- |"]
    for s, st in tok.get("per_source", {}).items():
        md.append(f"| {s} | {fmt(st['min'])} | {fmt(st['median'])} | {st['mean']} | {fmt(st['p95'])} | {fmt(st['max'])} |")
    ch = tok.get("chunks", {})
    if ch:
        md += ["", f"Chunk'lar (en fazla {ch['max_tokens']} token, paragraf/başlık sınırında): {fmt(ch['count'])} chunk, "
                   f"medyan {fmt(ch['median'])}, p95 {fmt(ch['p95'])} token."]
    buckets = [(0, 256), (256, 512), (512, 1024), (1024, 2048), (2048, 4096), (4096, 8192), (8192, 16384),
               (16384, 10 ** 9)]
    lab = ["<256", "256–511", "512–1023", "1024–2047", "2048–4095", "4096–8191", "8192–16383", "≥16384"]
    cnt = [sum(1 for d in docs if a <= d["token_count"] < b) for a, b in buckets]
    md += ["", "![Token dağılımı](figures/token_length.png)", ""]
    hbar(lab, cnt, "Doküman uzunluğu (token aralığı)", "token_length.png", "doküman")

    # split
    sp = Counter(d["split"] for d in docs)
    md += ["## 9. Veri ayrımı (doküman düzeyinde)", "", "| Küme | Doküman | Oran |", "| --- | --- | --- |"]
    md += [f"| {s} | {fmt(sp[s])} | {pct(sp[s], len(docs))} |" for s in ("train", "validation", "test")]
    md += ["", f"Seed {CFG['project']['random_seed']}; kaynak bazında tabakalı; Wikipedia EN/TR aynı madde (Wikidata QID) "
               "aynı kümede. Kümeler arası grup çakışması: 0 (`scripts/validate_datasets.py`).", ""]

    # yayın yılı
    yrs = Counter(d["publication_year"] for d in docs if d.get("publication_year"))
    md += ["## 10. Yayın / son düzenleme yılı", "", "| Yıl aralığı | Doküman |", "| --- | --- |"]
    for a, b in [(1990, 2004), (2005, 2014), (2015, 2019), (2020, 2023), (2024, 2026)]:
        md.append(f"| {a}–{b} | {fmt(sum(n for y, n in yrs.items() if a <= y <= b))} |")
    md.append(f"| bilinmiyor | {fmt(sum(1 for d in docs if not d.get('publication_year')))} |")

    (R / "statistics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (R / "statistics_summary.json").write_text(json.dumps({
        "sources": len(src_names), "raw": n_raw, "extraction_ok": n_ext_ok, "extraction_failed": n_ext_fail,
        "after_filter": n_filtered, "exact_dup": ded.get("exact_duplicates"), "near_dup": ded.get("near_duplicates"), "repost_dup": d2.get("repost_removed", 0),
        "final_docs": len(docs), "words": words, "tokens": tokens, "lang_token_share": dict(lang_tok),
        "removed_by_reason": dict(reasons), "subtopics": dict(sub), "splits": dict(sp)}, indent=2), encoding="utf-8")
    # 06'nın yazdığı split özeti 06b'den önceki sayıları taşır; final kümelerle yeniden yazılır
    (R / "split_summary.json").write_text(json.dumps(
        {s: {"documents": sum(1 for d in docs if d["split"] == s),
             "by_source": dict(Counter(d["source"] for d in docs if d["split"] == s))}
         for s in ("train", "validation", "test")} | {"note": "final kümeler (06b sonrası, 08 tarafından)"},
        indent=2), encoding="utf-8")
    log.info(f"statistics.md yazıldı: {len(docs)} doküman, {tokens:,} token")


if __name__ == "__main__":
    main()
