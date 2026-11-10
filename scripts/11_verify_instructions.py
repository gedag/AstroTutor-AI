"""11 — Üretilen instruction örneklerini doğrular; doğrulanamayanları nedeniyle eler (Instruction v2.0, İngilizce).

1) Kural tabanlı otomatik kontroller (tüm örnekler)
   llm_skipped, invalid_level, length, task_type_mismatch, wrong_language (İngilizce değil), exponent_loss,
   references_unseen_text, response_references_unseen_text, invalid_mcq_json / no_teaching_passage,
   mcq_answer_in_instruction, contains_url, contains_pii, latex_artifact, duplicate, near_duplicate, eval_overlap.
   Düzeltme (eleme değil): sınıflandırma talimatında öğeler sayılmışken "mentioned in the text" gibi atıf silinir.
2) Kanıt kontrolü (kaynak dokümanı olan Gemini örnekleri): destekleyen alıntı kaynakta geçmeli. Stack Exchange
   örnekleri orijinal metin olduğu için (cevabın kendisi kaynak) bu kontrolden geçmez.
3) Aşamalı LLM yargıç (Gemini, sıcaklık 0, ayrı çağrı; Eda kararı 10.11.2026; ayarlar config: instruction.judge)
   Aşama 1: işlerin rastgele initial_fraction'ı (iş türü x üretici türüne göre tabakalı, sabit seed; dosyaya sabitlenir)
   Karar  : grup = (üretici türü flash/lite, görev türü). Grup YALNIZ hata oranının tek yönlü üst güven sınırı
            (Clopper-Pearson, config judge.confidence) full_check_fail_rate'in altındaysa durdurulur; aksi hâlde
            grubun TÜM işleri değerlendirilir. Durdurulan gruplarda tahmini hata oranı raporlanır. Karar aşama 1
            bitince data/interim/instruction_judge_plan.json'a sabitlenir.
   Stack Exchange işlerinin tamamı her zaman değerlendirilir: yargıç seviyeyi de atar; seviyesi atanamayan SE örneği
   sete girmez (level_unassigned).
   Ölçütler: supported / correct / follows_instruction / instruction_clear / fluent_english -> pass/fail
   Kararlar data/interim/instruction_judgments.jsonl'de saklanır (kaldığı yerden devam).
Çıktı: data/interim/instructions_verified.jsonl, reports/removed_instructions.csv (stage=verify),
       reports/instruction_verification_summary.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from math import comb

from datasketch import MinHash, MinHashLSH
from pydantic import BaseModel

from common import CFG, ROOT, RemovalLog, append_jsonl, fill, get_logger, now_iso, p, read_jsonl, write_jsonl
from exponent_fix import fix_exponents
from mcq_check import PASSAGE_MIN_CHARS as MCQ_PASSAGE_MIN_CHARS, mcq_in_instruction, mcq_passage_chars
from press_boilerplate import EMAIL, PHONE

log = get_logger("11_verify_instructions")
I = CFG["instruction"]
J = I["judge"]
PD = ROOT / CFG["paths"]["prompts"] / I["prompt_version"]
TEXT_TYPES = {"summarization", "mcq_generation", "classification"}
SE_METHOD = "stackexchange_original_verbatim"
SE_UNASSIGNED_LEVEL = "unassigned"
PASSAGE_MIN_CHARS = 300   # özetleme/çoktan seçmeli talimatlarında pasaj; sınıflandırmada pasaj varsa atıf serbest
JUDGE_MAX_ATTEMPTS = 2    # kota dışı nedenle tamamlanamayan yargıç işi en fazla bu kadar denenir
CRIT = ("supported", "correct", "follows_instruction", "instruction_clear", "fluent_english")


def has_passage(ins: str) -> bool:
    return len(ins) >= PASSAGE_MIN_CHARS


def n_list_items(ins: str) -> int:
    """Talimatta sayılan öğe ayırıcıları (virgül, 'and', madde/numara satırı)."""
    return len(re.findall(r",\s|\sand\s|\n\s*[-*•]|\n\s*\d+[.)]", ins))


# Kullanıcının GÖRMEDİĞİ bir metne atıf (v1.0'daki "metne göre", "kaynakta" ... kalıplarının İngilizcesi)
_DOC = r"(?:text|passage|document|article|excerpt|source text|source material|reading|material provided)"
UNSEEN = re.compile(r"\b(?:according to the " + _DOC + r"|according to the source|in the (?:above |given |provided )?"
                    + _DOC + r"|(?:the|this) " + _DOC + r" (?:says|states|mentions|describes|notes|explains)|"
                    r"(?:mentioned|described|stated|discussed|listed|noted|given) in the " + _DOC + r"|"
                    r"based on the (?:" + _DOC + r"|source|provided|given) |the (?:provided|given|above) "
                    r"(?:text|passage|information|document|excerpt)|as (?:stated|described|mentioned|noted) above)\b",
                    re.I)

# Sınıflandırma talimatlarında öğeler sayıldığı hâlde kalan atıf ifadeleri ("Classify the objects mentioned in the text:
# Mercury, Venus ..."): görev çözülebilir, ama kullanıcının görmediği metne atıf öğretmesin diye ifade silinir (v1.0'da
# 35 talimat; silme sonrası hepsi doğal okunuyordu).
REF_PATTERNS = [
    re.compile(r"\s*\b(?:that are |which are )?(?:mentioned|listed|named|described|discussed) in the (?:source )?"
               r"(?:text|passage|document|article|source)\b", re.I),
    re.compile(r",?\s*\baccording to the (?:source )?(?:text|passage|document|article|source)\b,?", re.I),
    re.compile(r",?\s*\bbased on the (?:source )?(?:text|passage|document|article|source)\b,?", re.I),
    re.compile(r"\s*\b(?:from|in) the (?:source )?(?:text|passage|document|article)\b", re.I),
]


def strip_unseen_ref(ins: str) -> str:
    out = ins
    for pat in REF_PATTERNS:
        out = pat.sub(" ", out)
    out = re.sub(r"[ \t]{2,}", " ", out).strip()
    out = re.sub(r"\s+([,.;:?!])", r"\1", out)
    return (out[0].upper() + out[1:]) if out else out


# LaTeX/MathJax artığı: içinde LaTeX karakteri (\x5c ^ _ { }) olan $...$ blokları veya \x5ctimes, \x5crm ... komutları
LATEX = re.compile(r"\$[^$\n]{0,80}[\x5c^_{}][^$\n]{0,80}\$|\x5c(times|rm|frac|odot|mathrm|cdot|sim|approx)\b")


class Judgment(BaseModel):
    index: int
    supported: bool
    correct: bool
    follows_instruction: bool
    instruction_clear: bool
    fluent_english: bool
    level: str
    verdict: str
    issues: str


def check_mcq(resp: str) -> str | None:
    try:
        obj = json.loads(resp)
    except Exception:
        m = re.search(r"\{.*\}", resp, re.S)
        if not m:
            return "json_parse"
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return "json_parse"
    qs = obj.get("questions") if isinstance(obj, dict) else None
    if not isinstance(qs, list) or not 1 <= len(qs) <= 3:
        return "question_count"
    for q in qs:
        if not isinstance(q, dict):
            return "question_format"
        opts = q.get("options", {})
        if not isinstance(opts, dict) or set(opts) != {"A", "B", "C", "D"} or any(not str(v).strip() for v in opts.values()):
            return "options"
        if len({str(v).strip().lower() for v in opts.values()}) < 4:
            return "duplicate_option"
        if q.get("answer") not in ("A", "B", "C", "D") or not str(q.get("question", "")).strip():
            return "answer"
    return None


def tier(model: str | None) -> str:
    """Üretici türü: 'flash', 'lite' veya Stack Exchange için 'none' (Gemini yok)."""
    if not model:
        return "none"
    return "lite" if "lite" in model else "flash"


LANG_MIN_WORDS = 8   # daha kısa talimatlarda dil tespiti güvenilmez ("What is a pulsar?" -> İspanyolca, 10.11.2026 testi)


def is_english(det, resp: str, ins: str) -> bool:
    """Cevap her zaman, talimat yalnız en az LANG_MIN_WORDS kelimeyse kontrol edilir."""
    from lingua import Language

    if det.detect_language_of(resp[:1500]) != Language.ENGLISH:
        return False
    return len(ins.split()) < LANG_MIN_WORDS or det.detect_language_of(ins[:600]) == Language.ENGLISH


def rule_checks(rows: list[dict], removed: RemovalLog, det, grams: set) -> list[dict]:
    ok = []
    seen = set()
    for r in rows:
        rid, t = r["raw_example_id"], r["task_type"]
        # Model görev türü alanına seviyeyi de yazmışsa ("comparison, level=advanced"): biçim hatası, içerik değil.
        if r.get("planned_task_type") and t != r["planned_task_type"] and t.split(",")[0].strip() == r["planned_task_type"]:
            t = r["task_type"] = r["planned_task_type"]
        ins, resp = (r.get("instruction") or "").strip(), (r.get("response") or "").strip()
        r["level"] = (r.get("level") or "").strip().lower()
        # Talimat sonda tek başına "{" ile bitiyorsa (model JSON yazmaya başlamış): atılır (v1.0'da 12 talimat)
        if re.search(r"\s[{\[]\s*$", ins):
            ins = re.sub(r"\s*[{\[]\s*$", "", ins)
            r["instruction"] = ins
        # Yalnız öğeler talimatta sayılmışsa (≥3) atıf silinir; öğesiz "Classify the objects in the text" aşağıda elenir
        if t == "classification" and not has_passage(ins) and UNSEEN.search(ins) and n_list_items(ins) >= 3:
            new = strip_unseen_ref(ins)
            if new != ins:
                ins = new
                r["instruction"] = ins
                r["postprocess"] = "unseen_reference_removed"
        is_se = r.get("generation_method") == SE_METHOD
        reason = None
        if r.get("skip"):
            reason = ("llm_skipped", r.get("skip_reason"))
        elif r["level"] not in I["levels"] and not (is_se and r["level"] == SE_UNASSIGNED_LEVEL):
            reason = ("invalid_level", r["level"][:30])
        elif len(ins) < 10 or not (I["min_response_chars"] <= len(resp) <= I["max_response_chars"]):
            reason = ("length", f"ins={len(ins)} resp={len(resp)}")
        elif r.get("planned_task_type") and t != r["planned_task_type"]:
            reason = ("task_type_mismatch", f"{t}!={r['planned_task_type']}")
        elif not is_english(det, resp, ins):
            reason = ("wrong_language", "")
        elif fix_exponents(ins)[1] or fix_exponents(resp)[1]:
            # kaybolmuş üs ("1.99 x 1030 kg")
            reason = ("exponent_loss", "")
        elif not is_se and t not in TEXT_TYPES and UNSEEN.search(ins):
            reason = ("references_unseen_text", UNSEEN.search(ins).group(0))
        elif t == "classification" and not has_passage(ins) and UNSEEN.search(ins) and n_list_items(ins) < 3:
            # "Classify the molecules mentioned in the text": talimatta ne metin ne öğe listesi var
            reason = ("references_unseen_text", "classification_items_missing:" + UNSEEN.search(ins).group(0))
        elif not is_se and (t not in TEXT_TYPES or (t == "classification" and not has_passage(ins))) and UNSEEN.search(resp):
            # Kullanıcı metin vermediği hâlde cevap "according to the text" diyor: model görünmeyen bir kaynağa atıf
            # yapmayı öğrenir (v1.0'da 89 örnek; prompt v2.0 kural 9)
            reason = ("response_references_unseen_text", UNSEEN.search(resp).group(0))
        elif t == "mcq_generation" and (check_mcq(resp) or len(ins) < 250
                                        or mcq_passage_chars(ins) < MCQ_PASSAGE_MIN_CHARS):
            reason = ("invalid_mcq_json", check_mcq(resp) or "no_teaching_passage")
        elif t == "mcq_generation" and mcq_in_instruction(ins, resp):
            reason = ("mcq_answer_in_instruction", mcq_in_instruction(ins, resp))
        elif re.search(r"https?://|www\.", ins + " " + resp):
            reason = ("contains_url", "")
        elif EMAIL.search(ins + " " + resp) or PHONE.search(ins + " " + resp):
            reason = ("contains_pii", "")  # kişisel iletişim bilgisi (e-posta/telefon)
        elif LATEX.search(resp):
            reason = ("latex_artifact", LATEX.search(resp).group(0))
        elif ins.lower() in seen:
            reason = ("duplicate", "")
        else:
            w = re.findall(r"\w+", (ins + " " + resp).lower())
            n = I["decontam_ngram"]
            if grams and any(tuple(w[i:i + n]) in grams for i in range(len(w) - n + 1)):
                reason = ("eval_overlap", "")
        if reason:
            removed.add(rid, reason[0], r["source_name"], reason[1] or "")
            continue
        seen.add(ins.lower())
        ok.append(r)
    # near-duplicate talimatlar (kelime 3-gram MinHash, Jaccard >= 0.8)
    lsh = MinHashLSH(threshold=0.8, num_perm=64)
    keep = []
    for r in ok:
        w = re.findall(r"\w+", r["instruction"].lower())
        sh = {" ".join(w[i:i + 3]) for i in range(max(len(w) - 2, 1))}
        m = MinHash(num_perm=64, seed=CFG["project"]["random_seed"])
        for s in sh:
            m.update(s.encode("utf-8"))
        if lsh.query(m):
            removed.add(r["raw_example_id"], "near_duplicate", r["source_name"], "")
            continue
        lsh.insert(r["raw_example_id"], m)
        keep.append(r)
    return keep


def source_for(job_rows: list[dict], docs: dict) -> str:
    r = job_rows[0]
    if r.get("generation_method") == SE_METHOD:
        return ("(Stack Exchange: each example is an ORIGINAL user question and its top-voted answer, used verbatim. "
                "There is no separate source document: judge whether the answer is accurate, complete and "
                "self-contained for the question, and assign its level.)")
    if r["source_name"] == "none":
        return ("(No source: these are out-of-scope / insufficient-information examples. Judge whether the response "
                "states its limit correctly, contains no invented information, and whether the general information "
                "it gives is correct.)")
    d = docs[r["source_document"]]
    return f"Title: {d['title']}\n{d['text'][: I['source_doc_max_chars']]}"


def _w5(text: str) -> list[tuple]:
    # "^" yok sayılır: modelin alıntısında "10^8" ile "108" aynı sayılır
    w = re.findall(r"\w+", text.replace("^", "").lower())
    return [tuple(w[i:i + 5]) for i in range(len(w) - 4)]


def evidence_ok(evidence: str, source: str) -> tuple[bool, str]:
    """Modelin 'destekleyen alıntı' olarak verdiği metin kaynakta GERÇEKTEN geçiyor mu?
    Alıntı '...' ile bölünmüş parçalar olabilir; 8+ kelimelik parçaların kelime 5-gram'larının
    en az evidence_min_overlap oranı kaynakta bulunmalı. API çağrısı gerektirmez."""
    frags = [f for f in re.split(r"\.\.\.|…|\n|\|", evidence or "") if len(f.split()) >= 8]
    if not frags:
        return False, "quote_missing_or_too_short"
    src = set(_w5(source))
    g = [x for f in frags for x in _w5(f)]
    ratio = sum(1 for x in g if x in src) / max(len(g), 1)
    return ratio >= I["evidence_min_overlap"], f"overlap={ratio:.2f}"


def upper_bound(k: int, n: int, conf: float) -> float:
    """Hata oranı için tek yönlü Clopper-Pearson (kesin binom) üst güven sınırı: n örnekte k hata görüldüyse, gerçek
    oranın `conf` güvenle altında kaldığı en küçük u (P(X <= k | n, u) = 1 - conf). n = 0 ise 1.0 (bilgi yok).
    Standart kütüphaneyle ikiye bölme; scipy.stats.beta.ppf(conf, k + 1, n - k) ile aynı sonucu verir (testli)."""
    if n == 0:
        return 1.0
    if k >= n:
        return 1.0

    def cdf(u: float) -> float:
        return sum(comb(n, i) * u ** i * (1 - u) ** (n - i) for i in range(k + 1))

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if cdf(mid) > 1 - conf:
            lo = mid
        else:
            hi = mid
    return hi


def judge_failed(jd: dict) -> list[str]:
    """Başarısız ölçütler (boşsa geçti)."""
    failed = [k for k in CRIT if not jd[k]]
    if not failed and jd["verdict"] != "pass":
        failed = ["verdict"]
    return failed


def main() -> int:
    """Çıkış kodu: 0 = tamam, 2 = yargıçta kota/yoğunluk nedeniyle bekleyen iş var."""
    import random as _random

    from lingua import Language, LanguageDetectorBuilder

    ap = argparse.ArgumentParser()
    ap.add_argument("--no-judge", action="store_true", help="LLM yargıcı çalıştırma (yalnız kural + kanıt kontrolü)")
    a = ap.parse_args()
    import importlib

    b9 = importlib.import_module("09_build_instruction_sources")
    det = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.TURKISH, Language.GERMAN,
                                                 Language.FRENCH, Language.SPANISH).build()
    grams = b9.eval_ngrams(I["decontam_ngram"])
    # Bir iş, örnekleri yazıldıktan sonra "tamamlandı" kaydı yazılamadan kesilirse yeniden üretilir;
    # aynı raw_example_id'den yalnızca EN SON üretilen tutulur.
    latest = {}
    for r in read_jsonl(p("interim") / "instructions_raw.jsonl"):
        latest[r["raw_example_id"]] = r
    rows = list(latest.values())
    removed = RemovalLog(p("reports") / "removed_instructions.csv", "verify", reset=False)
    rows = rule_checks(rows, removed, det, grams)
    log.info(f"Kural kontrolünden geçen: {len(rows)}")

    docs = {}
    for s in ("train", "validation", "test"):
        for d in read_jsonl(p("final") / f"{s}.jsonl"):
            docs[d["document_id"]] = d

    # ---- 2) kanıt kontrolü (kaynak dokümanı olan Gemini örnekleri)
    kept = []
    for r in rows:
        if r["source_name"] not in ("none", "stackexchange_space_qa"):
            d = docs.get(r["source_document"])
            if d is None:
                removed.add(r["raw_example_id"], "source_missing", r["source_name"], r["source_document"])
                continue
            ok, detail = evidence_ok(r.get("supporting_evidence", ""), d["text"])
            if not ok:
                removed.add(r["raw_example_id"], "evidence_not_in_source", r["source_name"], detail)
                continue
        kept.append(r)
    log.info(f"Kanıt kontrolünden geçen: {len(kept)}")
    rows = kept

    # ---- 3) aşamalı LLM yargıç
    by_job = defaultdict(list)
    for r in rows:
        by_job[r["job_id"]].append(r)
    job_tier = {jid: tier(rs[0].get("generator_model")) for jid, rs in by_job.items()}
    se_jobs = {jid for jid, rs in by_job.items() if rs[0].get("generation_method") == SE_METHOD}
    # Aşama 1 örneklemi ilk hesaplandığında dosyaya sabitlenir (sonradan eklenen bir kural bir işin bütün örneklerini
    # elerse rastgele seçim baştan değişmesin). Tabaka: iş türü (doc/refusal) x üretici türü (flash/lite).
    sample_f = p("interim") / "instruction_judge_sample.json"
    # Örneklem ve grup kararı yalnız üretim TAMAMEN bittiğinde dosyaya sabitlenir; yoksa (ör. pilotta birkaç iş
    # varken) seçim yalnız o işlerden yapılıp kalıcı olurdu. Bitmemişse bu çalıştırmada bellekte hesaplanır.
    all_jobs = {j["job_id"] for j in read_jsonl(p("interim") / "instruction_jobs.jsonl")}
    done_jobs = {r["job_id"] for r in read_jsonl(p("interim") / "instruction_jobs_done.jsonl")}
    generation_complete = bool(all_jobs) and all_jobs <= done_jobs
    if not generation_complete:
        log.warning(f"Üretim bitmedi ({len(all_jobs - done_jobs)} iş kaldı): yargıç örneklemi ve grup kararı "
                    f"dosyaya SABİTLENMEZ")
    if sample_f.exists():
        sample_planned = set(json.loads(sample_f.read_text(encoding="utf-8")))
    else:
        rnd = _random.Random(CFG["project"]["random_seed"] + 111)
        strata = defaultdict(list)
        for jid in sorted(by_job):
            if jid not in se_jobs:
                strata[(jid.split("_")[1], job_tier[jid])].append(jid)
        sample_planned = set()
        for _, js in sorted(strata.items()):
            sample_planned.update(rnd.sample(js, max(1, round(len(js) * J["initial_fraction"]))))
        if generation_complete:
            sample_f.write_text(json.dumps(sorted(sample_planned), indent=0), encoding="utf-8")
    sample_jobs = {j for j in sample_planned if j in by_job}
    judged = {r["raw_example_id"]: r for r in read_jsonl(p("interim") / "instruction_judgments.jsonl")}
    attempts_f = p("interim") / "instruction_judge_attempts.jsonl"
    attempts = Counter(r["job_id"] for r in read_jsonl(attempts_f))

    def unjudged(jid: str) -> bool:
        return any(x["raw_example_id"] not in judged for x in by_job[jid])

    def pending(jobs) -> list[str]:
        return [j for j in sorted(jobs) if unjudged(j) and attempts[j] < JUDGE_MAX_ATTEMPTS]

    def group(r: dict) -> str:
        return f"{tier(r.get('generator_model'))}|{r['task_type']}"

    plan_f = p("interim") / "instruction_judge_plan.json"

    def make_plan() -> dict | None:
        """Aşama 1 bittiyse (bekleyen örneklem işi yoksa) grup kararını hesaplar ve dosyaya sabitler."""
        if plan_f.exists():
            return json.loads(plan_f.read_text(encoding="utf-8"))
        if pending(sample_jobs) or not generation_complete:
            return None
        stats = defaultdict(lambda: [0, 0])  # grup -> [değerlendirilen, başarısız]
        for jid in sample_jobs:
            for x in by_job[jid]:
                jd = judged.get(x["raw_example_id"])
                if jd is not None:
                    stats[group(x)][0] += 1
                    stats[group(x)][1] += bool(judge_failed(jd))
        all_groups = {group(x) for jid in by_job if jid not in se_jobs for x in by_job[jid]}
        # Grup YALNIZ hata oranının üst güven sınırı eşiğin altındaysa durdurulur (değerlendirilmemiş grup: tamamı)
        ub = {g: upper_bound(stats[g][1], stats[g][0], J["confidence"]) for g in all_groups}
        full = sorted(g for g in all_groups if ub[g] >= J["full_check_fail_rate"])
        plan = {"decided_at": now_iso(), "initial_fraction": J["initial_fraction"],
                "full_check_fail_rate": J["full_check_fail_rate"], "confidence": J["confidence"],
                "rule": "stop only if one-sided Clopper-Pearson upper bound of the fail rate < full_check_fail_rate",
                "stage1_groups": {g: {"judged": stats[g][0], "fail": stats[g][1],
                                      "fail_rate": round(stats[g][1] / stats[g][0], 4) if stats[g][0] else None,
                                      "upper_bound": round(ub[g], 4)}
                                  for g in sorted(all_groups)},
                "full_check_groups": full}
        plan_f.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info(f"Aşama 1 bitti; tamamı değerlendirilecek gruplar: {full}")
        return plan

    def full_jobs(plan: dict | None) -> set[str]:
        if plan is None:
            return set()
        fg = set(plan["full_check_groups"])
        return {jid for jid in by_job if jid not in se_jobs and jid not in sample_jobs
                and any(group(x) in fg for x in by_job[jid])}

    if not a.no_judge:
        from llm import Gemini, QuotaExhausted, TransientError

        llm = None
        tmpl = (PD / "judge.txt").read_text(encoding="utf-8")
        busy = 0
        stop = False
        # Önce aşama 1 ve SE işleri; aşama 1 bitince grup kararı verilir ve tam kontrol işleri eklenir
        for phase in ("stage1", "full"):
            plan = make_plan()
            if phase == "stage1":
                todo = pending(sample_jobs) + pending(se_jobs)
            else:
                if plan is None:
                    break
                todo = pending(full_jobs(plan))
            log.info(f"Yargıç ({phase}): değerlendirilecek iş {len(todo)} "
                     f"(örneklem {len(sample_jobs)}, SE {len(se_jobs)}, tam kontrol {len(full_jobs(plan))})")
            if todo and llm is None:
                llm = Gemini(I["judge_models"], I["judge_temperature"], I.get("judge_thinking_budget"))
            for jid in todo:
                rs = by_job[jid]
                exs = "\n\n".join(f"[{i}] (task type: {x['task_type']}, level: {x['level']})\nINSTRUCTION:\n"
                                  f"{x['instruction']}\nRESPONSE:\n{x['response']}" for i, x in enumerate(rs))
                prompt = fill(tmpl, task_hint="the task type given at the start of each example",
                              source=source_for(rs, docs), examples=exs)
                try:
                    res = llm.generate_json("You are a rigorous data quality auditor. Return only the requested JSON.",
                                            prompt, list[Judgment], exclude={x["generator_model"] for x in rs} - {None})
                except QuotaExhausted as e:
                    if len(llm.exhausted) == len(llm.models):
                        log.error(f"Tüm yargıç modellerinin günlük kotası doldu; kaldığı yerden devam: {e}")
                        stop = True
                        break
                    continue  # bu işin uygun yargıcı kalmadı; başka modelle üretilmiş işlere devam
                except TransientError as e:
                    # 503/bağlantı: işin kusuru değil, deneme sayılmaz; üst üste 3 kez olursa kota yanmasın diye durulur
                    busy += 1
                    log.warning(f"{jid} yargıç geçici hata ({busy}/3): {str(e)[:150]}")
                    if busy >= 3:
                        log.error("Üst üste 3 geçici hata; yargıç bu çalıştırmada durduruldu, sonra kaldığı yerden devam")
                        stop = True
                        break
                    continue
                except Exception as e:
                    log.error(f"{jid} yargıç hatası: {str(e)[:200]}")
                    attempts[jid] += 1
                    append_jsonl(attempts_f, {"job_id": jid, "result": "error", "detail": str(e)[:200], "at": now_iso()})
                    continue
                busy = 0
                seen_idx = set()
                for jd in res:
                    jd = jd.model_dump() if hasattr(jd, "model_dump") else jd
                    if 0 <= jd["index"] < len(rs) and jd["index"] not in seen_idx:
                        seen_idx.add(jd["index"])
                        jd["verdict"] = str(jd["verdict"]).strip().lower()
                        jd["level"] = str(jd["level"]).strip().lower()
                        rec = {"raw_example_id": rs[jd["index"]]["raw_example_id"], **jd, "judge_model": llm.last_model,
                               # üretim bitmeden verilen kararlar (pilot) aşama 1 istatistiğine karışmasın diye ayrı etiket
                               "judge_phase": ("pilot" if not generation_complete
                                               else "se" if jid in se_jobs else phase)}
                        judged[rec["raw_example_id"]] = rec
                        append_jsonl(p("interim") / "instruction_judgments.jsonl", rec)
                attempts[jid] += 1
                missing = sum(1 for x in rs if x["raw_example_id"] not in judged)
                append_jsonl(attempts_f, {"job_id": jid, "result": "ok" if not missing else "partial",
                                          "missing": missing, "model": llm.last_model, "at": now_iso()})
                if missing:
                    log.warning(f"{jid}: yargıç {len(rs)} örneğin {missing} tanesini değerlendirmedi "
                                f"(deneme {attempts[jid]}/{JUDGE_MAX_ATTEMPTS})")
            if stop:
                break

    # ---- 4) sonuç
    plan = make_plan() if not a.no_judge else (json.loads(plan_f.read_text(encoding="utf-8")) if plan_f.exists() else None)
    fjobs = full_jobs(plan)
    verified, fail_by, phase_n = [], Counter(), Counter()
    for r in rows:
        jd = judged.get(r["raw_example_id"])
        is_se = r["job_id"] in se_jobs
        if jd is not None:
            phase_n[jd.get("judge_phase", "?")] += 1
            failed = judge_failed(jd)
            if failed:
                fail_by[failed[0]] += 1
                removed.add(r["raw_example_id"], "judge_fail:" + failed[0], r["source_name"], jd["issues"])
                continue
            if is_se:
                if jd["level"] not in I["levels"]:
                    removed.add(r["raw_example_id"], "level_unassigned", r["source_name"], f"judge level={jd['level']}")
                    continue
                r["level"] = jd["level"]
                r["level_source"] = "llm_judge"
        elif is_se:
            # Seviyesi atanmamış SE örneği yayınlanmaz (yargıç bu işi tamamlayamadı ya da henüz değerlendirmedi)
            removed.add(r["raw_example_id"], "level_unassigned", r["source_name"], "not judged")
            continue
        verified.append({**r, "auto_verified": True, "llm_judged": jd is not None,
                         "judge": {k: jd[k] for k in ("verdict", "issues", "judge_model", "judge_phase")} if jd else None})
    removed.save()
    write_jsonl(p("interim") / "instructions_verified.jsonl", verified)

    # Aşama 1'de durulan gruplarda değerlendirilmeden kalan örnekler ve tahmini hata (aşama 1 oranıyla)
    unj = Counter(group(x) for x in verified if not x["llm_judged"])
    est, est_ub = 0.0, 0.0   # nokta tahmini ve üst güven sınırına göre (en kötü durum) tahmin
    if plan:
        for g, n in unj.items():
            s = plan["stage1_groups"].get(g) or {}
            est += (s.get("fail_rate") or 0) * n
            est_ub += s.get("upper_bound", 1.0) * n
    reasons = Counter(x["reason"] for x in removed.rows if x["stage"] == "verify")
    gave_up = [j for j in sorted(sample_jobs | se_jobs | fjobs) if unjudged(j) and attempts[j] >= JUDGE_MAX_ATTEMPTS]
    summary = {"verified": len(verified), "judged_examples": sum(phase_n.values()),
               "judged_by_phase": dict(phase_n), "judge_fail_by_criterion": dict(fail_by),
               "judge_fail": sum(fail_by.values()),
               "stage1_jobs": len(sample_jobs), "se_jobs": len(se_jobs), "full_check_jobs": len(fjobs),
               "plan": plan, "unjudged_examples_by_group": dict(unj),
               "estimated_errors_remaining": round(est, 1),
               "estimated_error_rate_remaining": round(est / len(verified), 4) if verified else None,
               # en kötü durum: durdurulan gruplarda hata oranı üst güven sınırında olsaydı
               "estimated_error_rate_remaining_upper": round(est_ub / len(verified), 4) if verified else None,
               "judge_gave_up_jobs": len(gave_up), "removed_by_reason": dict(reasons),
               "rule_fixes": dict(Counter(q for x in verified if x.get("postprocess") for q in x["postprocess"].split("+")))}
    (p("reports") / "instruction_verification_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Doğrulanan: {len(verified)}; yargıç {summary['judged_examples']} örnek {dict(phase_n)}, "
             f"başarısız {summary['judge_fail']}; değerlendirilmeyen {sum(unj.values())} (tahmini hata {est:.1f}); "
             f"elenen: {dict(reasons)}")
    if gave_up:
        log.warning(f"Yargıç {len(gave_up)} işte {JUDGE_MAX_ATTEMPTS} denemede tamamlanamadı")
    if not a.no_judge:
        left = pending(sample_jobs) + pending(se_jobs) + (pending(fjobs) if plan else [])
        if left or plan is None:
            log.info(f"Yargıçta bekleyen iş: {len(left)} (kota yenilenince devam)")
            return 2
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
