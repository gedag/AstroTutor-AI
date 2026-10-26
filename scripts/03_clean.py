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

from common import CFG, get_logger, p, read_jsonl, rng, write_jsonl
from html_residue import strip_html_residue

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
           "footnotes", "citations", "notes and references", "explanatory notes", "gallery", "publications",
           "selected publications", "selected bibliography", "selected works", "works", "selected papers"},
    "tr": {"kaynakça", "dış bağlantılar", "ayrıca bakınız", "notlar", "kaynaklar", "ek okumalar", "dipnotlar",
           "konuyla ilgili yayınlar", "galeri", "ileri okuma", "yayınlar", "yayınları", "seçilmiş yayınlar",
           "eserleri", "eserler"},
}

# ---------------------------------------------------------------- Kaynakça girdisi satırları
# "Campbell, B. A., Jawin, E. R. (2025). Refined ... Icarus 425, 116324. doi:..." biçimli satırlar.
# Metin içi atıflar ("... (Bechtol et al., 2015)") düzyazının parçasıdır, SİLİNMEZ: kural yalnız satır
# yazar adı + baş harf kalıbıyla BAŞLIYORSA ve yıl + yayın işareti (doi, dergi, cilt, sayfa) içeriyorsa uygulanır.
_PARTICLE = r"(?:(?:van|von|de|der|den|del|della|di|du|da|la|le|al|el|dos|das|ten|ter)\s)*"
_AUTHOR = _PARTICLE + r"[A-Z][\w'’\-]+(?:\s[A-Z][\w'’\-]+)?,\s?(?:[A-Z]\.\s?-?){1,3}"
BIB_START = re.compile(r"^[*‡†\s]*" + _AUTHOR)
BIB_AUTHOR = re.compile(_AUTHOR)
BIB_YEAR = re.compile(r"\b(19|20)\d{2}[a-z]?\b")
BIB_MARK = re.compile(r"doi|bibcode|arxiv:|\bvol\.|\bpp?\.\s?\d|geophys|astrophys|icarus|\bapj\b|\ba&a\b|journal|"
                      r"proceedings|conference|abstract|letters|review|science,|nature,|in press|submitted|"
                      r"circular|bulletin|monthly notices|mnras", re.I)
AUTHORS_LIST = re.compile(r"Authors?:\s")
INITIAL_NAME = re.compile(r"\b[A-Z]\.\s?(?:[A-Z]\.\s?)?[A-Z][a-z]")


def is_bib_entry(s: str) -> bool:
    if len(s) < 40:
        return False
    if BIB_START.match(s) and BIB_YEAR.search(s) and (BIB_MARK.search(s) or len(BIB_AUTHOR.findall(s)) >= 2):
        return True
    return bool(AUTHORS_LIST.search(s) and len(INITIAL_NAME.findall(s)) >= 5)


def drop_bib_entries(t: str) -> tuple[str, float]:
    """Kaynakça girdisi satırlarını siler; (metin, silinen satır oranı) döndürür."""
    lines = t.splitlines()
    nonempty = [x for x in lines if x.strip()]
    out = [x for x in lines if not is_bib_entry(x.strip())]
    n = len(lines) - len(out)
    rule_hits["bibliography_entry_line"] += n
    return "\n".join(out), n / max(len(nonempty), 1)


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
ALPHA_INDEX = re.compile(r"(?m)^\s*(?:[A-Z]\s*\|\s*){5,}[A-Z]\s*$")


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


def clean_doc(d: dict, boiler: set[str]) -> tuple[str, float]:
    """(temiz metin, kaynakça satırı oranı) döndürür. Oran 04_filter'da 'reference_list' kararı için kullanılır."""
    t, k = strip_html_residue(d["text"])  # <br>, <sub ...>, &amp; kalıntıları; <sup>x</sup> -> ^x
    rule_hits["html_residue"] += k
    t = unicode_normalize(t)
    src = d["source"]
    bib_ratio = 0.0
    if src == "openstax":
        t = clean_pdf(t)
    elif src.startswith("wikipedia"):
        t, bib_ratio = drop_bib_entries(clean_wikipedia(t, src.split("_")[1]))
    elif src == "nasa_apod":
        t = clean_apod(clean_html(t, boiler))
    elif src == "nasa_science":
        t, bib_ratio = drop_bib_entries(clean_html(t, boiler))
        n = len(ALPHA_INDEX.findall(t))
        t = ALPHA_INDEX.sub("", t)  # sözlük sayfalarındaki "A | B | C | ..." harf dizini
        rule_hits["glossary_alpha_index"] += n
    t = normalize_whitespace(t)
    # Sözlük sayfalarında kısa satırlar TERİMDİR ("biomass", "bow shock"): kısa satır kuralı uygulanmaz.
    # (24.10.2026 corpus incelemesi: kural 22 NASA sözlük sayfasında terimleri silip yalnız tanımları bırakıyordu.)
    is_glossary = src == "nasa_science" and "glossary" in (d.get("url") or "").lower()
    if src != "arxiv_astro_ph" and not is_glossary:  # arXiv özetinde başlık kısa olabilir, korunur
        t = drop_short_lone_lines(t)
    elif is_glossary:
        rule_hits["glossary_terms_kept"] += 1
    return normalize_whitespace(t), round(bib_ratio, 3)


RULE_DOCS = [
    # (anahtar, kural, ne yapar, neden)
    ("html_residue", "HTML kalıntısı", "`<br>`, `<sub ...>...</sub>` etiketleri ve `&amp;` gibi entity'ler; `<sup>x</sup>` -> `^x`",
     "Extraction araçlarının bıraktığı biçim kalıntısı; üst simge içeriği üs olarak korunur (24.10.2026 denetimi)"),
    ("superscript_to_caret", "Üs koruma (NFKC öncesi)", "10²³ -> 10^23, s⁻¹ -> s^-1",
     "NFKC üst simgeleri düz rakama çevirir (10²³ -> 1023) ve sayının anlamı bozulur"),
    (None, "Unicode NFKC", "Karakter varyantlarını tek biçime çeker (ﬁ -> fi, tam genişlikli karakterler)",
     "Aynı kelime farklı kodlamalarla yazılmış olabilir; PDF bağlaçları (ligature) çözülür"),
    (None, "Görünmez/kontrol karakterleri", "Yumuşak tire, sıfır genişlikli boşluk, BOM, kontrol karakterleri silinir",
     "Tokenizer'da gereksiz token üretir, görünmez olduğu için fark edilmez"),
    ("pdf_header_footer", "PDF tekrarlayan satır", "Rakamlar normalize edildiğinde 5+ sayfada tekrar eden ve "
     "header/footer biçimindeki satırları siler", "Sayfa başlığı/altbilgi ('Access for free at openstax.org')"),
    ("pdf_running_header", "PDF bölüm başlığı satırı", "'78 3 • Orbits and Gravity' biçimli satırlar",
     "Tek sayfalardaki bölüm başlıkları 5 sayfa eşiğinin altında kalıyordu"),
    ("pdf_box_label", "PDF kutu etiketleri", "'LINK TO LEARNING', 'Learning Objectives' gibi etiket satırları",
     "Bilgi taşımayan düzen etiketi"),
    ("pdf_link_to_learning_paragraph", "Link to Learning paragrafları", "openstax.org/l/ kısa bağlantısı içeren paragraflar",
     "Dış video/animasyon yönlendirmesi; alan bilgisi değil"),
    ("figure_credit_parenthetical", "Görsel kredisi", "'(credit: ...)' parantezleri",
     "Görsel sahibi bilgisi; metin bilgisi değil (görseller zaten alınmadı)"),
    ("pdf_dehyphenate", "Satır sonu tirelemesi", "'distri-\\nbution' -> 'distribution' (yalnız küçük harfle devam ederse)",
     "PDF satır kaydırması kelimeyi böler; 'X-ray' gibi gerçek tireler korunur"),
    ("pdf_page_break_join", "Sayfa sonu paragraf birleştirme", "Cümle sonu olmadan biten paragraf + küçük harfle "
     "başlayan devamı birleştirilir", "Sayfa sınırı paragrafı ikiye bölüyordu"),
    ("pdf_heading_detected", "Alt başlık işaretleme", "Kısa, noktalama ile bitmeyen satırlar '## ' başlığı olur",
     "Başlık sonraki paragrafa yapışıyordu; başlıklar chunk sınırı olarak da kullanılır"),
    ("wiki_drop_section", "Wikipedia kaynakça bölümleri", "References, See also, External links, Kaynakça, Dış "
     "bağlantılar... bölümleri atılır", "Kaynak listesi ve bağlantılar alan metni değil"),
    ("bibliography_entry_line", "Kaynakça girdisi satırı", "'Soyadı, A. B. (yıl). Başlık. Dergi, cilt, doi' "
     "biçimiyle BAŞLAYAN satırlar (NASA Science ve Wikipedia)", "Yayın listesi alan metni değil; düzyazıdaki "
     "metin içi atıflar ('(Bechtol et al., 2015)') korunur"),
    ("wiki_empty_heading", "Boş başlık", "Altında içerik kalmayan başlıklar silinir", "Bölüm atımından sonra kalan artık"),
    ("html_boilerplate_line", "Site menüsü / şablon satırı", "Kaynağın %2'sinden (en az 5) fazla dokümanında tekrar "
     "eden 100 karakterden kısa satırlar", "'Share', 'Keep Exploring', 'Discover More Topics From NASA' gibi menüler"),
    ("html_repeated_paragraph", "Tekrarlanan bilgi paragrafı", "Çok dokümanda geçen 100+ karakterlik paragraf yalnız "
     "ilk geçtiği dokümanda tutulur", "Bilgi korunur ama aynı paragraf corpus'ta defalarca yer almaz"),
    ("html_truncated_teaser", "Kesik tanıtım cümlesi", "'…' veya '...' ile biten satırlar",
     "Hub sayfalarındaki yarım cümleler; bilgi taşımaz"),
    ("html_heading_kept", "HTML alt başlık koruma", "Kısa başlık satırı, ardından uzun paragraf geliyorsa '## ' ile korunur",
     "Kısa satır kuralının başlıkları silmesini önler"),
    ("apod_credit_footer", "APOD kredi/altbilgi", "'Image Credit', 'Copyright', 'Tomorrow's picture' satırları",
     "Kişi adı içeren kredi satırı ve site altbilgisi"),
    ("short_lone_line", "Kısa yalnız satır", "20 karakterden kısa, rakam içermeyen, başlık olmayan satırlar "
     "(NASA sözlük sayfaları hariç)", "Menü ve sayfa numarası kalıntıları; rakamlı bilgi satırları "
     "(ör. '5,97 × 10^24 kg') korunur"),
    ("glossary_terms_kept", "Sözlük terimleri korunur", "NASA sözlük sayfalarında kısa satır kuralı uygulanmaz "
     "(sayfa sayısı)", "Sözlükte kısa satırlar terimdir ('biomass', 'bow shock'); ilk sürüm terimleri silip yalnız "
     "tanımları bırakıyordu"),
    ("glossary_alpha_index", "Sözlük harf dizini", "'A | B | C | ...' satırları", "Navigasyon; bilgi taşımaz"),
    (None, "Whitespace normalizasyonu", "Ardışık boşluklar teke, 3+ boş satır ikiye indirilir",
     "PDF sütun hizalaması bozuk boşluk üretir"),
]


def write_rules_md(per_src: dict) -> None:
    md = ["# Temizleme Kuralları", "",
          "Bu dosya `scripts/03_clean.py` tarafından üretilir. Kurallar bilgiyi koruyacak şekilde dar tutuldu: "
          "**sayılar, birimler, formüller, LaTeX ve 'CO2', 'Alternaria solani' türü terimler silinmez** "
          "(Vize Rehberi §7: `re.sub(r'\\d+', '', text)` gibi kaba kurallar kullanılmadı).", "",
          "| Kural | Ne yapar | Neden | Uygulama sayısı |", "| --- | --- | --- | --- |"]
    for key, name, what, why in RULE_DOCS:
        md.append(f"| {name} | {what} | {why} | {rule_hits.get(key, 0):,} |" if key else f"| {name} | {what} | {why} | tüm metin |")
    md += ["", "## Kaynak bazında etki", "", "| Kaynak | Doküman | Karakter (önce) | Karakter (sonra) | Silinen oran |",
           "| --- | --- | --- | --- | --- |"]
    for src, v in per_src.items():
        md.append(f"| {src} | {v['docs']:,} | {v['chars_before']:,} | {v['chars_after']:,} | %{100 * v['removed_ratio']:.1f} |")
    md += ["", "Öncesi/sonrası örnekleri: [cleaning_examples.md](cleaning_examples.md)"]
    (p("reports") / "cleaning_rules.md").write_text("\n".join(md) + "\n", encoding="utf-8")


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
            text, bib_ratio = clean_doc(d, boiler)
            d = {**d, "text": text, "bib_line_ratio": bib_ratio}
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
    write_rules_md(per_src)


if __name__ == "__main__":
    main()
