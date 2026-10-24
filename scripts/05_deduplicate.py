"""05 — Tekrar eden dokümanları ayıklar ve metadata'yı tamamlar (Vize Rehberi §8, §9).

Exact duplicate : normalize edilmiş metnin (küçük harf + tek boşluk) SHA-256 hash'i aynı olanlar
Near duplicate  : kelime 5-gram shingle'ları üzerinde MinHash LSH ile aday bulma + gerçek Jaccard
                  benzerliği >= dedup.jaccard_threshold (0.85) olan çiftlerden biri elenir.
Hangisinin tutulacağı: önce birincil kaynak (OpenStax > NASA Science > APOD > Wikipedia EN > Wikipedia TR > arXiv),
eşitse daha uzun doküman.

Eşik doğrulaması için LSH aday çiftlerinden 50'si (yarısı eşiğin üstünden, yarısı altından; seed 42+5)
reports/qc/near_dup_pairs_review.csv'ye yazılır
(claude_* = yapay zekâ destekli ön inceleme, son_karar_* = grup üyesinin kararı; dolu kararlar korunur).
Çıktı: data/interim/corpus_v0.9.jsonl
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter

from datasketch import MinHash, MinHashLSH

from common import CFG, RemovalLog, get_logger, p, read_jsonl, rng, text_hash, write_jsonl
from domain_lexicon import subtopic_scores

log = get_logger("05_deduplicate")
D = CFG["dedup"]
PRIORITY = {"openstax": 0, "nasa_science": 1, "nasa_apod": 2, "wikipedia_en": 3, "wikipedia_tr": 4,
            "arxiv_astro_ph": 5}
SOURCE_NAME = {"openstax": "openstax_astronomy_2e", "nasa_science": "nasa_science", "nasa_apod": "nasa_apod",
               "wikipedia_en": "wikipedia_en", "wikipedia_tr": "wikipedia_tr", "arxiv_astro_ph": "arxiv_astro_ph"}

WIKI_CAT_HINT = {
    "Solar System": "solar_system", "Güneş Sistemi": "solar_system", "Comets": "solar_system",
    "Kuyruklu yıldızlar": "solar_system", "Asteroids": "solar_system", "Asteroitler": "solar_system",
    "Meteoroids": "solar_system", "Göktaşları": "solar_system", "Eclipses": "solar_system", "Tutulmalar": "solar_system",
    "Planets of the Solar System": "planets_moons", "Gezegenler": "planets_moons",
    "Güneş Sistemi gezegenleri": "planets_moons", "Natural satellites": "planets_moons",
    "Doğal uydular": "planets_moons", "Dwarf planets": "planets_moons", "Cüce gezegenler": "planets_moons",
    "Planetary science": "planets_moons", "Gezegen bilimi": "planets_moons",
    "Stars": "stars_stellar_evolution", "Yıldızlar": "stars_stellar_evolution",
    "Stellar evolution": "stars_stellar_evolution", "Yıldız evrimi": "stars_stellar_evolution",
    "Stellar astronomy": "stars_stellar_evolution", "Variable stars": "stars_stellar_evolution",
    "Değişen yıldızlar": "stars_stellar_evolution", "Neutron stars": "stars_stellar_evolution",
    "Nötron yıldızları": "stars_stellar_evolution", "Black holes": "stars_stellar_evolution",
    "Kara delikler": "stars_stellar_evolution", "Nebulae": "stars_stellar_evolution", "Bulutsular": "stars_stellar_evolution",
    "Galaxies": "galaxies", "Gökadalar": "galaxies", "Milky Way": "galaxies", "Samanyolu": "galaxies",
    "Galaxy clusters": "galaxies", "Physical cosmology": "cosmology", "Fiziksel kozmoloji": "cosmology",
    "Kozmoloji": "cosmology", "Exoplanetology": "exoplanets", "Exoplanets": "exoplanets", "Ötegezegenler": "exoplanets",
    "Space telescopes": "observatories_telescopes", "Uzay teleskopları": "observatories_telescopes",
    "Astronomical observatories": "observatories_telescopes", "Gözlemevleri": "observatories_telescopes",
    "Telescopes": "observatories_telescopes", "Teleskoplar": "observatories_telescopes",
    "Observational astronomy": "observatories_telescopes", "Space probes": "missions_spacecraft",
    "Uzay sondaları": "missions_spacecraft",
}
ARXIV_HINT = {"astro-ph.EP": "exoplanets", "astro-ph.SR": "stars_stellar_evolution", "astro-ph.GA": "galaxies",
              "astro-ph.CO": "cosmology", "astro-ph.IM": "observatories_telescopes",
              "astro-ph.HE": "stars_stellar_evolution"}


def norm_for_hash(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower()).strip()


def shingles(t: str, k: int) -> set[str]:
    w = re.findall(r"\w+", t.lower())
    if len(w) < k:
        return {" ".join(w)}
    return {" ".join(w[i:i + k]) for i in range(len(w) - k + 1)}


def subtopic_hint(d: dict) -> str | None:
    if d["source"].startswith("wikipedia"):
        return WIKI_CAT_HINT.get(d.get("wiki_category"))
    if d["source"] == "arxiv_astro_ph":
        return ARXIV_HINT.get((d.get("categories") or [""])[0])
    if d["source"] == "nasa_science":
        g = (d.get("group") or "")
        if g.startswith("mission:"):
            return "missions_spacecraft"
        for key, val in [("exoplanet", "exoplanets"), ("galax", "galaxies"), ("star", "stars_stellar_evolution"),
                         ("planets", "planets_moons"), ("moons", "planets_moons"), ("jupiter", "planets_moons"),
                         ("saturn", "planets_moons"), ("uranus", "planets_moons"), ("neptune", "planets_moons"),
                         ("mars", "planets_moons"), ("moon", "planets_moons"), ("dwarf-planets", "planets_moons"),
                         ("solar-system", "solar_system"), ("sun", "solar_system"), ("eclipse", "solar_system"),
                         ("comets", "solar_system"), ("asteroids", "solar_system"), ("big-bang", "cosmology"),
                         ("dark-", "cosmology"), ("universe", "cosmology")]:
            if key in g or key in (d.get("url") or ""):
                return val
    return None


def assign_subtopic(d: dict) -> str:
    s = subtopic_scores(d["text"][:20000])
    hint = subtopic_hint(d)
    if hint:
        s[hint] = s.get(hint, 0) + max(3, int(0.5 * max(s.values())))
    best = max(s, key=s.get)
    return best if s[best] > 0 else "general_astronomy"


def main() -> None:
    docs = list(read_jsonl(p("interim") / "filtered.jsonl"))
    docs.sort(key=lambda d: (PRIORITY[d["source"]], -len(d["text"]), d["raw_id"]))
    removed = RemovalLog(p("reports") / "removed_documents.csv", "dedup", reset=False)
    log.info(f"Girdi: {len(docs)} doküman")

    # ---- exact
    seen: dict[str, str] = {}
    uniq = []
    for d in docs:
        h = text_hash(norm_for_hash(d["text"]))
        if h in seen:
            removed.add(d["raw_id"], "duplicate", d["source"], f"same_sha256_as={seen[h]}")
            continue
        seen[h] = d["raw_id"]
        d["text_sha256"] = h
        uniq.append(d)
    n_exact = len(docs) - len(uniq)
    log.info(f"Exact duplicate: {n_exact}")

    # ---- near (aday eşiği 0.6: hem eşik üstü hem altı çiftleri inceleme için yakalar)
    k, perm, thr = D["shingle_words"], D["num_perm"], D["jaccard_threshold"]
    sh = {d["raw_id"]: shingles(d["text"], k) for d in uniq}
    mh = {}
    lsh = MinHashLSH(threshold=0.6, num_perm=perm)
    for d in uniq:
        m = MinHash(num_perm=perm, seed=CFG["project"]["random_seed"])
        for s in sh[d["raw_id"]]:
            m.update(s.encode("utf-8"))
        mh[d["raw_id"]] = m
        lsh.insert(d["raw_id"], m)
    by_id = {d["raw_id"]: d for d in uniq}
    rank = {d["raw_id"]: i for i, d in enumerate(uniq)}  # küçük = öncelikli
    pairs = []
    for rid in by_id:
        for other in lsh.query(mh[rid]):
            if other <= rid:
                continue
            a, b = sh[rid], sh[other]
            j = len(a & b) / max(len(a | b), 1)
            pairs.append((j, rid, other))
    drop = {}
    for j, a, b in sorted(pairs, reverse=True):
        if j < thr:
            continue
        keep, lose = (a, b) if rank[a] < rank[b] else (b, a)
        if keep in drop or lose in drop:
            continue
        drop[lose] = (keep, j)
    for lose, (keep, j) in drop.items():
        removed.add(lose, "near_duplicate", by_id[lose]["source"], f"jaccard={j:.3f} kept={keep}")
    final = [d for d in uniq if d["raw_id"] not in drop]
    log.info(f"Near duplicate (Jaccard>={thr}): {len(drop)}; aday çift: {len(pairs)}")

    # ---- eşik inceleme tablosu
    r = rng(5)
    # sıralama şart: LSH sorgu sonuçları küme (set) olarak döner ve sırası çalıştırmadan çalıştırmaya değişir;
    # sıralanmazsa aynı seed ile farklı inceleme örneklemi çıkıyordu (24.10.2026)
    hi = sorted(x for x in pairs if x[0] >= thr)
    lo = sorted(x for x in pairs if x[0] < thr)
    half = D["review_pairs"] // 2
    sample = r.sample(hi, min(half, len(hi))) + r.sample(lo, min(D["review_pairs"] - min(half, len(hi)), len(lo)))
    # İnceleme iki aşamalı ve ayrı sütunlarda: claude_* = yapay zekâ destekli ön inceleme, son_karar_* = grup
    # üyesinin nihai kararı. Script yeniden çalıştırılırsa doldurulmuş kararlar (id_a, id_b) eşleşmesiyle korunur.
    review_f = p("qc") / "near_dup_pairs_review.csv"
    review_cols = ["claude_tekrar_mi", "claude_gerekce", "son_karar_tekrar_mi", "insan_notu"]
    prev = {}
    if review_f.exists():
        with open(review_f, encoding="utf-8-sig") as f:
            prev = {(x["id_a"], x["id_b"]): x for x in csv.DictReader(f)}
    with open(review_f, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["jaccard", "above_threshold", "id_a", "id_b", "title_a", "title_b", "snippet_a", "snippet_b",
                    *review_cols])
        for j, a, b in sorted(sample, reverse=True):
            old = prev.get((a, b), {})
            w.writerow([f"{j:.3f}", j >= thr, a, b, by_id[a].get("title"), by_id[b].get("title"),
                        by_id[a]["text"][:400].replace("\n", " "), by_id[b]["text"][:400].replace("\n", " "),
                        *[old.get(c, "") for c in review_cols]])
    hist = Counter(round(int(x[0] * 20) / 20, 2) for x in pairs)

    # ---- metadata (Rehber §9)
    final.sort(key=lambda d: (d["source"], d["raw_id"]))
    out = []
    for i, d in enumerate(final, 1):
        group = d.get("wikidata") or d["raw_id"]  # EN/TR aynı madde -> aynı grup (split'te aynı kümeye)
        out.append({
            "document_id": f"DOC_{i:06d}", "title": d.get("title"), "source": SOURCE_NAME[d["source"]],
            "url": d.get("url"), "language": d["language"], "document_type": d["document_type"],
            "publication_year": d.get("publication_year"), "subtopic": assign_subtopic(d),
            "license": d.get("license"), "retrieved_at": d.get("retrieved_at"), "raw_id": d["raw_id"],
            "group_key": group, "char_count": len(d["text"]), "word_count": len(d["text"].split()),
            "text": d["text"]})
    write_jsonl(p("interim") / "corpus_v0.9.jsonl", out)
    removed.save()
    summary = {"input": len(docs), "exact_duplicates": n_exact, "near_duplicates": len(drop),
               "candidate_pairs": len(pairs), "jaccard_histogram": {str(k): v for k, v in sorted(hist.items())},
               "final": len(out), "threshold": thr, "shingle_words": k, "num_perm": perm}
    (p("reports") / "dedup_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info(f"Corpus v0.9: {len(out)} doküman")


if __name__ == "__main__":
    main()
