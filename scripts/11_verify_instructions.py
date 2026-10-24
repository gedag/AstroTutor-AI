"""11 — Üretilen instruction örneklerini doğrular; doğrulanamayanları nedeniyle eler (Vize Rehberi §11, §12).

1) Kural tabanlı otomatik kontroller
   llm_skipped, length, task_type_mismatch, wrong_language, references_unseen_text, invalid_mcq_json,
   mcq_answer_in_instruction (soru/şık/cevap talimatta verilmiş), response_references_unseen_text, contains_url, duplicate, near_duplicate, eval_overlap
2) LLM yargıç (Gemini, sıcaklık 0, ayrı çağrı): her örnek KAYNAĞIYLA birlikte değerlendirilir
   supported / correct / follows_instruction / instruction_clear / fluent_turkish -> pass/fail
   Kararlar data/interim/instruction_judgments.jsonl'de saklanır (kaldığı yerden devam).
Çıktı: data/interim/instructions_verified.jsonl, reports/removed_instructions.csv (stage=verify)
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from typing import List

from datasketch import MinHash, MinHashLSH
from pydantic import BaseModel

from common import CFG, ROOT, RemovalLog, append_jsonl, fill, get_logger, p, read_jsonl, write_jsonl
from exponent_fix import fix_exponents
from mcq_check import mcq_in_instruction
from press_boilerplate import EMAIL, PHONE
from turkish_check import missing_turkish_chars

log = get_logger("11_verify_instructions")
I = CFG["instruction"]
PD = ROOT / CFG["paths"]["prompts"] / I["prompt_version"]
TEXT_TYPES = {"ozetleme", "coktan_secmeli_soru_uretimi", "siniflandirma"}
PASSAGE_MIN_CHARS = 300   # özetleme/çoktan seçmeli talimatlarının en kısası 206/282 karakter; sınıflandırmada pasaj


def has_passage(ins: str) -> bool:
    return len(ins) >= PASSAGE_MIN_CHARS


def n_list_items(ins: str) -> int:
    """Talimatta sayılan öğe ayırıcıları (virgül, 've', madde/numara satırı)."""
    return len(re.findall(r",\s|\sve\s|\n\s*[-*•]|\n\s*\d+[.)]", ins))
UNSEEN = re.compile(r"\b(metne göre|metinde|dokümanda|dokümana göre|kaynakta|kaynağa göre|yukarıdaki (metin|yazı)|"
                    r"verilen metin|bu makalede|bu yazıda|kaynaktaki|metindeki|dokümandaki|kaynak metn\w*|"
                    r"kaynak metin\w*)\b", re.I)  # "kaynaktan" alınmadı: çoğunlukla "ışık kaynağından" anlamında


# LaTeX/MathJax artigi: icinde LaTeX karakteri (\x5c ^ _ { }) olan $...$ bloklari veya \x5ctimes, \x5crm ... komutlari
LATEX = re.compile(r"\$[^$\n]{0,80}[\x5c^_{}][^$\n]{0,80}\$|\x5c(times|rm|frac|odot|mathrm|cdot|sim|approx)\b")


class Judgment(BaseModel):
    index: int
    supported: bool
    correct: bool
    follows_instruction: bool
    instruction_clear: bool
    fluent_turkish: bool
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
    qs = obj.get("sorular") if isinstance(obj, dict) else None
    if not isinstance(qs, list) or not 1 <= len(qs) <= 3:
        return "soru_sayisi"
    for q in qs:
        opts = q.get("secenekler", {})
        if set(opts) != {"A", "B", "C", "D"} or any(not str(v).strip() for v in opts.values()):
            return "secenekler"
        if len({str(v).strip().lower() for v in opts.values()}) < 4:
            return "tekrar_eden_secenek"
        if q.get("dogru_cevap") not in ("A", "B", "C", "D") or not str(q.get("soru", "")).strip():
            return "dogru_cevap"
    return None


def rule_checks(rows: list[dict], removed: RemovalLog, det, grams: set) -> list[dict]:
    from lingua import Language

    ok = []
    seen = set()
    for r in rows:
        rid, t = r["raw_example_id"], r["task_type"]
        ins, resp = (r.get("instruction") or "").strip(), (r.get("response") or "").strip()
        # seviye alanı normalleştirilir (bir lite çıktısında " ileri" gibi baş boşluğu görüldü)
        r["level"] = (r.get("level") or "").strip().lower()
        # 12 çoktan seçmeli talimatı sonda tek başına "{" ile bitiyordu (model JSON yazmaya başlamış): atılır
        if re.search(r"\s[{\[]\s*$", ins):
            ins = re.sub(r"\s*[{\[]\s*$", "", ins)
            r["instruction"] = ins
        reason = None
        if r.get("skip"):
            reason = ("llm_skipped", r.get("skip_reason"))
        elif r["level"] not in ("baslangic", "orta", "ileri"):
            reason = ("invalid_level", r["level"][:30])
        elif len(ins) < 10 or not (I["min_response_chars"] <= len(resp) <= I["max_response_chars"]):
            reason = ("length", f"ins={len(ins)} resp={len(resp)}")
        elif r.get("planned_task_type") and t != r["planned_task_type"]:
            reason = ("task_type_mismatch", f"{t}!={r['planned_task_type']}")
        elif det.detect_language_of(resp[:1500]) != Language.TURKISH or \
                det.detect_language_of(re.split(r"[:\n]", ins)[0][:300] or ins[:300]) != Language.TURKISH:
            reason = ("wrong_language", "")
        elif missing_turkish_chars(ins, resp):
            reason = ("turkish_chars_missing", missing_turkish_chars(ins, resp))
        elif fix_exponents(ins)[1] or fix_exponents(resp)[1]:
            # kaybolmuş üs ("1.99 x 1030 kg"): kaynak metin üretim sırasında üssüz verilmişti (06b'de düzeltildi)
            reason = ("exponent_loss", "")
        elif t not in TEXT_TYPES and UNSEEN.search(ins):
            reason = ("references_unseen_text", UNSEEN.search(ins).group(0))
        elif t == "siniflandirma" and not has_passage(ins) and UNSEEN.search(ins) and n_list_items(ins) < 3:
            # "Metinde geçen molekülleri sınıflandır": talimatta ne metin ne öğe listesi var (24.10.2026, 39 örnek)
            reason = ("references_unseen_text", "siniflandirma_ogeleri_yok:" + UNSEEN.search(ins).group(0))
        elif (t not in TEXT_TYPES or (t == "siniflandirma" and not has_passage(ins))) and UNSEEN.search(resp):
            # Kullanıcı metin vermediği hâlde cevap "kaynakta verilen bilgiye göre" diyor: model görünmeyen bir
            # kaynağa atıf yapmayı öğrenir (24.10.2026: 52 + 37 örnek; prompt v1.2 kural 11)
            reason = ("response_references_unseen_text", UNSEEN.search(resp).group(0))
        elif t == "coktan_secmeli_soru_uretimi" and (check_mcq(resp) or len(ins) < 250):
            reason = ("invalid_mcq_json", check_mcq(resp) or "ogretim_metni_yok")
        elif t == "coktan_secmeli_soru_uretimi" and mcq_in_instruction(ins, resp):
            reason = ("mcq_answer_in_instruction", mcq_in_instruction(ins, resp))
        elif re.search(r"https?://|www\.", resp):
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


def source_for(job_rows: list[dict], docs: dict, se_items: dict) -> str:
    r = job_rows[0]
    if r["source_name"] == "stackexchange_space_qa":
        return "\n\n".join(f"[{x['source_document']}]\nQUESTION: {se_items[x['source_document']]['question']}\n"
                           f"ANSWER: {se_items[x['source_document']]['answer']}" for x in job_rows)
    if r["source_name"] == "none":
        return "(Kaynak yok: bunlar kapsam dışı / bilgi yetersizliği örnekleri. Cevabın sınırını doğru bildirip " \
               "bildirmediğini, uydurma bilgi içerip içermediğini ve verdiği genel bilgilerin doğruluğunu değerlendir.)"
    d = docs[r["source_document"]]
    return f"Başlık: {d['title']}\n{d['text'][: I['source_doc_max_chars']]}"


def _w5(text: str) -> list[tuple]:
    # "^" yok sayılır: corpus'ta üsler sonradan geri yazıldı ("108" -> "10^8", 06b); üretim sırasında modele
    # eski metin verildiği için alıntılarda "108" kalmış olabilir. İkisi de "108" olarak karşılaştırılır.
    w = re.findall(r"\w+", text.replace("^", "").lower())
    return [tuple(w[i:i + 5]) for i in range(len(w) - 4)]


def evidence_ok(evidence: str, source: str) -> tuple[bool, str]:
    """Modelin 'destekleyen alıntı' olarak verdiği metin kaynakta GERÇEKTEN geçiyor mu?
    Alıntı '...' ile bölünmüş parçalar olabilir; 8+ kelimelik parçaların kelime 5-gram'larının
    en az evidence_min_overlap oranı kaynakta bulunmalı. API çağrısı gerektirmez."""
    frags = [f for f in re.split(r"\.\.\.|…|\n|\|", evidence or "") if len(f.split()) >= 8]
    if not frags:
        return False, "alinti_yok_veya_cok_kisa"
    src = set(_w5(source))
    g = [x for f in frags for x in _w5(f)]
    ratio = sum(1 for x in g if x in src) / max(len(g), 1)
    return ratio >= I["evidence_min_overlap"], f"overlap={ratio:.2f}"


def source_text(r: dict, docs: dict, se_items: dict) -> str | None:
    if r["source_name"] == "stackexchange_space_qa":
        it = se_items.get(r["source_document"])
        return f"{it['question']}\n{it['answer']}" if it else None
    if r["source_name"] == "none":
        return None
    d = docs.get(r["source_document"])
    return d["text"] if d else None


def main() -> int:
    """Çıkış kodu: 0 = tamam, 2 = yargıç örnekleminde kota nedeniyle bekleyen iş var."""
    import json as _json
    import random as _random

    from lingua import Language, LanguageDetectorBuilder

    ap = argparse.ArgumentParser()
    ap.add_argument("--no-judge", action="store_true", help="LLM yargıcı çalıştırma (yalnız kural + kanıt kontrolü)")
    a = ap.parse_args()
    import importlib

    b9 = importlib.import_module("09_build_instruction_sources")
    det = LanguageDetectorBuilder.from_languages(Language.TURKISH, Language.ENGLISH, Language.AZERBAIJANI,
                                                 Language.GERMAN).build()
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
    se_items = {}
    for j in read_jsonl(p("interim") / "instruction_jobs.jsonl"):
        for it in j.get("items", []):
            se_items[it["rid"]] = it

    # ---- 2) kanıt kontrolü (kaynak dokümanı olan her örnek)
    kept = []
    for r in rows:
        src = source_text(r, docs, se_items)
        if r["source_name"] != "none":
            if src is None:
                removed.add(r["raw_example_id"], "source_missing", r["source_name"], r["source_document"])
                continue
            ok, detail = evidence_ok(r.get("supporting_evidence", ""), src)
            if not ok:
                removed.add(r["raw_example_id"], "evidence_not_in_source", r["source_name"], detail)
                continue
        kept.append(r)
    log.info(f"Kanıt kontrolünden geçen: {len(kept)}")
    rows = kept

    # ---- 3) LLM yargıç: işlerin rastgele örneklemi (iş türüne göre tabakalı, sabit seed)
    by_job = defaultdict(list)
    for r in rows:
        by_job[r["job_id"]].append(r)
    rnd = _random.Random(CFG["project"]["random_seed"] + 111)
    kinds = defaultdict(list)
    for jid in sorted(by_job):
        kinds[jid.split("_")[1]].append(jid)
    sample_jobs = set()
    for k, js in kinds.items():
        sample_jobs.update(rnd.sample(js, max(1, round(len(js) * I["judge_sample_fraction"]))))
    judged = {r["raw_example_id"]: r for r in read_jsonl(p("interim") / "instruction_judgments.jsonl")}
    if not a.no_judge:
        from llm import Gemini, QuotaExhausted

        llm = Gemini(I["judge_models"], I["judge_temperature"], I.get("judge_thinking_budget"))
        tmpl = (PD / "judge.txt").read_text(encoding="utf-8")
        todo = [jid for jid in sorted(sample_jobs) if any(x["raw_example_id"] not in judged for x in by_job[jid])]
        log.info(f"Yargıç örneklemi: {len(sample_jobs)} iş; değerlendirilecek: {len(todo)}")
        for jid in todo:
            rs = by_job[jid]
            exs = "\n\n".join(f"[{i}] (görev türü: {x['task_type']}, seviye: {x['level']})\nTALİMAT:\n{x['instruction']}"
                              f"\nCEVAP:\n{x['response']}" for i, x in enumerate(rs))
            prompt = fill(tmpl, task_hint="her örneğin başında belirtilen görev türü",
                          source=source_for(rs, docs, se_items), examples=exs)
            try:
                res = llm.generate_json("Titiz bir veri kalite denetçisisin. Yalnızca istenen JSON'u döndür.",
                                        prompt, list[Judgment], exclude={x["generator_model"] for x in rs})
            except QuotaExhausted as e:
                if len(llm.exhausted) == len(llm.models):
                    log.error(f"Tüm yargıç modellerinin günlük kotası doldu; yarın kaldığı yerden devam: {e}")
                    break
                continue  # bu işin uygun yargıcı kalmadı; başka modelle üretilmiş işlere devam
            except Exception as e:
                log.error(f"{jid} yargıç hatası: {str(e)[:200]}")
                continue
            for jd in res:
                jd = jd.model_dump() if hasattr(jd, "model_dump") else jd
                if 0 <= jd["index"] < len(rs):
                    rec = {"raw_example_id": rs[jd["index"]]["raw_example_id"], **jd, "judge_model": llm.last_model}
                    judged[rec["raw_example_id"]] = rec
                    append_jsonl(p("interim") / "instruction_judgments.jsonl", rec)

    # ---- 4) sonuç
    crit = ("supported", "correct", "follows_instruction", "instruction_clear", "fluent_turkish")
    verified, n_judged, n_fail, fail_by = [], 0, 0, Counter()
    for r in rows:
        jd = judged.get(r["raw_example_id"])
        if jd is not None:
            n_judged += 1
            if jd["verdict"] != "pass" or not all(jd[k] for k in crit):
                failed = [k for k in crit if not jd[k]] or ["verdict"]
                n_fail += 1
                fail_by[failed[0]] += 1
                removed.add(r["raw_example_id"], "judge_fail:" + failed[0], r["source_name"], jd["issues"])
                continue
        verified.append({**r, "auto_verified": True, "llm_judged": jd is not None,
                         "judge": {k: jd[k] for k in ("verdict", "issues", "judge_model")} if jd else None})
    removed.save()
    write_jsonl(p("interim") / "instructions_verified.jsonl", verified)
    reasons = Counter(x["reason"] for x in removed.rows if x["stage"] == "verify")
    summary = {"verified": len(verified), "judged_examples": n_judged, "judge_fail": n_fail,
               "judge_fail_rate": round(n_fail / n_judged, 4) if n_judged else None,
               "judge_fail_by_criterion": dict(fail_by), "removed_by_reason": dict(reasons),
               "sample_jobs": len(sample_jobs)}
    (p("reports") / "instruction_verification_summary.json").write_text(
        _json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Doğrulanan: {len(verified)}; yargıç örneklemi {n_judged} örnek, başarısız {n_fail}; "
             f"elenen: {dict(reasons)}")
    pending = sum(1 for jid in sample_jobs if any(x["raw_example_id"] not in judged for x in by_job[jid]))
    if pending and not a.no_judge:
        log.info(f"Yargıç örnekleminde bekleyen iş: {pending} (kota yenilenince devam)")
        return 2
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
