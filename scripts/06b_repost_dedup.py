"""06b — İkinci geçiş: üs düzeltmesi, APOD duyuru satırları ve yeniden yayın tekrarları (kalite kontrolünde bulundu).

Adımlar (çalışma sırasıyla):
0) Kaybolmuş üsler geri yazılır ("1.5 × 108 km" -> "1.5 × 10^8 km"; kurallar ve testler: scripts/exponent_fix.py).
1) APOD site duyurusu satırları ("Follow APOD on...", "Gallery: ...", "Open Science: Browse ...") silinir.
1b) NASA basın bülteni künyesi (kredi, iletişim blokları, "For more information... visit", yalnız bağlantı satırları)
    ve kişisel iletişim bilgisi (e-posta, telefon) silinir (scripts/press_boilerplate.py).
1c) 1000 karakterden kısa iletişim dizini sayfaları (contact_page) ve temizlikten sonra filtering.min_chars'ın
    altına düşen dokümanlar (too_short_after_06b) çıkarılır.
1d) Tek astronomi kategorisi kendi adını taşıyan kurgu/eser Wikipedia maddeleri (fiction_work_06b) çıkarılır.
1e) arXiv alt konusu birincil arXiv kategorisinden belirlenir (GA, CO, IM doğrudan; SR, EP, HE kategoriye uygun
    alt konular arasında anahtar kelimeyle).
2) Yeniden yayın tekrarı: aynı kaynaktan iki doküman
     nasa_apod    : kelime 5-gram Jaccard >= 0.50 VE karakter dizisi benzerliği (difflib) >= 0.85
     nasa_science : kelime 5-gram Jaccard >= 0.75 VE karakter dizisi benzerliği >= 0.90
   Wikipedia'ya uygulanmaz (farklı maddeler = farklı konular). Çiftten EN SON yayımlanan tutulur (yeniden
   yayında bilgiler güncelleniyor); instruction kaynağı olan doküman hiçbir zaman çıkarılmaz (ikisi de kaynaksa
   ikisi de tutulur ve loglanır).
Veri zaten işaretliyse (postprocess="06b") yalnız idempotent HTML kalıntısı düzeltmesi uygulanır
(scripts/html_residue.py; 03'te de var).

Neden ayrı adım: 24.10.2026'da near-duplicate eşik incelemesi (reports/qc/near_dup_pairs_review.csv), 0.85
eşiğinin hiç yanlış eleme yapmadığını ama APOD'un aynı açıklamayı yıllar sonra küçük düzeltmelerle yeniden
yayımladığı sayfaları (Jaccard 0.5–0.85) kaçırdığını gösterdi. Bunların bir kısmı farklı kümelerdeydi (sızıntı).
Genel eşiği düşürmek doğru değil: NASA'nın uydu sayfaları ortak şablona rağmen farklı uyduların bilgisini taşıyor
ve Jaccard 0.74'e kadar çıkıyor. Ayrıca 05'i değiştirmek DOC_ kimliklerini kaydırır ve instruction örneklerinin
kaynak bağını koparırdı. Bu yüzden bu adım 06'dan SONRA çalışır, kimlikleri ve kümeleri DEĞİŞTİRMEZ, yalnız
satır/doküman çıkarır (çıkan dokümanın kimliği boş kalır).

Girdi/çıktı: data/final/{train,validation,test}.jsonl (yerinde güncellenir). Elenenler: reports/removed_documents.csv
(stage=dedup2). Özet: reports/dedup2_summary.json.
"""
from __future__ import annotations

import difflib
import importlib
import json
import re

from datasketch import MinHash, MinHashLSH

from collections import Counter

from common import CFG, RemovalLog, get_logger, p, read_jsonl, write_jsonl
from domain_lexicon import _lower_tr, subtopic_scores, wiki_category_on_topic
from exponent_fix import fix_exponents
from html_residue import strip_html_residue
from press_boilerplate import clean_press, scrub_inline_pii

log = get_logger("06b_repost_dedup")
SPLITS = ("train", "validation", "test")
APOD_NOTICE = re.compile(
    r"^(Follow APOD|APOD (in|across) world languages|Almost Hyperspace|Portal Universe|Your Sky Surprise|"
    r"Note: How to find APOD|Free (APOD|Download)|Astrophysicists: Browse|Open Science: Browse|Gallery:|"
    r"Notable APOD|New: APOD|Tonight:|Discover the cosmos)", re.I)
RULES = {"nasa_apod": (0.50, 0.85), "nasa_science": (0.75, 0.90)}
# iletişim dizini sayfaları (ör. /mission/psyche/media-contacts/); 1000 karakterden uzunsa içerik barındırabilir, tutulur
WORK_CATEGORY = re.compile(r"\bfilms?\b|novels?\b|\bsongs?\b|albums|television|video games|comics|anime|manga|"
                           r"\bfiction\b|filmler|filmleri|romanlar|şarkı|albüm|dizileri|oyunları|kurgu")
CONTACT_URL = re.compile(r"/(media-contacts?|media-resources|media-relations|contacts?|contact-us|press-contacts?)/?$",
                         re.I)


HE_GAL = re.compile(r"\b(qsos?|quasars?|agns?|active galactic|blazars?|bl lac\w*|seyferts?|supermassive|smbhs?|"
                    r"radio galax\w*|fsrqs?|galax\w*|m87\*?|sgr a\*|sagittarius a\*|tidal disruption|tdes?)\b")
HE_STAR = re.compile(r"\b(neutron stars?|pulsars?|magnetars?|x-ray binar\w*|white dwarfs?|supernovae?|supernova "
                     r"remnants?|stellar|stars?|grbs?|gamma-ray bursts?|kilonovae?|black hole binar\w*|microquasars?|"
                     r"compact objects?|binary|black holes?|bhs?)\b")
HE_AGN_STRONG = re.compile(r"\b(qsos?|quasars?|agns?|active galactic|blazars?|bl lac\w*|seyferts?|supermassive|"
                           r"smbhs?|m87\*?|sgr a\*|sagittarius a\*|tidal disruption|tdes?)\b")
HE_COS = re.compile(r"\b(cosmolog\w*|dark matter|primordial|early universe|cmb|cosmic microwave|reionization)\b")


def arxiv_subtopic(cat: str, text: str, current: str) -> str:
    """Birincil arXiv kategorisi -> alt konu. Kategori birden fazla alt konuyu kapsıyorsa (SR, EP, HE) karar,
    yalnız o kategoriye uygun alt konular arasında anahtar kelime puanıyla verilir."""
    fixed = {"astro-ph.GA": "galaxies", "astro-ph.CO": "cosmology", "astro-ph.IM": "observatories_telescopes"}
    if cat in fixed:
        return fixed[cat]
    if cat == "astro-ph.HE":
        # Genel anahtar kelime listesinde "black hole" yıldızlara bağlı ve "QSO/blazar/AGN" yok; bu yüzden HE için
        # ayrı terimler: kompakt yıldız nesneleri / aktif galaksi çekirdekleri / kozmoloji. Sinyal yoksa (ör. kozmik
        # ışın sağanakları, nötrino dedektörleri) general_astronomy.
        t = text.lower()
        # güçlü aktif galaksi çekirdeği işareti en az iki kez geçiyorsa galaksiler (kuasar makaleleri "black hole"
        # sözcüğünü "QSO"dan sık kullanabiliyor)
        if len(HE_AGN_STRONG.findall(t)) >= 2:
            return "galaxies"
        # galaksi terimleri 2 kat: "supermassive", "QSO", "M87" açık sinyaldir; "black hole" iki bağlamda da geçer
        sc = {"galaxies": 2 * len(HE_GAL.findall(t)), "stars_stellar_evolution": len(HE_STAR.findall(t)),
              "cosmology": len(HE_COS.findall(t))}
        best = max(sc, key=lambda k: (sc[k], k == "stars_stellar_evolution"))
        return best if sc[best] > 0 else "general_astronomy"
    allowed = {"astro-ph.SR": ["stars_stellar_evolution", "solar_system"],
               "astro-ph.EP": ["exoplanets", "planets_moons", "solar_system"]}.get(cat)
    if not allowed:
        return current
    s = subtopic_scores(text)
    best = max(allowed, key=lambda k: (s.get(k, 0), -allowed.index(k)))  # eşitlikte listedeki ilk (varsayılan)
    return best


def date_key(d: dict) -> tuple:
    m = re.search(r"apod-(\d{4})-([a-z]+)-(\d{1,2})-", d.get("url") or "")
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
              "november", "december"]
    if m and m.group(2) in months:
        return (int(m.group(1)), months.index(m.group(2)), int(m.group(3)), d["document_id"])
    return (d.get("publication_year") or 9999, 0, 0, d["document_id"])


def main() -> None:
    d05 = importlib.import_module("05_deduplicate")
    docs = {s: list(read_jsonl(p("final") / f"{s}.jsonl")) for s in SPLITS}
    # Her doküman "postprocess": "06b" işareti taşır. 06 final dosyalarını yeniden yazınca işaret kalkar ve adım
    # yeniden uygulanır; işaretli veriye ikinci kez çalıştırılırsa hiçbir şey yapılmaz (kayıtlar ezilmez).
    if all(d.get("postprocess") == "06b" for s in SPLITS for d in docs[s]):
        # Yalnız idempotent metin düzeltmesi uygulanır: HTML kalıntısı (24.10.2026 denetimi; 03'e de eklendi, böylece
        # sıfırdan çalıştırmada aynı sonuç çıkar). Doküman çıkarılmaz, kayıtlar ezilmez.
        n_html, touched = 0, []
        for s in SPLITS:
            for d in docs[s]:
                t, k = strip_html_residue(d["text"])
                if k:
                    n_html += k
                    touched.append(d["document_id"])
                    d["text"] = t
                    d["char_count"], d["word_count"] = len(t), len(t.split())
            if any(d["document_id"] in touched for d in docs[s]):
                tmp = p("final") / f"{s}.jsonl.tmp"
                write_jsonl(tmp, docs[s])
                tmp.replace(p("final") / f"{s}.jsonl")
        if touched:
            f = p("reports") / "dedup2_summary.json"
            sm = json.loads(f.read_text(encoding="utf-8"))
            sm["html_residue_fixes"] = sm.get("html_residue_fixes", 0) + n_html
            sm["html_residue_docs"] = sorted(set(sm.get("html_residue_docs", [])) | set(touched))
            f.write_text(json.dumps(sm, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info(f"Bu adım mevcut final veriye zaten uygulanmış; yalnız HTML kalıntısı düzeltmesi: {n_html} kalıntı, "
                 f"{len(touched)} doküman {touched}")
        return
    removed = RemovalLog(p("reports") / "removed_documents.csv", "dedup2", reset=False)
    # 0) kaybolmuş üsler (scripts/exponent_fix.py): "1.5 × 108 km" -> "1.5 × 10^8 km"
    n_exp, exp_docs = 0, Counter()
    for s in SPLITS:
        for d in docs[s]:
            t, k = fix_exponents(d["text"])
            if k:
                n_exp += k
                exp_docs[d["source"]] += 1
                d["text"] = t
                d["char_count"], d["word_count"] = len(t), len(t.split())
    log.info(f"Üs düzeltmesi: {n_exp} ifade, {sum(exp_docs.values())} doküman {dict(exp_docs)}")
    # 1) APOD duyuru satırları
    n_lines = n_docs_touched = 0
    for s in SPLITS:
        for d in docs[s]:
            if d["source"] != "nasa_apod":
                continue
            lines = d["text"].splitlines()
            keep = [x for x in lines if not APOD_NOTICE.match(x.strip())]
            if len(keep) != len(lines):
                n_lines += len(lines) - len(keep)
                n_docs_touched += 1
                d["text"] = "\n".join(keep).strip()
                d["char_count"], d["word_count"] = len(d["text"]), len(d["text"].split())
    log.info(f"APOD duyuru satırı: {n_lines} satır, {n_docs_touched} doküman")

    # 1b) NASA basın bülteni künyesi ve kişisel iletişim bilgisi (scripts/press_boilerplate.py)
    press, press_docs, pii_inline, big_cut = Counter(), 0, 0, []
    for s in SPLITS:
        for d in docs[s]:
            if d["source"] not in ("nasa_science", "nasa_apod"):
                continue
            t, k = clean_press(d["text"])
            t, k2 = scrub_inline_pii(t)
            if len(t) < 0.7 * len(d["text"]):
                big_cut.append((round(1 - len(t) / max(len(d["text"]), 1), 2), d["document_id"], d["url"]))
            if sum(k.values()) or k2:
                press.update(k)
                pii_inline += k2
                press_docs += 1
                d["text"] = t
                d["char_count"], d["word_count"] = len(t), len(t.split())
    log.info(f"Basın künyesi/iletişim: {dict(press)}, satır içi e-posta/telefon {pii_inline}, {press_docs} doküman")
    # güvenlik kontrolü: bu adımda metninin %30'undan fazlasını kaybeden doküman elle incelenmeli
    for x in sorted(big_cut, reverse=True):
        log.warning(f"Basın temizliği metnin %{100 * x[0]:.0f}'ini sildi: {x[1]} {x[2]}")

    allx = {d["document_id"]: d for s in SPLITS for d in docs[s]}
    sources = {j["source_document"] for j in read_jsonl(p("interim") / "instruction_jobs.jsonl")
               if j.get("kind") == "doc"}
    # 1c) iletişim dizini sayfaları ve temizlikten sonra çok kısa kalan dokümanlar (instruction kaynağı asla çıkmaz)
    other_drop: dict[str, tuple[str, str]] = {}
    for i, d in allx.items():
        if i in sources:
            continue
        if d["source"] == "nasa_science" and CONTACT_URL.search(d["url"] or "") and len(d["text"]) < 1000:
            other_drop[i] = ("contact_page", f"{len(d['text'])} karakter; {d['url']}")
        elif len(d["text"]) < CFG["filtering"]["min_chars"]:
            other_drop[i] = ("too_short_after_06b", f"{len(d['text'])} karakter")
    # 1d) Wikipedia kurgu/eser maddeleri: tek astronomi kategorisi maddenin KENDİ ADINI taşıyan kategoriyse
    # ("Treasure Planet" filmi -> kategori "Treasure Planet" ~ "planet") ve madde film/roman/şarkı gibi bir eser
    # kategorisindeyse alan dışıdır. (04'te düzeltilmedi: 04'ün sonucu değişirse DOC_ kimlikleri kayar.)
    wiki_cats = {}
    for lang in ("en", "tr"):
        f = p("raw") / "wikipedia" / lang / "page_categories.json"
        if f.exists():
            for pid, cs in json.loads(f.read_text(encoding="utf-8")).items():
                wiki_cats[f"WIKI{lang.upper()}_{pid}"] = cs
    for i, d in allx.items():
        if i in sources or i in other_drop or not d["source"].startswith("wikipedia") or d["raw_id"] not in wiki_cats:
            continue
        cs = wiki_cats[d["raw_id"]]
        title, base = _lower_tr(d["title"]), _lower_tr(re.sub(r"\s*\(.*?\)\s*$", "", d["title"]))
        non_epon = [c for c in cs if _lower_tr(c) not in (title, base)]
        if any(WORK_CATEGORY.search(_lower_tr(c)) for c in cs) and not wiki_category_on_topic(non_epon, d["text"]):
            other_drop[i] = ("fiction_work_06b", f"{d['title']} | kategoriler: {'; '.join(cs[:6])}")
    log.info(f"İletişim sayfası / kısa kalan / eser: {len(other_drop)} doküman "
             f"{dict(Counter(v[0] for v in other_drop.values()))}")

    # 1e) arXiv alt konusu: yazarın seçtiği ve moderatörün onayladığı birincil arXiv kategorisinden
    # (05'te yalnız ek puandı; anahtar kelimeler baskın çıkınca "astro-ph.HE" makalelerinin %92'si, kuasar ve
    # blazarlar dahil, "stars" etiketi alıyordu — 24.10.2026 corpus incelemesi).
    arx_cat = {}
    for r in read_jsonl(p("extracted") / "arxiv_astro_ph.jsonl"):
        arx_cat[r["raw_id"]] = (r.get("categories") or [""])[0]
    relabel = Counter()
    for i, d in allx.items():
        if d["source"] != "arxiv_astro_ph":
            continue
        new = arxiv_subtopic(arx_cat.get(d["raw_id"], ""), d["text"], d["subtopic"])
        if new != d["subtopic"]:
            relabel[(d["subtopic"], new)] += 1
            d["subtopic"] = new
    log.info(f"arXiv alt konu düzeltmesi: {sum(relabel.values())} doküman; {dict(relabel.most_common(8))}")
    for i in other_drop:
        allx.pop(i)

    # 2) yeniden yayın tekrarları
    drop: dict[str, tuple[str, float, float]] = {}
    both_sources = []
    for src, (jthr, cthr) in RULES.items():
        ids = sorted(i for i, d in allx.items() if d["source"] == src)
        sh = {i: d05.shingles(allx[i]["text"], 5) for i in ids}
        lsh, mh = MinHashLSH(threshold=jthr, num_perm=128), {}
        for i in ids:
            x = MinHash(num_perm=128)
            for g in sh[i]:
                x.update(g.encode("utf-8"))
            mh[i] = x
            lsh.insert(i, x)
        pairs = []
        for i in ids:
            for k in lsh.query(mh[i]):
                if i < k:
                    jac = len(sh[i] & sh[k]) / max(len(sh[i] | sh[k]), 1)
                    if jac >= jthr:
                        ch = difflib.SequenceMatcher(None, allx[i]["text"], allx[k]["text"], autojunk=False).ratio()
                        if ch >= cthr:
                            pairs.append((ch, jac, i, k))
        for ch, jac, a, b in sorted(pairs, reverse=True):
            if a in drop or b in drop:
                continue
            # en son yayımlanan tutulur: yeniden yayınlarda bilgi güncelleniyor (ör. Veil Nebula yaşı
            # 2009'da "7,500 yıl", 2012'de "9,000 yıl")
            lose, keep = sorted((a, b), key=lambda i: date_key(allx[i]))
            if lose in sources:
                keep, lose = lose, keep
            if lose in sources:
                both_sources.append((a, b))
                continue
            drop[lose] = (keep, jac, ch)
        log.info(f"{src}: {len(pairs)} yeniden yayın çifti (Jaccard>={jthr}, karakter>={cthr})")
    cross = 0
    for lose, (keep, jac, ch) in sorted(drop.items()):
        cross += allx[lose]["split"] != allx[keep]["split"]
        removed.add(allx[lose]["raw_id"], "repost_duplicate", allx[lose]["source"],
                    f"{lose} -> tutulan {keep} ({allx[keep]['split']}); jaccard={jac:.3f} karakter={ch:.3f}")
    by_id_all = {d["document_id"]: d for s in SPLITS for d in docs[s]}
    for i, (reason, detail) in sorted(other_drop.items()):
        removed.add(by_id_all[i]["raw_id"], reason, by_id_all[i]["source"], f"{i}: {detail}")
    removed.save()
    drop_ids = set(drop) | set(other_drop)
    for s in SPLITS:
        out = [{**d, "postprocess": "06b"} for d in docs[s] if d["document_id"] not in drop_ids]
        tmp = p("final") / f"{s}.jsonl.tmp"
        write_jsonl(tmp, out)
        tmp.replace(p("final") / f"{s}.jsonl")
    summary = {"exponent_fixes": n_exp, "exponent_fixed_docs_by_source": dict(exp_docs),
               "apod_notice_lines": n_lines, "apod_docs_touched": n_docs_touched,
               "press_boilerplate_lines": dict(press), "press_docs_touched": press_docs, "pii_inline_scrubbed": pii_inline,
               "press_big_cut_docs": [x[1] for x in sorted(big_cut, reverse=True)],
               "repost_removed": len(drop),
               "repost_removed_by_source": {s: sum(1 for x in drop if allx[x]["source"] == s) for s in RULES},
               "removed_pairs_across_splits": cross, "kept_both_instruction_sources": both_sources,
               "rules": {k: {"jaccard": v[0], "char_ratio": v[1]} for k, v in RULES.items()},
               "other_removed": dict(Counter(v[0] for v in other_drop.values())),
               "arxiv_subtopic_relabeled": sum(relabel.values()),
               "final_docs": sum(len(docs[s]) for s in SPLITS) - len(drop_ids)}
    (p("reports") / "dedup2_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                                       encoding="utf-8")
    log.info(f"Yeniden yayın tekrarı: {len(drop)} doküman çıkarıldı ({cross} çift farklı kümelerdeydi); "
             f"final {summary['final_docs']}")


if __name__ == "__main__":
    main()
