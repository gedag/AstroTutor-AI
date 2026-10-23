"""04 — Kalite ve kapsam filtresi (Vize Rehberi §7, §12).

Sırasıyla uygulanan filtreler ve çıkarma etiketleri:
  too_short       : temizleme sonrası < filtering.min_chars karakter
  garbled         : bozuk karakter (�, mojibake, özel kullanım alanı) oranı > max_garbled_ratio
                    veya metnin yarısından fazlası rakam/simge (tablo artığı)
  wrong_language  : lingua ile tespit edilen dil allowed_languages dışında
  out_of_domain   : astronomi terim yoğunluğu < min_domain_score  veya astroloji işaretleri

Girdi : data/cleaned/*.jsonl      Çıktı : data/interim/filtered.jsonl
Elenenler: reports/removed_documents.csv (stage=filter)
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter

from common import CFG, RemovalLog, get_logger, p, read_jsonl, write_jsonl
from domain_lexicon import domain_score, off_topic_hits

log = get_logger("04_filter")
F = CFG["filtering"]
SOURCES = ["nasa_science", "nasa_apod", "openstax", "arxiv_astro_ph", "wikipedia_en", "wikipedia_tr"]
MOJIBAKE = re.compile(r"(Ã.|Ä.|Å.|â€|Â )")


def garbled_ratio(t: str) -> float:
    bad = t.count("�") + 2 * len(MOJIBAKE.findall(t))
    bad += sum(1 for ch in t if unicodedata.category(ch) in ("Co", "Cs", "Cn"))
    return bad / max(len(t), 1)


def symbol_ratio(t: str) -> float:
    s = re.sub(r"\s", "", t)
    if not s:
        return 1.0
    return sum(1 for ch in s if not ch.isalpha()) / len(s)


def build_detector():
    from lingua import Language, LanguageDetectorBuilder

    langs = [Language.ENGLISH, Language.TURKISH, Language.GERMAN, Language.FRENCH, Language.SPANISH,
             Language.ITALIAN, Language.PORTUGUESE, Language.DUTCH, Language.RUSSIAN, Language.ARABIC,
             Language.CHINESE, Language.JAPANESE, Language.LATIN, Language.AZERBAIJANI]
    return LanguageDetectorBuilder.from_languages(*langs).with_preloaded_language_models().build()


def main() -> None:
    det = build_detector()
    removed = RemovalLog(p("reports") / "removed_documents.csv", "filter", reset=False)
    kept, stats = [], Counter()
    lang_counts = Counter()
    for src in SOURCES:
        for d in read_jsonl(p("cleaned") / f"{src}.jsonl"):
            t = d["text"]
            stats[f"{src}:in"] += 1
            if len(t) < F["min_chars"]:
                removed.add(d["raw_id"], "too_short", src, f"{len(t)} chars")
                continue
            g = garbled_ratio(t)
            sr = symbol_ratio(t)
            if g > F["max_garbled_ratio"] or sr > 0.5:
                removed.add(d["raw_id"], "garbled", src, f"garbled={g:.3f} symbol={sr:.2f}")
                continue
            lang = det.detect_language_of(t[:3000])
            code = lang.iso_code_639_1.name.lower() if lang else "unknown"
            if code not in F["allowed_languages"]:
                removed.add(d["raw_id"], "wrong_language", src, code)
                continue
            ds = domain_score(t)
            ot = off_topic_hits(t)
            if ds < F["min_domain_score"] or ot >= 3:
                removed.add(d["raw_id"], "out_of_domain", src, f"domain_score={ds:.1f} off_topic={ot}")
                continue
            d.update({"language": code, "domain_score": round(ds, 1), "garbled_ratio": round(g, 4)})
            kept.append(d)
            stats[f"{src}:kept"] += 1
            lang_counts[code] += 1
    removed.save()
    write_jsonl(p("interim") / "filtered.jsonl", kept)
    reasons = Counter(r["reason"] for r in removed.rows if r["stage"] == "filter")
    summary = {"kept": len(kept), "removed_by_reason": dict(reasons), "per_source": dict(stats),
               "languages": dict(lang_counts)}
    (p("reports") / "filter_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                                      encoding="utf-8")
    log.info(f"Kalan {len(kept)} doküman; elenen: {dict(reasons)}; diller: {dict(lang_counts)}")


if __name__ == "__main__":
    main()
