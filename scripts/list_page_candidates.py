"""Liste/haber sayfası adayları inceleme tablosu (Corpus v2.0, 09.11.2026).

v1.0 kartında "bilgi taşımayan liste/galeri sayfaları bir sonraki sürümde çıkarılacak" denmişti. Otomatik eşik tek
başına güvenilir değil: cümle oranı düşük sayfaların bir kısmı çöp (haber başlığı listeleri, eğitim standartları
tabloları, etkinlik takvimleri), bir kısmı ise değerli tablolar (uydu verileri, görev listeleri). Bu yüzden adaylar
tabloya çıkarılır, her biri için yapay zekâ destekli ön karar ve gerekçe yazılır, son kararı grup üyesi verir.
06b_repost_dedup.py yalnız son_karar = "cikar" olan dokümanları çıkarır (neden: list_page_06b).

Cümle oranı = noktalı cümle içeren satırlardaki kelimelerin, başlık dışı tüm kelimelere oranı.
Kaynak: yalnız NASA Science ve APOD (Wikipedia'da düşük oranlı sayfalar formül ağırlıklı maddeler, değerli).

Kullanım: python scripts/list_page_candidates.py   (dolu kararlar korunur; yeni aday yalnız eklenir)
"""
from __future__ import annotations

import csv
import re

from common import CFG, ROOT, get_logger, p, read_jsonl

log = get_logger("list_page_candidates")
COLS = ["document_id", "source", "title", "url", "char_count", "cumle_orani", "metin_ilk_800",
        "claude_karar", "claude_gerekce", "son_karar", "insan_notu"]


def sentence_ratio(text: str) -> float:
    body = [x for x in text.split("\n") if x.strip() and not x.startswith("#")]
    words = sum(len(x.split()) for x in body) or 1
    sent = sum(len(x.split()) for x in body
               if re.search(r"[.!?][\"”’)]?\s*$", x.strip()) or re.search(r"[a-z][.!?] [A-Z]", x))
    return sent / words


def main() -> None:
    thr = CFG["corpus"]["list_page_candidate_ratio"]
    out = ROOT / CFG["corpus"]["list_page_review_file"]
    prev = {}
    if out.exists():
        with open(out, encoding="utf-8-sig") as f:
            prev = {r["document_id"]: r for r in csv.DictReader(f)}
    rows = []
    for s in ("train", "validation", "test"):
        for d in read_jsonl(p("final") / f"{s}.jsonl"):
            if d["source"] not in ("nasa_science", "nasa_apod"):
                continue
            r = sentence_ratio(d["text"])
            if r < thr or d["document_id"] in prev:
                old = prev.get(d["document_id"], {})
                rows.append({"document_id": d["document_id"], "source": d["source"], "title": d["title"],
                             "url": d["url"], "char_count": d["char_count"], "cumle_orani": f"{r:.2f}",
                             "metin_ilk_800": d["text"][:800],
                             **{c: old.get(c, "") for c in ("claude_karar", "claude_gerekce", "son_karar", "insan_notu")}})
    rows.sort(key=lambda x: (float(x["cumle_orani"]), x["document_id"]))
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    log.info(f"{out.name}: {len(rows)} aday (cümle oranı < {thr}); önceki kararlar korundu ({len(prev)})")


if __name__ == "__main__":
    main()
