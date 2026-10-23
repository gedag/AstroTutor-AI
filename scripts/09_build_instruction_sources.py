"""09 — Instruction üretimi için kaynakları ve üretim işlerini (job) hazırlar.

A) StackExchange Space/Astronomy (CC BY-SA 4.0) -> 'soru_cevap' görev türü için aday Q&A çiftleri
   - cevapsız / düşük puanlı / çok kısa-uzun kayıtlar elenir
   - kapsam dışı etiketler (roket mühendisliği, şirketler, yazılım, maliyet, hukuk...) elenir
   - görsele dayanan sorular ("identify this object", "this image") elenir
   - üs kaybı düzeltmesi: "1.989 × 1030 kg" -> "1.989 × 10^30 kg" (veri kümesinde <sup> kaybolmuş)
   - değerlendirme setleriyle (Astro-mcqa, astro-mcq, HST-MCQ, Astrobench) 8-gram örtüşmesi olanlar elenir
B) Domain Corpus v1.0 -> diğer görev türleri için kaynak doküman seçimi (kaynak/alt konu dengeli) ve
   her dokümana taksonomi kotalarına göre görev türü ataması.
C) Kapsam dışı / bilgi yetersizliği örnekleri için tema listesi (kaynak dokümansız).

Çıktı: data/interim/instruction_jobs.jsonl (deterministik, seed 42), reports/removed_instructions.csv (stage=source)
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter, defaultdict

from common import CFG, ROOT, RemovalLog, get_logger, p, read_jsonl, rng, write_jsonl
from domain_lexicon import domain_score

log = get_logger("09_build_instruction_sources")
I = CFG["instruction"]

SE_DENY_TAGS = {"spacex", "rockets", "launch", "falcon-9", "engines", "engine-design", "propulsion", "fuel",
                "liquid-fuel", "spacex-starship", "falcon-heavy", "launch-vehicle", "launch-site", "cost", "python",
                "software", "data-analysis", "photography", "identify-this-object", "design", "design-alternative",
                "materials", "safety", "spacesuits", "colonization", "reuse", "cubesat", "communication-satellite",
                "thrust", "solid-fuel", "blue-origin", "law", "policy", "funding", "economics", "military",
                "space-law", "fiction", "movies", "budget", "commercial", "insurance", "jobs", "career",
                "education", "software-tools", "astropy", "programming", "equipment", "eyepiece", "mount",
                "telescope-making", "camera", "astrophotography", "light-pollution-filter", "food", "toilet",
                "medical", "health", "spacex-dragon", "starlink", "rocket-lab", "ula", "boeing", "virgin-galactic"}
IMAGE_HINT = re.compile(r"(this (image|picture|photo|video)|attached (image|picture)|see (the )?image|!\[)", re.I)
EXP_FIX = re.compile(r"(\d(?:\.\d+)?)\s?[×x]\s?10(-?[1-9]\d{0,2})\b")


def fix_exponents(t: str) -> str:
    return EXP_FIX.sub(lambda m: f"{m.group(1)} × 10^{m.group(2)}", t)


def eval_ngrams(n: int) -> set[tuple]:
    """Değerlendirme setlerindeki tüm soru/seçenek metinlerinin kelime n-gram'ları."""
    import pandas as pd

    grams = set()
    for f in glob.glob(str(p("eval_reference") / "**" / "*"), recursive=True):
        try:
            if f.endswith(".parquet"):
                df = pd.read_parquet(f)
            elif f.endswith(".csv"):
                df = pd.read_csv(f)
            elif f.endswith((".json", ".jsonl")):
                df = pd.read_json(f, lines=f.endswith(".jsonl"))
            else:
                continue
        except Exception as e:
            log.warning(f"eval okunamadı {f}: {e}")
            continue
        for col in df.columns:
            if df[col].dtype == object:
                for v in df[col].dropna().astype(str):
                    w = re.findall(r"\w+", v.lower())
                    grams.update(tuple(w[i:i + n]) for i in range(len(w) - n + 1))
    return grams


def overlaps(text: str, grams: set, n: int) -> int:
    w = re.findall(r"\w+", text.lower())
    return sum(1 for i in range(len(w) - n + 1) if tuple(w[i:i + n]) in grams)


def build_se(removed: RemovalLog, grams: set, n_target: int) -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(ROOT / "data/raw/stackexchange_space_qa/data/stackexchange_space_qa.parquet")
    cands = []
    for row in df.itertuples(index=False):
        rid = f"SE_{row.site}_{row.qid}"
        ans = row.answer_body if isinstance(row.answer_body, str) else ""
        q = f"{row.question_title}\n\n{row.question_body or ''}"
        tags = set(t for t in (row.question_tags or "").strip("|").split("|") if t)
        if not ans.strip():
            removed.add(rid, "no_answer", "stackexchange")
            continue
        if not (bool(row.answer_accepted) or (row.answer_score or 0) >= 5) or (row.question_score or 0) < 2:
            removed.add(rid, "low_score", "stackexchange", f"q={row.question_score} a={row.answer_score}")
            continue
        if not (300 <= len(ans) <= 3500) or len(q) > 2500:
            removed.add(rid, "length_out_of_range", "stackexchange", f"answer_chars={len(ans)}")
            continue
        if tags & SE_DENY_TAGS:
            removed.add(rid, "out_of_scope_tag", "stackexchange", ",".join(sorted(tags & SE_DENY_TAGS)))
            continue
        if IMAGE_HINT.search(q) or IMAGE_HINT.search(ans):
            removed.add(rid, "depends_on_image", "stackexchange")
            continue
        if domain_score(q + " " + ans) < 8:
            removed.add(rid, "out_of_domain", "stackexchange")
            continue
        if grams and overlaps(q + " " + ans, grams, I["decontam_ngram"]) > 0:
            removed.add(rid, "eval_overlap", "stackexchange")
            continue
        cands.append({"rid": rid, "site": row.site, "url": row.url, "qscore": int(row.question_score or 0),
                      "question": fix_exponents(q.strip()), "answer": fix_exponents(ans.strip()),
                      "tags": sorted(tags), "accepted": bool(row.answer_accepted)})
    log.info(f"StackExchange: {len(df)} kayıt -> {len(cands)} uygun aday")
    # site dengesi: astronomy %65 / space %35, her sitede soru puanına göre en iyiler, sonra karıştır
    r = rng(9)
    pick = []
    for site, share in (("astronomy", 0.65), ("space", 0.35)):
        cs = sorted([c for c in cands if c["site"] == site], key=lambda c: -c["qscore"])
        pick += cs[: int(n_target * share) + 1]
    r.shuffle(pick)
    return pick


def build_doc_jobs(quota: dict[str, int]) -> list[dict]:
    docs = []
    for split in ("train", "validation", "test"):
        # 12-14 örnek çıkarabilmek için uzun dokümanlar (arXiv özetleri doğası gereği kısa: >= 1000)
        docs += [d for d in read_jsonl(p("final") / f"{split}.jsonl")
                 if d["char_count"] >= (1000 if d["source"] == "arxiv_astro_ph" else 3000)]
    r = rng(10)
    by_src = defaultdict(list)
    for d in docs:
        by_src[d["source"]].append(d)
    # her kaynaktan hedef doküman payı (öğretici kaynaklar ağırlıklı, arXiv ileri seviye için az)
    share = {"openstax_astronomy_2e": 0.22, "nasa_science": 0.26, "wikipedia_en": 0.22, "wikipedia_tr": 0.12,
             "nasa_apod": 0.10, "arxiv_astro_ph": 0.08}
    total_examples = sum(quota.values())
    per_doc_avg = 12  # uzun dokümanlarda 14, orta 10, arXiv 5 -> ortalama
    n_docs = int(total_examples / per_doc_avg) + 1
    chosen = []
    for src, sh in share.items():
        pool = by_src.get(src, [])
        # alt konu dengesi: alt konulara göre round-robin
        sub = defaultdict(list)
        for d in pool:
            sub[d["subtopic"]].append(d)
        for v in sub.values():
            r.shuffle(v)
        want = int(n_docs * sh)
        keys = sorted(sub)
        i = 0
        while len([c for c in chosen if c["source"] == src]) < min(want, len(pool)):
            k = keys[i % len(keys)]
            if sub[k]:
                chosen.append(sub[k].pop())
            i += 1
    r.shuffle(chosen)
    remaining = dict(quota)
    jobs = []
    text_types = {"ozetleme", "coktan_secmeli_soru_uretimi", "siniflandirma"}
    for d in chosen:
        ep = I["examples_per_doc_job"]
        n = ep["long"] if d["char_count"] >= 6000 else ep["medium"] if d["char_count"] >= 3000 else ep["short"]
        if d["source"] == "arxiv_astro_ph":
            n = ep["arxiv"]
        types = []
        for _ in range(n):
            avail = {t: c for t, c in remaining.items() if c > 0 and types.count(t) < 3}
            if d["source"] == "arxiv_astro_ph":  # özetler kısa: anlatım/özet/neden-sonuç/ileri tanım
                avail = {t: c for t, c in avail.items() if t in ("tanim_aciklama", "seviyeli_anlatim", "ozetleme",
                                                                 "neden_sonuc", "coktan_secmeli_soru_uretimi")}
            if not avail:
                break
            t = r.choices(list(avail), weights=list(avail.values()))[0]
            types.append(t)
            remaining[t] -= 1
        if not types:
            continue
        levels = []
        for t in types:
            if d["source"] == "arxiv_astro_ph":
                levels.append("ileri")
            else:
                levels.append(r.choice(["baslangic", "orta", "ileri"]))
        jobs.append({"job_id": f"JOB_DOC_{d['document_id']}", "kind": "doc", "source_document": d["document_id"],
                     "source_url": d["url"], "source_name": d["source"], "language": d["language"],
                     "split": d["split"], "title": d["title"], "subtopic": d["subtopic"],
                     "task_types": types, "levels": levels, "includes_text_types": sorted(set(types) & text_types)})
    log.info(f"Doküman işleri: {len(jobs)} doküman, {sum(len(j['task_types']) for j in jobs)} örnek; "
             f"karşılanamayan kota: { {k: v for k, v in remaining.items() if v > 0} }")
    return jobs


REFUSAL_THEMES = [
    "astroloji ve burç yorumu", "kişisel fal / gelecek tahmini", "kripto para ve borsa fiyatı",
    "uzay şirketlerinin hisse fiyatı", "anlık konum (ISS şu an nerede gibi gerçek zamanlı veri)",
    "bugünkü hava durumu ve gözlem koşulu (gerçek zamanlı)", "tıbbi teşhis veya ilaç önerisi",
    "siyasi görüş ve seçim tahmini", "henüz gerçekleşmemiş görevlerin kesin sonucu",
    "kaynakta bulunmayan çok yeni keşif hakkında kesin sayı", "kişisel veriler / ünlülerin özel hayatı",
    "UFO komplo teorilerini doğrulama talebi", "düz dünya iddiasını kanıtlama talebi",
    "kesin olmayan bilimsel konuda kesin hüküm isteme (örn. evrende kesin olarak yaşam var mı)",
    "ödev/sınavda kopya isteme (cevapları doğrudan verme yerine öğretme)", "spor, yemek tarifi gibi alan dışı konular",
    "uzay temalı oyun hilesi isteme", "astronomik olmayan matematik ödevi",
]


def quotas() -> tuple[dict, int, int]:
    total = I["target_total"]
    quota = {k: round(v * total) for k, v in I["taxonomy"].items()}
    return quota, quota.pop("soru_cevap"), quota.pop("bilgi_yetersizligi_kapsam_disi")


def write_summary(jobs: list[dict], removed: RemovalLog) -> None:
    reasons = Counter(x["reason"] for x in removed.rows if x["stage"] == "source")
    doc_jobs = [j for j in jobs if j["kind"] == "doc"]
    (p("reports") / "instruction_sources_summary.json").write_text(json.dumps({
        "stackexchange_candidates_selected": sum(len(j["items"]) for j in jobs if j["kind"] == "se"),
        "stackexchange_removed": dict(reasons),
        "doc_jobs": len(doc_jobs), "doc_examples_planned": sum(len(j["task_types"]) for j in doc_jobs),
        "se_jobs": sum(1 for j in jobs if j["kind"] == "se"),
        "refusal_jobs": sum(1 for j in jobs if j["kind"] == "refusal"),
        "planned_by_type": dict(Counter(t for j in doc_jobs for t in j["task_types"]))}, indent=2,
        ensure_ascii=False), encoding="utf-8")


def main() -> None:
    """İki parça hâlinde çalışır; böylece corpus beklenirken kota boşa gitmez:
      --part se_ref : StackExchange + kapsam dışı işleri (corpus'a bağlı DEĞİL) -> iş listesini oluşturur
      --part doc    : corpus dokümanı işleri (Corpus v1.0 final olduktan sonra) -> iş listesine EKLER
    Var olan işler asla değiştirilmez (üretilmiş örneklerin job_id'leri ile uyumu korunur).
    """
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["se_ref", "doc"], required=True)
    a = ap.parse_args()
    jobs_file = p("interim") / "instruction_jobs.jsonl"
    jobs = list(read_jsonl(jobs_file))
    kinds = {j["kind"] for j in jobs}
    quota, se_n, ref_n = quotas()
    removed = RemovalLog(p("reports") / "removed_instructions.csv", "source", reset=False)

    if a.part == "se_ref":
        if kinds & {"se", "refusal"}:
            log.info("SE/kapsam dışı işleri zaten var; değiştirilmedi")
            return
        grams = eval_ngrams(I["decontam_ngram"])
        log.info(f"Değerlendirme setlerinden {len(grams):,} adet {I['decontam_ngram']}-gram")
        se = build_se(removed, grams, int(se_n * 1.10))  # LLM "skip" ve kural elemeleri için %10 fazla
        bs = I["se_items_per_job"]
        new = [{"job_id": f"JOB_SE_{i // bs:04d}", "kind": "se", "items": se[i:i + bs]} for i in range(0, len(se), bs)]
        r = rng(11)
        per = I["refusal_per_job"]
        for i in range(int(ref_n * 1.1 / per) + 1):
            new.append({"job_id": f"JOB_REF_{i:03d}", "kind": "refusal", "themes": r.sample(REFUSAL_THEMES, 3),
                        "n": per})
        removed.save()
    else:
        if "doc" in kinds:
            log.info("Doküman işleri zaten var; değiştirilmedi")
            return
        if not (p("final") / "train.jsonl").exists():
            raise SystemExit("Corpus v1.0 (data/final/train.jsonl) yok; önce 01-08 çalıştırılmalı")
        new = build_doc_jobs(quota)  # target_total zaten eleme payını içeriyor
    jobs += new
    write_jsonl(jobs_file, jobs)
    write_summary(jobs, removed)
    log.info(f"{len(new)} yeni iş eklendi; toplam: " + ", ".join(f"{k}={v}" for k, v in
                                                                 Counter(j["kind"] for j in jobs).items()))


if __name__ == "__main__":
    main()
