"""02 — Ham dosyalardan metin çıkarır.

HTML (NASA Science, APOD) : Trafilatura, başarısız olursa BeautifulSoup yedeği
PDF  (OpenStax)           : PyMuPDF; içindekiler (TOC) 2. seviyesi = 1 doküman. pdfplumber ile karşılaştırma yapılır.
XML  (arXiv OAI-PMH)      : başlık + özet
JSON (Wikipedia API)      : explaintext çıktısı (bölüm başlıkları == ... == biçiminde korunur)

Çıktılar:
  data/extracted/<kaynak>.jsonl             (doküman başına bir satır, metadata ile)
  data/extracted/<kaynak>/<raw_id>.txt      (doküman başına düz metin)
  reports/extraction_failures.csv           (boş / çok kısa / hatalı çıktılar ve nedenleri)
  reports/extraction_tool_comparison.md     (PyMuPDF vs pdfplumber)
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from common import CFG, ROOT, RemovalLog, get_logger, p, read_jsonl, write_jsonl

log = get_logger("02_extract")
RAW, OUT = p("raw"), p("extracted")
MIN_OK = CFG["extraction"]["min_chars_success"]
fails = RemovalLog(p("reports") / "extraction_failures.csv", "extraction")
stats: dict[str, Counter] = {}


def emit(source: str, rows: list[dict]) -> None:
    sdir = OUT / source
    sdir.mkdir(parents=True, exist_ok=True)
    good = []
    c = stats.setdefault(source, Counter())
    for r in rows:
        c["raw"] += 1
        t = (r.get("text") or "").strip()
        if not t:
            fails.add(r["raw_id"], "extraction_error", source, "empty_output")
            c["failed"] += 1
            continue
        if len(t) < MIN_OK:
            fails.add(r["raw_id"], "extraction_error", source, f"too_little_text({len(t)} chars)")
            c["failed"] += 1
            continue
        r["text"] = t
        (sdir / f"{r['raw_id']}.txt").write_text(t, encoding="utf-8")
        good.append(r)
    c["ok"] = len(good)
    write_jsonl(OUT / f"{source}.jsonl", good)
    log.info(f"{source}: ham={c['raw']} başarılı={c['ok']} başarısız={c['failed']}")


def manifest_rows(path: Path) -> list[dict]:
    """Manifest'te aynı raw_id birden fazla kez olabilir (indirme yeniden başlatıldığında). Her raw_id için
    başarılı (200) bir kayıt varsa onu, yoksa son kaydı döndürür."""
    best: dict[str, dict] = {}
    for m in read_jsonl(path):
        cur = best.get(m["raw_id"])
        if cur is None or m.get("http_status") == 200 or cur.get("http_status") != 200:
            best[m["raw_id"]] = m
    return list(best.values())


# --------------------------------------------------------------------------- HTML
def html_extract(html: str) -> tuple[str, dict]:
    import trafilatura

    meta = {}
    try:
        d = trafilatura.bare_extraction(html, include_comments=False, include_tables=True,
                                        favor_precision=True, with_metadata=True)
        if d is not None:
            d = d if isinstance(d, dict) else d.as_dict()
            meta = {"title": d.get("title"), "date": d.get("date")}
            if d.get("text") and len(d["text"]) >= MIN_OK:
                return d["text"], {**meta, "method": "trafilatura"}
    except Exception as e:
        meta["trafilatura_error"] = str(e)[:200]
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = "\n".join(x.get_text(" ", strip=True) for x in main.find_all(["h1", "h2", "h3", "p", "li"]))
    if not meta.get("title") and soup.title:
        meta["title"] = soup.title.get_text(strip=True)
    return text, {**meta, "method": "beautifulsoup_fallback"}


def nasa_doc_type(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if path.startswith(("mission/", "missions/")):
        return "gorev_sayfasi"
    if "glossary" in path:
        return "sozluk"
    if path.startswith(("learn/", "kids/")) or "basics" in path:
        return "egitim_sayfasi"
    return "web_makale"


def extract_html_source(source: str, prefix_dir: Path) -> None:
    rows = []
    for m in manifest_rows(prefix_dir / "manifest.jsonl"):
        if m.get("http_status") != 200:
            fails.add(m["raw_id"], "download_error", source, f"http_status={m.get('http_status')}")
            continue
        html = (ROOT / m["file"]).read_text(encoding="utf-8", errors="replace")
        try:
            text, meta = html_extract(html)
        except Exception as e:
            text, meta = "", {"method": "error", "error": str(e)[:200]}
        url = m.get("final_url") or m["url"]
        year = None
        if meta.get("date"):
            year = int(str(meta["date"])[:4])
        if source == "nasa_apod":
            year = m["extra"].get("year") or year
            dtype = "apod_aciklama"
        else:
            dtype = nasa_doc_type(url)
        title = (meta.get("title") or "").replace(" - NASA Science", "").strip()
        rows.append({"raw_id": m["raw_id"], "source": source, "url": url, "title": title,
                     "language_hint": "en", "document_type": dtype, "publication_year": year,
                     "license": m["license"], "retrieved_at": m["retrieved_at"],
                     "extraction_method": meta.get("method"), "group": m["extra"].get("group"), "text": text})
    emit(source, rows)


# --------------------------------------------------------------------------- PDF
SKIP_SECTIONS = re.compile(r"^(For Further Exploration|Collaborative Group Activities|Exercises|Review Questions|"
                           r"Thought Questions|Figuring for Yourself|Index|Preface|Chapter Outline|About OpenStax|"
                           r"Contents|Answers)", re.I)


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def heading_regex(title: str) -> re.Pattern:
    """Başlığın satır sonlarıyla bölünmüş hâlini de yakalayan regex (örn. '1.2 The Nature\\nof Science')."""
    return re.compile(r"\s+".join(re.escape(w) for w in title.split()))


def extract_openstax() -> None:
    import pymupdf

    src_dir = RAW / "openstax"
    man = list(read_jsonl(src_dir / "manifest.jsonl"))
    if not man:
        log.warning("openstax manifest yok, atlanıyor")
        return
    m = man[-1]
    pdf = pymupdf.open(ROOT / m["file"])
    # Varsayılan okuma sırası içerik akışını izler; kenar kutuları (Learning Objectives vb.) paragrafların
    # ortasına karışıyordu. Metin blokları sayfadaki dikey (sonra yatay) konuma göre sıralanır ve
    # her blok boş satırla ayrılır -> blok = paragraf.
    def page_text(pg) -> str:
        blocks = [b for b in pg.get_text("blocks") if b[6] == 0 and b[4].strip()]
        blocks.sort(key=lambda b: (round(b[1]), b[0]))
        return "\n\n".join(b[4].strip() for b in blocks)

    pages = [page_text(pg) for pg in pdf]
    no_text = sum(1 for t in pages if len(t.strip()) < 20)
    log.info(f"OpenStax: {len(pages)} sayfa, metin katmanı olmayan/boş sayfa: {no_text}")
    # Header/footer adayları: rakamlar # ile normalize edildiğinde 5+ sayfada tekrar eden satırlar
    line_pages = Counter()
    for t in pages:
        for ln in {re.sub(r"\d+", "#", norm_ws(x)) for x in t.splitlines() if x.strip()}:
            line_pages[ln] += 1
    min_pages = CFG["cleaning"]["repeated_line_min_pages"]
    repeated = sorted([ln for ln, n in line_pages.items() if n >= min_pages], key=lambda x: -line_pages[x])
    (OUT / "openstax_pages_meta.json").write_text(json.dumps(
        {"pages": len(pages), "empty_pages": no_text,
         "repeated_lines": [{"line": ln, "pages": line_pages[ln]} for ln in repeated]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log.info(f"OpenStax: {len(repeated)} satır {min_pages}+ sayfada tekrar ediyor (header/footer adayı)")
    toc = pdf.get_toc()  # [level, title, page(1-based)]
    level = CFG["extraction"]["pdf_level_for_documents"]
    chapter = None
    entries = []
    for lv, title, page in toc:
        if lv == 1:
            chapter = title
        if lv == level:
            entries.append((title.strip(), page, chapter))
    rows, skipped = [], 0
    for i, (title, page, chap) in enumerate(entries):
        end_page = entries[i + 1][1] if i + 1 < len(entries) else len(pages)
        rid = f"OPENSTAX_{i:04d}"
        if SKIP_SECTIONS.match(title) or (chap and chap.lower().startswith(("appendix", "index", "preface"))):
            skipped += 1
            fails.add(rid, "non_content_section", "openstax", f"{chap} / {title}")
            continue
        # Bölümler sayfa ortasında başlayıp bitebildiği için: başlangıç sayfasından bir sonraki bölümün
        # başladığı sayfaya kadar al, sonra kendi başlığında başlat ve sonraki bölümün başlığında kes.
        flat = "\n".join(pages[page - 1: max(end_page, page)])
        mt = heading_regex(title).search(flat)
        if mt:
            flat = flat[mt.start():]
        if i + 1 < len(entries):
            mn = next((x for x in heading_regex(entries[i + 1][0]).finditer(flat) if x.start() > 50), None)
            if mn:
                flat = flat[: mn.start()]
        year = m["extra"]["publication_year"]
        dtype = "ders_kitabi_ozet" if title.lower().startswith(("summary", "key terms")) else "ders_kitabi"
        rows.append({"raw_id": rid, "source": "openstax", "url": f"{m['landing_url']}#page={page}",
                     "title": f"{title}", "chapter": chap, "pdf_pages": [page, end_page],
                     "language_hint": "en", "document_type": dtype, "publication_year": year,
                     "license": m["license"], "retrieved_at": m["retrieved_at"], "extraction_method": "pymupdf",
                     "text": flat})
    log.info(f"OpenStax: TOC {len(entries)} bölüm, {skipped} içerik dışı bölüm (alıştırma/kaynakça/ek) atlandı")
    emit("openstax", rows)
    compare_pdf_tools(ROOT / m["file"], pdf)


def compare_pdf_tools(path: Path, pdf, n_pages: int = 40) -> None:
    """PyMuPDF ve pdfplumber'ı aynı sayfalar üzerinde hız ve çıktı açısından karşılaştırır (experiments.md için)."""
    import pdfplumber

    r = __import__("random").Random(CFG["project"]["random_seed"])
    idx = sorted(r.sample(range(20, len(pdf) - 20), n_pages))
    t0 = time.time()
    mu = [pdf[i].get_text("text") for i in idx]
    t_mu = time.time() - t0
    t0 = time.time()
    with pdfplumber.open(path) as pl:
        pp = [(pl.pages[i].extract_text() or "") for i in idx]
    t_pl = time.time() - t0
    ok_mu = sum(1 for t in mu if len(t.strip()) > 200)
    ok_pl = sum(1 for t in pp if len(t.strip()) > 200)
    # kelime birleşmesi göstergesi: 25+ harflik "kelimeler" (boşluk kaybı)
    glued = lambda ts: sum(len(re.findall(r"[A-Za-z]{25,}", t)) for t in ts)
    md = [
        "# PDF extraction aracı karşılaştırması", "",
        f"Dosya: `{path.name}` — rastgele {n_pages} sayfa (seed {CFG['project']['random_seed']}).", "",
        "| Araç | Süre (sn) | >200 karakter çıkan sayfa | Toplam karakter | Boşluk kaybı şüphesi (25+ harf) |",
        "| --- | --- | --- | --- | --- |",
        f"| PyMuPDF | {t_mu:.2f} | {ok_mu}/{n_pages} | {sum(map(len, mu)):,} | {glued(mu)} |",
        f"| pdfplumber | {t_pl:.2f} | {ok_pl}/{n_pages} | {sum(map(len, pp)):,} | {glued(pp)} |", "",
        f"PyMuPDF pdfplumber'dan yaklaşık {t_pl / max(t_mu, 1e-6):.0f} kat hızlı.", "",
        "## Örnek sayfa (ilk 600 karakter)", "", "### PyMuPDF", "```", mu[0][:600], "```", "### pdfplumber", "```",
        pp[0][:600], "```"]
    (p("reports") / "extraction_tool_comparison.md").write_text("\n".join(md), encoding="utf-8")
    log.info(f"PDF araç karşılaştırması: PyMuPDF {t_mu:.2f}s, pdfplumber {t_pl:.2f}s")


# --------------------------------------------------------------------------- arXiv
def extract_arxiv() -> None:
    src_dir = RAW / "arxiv_astro_ph"
    ns = {"o": "http://www.openarchives.org/OAI/2.0/", "a": "http://arxiv.org/OAI/arXiv/"}
    pref = CFG["sources"]["arxiv"]["primary_category_prefix"]
    man = {Path(m["file"]).name: m for m in read_jsonl(src_dir / "manifest.jsonl")}
    recs: dict[str, dict] = {}
    non_primary = 0
    for fp in sorted((src_dir / "oai").glob("page_*.xml")):
        m = man.get(fp.name, {})
        root = ET.fromstring(fp.read_bytes())
        for rec in root.findall(".//o:record", ns):
            md = rec.find(".//a:arXiv", ns)
            if md is None:
                continue
            aid = md.findtext("a:id", default="", namespaces=ns).strip()
            cats = md.findtext("a:categories", default="", namespaces=ns).split()
            if not cats or not cats[0].startswith(pref):
                non_primary += 1
                continue
            title = norm_ws(md.findtext("a:title", default="", namespaces=ns))
            abstract = norm_ws(md.findtext("a:abstract", default="", namespaces=ns))
            created = md.findtext("a:created", default="", namespaces=ns)
            recs[aid] = {"raw_id": f"ARXIV_{aid.replace('/', '_')}", "source": "arxiv_astro_ph",
                         "url": f"https://arxiv.org/abs/{aid}", "title": title, "language_hint": "en",
                         "document_type": "makale_ozeti", "publication_year": int(created[:4]) if created else None,
                         "categories": cats, "paper_license": md.findtext("a:license", default="", namespaces=ns),
                         "license": CFG["sources"]["arxiv"]["license"], "retrieved_at": m.get("retrieved_at"),
                         "extraction_method": "oai_xml", "text": f"{title}\n\n{abstract}"}
    log.info(f"arXiv: {len(recs)} birincil astro-ph kayıt ({non_primary} çapraz-listelenmiş kayıt alınmadı)")
    emit("arxiv_astro_ph", list(recs.values())[: CFG["sources"]["arxiv"]["max_records"]])


# --------------------------------------------------------------------------- Wikipedia
def extract_wikipedia(lang: str) -> None:
    src_dir = RAW / "wikipedia" / lang
    rows = []
    for m in manifest_rows(src_dir / "manifest.jsonl"):
        if m.get("http_status") != 200:
            fails.add(m["raw_id"], "download_error", f"wikipedia_{lang}", f"http_status={m.get('http_status')}")
            continue
        page = json.loads((ROOT / m["file"]).read_text(encoding="utf-8"))["query"]["pages"][0]
        ts = (page.get("revisions") or [{}])[0].get("timestamp", "")
        rows.append({"raw_id": m["raw_id"], "source": f"wikipedia_{lang}", "url": page.get("fullurl"),
                     "title": page.get("title"), "language_hint": lang, "document_type": "ansiklopedi_maddesi",
                     "publication_year": int(ts[:4]) if ts else None, "license": m["license"],
                     "retrieved_at": m["retrieved_at"], "extraction_method": "mediawiki_textextracts",
                     "wikidata": m["extra"].get("wikidata"), "wiki_category": m["extra"].get("category"),
                     "revid": m["extra"].get("revid"), "text": page.get("extract", "")})
    emit(f"wikipedia_{lang}", rows)


if __name__ == "__main__":
    extract_html_source("nasa_science", RAW / "nasa_science")
    extract_html_source("nasa_apod", RAW / "nasa_apod")
    extract_openstax()
    extract_arxiv()
    extract_wikipedia("en")
    extract_wikipedia("tr")
    fails.save()
    total = Counter()
    for c in stats.values():
        total.update(c)
    summary = {"per_source": {k: dict(v) for k, v in stats.items()}, "total": dict(total),
               "failure_rate": round(total["failed"] / max(total["raw"], 1), 4)}
    (p("reports") / "extraction_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                                          encoding="utf-8")
    log.info(f"TOPLAM ham={total['raw']} başarılı={total['ok']} başarısız={total['failed']} "
             f"(oran %{100 * summary['failure_rate']:.2f})")
