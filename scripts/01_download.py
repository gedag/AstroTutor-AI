"""01 — Ham veriyi indirir ve data/raw/<kaynak>/ altında DEĞİŞTİRMEDEN saklar.

Her kaynak için bir manifest.jsonl tutulur: raw_id, url, dosya, sha256, erişim zamanı, lisans.
Script kaldığı yerden devam eder (manifest'te olan dosyalar tekrar indirilmez).

Kullanım:
    python scripts/01_download.py --source all
    python scripts/01_download.py --source nasa_science --dry-run   # sadece seçilecek URL sayılarını gösterir
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from common import CFG, PoliteSession, ROOT, append_jsonl, file_sha256, get_logger, now_iso, p, read_jsonl, rng

log = get_logger("01_download")
RAW = p("raw")
SM_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def url_id(prefix: str, url: str) -> str:
    return f"{prefix}_{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}"


def manifest_done(src_dir: Path) -> set[str]:
    return {r["raw_id"] for r in read_jsonl(src_dir / "manifest.jsonl") if r.get("http_status") == 200}


# --------------------------------------------------------------------------- NASA sitemap
def fetch_sitemap_urls(sess: PoliteSession, types: list[str], save_dir: Path) -> list[tuple[str, str]]:
    """Sitemap index'ten verilen içerik türlerinin tüm URL'lerini (tür, url) olarak döndürür."""
    save_dir.mkdir(parents=True, exist_ok=True)
    idx = sess.get(CFG["sources"]["nasa_science"]["sitemap_index"]).text
    (save_dir / "wp-sitemap.xml").write_text(idx, encoding="utf-8")
    locs = [e.text for e in ET.fromstring(idx.encode("utf-8")).findall(".//sm:loc", SM_NS)]
    out = []
    for loc in locs:
        m = re.search(r"wp-sitemap-posts-([a-z\-]+)-\d+\.xml$", loc)
        if not m or m.group(1) not in types:
            continue
        fname = save_dir / Path(urlparse(loc).path).name
        if fname.exists():
            xml = fname.read_text(encoding="utf-8")
        else:
            xml = sess.get(loc).text
            fname.write_text(xml, encoding="utf-8")
        for e in ET.fromstring(xml.encode("utf-8")).findall(".//sm:loc", SM_NS):
            out.append((m.group(1), e.text.strip()))
    log.info(f"sitemap: {len(out)} URL ({', '.join(types)})")
    return out


def nasa_select(urls: list[tuple[str, str]]) -> list[dict]:
    c = CFG["sources"]["nasa_science"]
    missions = set(c["astro_missions"])
    groups: dict[str, list[str]] = defaultdict(list)
    stats = defaultdict(int)
    for _type, url in urls:
        path = urlparse(url).path.lstrip("/")
        if not any(path.startswith(pre) for pre in c["include_prefixes"]):
            stats["not_in_scope_prefix"] += 1
            continue
        if any(x in "/" + path for x in c["exclude_substrings"]):
            stats["excluded_substring"] += 1
            continue
        parts = [x for x in path.split("/") if x]
        if parts[0] in ("missions", "mission"):
            if len(parts) < 2 or parts[1] not in missions:
                stats["non_astro_mission"] += 1
                continue
            group = f"mission:{parts[1]}"
        else:
            group = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
        groups[group].append(url)
    log.info(f"NASA URL eleme istatistikleri: {dict(stats)}; {len(groups)} grup")

    r = rng(1)
    chosen: list[dict] = []
    for g in sorted(groups):
        us = sorted(set(groups[g]))
        r.shuffle(us)
        for u in us[: c["max_per_group"]]:
            chosen.append({"url": u, "group": g})
    # seed listesi (elle seçilmiş temel öğretici sayfalar) her zaman dahil
    seed_file = ROOT / c["seed_urls_file"]
    seeds = []
    if seed_file.exists():
        with open(seed_file, encoding="utf-8") as f:
            seeds = [row["url"] for row in csv.DictReader(f)]
    have = {x["url"] for x in chosen}
    for s in seeds:
        if s not in have:
            chosen.append({"url": s, "group": "seed"})
    if len(chosen) > c["max_documents"]:
        seed_set = set(seeds)
        keep = [x for x in chosen if x["url"] in seed_set]
        rest = [x for x in chosen if x["url"] not in seed_set]
        r.shuffle(rest)
        chosen = keep + rest[: c["max_documents"] - len(keep)]
    log.info(f"NASA seçilen URL: {len(chosen)}")
    return chosen


def download_html_list(sess: PoliteSession, items: list[dict], src: str, prefix: str, license_: str) -> None:
    src_dir = RAW / src
    (src_dir / "html").mkdir(parents=True, exist_ok=True)
    done = manifest_done(src_dir)
    todo = [x for x in items if url_id(prefix, x["url"]) not in done]
    log.info(f"{src}: {len(items)} hedef, {len(done)} zaten var, {len(todo)} indirilecek")
    ok = fail = 0
    for i, it in enumerate(todo, 1):
        rid = url_id(prefix, it["url"])
        try:
            r = sess.get(it["url"])
            status = r.status_code
        except Exception as e:
            log.warning(f"HATA {it['url']}: {e}")
            status, r = -1, None
        row = {"raw_id": rid, "source": src, "url": it["url"], "http_status": status,
               "retrieved_at": now_iso(), "license": license_, "extra": {k: v for k, v in it.items() if k != "url"}}
        if status == 200 and r is not None:
            fp = src_dir / "html" / f"{rid}.html"
            fp.write_bytes(r.content)
            row.update({"file": str(fp.relative_to(ROOT)).replace("\\", "/"), "sha256": file_sha256(fp),
                        "final_url": r.url})
            ok += 1
        else:
            fail += 1
        append_jsonl(src_dir / "manifest.jsonl", row)
        if i % 100 == 0:
            log.info(f"{src}: {i}/{len(todo)} (ok={ok}, fail={fail})")
    log.info(f"{src}: bitti ok={ok} fail={fail}")


def dl_nasa_science(dry: bool) -> None:
    sess = PoliteSession()
    urls = fetch_sitemap_urls(sess, CFG["sources"]["nasa_science"]["sitemap_types"], RAW / "nasa_science" / "sitemaps")
    chosen = nasa_select(urls)
    groups = defaultdict(int)
    for x in chosen:
        groups[x["group"]] += 1
    top = sorted(groups.items(), key=lambda kv: -kv[1])[:25]
    log.info("En büyük gruplar: " + ", ".join(f"{g}={n}" for g, n in top))
    if dry:
        return
    download_html_list(sess, chosen, "nasa_science", "NASA",
                       "NASA web content (science.nasa.gov) - NASA Images and Media Usage Guidelines; third-party content excluded")


def dl_nasa_apod(dry: bool) -> None:
    c = CFG["sources"]["nasa_apod"]
    sess = PoliteSession()
    urls = fetch_sitemap_urls(sess, [c["sitemap_type"]], RAW / "nasa_apod" / "sitemaps")
    by_year: dict[str, list[str]] = defaultdict(list)
    for _t, u in urls:
        m = re.search(r"/image-article/apod-(\d{4})-", u)
        if m:
            by_year[m.group(1)].append(u)
    r = rng(2)
    chosen = []
    for y in sorted(by_year):
        us = sorted(set(by_year[y]))
        r.shuffle(us)
        chosen += [{"url": u, "year": int(y)} for u in us[: c["per_year"]]]
    log.info(f"APOD: {sum(len(v) for v in by_year.values())} sayfa, {len(by_year)} yıl, seçilen {len(chosen)}")
    if dry:
        return
    download_html_list(sess, chosen, "nasa_apod", "APOD", c["license"])


# --------------------------------------------------------------------------- OpenStax PDF
def dl_openstax(dry: bool) -> None:
    c = CFG["sources"]["openstax"]
    src_dir = RAW / "openstax"
    src_dir.mkdir(parents=True, exist_ok=True)
    fp = src_dir / "astronomy-2e.pdf"
    if fp.exists() or dry:
        log.info(f"OpenStax: {'mevcut' if fp.exists() else 'dry-run'}")
        return
    sess = PoliteSession()
    r = sess.get(c["pdf_url"], stream=True)
    with open(fp, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    append_jsonl(src_dir / "manifest.jsonl", {
        "raw_id": "OPENSTAX_astronomy-2e", "source": "openstax", "url": c["pdf_url"], "landing_url": c["landing_url"],
        "http_status": r.status_code, "retrieved_at": now_iso(), "license": c["license"],
        "file": str(fp.relative_to(ROOT)).replace("\\", "/"), "sha256": file_sha256(fp),
        "extra": {"publication_year": c["publication_year"], "title": c["title"]}})
    log.info(f"OpenStax PDF indirildi: {fp.stat().st_size/1e6:.1f} MB")


# --------------------------------------------------------------------------- arXiv OAI-PMH
def dl_arxiv(dry: bool) -> None:
    c = CFG["sources"]["arxiv"]
    src_dir = RAW / "arxiv_astro_ph"
    (src_dir / "oai").mkdir(parents=True, exist_ok=True)
    if dry:
        return
    sess = PoliteSession(delay=CFG["http"]["arxiv_delay_seconds"])
    ns = {"o": "http://www.openarchives.org/OAI/2.0/", "a": "http://arxiv.org/OAI/arXiv/"}
    pages = sorted((src_dir / "oai").glob("page_*.xml"))
    n_primary = 0
    token = None
    for pg in pages:  # devam: mevcut sayfaları say, son token'ı bul
        root = ET.fromstring(pg.read_bytes())
        for rec in root.findall(".//o:record", ns):
            cats = rec.find(".//a:categories", ns)
            if cats is not None and cats.text.split()[0].startswith(c["primary_category_prefix"]):
                n_primary += 1
        t = root.find(".//o:resumptionToken", ns)
        token = t.text if t is not None and t.text else None
    if pages and token is None:
        log.info(f"arXiv: tamamlanmış ({n_primary} birincil astro-ph kayıt)")
        return
    i = len(pages)
    while n_primary < c["max_records"]:
        if token:
            url = f"{c['oai_base']}?verb=ListRecords&resumptionToken={token}"
        else:
            url = f"{c['oai_base']}?verb=ListRecords&metadataPrefix=arXiv&set={c['set']}&from={c['from_date']}"
        r = sess.get(url)
        fp = src_dir / "oai" / f"page_{i:04d}.xml"
        fp.write_bytes(r.content)
        root = ET.fromstring(r.content)
        recs = root.findall(".//o:record", ns)
        for rec in recs:
            cats = rec.find(".//a:categories", ns)
            if cats is not None and cats.text.split()[0].startswith(c["primary_category_prefix"]):
                n_primary += 1
        append_jsonl(src_dir / "manifest.jsonl", {
            "raw_id": f"ARXIVPAGE_{i:04d}", "source": "arxiv_astro_ph", "url": url, "http_status": r.status_code,
            "retrieved_at": now_iso(), "license": c["license"], "file": str(fp.relative_to(ROOT)).replace("\\", "/"),
            "sha256": file_sha256(fp), "extra": {"records": len(recs)}})
        log.info(f"arXiv sayfa {i}: {len(recs)} kayıt, birincil astro-ph toplam {n_primary}")
        t = root.find(".//o:resumptionToken", ns)
        token = t.text if t is not None and t.text else None
        i += 1
        if not token:
            break


# --------------------------------------------------------------------------- Wikipedia
def dl_wikipedia(key: str, dry: bool) -> None:
    c = CFG["sources"][key]
    lang = c["lang"]
    cat_ns = "Category:" if lang == "en" else "Kategori:"
    src_dir = RAW / "wikipedia" / lang
    (src_dir / "json").mkdir(parents=True, exist_ok=True)
    sess = PoliteSession(delay=CFG["http"]["wikipedia_delay_seconds"])
    list_re = re.compile(r"^(List of|Lists of|Timeline of|Index of|Glossary of)|(listesi|Listesi)$|^Liste")

    def members(cat: str, ctype: str) -> list[dict]:
        out, cont = [], {}
        while True:
            params = {"action": "query", "format": "json", "formatversion": "2", "generator": "categorymembers",
                      "gcmtitle": cat, "gcmtype": ctype, "gcmlimit": "500", "prop": "info|pageprops",
                      "ppprop": "wikibase_item", "maxlag": "5", **cont}
            d = sess.get(c["api"], params=params).json()
            out += d.get("query", {}).get("pages", [])
            if "continue" not in d:
                return out
            cont = d["continue"]

    cand_file = src_dir / "candidates.json"
    if cand_file.exists():
        chosen = json.loads(cand_file.read_text(encoding="utf-8"))
    else:
        chosen, seen = [], set()
        for cat in c["categories"]:
            full = cat_ns + cat
            pages = members(full, "page")
            subcats = members(full, "subcat")
            for sc in subcats[:40]:  # derinlik 1
                pages += members(sc["title"], "page")
            if not pages:
                log.warning(f"{lang}: kategori boş/bulunamadı: {full}")
                continue
            pages = [x for x in pages if x.get("ns") == 0 and x.get("length", 0) >= c["min_bytes"]
                     and not list_re.search(x["title"])]
            uniq = {x["pageid"]: x for x in pages}
            pages = sorted(uniq.values(), key=lambda x: -x.get("length", 0))
            added = 0
            for x in pages:
                if x["pageid"] in seen:
                    continue
                seen.add(x["pageid"])
                chosen.append({"pageid": x["pageid"], "title": x["title"], "length": x.get("length"),
                               "wikidata": x.get("pageprops", {}).get("wikibase_item"), "category": cat})
                added += 1
                if added >= c["per_category"]:
                    break
            log.info(f"{lang}: {full}: {len(uniq)} aday sayfa, {added} seçildi (toplam {len(chosen)})")
        chosen = chosen[: c["max_documents"]]
        cand_file.write_text(json.dumps(chosen, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info(f"wikipedia_{lang}: {len(chosen)} madde seçildi")
    if dry:
        return
    done = manifest_done(src_dir)
    for i, x in enumerate(chosen, 1):
        rid = f"WIKI{lang.upper()}_{x['pageid']}"
        if rid in done:
            continue
        params = {"action": "query", "format": "json", "formatversion": "2", "prop": "extracts|info|pageprops|revisions",
                  "explaintext": "1", "exsectionformat": "wiki", "inprop": "url", "rvprop": "ids|timestamp",
                  "ppprop": "wikibase_item", "pageids": str(x["pageid"]), "maxlag": "5"}
        r = sess.get(c["api"], params=params)
        fp = src_dir / "json" / f"{rid}.json"
        fp.write_bytes(r.content)
        page = r.json()["query"]["pages"][0]
        append_jsonl(src_dir / "manifest.jsonl", {
            "raw_id": rid, "source": f"wikipedia_{lang}", "url": page.get("fullurl"), "http_status": r.status_code,
            "retrieved_at": now_iso(), "license": "CC BY-SA 4.0 (Wikipedia contributors)",
            "file": str(fp.relative_to(ROOT)).replace("\\", "/"), "sha256": file_sha256(fp),
            "extra": {"title": x["title"], "category": x["category"], "wikidata": x["wikidata"],
                      "revid": (page.get("revisions") or [{}])[0].get("revid")}})
        if i % 200 == 0:
            log.info(f"wikipedia_{lang}: {i}/{len(chosen)}")
    log.info(f"wikipedia_{lang}: bitti")


# --------------------------------------------------------------------------- Hugging Face
def hf_snapshot(repo: str, dest: Path, license_: str, source: str) -> None:
    from huggingface_hub import HfApi, snapshot_download

    dest.mkdir(parents=True, exist_ok=True)
    info = HfApi().dataset_info(repo)
    snapshot_download(repo_id=repo, repo_type="dataset", local_dir=str(dest), revision=info.sha)
    append_jsonl(dest / "manifest.jsonl", {
        "raw_id": repo.replace("/", "__"), "source": source, "url": f"https://huggingface.co/datasets/{repo}",
        "http_status": 200, "retrieved_at": now_iso(), "license": license_, "extra": {"revision": info.sha}})
    log.info(f"HF {repo} indirildi (rev {info.sha[:8]})")


def dl_stackexchange(dry: bool) -> None:
    if not dry:
        c = CFG["sources"]["stackexchange"]
        hf_snapshot(c["hf_repo"], RAW / "stackexchange_space_qa", c["license"], "stackexchange_space_qa")


def dl_eval_reference(dry: bool) -> None:
    if dry:
        return
    for repo in CFG["sources"]["eval_reference"]:
        try:
            hf_snapshot(repo, p("eval_reference") / repo.replace("/", "__"), "see dataset card", "eval_reference")
        except Exception as e:
            log.warning(f"{repo} indirilemedi: {e}")


SOURCES = {
    "openstax": dl_openstax,
    "stackexchange": dl_stackexchange,
    "eval_reference": dl_eval_reference,
    "wikipedia_en": lambda d: dl_wikipedia("wikipedia_en", d),
    "wikipedia_tr": lambda d: dl_wikipedia("wikipedia_tr", d),
    "arxiv": dl_arxiv,
    "nasa_science": dl_nasa_science,
    "nasa_apod": dl_nasa_apod,
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="all", choices=["all", *SOURCES])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for name, fn in SOURCES.items():
        if a.source in ("all", name):
            log.info(f"=== {name} ===")
            fn(a.dry_run)
