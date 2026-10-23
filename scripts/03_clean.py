"""03 — Çıkarılmış metinleri temizler (Vize Rehberi §7).

Her kural bilgiyi koruyacak şekilde dar tutulmuştur: sayılar, birimler, formüller, LaTeX ve
"CO2", "Alternaria solani" türü terimler SİLİNMEZ. Kural listesi ve gerekçeleri reports/cleaning_rules.md'de.

Girdi : data/extracted/<kaynak>.jsonl
Çıktı : data/cleaned/<kaynak>.jsonl, reports/cleaning_examples.md, reports/cleaning_stats.json
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from common import CFG, get_logger, p, read_jsonl, rng, write_jsonl

log = get_logger("03_clean")
EXT, OUT = p("extracted"), p("cleaned")
SHORT = CFG["cleaning"]["short_line_chars"]
SOURCES = ["nasa_science", "nasa_apod", "openstax", "arxiv_astro_ph", "wikipedia_en", "wikipedia_tr"]
rule_hits: Counter = Counter()

# ---------------------------------------------------------------- 1) Unicode
SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
SUP_RUN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+")
INVISIBLE = re.compile(r"[­​‌‍⁠﻿ ]")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def unicode_normalize(t: str) -> str:
    # NFKC üst simgeleri düz rakama çevirir (10²³ -> 1023) ve bilgi kaybına yol açar.
    # Bu yüzden önce üs ifadeleri ^ notasyonuna alınır: 10²³ -> 10^23, m s⁻² -> m s^-2
    n0 = len(SUP_RUN.findall(t))
    t = SUP_RUN.sub(lambda m: "^" + m.group(0).translate(SUP), t)
    rule_hits["superscript_to_caret"] += n0
    t = t.replace(" ", " ")
    t = INVISIBLE.sub("", t)
    t = CONTROL.sub("", t)
    return unicodedata.normalize("NFKC", t)


# ---------------------------------------------------------------- 2) Whitespace
def normalize_whitespace(t: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in t.splitlines()]
    t = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# ---------------------------------------------------------------- 3) Kaynağa özgü kurallar
def load_pdf_repeated() -> set[str]:
    f = EXT / "openstax_pages_meta.json"
    if not f.exists():
        return set()
    rep = json.loads(f.read_text(encoding="utf-8"))["repeated_lines"]
    # Yalnızca header/footer BİÇİMİNDEKİ tekrarlar silinir: "36 1 • Science and..." , sayfa no, site notu.
    shape = re.compile(r"(•|openstax\.org|^#$|^#\.#$)")
    return {x["line"] for x in rep if shape.search(x["line"])}


PDF_REPEATED = load_pdf_repeated()
PDF_LABELS = {"LINK TO LEARNING", "MAKING CONNECTIONS", "VOYAGERS IN ASTRONOMY", "ASTRONOMY BASICS",
              "Learning Objectives", "Check Your Learning"}
RUNNING_HEADER = re.compile(r"^(\d+\s+)?\d+(\.\d+)?\s+•\s+.{3,90}?(\s+\d+)?$")
CREDIT_PAREN =re.compile(r"\s*\((credit|Credit)[^()]*(\([^()]*\)[^()]*)*\)")


def digit_key(ln: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", ln).strip())


def is_heading(s: str) -> bool:
    return (len(s) < 80 and len(s.split()) <= 12 and (s[:1].isupper() or re.match(r"^\d+\.\d+ [A-Z]", s))
            and not re.search(r"[.!?,;:”\"]$", s) and not s.startswith("##")
            and not re.match(r"^(Figure|Table) \d", s))


def clean_pdf(t: str) -> str:
    out = []
    for ln in t.splitlines():
        s = ln.strip()
        if digit_key(s) in PDF_REPEATED:
            rule_hits["pdf_header_footer"] += 1
            continue
        if RUNNING_HEADER.match(s):  # "78 3 • Orbits and Gravity" / "3.3 • Newton’s ... 79"
            rule_hits["pdf_running_header"] += 1
            continue
        if s in PDF_LABELS or re.fullmatch(r"E X A M P L E( \d)+( \. \d)+", s):
            rule_hits["pdf_box_label"] += 1
            continue
        out.append(ln)
    t = "\n".join(out)
    n = len(CREDIT_PAREN.findall(t))
    t = CREDIT_PAREN.sub("", t)
    rule_hits["figure_credit_parenthetical"] += n
    # satır sonu tirelemesi: "distri-\nbution" -> "distribution" (yalnız küçük harfle devam ediyorsa)
    n = len(re.findall(r"(\w)-\n([a-z])", t))
    t = re.sub(r"(\w)-\n([a-z])", r"\1\2", t)
    rule_hits["pdf_dehyphenate"] += n
    # Extraction'da her PDF metin bloğu boş satırla ayrıldı (blok = paragraf).
    # Blok içindeki sabit satır kaydırmaları birleştirilir; sayfa sonunda bölünen paragraf
    # (önceki blok cümle sonu ile bitmiyor ve sonraki küçük harfle başlıyorsa) yeniden birleştirilir.
    blocks = [" ".join(x.strip() for x in b.splitlines() if x.strip()) for b in re.split(r"\n\s*\n", t)]
    blocks = [b for b in blocks if b]
    paras: list[str] = []
    for b in blocks:
        if is_heading(b):
            paras.append("## " + b)
            rule_hits["pdf_heading_detected"] += 1
        elif paras and not paras[-1].startswith("## ") and not re.search(r"[.!?:;”\")]$", paras[-1]) \
                and b[:1].islower():
            paras[-1] += " " + b
            rule_hits["pdf_page_break_join"] += 1
        else:
            paras.append(b)
    # "Link to Learning" kutuları: dış video/animasyon yönlendirmesi, alan bilgisi taşımaz
    kept = [x for x in paras if "openstax.org/l/" not in x.replace("/ ", "/")]
    rule_hits["pdf_link_to_learning_paragraph"] += len(paras) - len(kept)
    return "\n".join(kept)


WIKI_DROP_SECTIONS = {
    "en": {"references", "external links", "see also", "further reading", "notes", "bibliography", "sources",
           "footnotes", "citations", "notes and references", "explanatory notes", "gallery"},
    "tr": {"kaynakça", "dış bağlantılar", "ayrıca bakınız", "notlar", "kaynaklar", "ek okumalar", "dipnotlar",
           "konuyla ilgili yayınlar", "galeri", "ileri okuma"},
}


def clean_wikipedia(t: str, lang: str) -> str:
    out, skip_level = [], None
    for ln in t.splitlines():
        m = re.match(r"^(=+)\s*(.*?)\s*=+$", ln.strip())
        if m:
            level, name = len(m.group(1)), m.group(2)
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if name.lower() in WIKI_DROP_SECTIONS[lang]:
                skip_level = level
                rule_hits["wiki_drop_section"] += 1
                continue
            if skip_level is None:
                out.append("#" * max(level, 2) + " " + name)
            continue
        if skip_level is None:
            out.append(ln)
    # içeriği olmayan başlıkları at
    res = []
    for i, ln in enumerate(out):
        if ln.startswith("#"):
            nxt = next((x for x in out[i + 1:] if x.strip()), "")
            if not nxt or nxt.startswith("#") and len(nxt.split()[0]) <= len(ln.split()[0]):
                rule_hits["wiki_empty_heading"] += 1
                continue
        res.append(ln)
    return "\n".join(res)


APOD_DROP = re.compile(r"^(Image Credit|Video Credit|Illustration Credit|Credit|Copyright|Tomorrow'?s picture|"
                       r"Authors? & editors|NASA Official|A service of|Specific rights apply|Explore Your Universe)",
                       re.I)


def clean_apod(t: str) -> str:
    out = []
    for ln in t.splitlines():
        s = ln.strip()
        if APOD_DROP.match(s):
            rule_hits["apod_credit_footer"] += 1
            continue
        s = re.sub(r"^Explanation:\s*", "", s)
        out.append(s)
    return "\n".join(out)


TEASER = re.compile(r"(…|\.\.\.)\s*$")


def build_html_boilerplate(docs: list[dict]) -> set[str]:
    """Bir kaynakta çok sayıda farklı dokümanda tekrar eden satırlar (menü, 'Share', 'Keep Exploring' vb.)."""
    df = Counter()
    for d in docs:
        df.update({digit_key(x) for x in d["text"].splitlines() if x.strip()})
    thr = max(5, int(0.02 * len(docs)))
    return {ln for ln, n in df.items() if n >= thr}


LONG_REPEAT_SEEN: set[str] = set()


def clean_html(t: str, boiler: set[str]) -> str:
    out = []
    lines = [x.strip() for x in t.splitlines()]
    for i, s in enumerate(lines):
        key = digit_key(s)
        if s and key in boiler:
            if len(s) >= 100:
                # Uzun tekrar = bilgi taşıyan ortak paragraf (ör. aynı uydu grubunun açıklaması).
                # Bilgiyi kaybetmemek için ilk geçtiği dokümanda tutulur, diğerlerinden atılır.
                if key not in LONG_REPEAT_SEEN:
                    LONG_REPEAT_SEEN.add(key)
                    out.append(s)
                    continue
                rule_hits["html_repeated_paragraph"] += 1
            else:
                rule_hits["html_boilerplate_line"] += 1
            continue
        if TEASER.search(s):  # hub sayfalarındaki kesik tanıtım metinleri: yarım cümle, bilgi taşımaz
            rule_hits["html_truncated_teaser"] += 1
            continue
        nxt = next((x for x in lines[i + 1:] if x), "")
        if s and is_heading(s) and len(nxt) > 80:
            out.append("## " + s)  # alt başlık korunur (chunk sınırı için de kullanılır)
            rule_hits["html_heading_kept"] += 1
            continue
        out.append(s)
    return "\n".join(out)


# ---------------------------------------------------------------- 4) Kısa yalnız satır
def drop_short_lone_lines(t: str) -> str:
    out = []
    for ln in t.splitlines():
        s = ln.strip()
        if s and len(s) < SHORT and not s.startswith("#") and not re.search(r"\d", s) and not s.endswith(":"):
            rule_hits["short_lone_line"] += 1
            continue
        out.append(ln)
    return "\n".join(out)


def clean_doc(d: dict, boiler: set[str]) -> str:
    t = unicode_normalize(d["text"])
    src = d["source"]
    if src == "openstax":
        t = clean_pdf(t)
    elif src.startswith("wikipedia"):
        t = clean_wikipedia(t, src.split("_")[1])
    elif src == "nasa_apod":
        t = clean_apod(clean_html(t, boiler))
    elif src == "nasa_science":
        t = clean_html(t, boiler)
    t = normalize_whitespace(t)
    if src != "arxiv_astro_ph":  # arXiv özetinde başlık kısa olabilir, korunur
        t = drop_short_lone_lines(t)
    return normalize_whitespace(t)


def main() -> None:
    examples, per_src = [], {}
    r = rng(3)
    for src in SOURCES:
        docs = sorted(read_jsonl(EXT / f"{src}.jsonl"), key=lambda d: d["raw_id"])  # deterministik sıra
        if not docs:
            log.warning(f"{src}: extracted veri yok")
            continue
        boiler = build_html_boilerplate(docs) if src in ("nasa_science", "nasa_apod") else set()
        if boiler:
            (OUT / f"{src}_boilerplate_lines.txt").write_text("\n".join(sorted(boiler)), encoding="utf-8")
        before = after = 0
        out = []
        for d in docs:
            raw = d["text"]
            d = {**d, "text": clean_doc(d, boiler)}
            before += len(raw)
            after += len(d["text"])
            out.append(d)
        write_jsonl(OUT / f"{src}.jsonl", out)
        per_src[src] = {"docs": len(out), "chars_before": before, "chars_after": after,
                        "removed_ratio": round(1 - after / max(before, 1), 4), "boilerplate_lines": len(boiler)}
        log.info(f"{src}: {len(out)} doküman, karakter {before:,} -> {after:,}")
        # Rehber: en az 10-20 örnekte öncesi/sonrası kaydı
        idx = r.sample(range(len(docs)), min(4 if src != "arxiv_astro_ph" else 2, len(docs)))
        examples += [(docs[i], out[i]) for i in idx]
    (p("reports") / "cleaning_stats.json").write_text(json.dumps({"per_source": per_src, "rule_hits": rule_hits},
                                                                 indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Temizleme: öncesi / sonrası örnekleri", "",
          f"Rastgele seçilmiş {len(examples)} doküman (seed {CFG['project']['random_seed']}). "
          "Her örnekte ilk 1.200 karakter gösterilmiştir.", ""]
    for i, (b, a) in enumerate(examples, 1):
        md += [f"## {i}. {b['source']} — {b.get('title') or b['raw_id']}", f"`{b['raw_id']}` · {b.get('url')}", "",
               f"Uzunluk: {len(b['text']):,} → {len(a['text']):,} karakter", "", "**ÖNCE**", "```text",
               b["text"][:1200], "```", "**SONRA**", "```text", a["text"][:1200], "```", ""]
    (p("reports") / "cleaning_examples.md").write_text("\n".join(md), encoding="utf-8")
    log.info(f"Kural isabetleri: {dict(rule_hits)}")


if __name__ == "__main__":
    main()
