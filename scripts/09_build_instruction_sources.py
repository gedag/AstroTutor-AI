"""09 — Instruction üretimi için kaynakları ve üretim işlerini (job) hazırlar (Instruction v2.0, İngilizce).

A) StackExchange Space/Astronomy (CC BY-SA 4.0) -> 'question_answering' görev türü. v2.0'da Gemini KULLANILMAZ:
   orijinal İngilizce soru (başlık + gövde) ve en iyi cevap metni DEĞİŞTİRİLMEDEN alınır (Eda kararı 09.11.2026).
   - cevapsız / düşük puanlı / çok kısa-uzun kayıtlar elenir
   - kapsam dışı etiketler (roket mühendisliği, şirketler, yazılım, maliyet, hukuk...) elenir
   - görsele dayanan sorular ("identify this object", "this image") elenir
   - metni değiştirmeden kullanılamayacak kayıtlar elenir: LaTeX/MathJax, @kullanıcı, bağlantı, HTML/kod kalıntısı,
     dipnot numarası, kaybolmuş üs ("1.989 × 1030 kg"), boşta kalan atıf ("this answer", "see below", "EDIT",
     "comments") (10.11.2026 ölçümü: v1.0 filtrelerinden geçen 10.568 kaydın ~5.700'ü temiz)
   - değerlendirme setleriyle (Astro-mcqa, astro-mcq, HST-MCQ, Astrobench) 8-gram örtüşmesi olanlar elenir
   Seviyeyi LLM yargıç atar (11).
B) Domain Corpus -> diğer görev türleri için kaynak doküman seçimi (kaynak/alt konu dengeli; paylar config'te) ve
   her dokümana taksonomi kotalarına göre görev türü ataması.
C) Kapsam dışı / bilgi yetersizliği örnekleri için tema listesi (kaynak dokümansız).

Çıktı: data/interim/instruction_jobs.jsonl (deterministik, seed 42), reports/removed_instructions.csv (stage=source)
"""
from __future__ import annotations

import csv
import glob
import json
import re
from collections import Counter, defaultdict

import pyarrow.parquet as pq

from common import CFG, ROOT, RemovalLog, get_logger, p, read_jsonl, rng, write_jsonl
from domain_lexicon import domain_score
from exponent_fix import fix_exponents as exponent_loss
from press_boilerplate import EMAIL, PHONE

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
# v2.0: metin değiştirilmediği için bu öğeleri içeren kayıtlar düzeltilmez, ELENİR (neden removed_instructions.csv'de)
SE_LATEX = re.compile(r"\$[^$\n]+\$|\\(?:frac|mathrm|times|sqrt|rm|odot|cdot|Delta|alpha|text|left|right)\b")
SE_MENTION = re.compile(r"(?<![\w.])@\w+")
SE_URL = re.compile(r"https?://|www\.", re.I)
SE_MARKUP = re.compile(r"(?m)<[a-zA-Z/][^>]*>|&[a-z]+;|`|^\s*>")
SE_FOOTNOTE = re.compile(r"\[\d+\]")
# Cevapta, metinde olmayan bir şeye (silinmiş bağlantı, başka cevap, yorumlar, görsel) ya da düzenleme geçmişine atıf
SE_DANGLING = re.compile(r"\b(?:this|the following|the above|that|here is a|see this) (?:link|answer|blog|article|post|"
                         r"page|image|picture|graph|diagram|figure|video|spreadsheet|table|chart|plot)\b|"
                         r"\bclick here\b|\bsee (?:here|below|above)\b|\bother answers?\b|\bcomments?\b|\bEDIT\b|"
                         r"\bupdate:|\bupvote|\bdownvote", re.I)
# Soruda silinmiş görsele/videoya/bağlantıya atıf ("pictures ... such as this:", "In the video ...", "this graph").
# Tek başına "image"/"video" kelimesi aranmaz ("Looking at an image of the orbiter" zararsız). 10.11.2026 pilotunda
# seçilen 502 sorunun 67'sinde soruda boşta atıf vardı (önce yalnız cevap kontrol ediliyordu).
SE_Q_MEDIA = re.compile(r"\b(?:such as|like|see|as in|as shown in|shown in) this\s*[:.]|\bthis:\s*(?:\n|\.\.\.)|"
                        r"\b(?:in|from|watching) (?:the|this) (?:video|clip)\b|"
                        r"\bthis (?:video|clip|picture|image|photo|screenshot|graph|diagram|figure|plot|chart)\b", re.I)


def se_text_issue(q: str, ans: str) -> str | None:
    """Metni değiştirmeden kullanılamayacak bir öğe varsa nedenini döndürür (v2.0)."""
    both = q + "\n" + ans
    for name, pat in (("latex", SE_LATEX), ("email", EMAIL), ("phone", PHONE), ("user_mention", SE_MENTION),
                      ("url", SE_URL), ("markup", SE_MARKUP), ("footnote", SE_FOOTNOTE)):
        m = pat.search(both)
        if m:
            return f"{name}:{m.group(0)[:40]}"
    m = SE_DANGLING.search(ans)
    if m:
        return f"dangling_reference:{m.group(0)[:40]}"
    m = SE_DANGLING.search(q) or SE_Q_MEDIA.search(q)
    if m:
        return f"dangling_reference_in_question:{m.group(0)[:40]}"
    if exponent_loss(both)[1]:
        return "exponent_loss"
    return None


# Sızıntı kontrolüne girmeyen sütunlar: kimlik/etiket alanları ve Hubble MCQ'nun soruların üretildiği bağlam pasajı
# (source_document; corpus ile örtüşmesi validate_datasets.py'de ayrıca raporlanır)
EVAL_ID_COLS = {"uid", "id", "model_id", "mcq_source", "labels", "permutation_idx", "answerable"}
EVAL_CONTEXT_COLS = {"source_document"}


def eval_ngrams(n: int, context: bool = False) -> set[tuple]:
    """Değerlendirme setlerindeki soru/seçenek/cevap/açıklama metinlerinin kelime n-gram'ları.
    context=True: yalnız soruların üretildiği bağlam pasajları (Hubble MCQ `source_document`).

    24.10.2026 hata düzeltmesi: ilk sürüm yalnız `dtype == object` sütunlara bakıyordu; pandas 3'te metin sütunları
    `str` tipinde olduğu için Astrobench, Astro-mcqa ve Hubble MCQ hiç okunmuyordu (yalnız astro-mcq'nun liste
    sütunları giriyordu: 5.853 n-gram)."""
    import pandas as pd

    grams = set()
    for f in glob.glob(str(p("eval_reference") / "**" / "*"), recursive=True):
        if f.endswith("manifest.jsonl"):
            continue
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
            if col in EVAL_ID_COLS or ((col in EVAL_CONTEXT_COLS) != context):
                continue
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
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
        issue = se_text_issue(q, ans)
        if issue:
            removed.add(rid, "not_usable_verbatim", "stackexchange", issue)
            continue
        if grams and overlaps(q + " " + ans, grams, I["decontam_ngram"]) > 0:
            removed.add(rid, "eval_overlap", "stackexchange")
            continue
        # Metin olduğu gibi: yalnız baştaki/sondaki boşluk atılır
        cands.append({"rid": rid, "site": row.site, "url": row.url, "qscore": int(row.question_score or 0),
                      "question": q.strip(), "answer": ans.strip(),
                      "tags": sorted(tags), "accepted": bool(row.answer_accepted)})
    log.info(f"StackExchange: {len(df)} kayıt -> {len(cands)} uygun aday")
    # site dengesi (config: se_site_share), her sitede soru puanına göre en iyiler (eşitlikte kimlik sırası), sonra karıştır
    r = rng(9)
    pick = []
    # sözlükler ADA GÖRE sıralı okunur: config.yaml'da satırların sırası değişse de seçim aynı kalır (10.11.2026)
    for site, share in sorted(I["se_site_share"].items()):
        cs = sorted([c for c in cands if c["site"] == site], key=lambda c: (-c["qscore"], c["rid"]))
        pick += cs[: int(n_target * share) + 1]
    r.shuffle(pick)
    return pick


def build_doc_jobs(quota: dict[str, int], exclude_docs: frozenset = frozenset(), per_type_cap: int = 3,
                   seed_offset: int = 10, batch: str | None = None) -> list[dict]:
    """exclude_docs: zaten işi olan dokümanlar (ek pakette aynı doküman ikinci kez kullanılmaz).
    per_type_cap: bir dokümandan aynı görev türünden en fazla kaç örnek istenir."""
    docs = []
    for split in ("train", "validation", "test"):
        # 12-14 örnek çıkarabilmek için uzun dokümanlar (arXiv özetleri doğası gereği kısa: ayrı sınır)
        docs += [d for d in read_jsonl(p("final") / f"{split}.jsonl")
                 if d["char_count"] >= (I["arxiv_min_chars"] if d["source"] == "arxiv_astro_ph" else I["doc_min_chars"])
                 and d["document_id"] not in exclude_docs]
    r = rng(seed_offset)
    by_src = defaultdict(list)
    for d in docs:
        by_src[d["source"]].append(d)
    # her kaynaktan hedef doküman payı (config: source_share; öğretici kaynaklar ağırlıklı, arXiv ileri seviye için az)
    share = I["source_share"]
    total_examples = sum(quota.values())
    # Aday doküman sayısı bilerek fazla tutulur (ortalama ~11,7 örnek/doküman yerine 8 varsayılır): işler
    # sırayla oluşturulur ve görev türü kotaları dolunca kalan adaylar iş almaz. İlk sürüm 12 varsayınca
    # kotanın 369 örneği karşılanamıyordu (23.10.2026).
    n_docs = int(total_examples / 8) + 1
    per_doc = per_type_cap * len(quota)  # tek türlü pakette doküman başına en fazla per_type_cap örnek çıkar
    if per_doc <= 8:
        # APOD'da uzun doküman yok ve kaynak payları aşağı yuvarlanıyor: aday sayısı %50 fazla tutulur (ek2, 24.10.2026)
        n_docs = int(total_examples / per_doc * 1.5) + 1
    chosen = []
    for src, sh in sorted(share.items()):  # config sırasından bağımsız (10.11.2026)
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
    text_types = {"summarization", "mcq_generation", "classification"}
    for d in chosen:
        ep = I["examples_per_doc_job"]
        n = ep["long"] if d["char_count"] >= 6000 else ep["medium"] if d["char_count"] >= 3000 else ep["short"]
        if d["source"] == "arxiv_astro_ph":
            n = ep["arxiv"]
        types = []
        for _ in range(n):
            avail = {t: c for t, c in remaining.items() if c > 0 and types.count(t) < per_type_cap}
            if d["source"] == "arxiv_astro_ph":  # özetler kısa: anlatım/özet/neden-sonuç/ileri tanım
                avail = {t: c for t, c in avail.items() if t in ("definition_explanation", "leveled_explanation",
                                                                 "summarization", "cause_effect", "mcq_generation")}
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
                levels.append("advanced")
            else:
                levels.append(r.choice(I["levels"]))
        jobs.append({"job_id": f"JOB_DOC_{d['document_id']}", "kind": "doc", "source_document": d["document_id"],
                     "source_url": d["url"], "source_name": d["source"], "language": d["language"],
                     "split": d["split"], "title": d["title"], "subtopic": d["subtopic"],
                     "task_types": types, "levels": levels, "includes_text_types": sorted(set(types) & text_types),
                     **({"batch": batch} if batch else {})})
    log.info(f"Doküman işleri: {len(jobs)} doküman, {sum(len(j['task_types']) for j in jobs)} örnek; "
             f"karşılanamayan kota: { {k: v for k, v in remaining.items() if v > 0} }")
    return jobs


REFUSAL_THEMES = [  # v1.0 temalarının İngilizcesi
    "astrology and horoscope readings", "personal fortune telling / predicting the future",
    "cryptocurrency and stock prices", "share prices of space companies",
    "real-time position (e.g. where the ISS is right now)", "today's weather and observing conditions (real-time)",
    "medical diagnosis or medication advice", "political opinions and election predictions",
    "the definite outcome of missions that have not happened yet",
    "exact figures about very recent discoveries it has no reliable information on",
    "personal data / private lives of celebrities", "requests to confirm UFO conspiracy theories",
    "requests to prove the flat Earth claim",
    "demanding a definitive verdict on an unsettled scientific question (e.g. is there definitely life elsewhere)",
    "asking for answers to cheat on homework or an exam (teach instead of giving answers)",
    "off-topic subjects such as sports or recipes", "cheats for space-themed video games",
    "non-astronomy math homework",
]


def quotas() -> tuple[dict, int, int]:
    total = I["target_total"]
    # ADA GÖRE sıralı: görev ataması kotaların sırasına göre rastgele sayı tükettiği için config.yaml'daki
    # satır sırası sonucu değiştiriyordu (aynı ayarlarla 287 / sıra değişince 283 iş; 10.11.2026 denetimi)
    quota = {k: round(v * total) for k, v in sorted(I["taxonomy"].items())}
    return quota, quota.pop("question_answering"), quota.pop("out_of_scope_refusal")


def write_summary(jobs: list[dict], removed: RemovalLog) -> None:
    reasons = Counter(x["reason"] for x in removed.rows if x["stage"] == "source")
    if not reasons and removed.path.exists():
        # doc / doc_supplement çalıştırmalarında "source" kayıtları bellekte yoktur (RemovalLog kendi aşamasını
        # yeniden yazmak için dışarıda bırakır); özet dosyadaki kayıtlardan hesaplanır. İlk sürüm burada {} yazıyordu.
        with open(removed.path, encoding="utf-8") as f:
            reasons = Counter(r["reason"] for r in csv.DictReader(f) if r["stage"] == "source")
    se_file = ROOT / "data/raw/stackexchange_space_qa/data/stackexchange_space_qa.parquet"
    se_total = pq.ParquetFile(se_file).metadata.num_rows if se_file.exists() else None
    doc_jobs = [j for j in jobs if j["kind"] == "doc"]
    (p("reports") / "instruction_sources_summary.json").write_text(json.dumps({
        "stackexchange_total": se_total,
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
      --part doc    : corpus dokümanı işleri (Corpus final olduktan sonra) -> iş listesine EKLER
    Var olan işler asla değiştirilmez (üretilmiş örneklerin job_id'leri ile uyumu korunur).
    """
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["se_ref", "doc", "doc_supplement"], required=True)
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
    elif a.part == "doc_supplement":
        # Ek doküman işleri (config: instruction.supplement). Yalnız henüz işi olmayan dokümanlar kullanılır;
        # var olan işler değişmez. Aynı paket ikinci kez eklenmez.
        sups = I["supplement"] if isinstance(I["supplement"], list) else [I["supplement"]]
        new = []
        for k, sup in enumerate(sups):  # paketler sırayla; seed her pakette farklı (ek1: 12, ek2: 13)
            if any(j.get("batch") == sup["name"] for j in jobs + new):
                log.info(f"'{sup['name']}' ek paketi zaten var; değiştirilmedi")
                continue
            used = frozenset(j["source_document"] for j in jobs + new if j["kind"] == "doc")
            add = build_doc_jobs(dict(sorted(sup["quota"].items())), exclude_docs=used, per_type_cap=sup["per_type_cap"],
                                 seed_offset=12 + k, batch=sup["name"])
            clash = {j["job_id"] for j in add} & {j["job_id"] for j in jobs + new}
            if clash:
                raise SystemExit(f"İş kimliği çakışması: {sorted(clash)[:5]}")
            new += add
        if not new:
            return
    else:
        if "doc" in kinds:
            log.info("Doküman işleri zaten var; değiştirilmedi")
            return
        if not (p("final") / "train.jsonl").exists():
            raise SystemExit("Corpus (data/final/train.jsonl) yok; önce 01-08 çalıştırılmalı")
        new = build_doc_jobs(quota)  # target_total zaten eleme payını içeriyor
    jobs += new
    # Üretim döngüsü dosyayı okurken yarım dosya görmesin: önce geçici dosyaya yaz, sonra tek adımda değiştir
    tmp = jobs_file.with_suffix(".jsonl.tmp")
    write_jsonl(tmp, jobs)
    tmp.replace(jobs_file)
    write_summary(jobs, removed)
    log.info(f"{len(new)} yeni iş eklendi; toplam: " + ", ".join(f"{k}={v}" for k, v in
                                                                 Counter(j["kind"] for j in jobs).items()))


if __name__ == "__main__":
    main()
