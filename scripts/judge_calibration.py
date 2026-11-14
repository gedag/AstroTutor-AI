"""Toplu yargıç kalibrasyonu (Instruction v2.0; Eda onayı 11.11.2026).

Soru: Bir yargıç çağrısında 3 iş değerlendirmek (config judge.jobs_per_call = 3), her işi ayrı çağrıda değerlendirmekle
aynı kararları veriyor mu? (Ücretsiz katmanda günlük istek sınırı darboğaz: 3 iş/çağrı yargıç isteğini ~324'ten ~110'a
indirir.)

Yöntem
- Üretimi bitmiş işlerden sabit seed ile 6 üçlü seçilir: 4 doküman (12 iş), 1 kapsam dışı (3 iş), 1 Stack Exchange
  (3 iş). Üçlüler 11'deki make_batches kuralına uyar: aynı iş türü ve aynı üretici model. Doküman üçlüleri mümkün
  olduğunca farklı üretici modellerden seçilir. Seçim ilk tam seçimde data/interim/judge_calibration/selection.json'a
  sabitlenir.
- Her iş önce TEK çağrıda (prompts/judge.txt), sonra üçlüsüyle TOPLU çağrıda (prompts/judge_batch.txt) yargılanır
  (çift sıralı üçlülerde önce tekli, tek sıralılarda önce toplu). Karşılaştırma yalnız toplu yöntemin etkisini ölçsün
  diye bir üçlünün iki modu da AYNI yargıç modeliyle yapılır (config judge_models sırasıyla üreticiden farklı ilk model).
- Örnekler 11'in kural + kanıt kontrolünden geçmiş hâlleridir (11.prepare_rows).

Önceden belirlenen kabul ölçütü (sonuçlar görülmeden yazıldı, 11.11.2026; Eda onayı):
  (1) örnek düzeyinde karar (geçti/kaldı) uyumu >= %90
  (2) tekli yargıcın elediği örneklerin >= %90'ı toplu yargıçta da elenir (toplu yargıç daha gevşek değil).
      Tekli yargıç 5'ten az örnek elediyse (2) değerlendirilemez -> ölçüt SAĞLANMAMIŞ sayılır (veri yetersiz).
  (3) uyuşmayan örnekler elle incelenir; kaynak karıştırma görülürse (1)-(2) sağlansa bile toplu yöntem kullanılmaz.
Sonuçlar resmî yargıç dosyalarına KARIŞMAZ: data/interim/judge_calibration/. Rapor: reports/judge_calibration.md (+.json).
config judge.jobs_per_call yalnız Eda raporu inceleyip onaylarsa 3 yapılır.

    python scripts/judge_calibration.py     # kaldığı yerden devam eder
Çıkış: 0 = rapor yazıldı, 2 = kota/yoğunluk nedeniyle bekleyen çağrı var, 3 = seçim için yeterli iş yok (bekleyin)
"""
from __future__ import annotations

import importlib
import json
import random
import sys
from collections import Counter, defaultdict

from common import CFG, RemovalLog, append_jsonl, get_logger, now_iso, p, read_jsonl

log = get_logger("judge_calibration")
v11 = importlib.import_module("11_verify_instructions")
I = CFG["instruction"]
OUT = p("interim") / "judge_calibration"
SIZE = 3
PLAN = {"DOC": 4, "REF": 1, "SE": 1}       # türe göre üçlü sayısı (iş kimliğindeki tür: JOB_DOC_, JOB_REF_, JOB_SE_)
CRITERIA = {"min_agreement": 0.90, "min_fail_recall": 0.90, "min_single_fails": 5}
MAX_ATTEMPTS = 2                           # içerikle ilgili hata/eksik cevapta bir çağrı en fazla bu kadar denenir


def select(by_job: dict) -> list[list[str]] | None:
    rnd = random.Random(CFG["project"]["random_seed"] + 222)
    triples = []
    for kind, n in PLAN.items():
        keyed = defaultdict(list)
        for j in sorted(by_job):
            if j.split("_")[1] == kind:
                keyed[tuple(sorted(v11.job_models(by_job[j])))].append(j)
        pools = []
        for key in sorted(keyed):
            js = keyed[key][:]
            rnd.shuffle(js)
            pools.append([sorted(js[i:i + SIZE]) for i in range(0, len(js) - SIZE + 1, SIZE)])
        # sırayla her üretici modelden birer üçlü (çeşitlilik), yetmezse kalanlardan
        chosen = []
        while len(chosen) < n and any(pools):
            for pool in pools:
                if pool and len(chosen) < n:
                    chosen.append(pool.pop(0))
        if len(chosen) < n:
            log.warning(f"{kind}: {n} üçlü gerekli, {len(chosen)} oluşturulabildi (üretici başına tamamlanmış iş: "
                        f"{ {k: len(v) for k, v in keyed.items()} })")
            return None
        triples += chosen
    return triples


def judge_model_for(rows: list[dict]) -> str:
    excl = v11.job_models(rows)
    return next(m for m in I["judge_models"] if m not in excl)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, docs = v11.prepare_rows(RemovalLog(OUT / "unused_removed.csv", "calibration"))  # kaydedilmez
    by_job = defaultdict(list)
    for r in rows:
        by_job[r["job_id"]].append(r)

    sel_f = OUT / "selection.json"
    if sel_f.exists():
        sel = json.loads(sel_f.read_text(encoding="utf-8"))
    else:
        triples = select(by_job)
        if triples is None:
            log.info("Seçim için yeterli tamamlanmış iş yok; üretim ilerleyince yeniden çalıştırın")
            return 3
        sel = {"created_at": now_iso(), "size": SIZE, "plan": PLAN, "criteria": CRITERIA,
               "triples": [{"jobs": t, "judge_model": judge_model_for([x for j in t for x in by_job[j]])}
                           for t in triples]}
        sel_f.write_text(json.dumps(sel, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info(f"Seçim sabitlendi: {len(triples)} üçlü, {sum(len(t) for t in triples)} iş")

    files = {"single": OUT / "single.jsonl", "batch": OUT / "batch.jsonl"}
    judged = {m: {r["raw_example_id"]: r for r in read_jsonl(f)} for m, f in files.items()}
    att_f = OUT / "attempts.jsonl"
    attempts = Counter(r["task"] for r in read_jsonl(att_f))

    tasks = []   # (görev adı, mod, iş listesi, yargıç modeli, üçlü sırası)
    for t, tr in enumerate(sel["triples"]):
        single = [(f"single:{j}", "single", [j], tr["judge_model"], t) for j in tr["jobs"]]
        batch = [(f"batch:{t}", "batch", tr["jobs"], tr["judge_model"], t)]
        tasks += (single + batch) if t % 2 == 0 else (batch + single)

    def done(mode: str, jobs: list[str]) -> bool:
        return all(x["raw_example_id"] in judged[mode] for j in jobs for x in by_job[j])

    todo = [tk for tk in tasks if not done(tk[1], tk[2]) and attempts[tk[0]] < MAX_ATTEMPTS]
    missing_jobs = [j for tr in sel["triples"] for j in tr["jobs"] if j not in by_job]
    if missing_jobs:
        log.warning(f"Seçimdeki {len(missing_jobs)} işin kontrolden geçen örneği yok: {missing_jobs}")
    if todo:
        from llm import Gemini, QuotaExhausted, TransientError

        llm = Gemini(I["judge_models"], I["judge_temperature"], I.get("judge_thinking_budget"))
        tmpl = (v11.PD / "judge.txt").read_text(encoding="utf-8")
        tmpl_b = (v11.PD / "judge_batch.txt").read_text(encoding="utf-8")
        log.info(f"Kalibrasyon: {len(todo)} çağrı bekliyor")
        unavailable = set()   # bu çalıştırmada yoğun/kotası dolu yargıç modelleri: yalnız onların görevleri atlanır
        for name, mode, jobs, model, t in todo:
            if model in unavailable:
                continue
            prompt, flat = v11.judge_prompt(jobs, by_job, docs, tmpl, tmpl_b if mode == "batch" else None)
            try:
                # yalnız seçilen yargıç modeli (iki mod aynı modelle)
                res = llm.generate_json(v11.JUDGE_SYSTEM, prompt, list[v11.Judgment],
                                        exclude=set(I["judge_models"]) - {model})
            except (QuotaExhausted, TransientError) as e:
                unavailable.add(model)
                log.warning(f"{name}: {model} şu an kullanılamıyor ({str(e)[:120]}); bu modelin görevleri "
                            f"sonra devam eder")
                continue
            except Exception as e:
                attempts[name] += 1
                append_jsonl(att_f, {"task": name, "result": "error", "detail": str(e)[:200], "at": now_iso()})
                log.error(f"{name}: {str(e)[:200]}")
                continue
            if llm.last_model != model:
                raise RuntimeError(f"{name}: beklenen yargıç {model}, kullanılan {llm.last_model}")
            for x, jd in v11.parse_judgments(res, flat):
                rec = {"raw_example_id": x["raw_example_id"], "job_id": x["job_id"], "mode": mode, "triple": t,
                       **jd, "judge_model": llm.last_model, "at": now_iso()}
                judged[mode][rec["raw_example_id"]] = rec
                append_jsonl(files[mode], rec)
            attempts[name] += 1
            miss = sum(1 for j in jobs for x in by_job[j] if x["raw_example_id"] not in judged[mode])
            append_jsonl(att_f, {"task": name, "result": "ok" if not miss else "partial", "missing": miss,
                                 "model": llm.last_model, "at": now_iso()})
            log.info(f"{name}: {len(flat) - miss}/{len(flat)} örnek değerlendirildi ({llm.last_model})")
        todo = [tk for tk in tasks if not done(tk[1], tk[2]) and attempts[tk[0]] < MAX_ATTEMPTS]
        if todo:
            return 2

    report(sel, by_job, judged)
    return 0


def report(sel: dict, by_job: dict, judged: dict) -> None:
    kind_of = {j: j.split("_")[1] for tr in sel["triples"] for j in tr["jobs"]}
    ex = [x for tr in sel["triples"] for j in tr["jobs"] for x in by_job.get(j, [])]
    pairs, gaps = [], []
    for x in ex:
        s, b = judged["single"].get(x["raw_example_id"]), judged["batch"].get(x["raw_example_id"])
        (pairs if s and b else gaps).append((x, s, b))
    n = len(pairs)
    sf = [bool(v11.judge_failed(s)) for _, s, _ in pairs]
    bf = [bool(v11.judge_failed(b)) for _, _, b in pairs]
    agree = sum(a == c for a, c in zip(sf, bf))
    n_sf, both = sum(sf), sum(a and c for a, c in zip(sf, bf))
    recall = both / n_sf if n_sf else None
    by_kind = {}
    for k in PLAN:
        idx = [i for i, (x, _, _) in enumerate(pairs) if kind_of[x["job_id"]] == k]
        by_kind[k] = {"examples": len(idx), "agreement": round(sum(sf[i] == bf[i] for i in idx) / len(idx), 4) if idx else None,
                      "single_fail": sum(sf[i] for i in idx), "batch_fail": sum(bf[i] for i in idx)}
    crit_diff = {c: sum(bool(s[c]) != bool(b[c]) for _, s, b in pairs) for c in v11.CRIT}
    se = [(s, b) for x, s, b in pairs if kind_of[x["job_id"]] == "SE"]
    lvl = sum(s["level"] == b["level"] for s, b in se)
    c1 = n > 0 and agree / n >= CRITERIA["min_agreement"]
    c2_eval = n_sf >= CRITERIA["min_single_fails"]
    c2 = c2_eval and recall >= CRITERIA["min_fail_recall"]
    dis = []
    for (x, s, b), a, c in zip(pairs, sf, bf):
        if a != c:
            dis.append({"raw_example_id": x["raw_example_id"], "job_id": x["job_id"], "task_type": x["task_type"],
                        "single": f"{'FAIL' if a else 'pass'} {v11.judge_failed(s)} {s['issues']}",
                        "batch": f"{'FAIL' if c else 'pass'} {v11.judge_failed(b)} {b['issues']}",
                        "instruction": x["instruction"][:160].replace("\n", " ")})
    res = {"at": now_iso(), "selection_created_at": sel["created_at"], "criteria": sel["criteria"],
           "triples": sel["triples"], "examples_selected": len(ex), "examples_compared": n,
           "examples_not_compared": [x["raw_example_id"] for x, _, _ in gaps],
           "agreement": round(agree / n, 4) if n else None, "single_fail": n_sf, "batch_fail": sum(bf),
           "fail_both": both, "fail_recall": round(recall, 4) if recall is not None else None,
           "single_only_fail": sum(a and not c for a, c in zip(sf, bf)),
           "batch_only_fail": sum(c and not a for a, c in zip(sf, bf)),
           "by_kind": by_kind, "criterion_disagreements": crit_diff,
           "se_level_agreement": round(lvl / len(se), 4) if se else None,
           "criterion_1_agreement_ok": c1, "criterion_2_evaluable": c2_eval, "criterion_2_recall_ok": c2,
           "automatic_criteria_met": bool(c1 and c2), "disagreements": dis}
    (p("reports") / "judge_calibration.json").write_text(json.dumps(res, indent=2, ensure_ascii=False),
                                                              encoding="utf-8")
    pct = lambda v: "—" if v is None else f"%{100 * v:.1f}"  # noqa: E731
    L = ["# Toplu yargıç kalibrasyonu", "",
         f"Rapor: {res['at']} · seçim: {sel['created_at']} · üretici: `scripts/judge_calibration.py`", "",
         "Soru: Bir yargıç çağrısında 3 iş değerlendirmek, her işi ayrı çağrıda değerlendirmekle aynı kararları veriyor mu? "
         "Her iş iki kez, **aynı yargıç modeliyle** değerlendirildi: tek başına ve üçlüsüyle birlikte.", "",
         "## Önceden belirlenen ölçüt (11.11.2026, sonuçlardan önce)",
         f"1. Karar uyumu ≥ %{100 * CRITERIA['min_agreement']:.0f}",
         f"2. Tekli yargıcın elediği örneklerin ≥ %{100 * CRITERIA['min_fail_recall']:.0f}'ı toplu yargıçta da elenir "
         f"(tekli yargıç {CRITERIA['min_single_fails']}'ten az örnek elediyse değerlendirilemez = sağlanmadı)",
         "3. Uyuşmayan örneklerde kaynak karıştırma yok (elle inceleme)", "",
         "## Sonuç", "| Ölçü | Değer |", "|---|---|",
         f"| Karşılaştırılan örnek | {n} / {len(ex)} |",
         f"| Karar uyumu | {pct(res['agreement'])} |",
         f"| Tekli yargıcın elediği | {n_sf} |", f"| Toplu yargıcın elediği | {sum(bf)} |",
         f"| İkisinin de elediği | {both} (yakalama {pct(res['fail_recall'])}) |",
         f"| Yalnız tekli eledi (toplu daha gevşek) | {res['single_only_fail']} |",
         f"| Yalnız toplu eledi (toplu daha sıkı) | {res['batch_only_fail']} |",
         f"| SE seviye uyumu | {pct(res['se_level_agreement'])} ({len(se)} örnek) |", "",
         f"- Ölçüt 1 (uyum): **{'sağlandı' if c1 else 'SAĞLANMADI'}**",
         f"- Ölçüt 2 (yakalama): **{'sağlandı' if c2 else ('SAĞLANMADI' if c2_eval else 'DEĞERLENDİRİLEMEDİ (veri yetersiz)')}**",
         "- Ölçüt 3 (kaynak karıştırma): uyuşmayan örneklerin elle incelenmesi gerekir (aşağıdaki tablo)", "",
         "## Türe göre", "| Tür | Örnek | Uyum | Tekli eledi | Toplu eledi |", "|---|---|---|---|---|"]
    L += [f"| {k} | {v['examples']} | {pct(v['agreement'])} | {v['single_fail']} | {v['batch_fail']} |"
          for k, v in by_kind.items()]
    L += ["", "## Ölçüt bazında farklı karar sayısı", "| Ölçüt | Farklı |", "|---|---|"]
    L += [f"| {c} | {d} |" for c, d in crit_diff.items()]
    L += ["", "## Üçlüler", "| # | İşler | Yargıç modeli |", "|---|---|---|"]
    L += [f"| {t} | {', '.join(tr['jobs'])} | {tr['judge_model']} |" for t, tr in enumerate(sel["triples"])]
    L += ["", f"## Uyuşmayan örnekler ({len(dis)})", "| Örnek | Görev | Tekli | Toplu | Talimat |", "|---|---|---|---|---|"]
    esc = lambda s: str(s).replace("|", "/").replace("\n", " ")  # noqa: E731
    L += [f"| {d['raw_example_id']} | {d['task_type']} | {esc(d['single'])[:220]} | {esc(d['batch'])[:220]} | "
          f"{esc(d['instruction'])} |" for d in dis]
    if gaps:
        L += ["", f"Karşılaştırılamayan örnek: {len(gaps)} (bir modda değerlendirilemedi)"]
    L += ["", "Karar: bu rapor Eda'ya sunulur; `config.yaml` → `instruction.judge.jobs_per_call` yalnız Eda onaylarsa 3 yapılır."]
    (p("reports") / "judge_calibration.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log.info(f"Rapor: uyum {pct(res['agreement'])}, tekli eledi {n_sf}, toplu eledi {sum(bf)}, yakalama "
             f"{pct(res['fail_recall'])}; otomatik ölçüt {'sağlandı' if res['automatic_criteria_met'] else 'sağlanmadı'}")


if __name__ == "__main__":
    sys.exit(main())
