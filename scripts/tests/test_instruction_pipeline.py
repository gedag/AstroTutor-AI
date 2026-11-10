"""Instruction v2.0 pipeline'ının SAHTE Gemini ile uçtan uca testi: 09 -> 10 -> 11 -> 12 -> 13 -> 14 -> validate.

- Gemini'ye istek GÖNDERMEZ (llm.Gemini sahte sınıfla değiştirilir); gerçek veriye DOKUNMAZ: interim/final/reports/qc/
  logs/samples geçici bir klasöre yönlendirilir (ASTROTUTOR_CONFIG), corpus'un küçük bir alt kümesi oraya kopyalanır.
- Sahte model bilerek kusurlu örnekler üretir; kuralların ve aşamalı yargıcın bunları yakaladığı doğrulanır.

    python scripts/tests/test_instruction_pipeline.py
"""
from __future__ import annotations

import csv
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="astrotutor_test_"))
SOURCES = ("nasa_science", "wikipedia_en", "openstax_astronomy_2e", "arxiv_astro_ph")

# ---------------------------------------------------------------- 1) test yapılandırması (geçici yollar)
cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
for k in ("interim", "final", "samples", "reports", "qc", "logs"):
    cfg["paths"][k] = str(TMP / k)
cfg["instruction"]["target_total"] = 400
# küçük test setinde grupların bir kısmı durabilsin diye eşik gevşek (gerçek ayar: %5, %95 güven)
cfg["instruction"]["judge"]["full_check_fail_rate"] = 0.5
cfg["qc"]["instruction_sample"] = 30
(TMP / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
os.environ["ASTROTUTOR_CONFIG"] = str(TMP / "config.yaml")

# ---------------------------------------------------------------- 2) küçük corpus alt kümesi (gerçek dokümanlar, değiştirilmeden)
(TMP / "final").mkdir(parents=True)
per = Counter()
for s in ("train", "validation", "test"):
    with open(ROOT / "data/final" / f"{s}.jsonl", encoding="utf-8") as fin, \
            open(TMP / "final" / f"{s}.jsonl", "w", encoding="utf-8") as fout:
        for line in fin:
            d = json.loads(line)
            lim = 3000 if d["source"] != "arxiv_astro_ph" else 1000
            cap = 40 if s == "train" else 6
            if d["source"] in SOURCES and d["char_count"] >= lim and per[(s, d["source"])] < cap:
                per[(s, d["source"])] += 1
                fout.write(line)
            elif d["source"] == "nasa_apod" and per[(s, "apod")] < 3:   # uygun olmayan kaynak da bulunsun
                per[(s, "apod")] += 1
                fout.write(line)
CORPUS = {}
for s in ("train", "validation", "test"):
    for line in open(TMP / "final" / f"{s}.jsonl", encoding="utf-8"):
        d = json.loads(line)
        CORPUS[d["document_id"]] = d

sys.path.insert(0, str(ROOT / "scripts"))
import llm  # noqa: E402  (ASTROTUTOR_CONFIG ayarlandıktan SONRA)

bad = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global bad
    bad += not ok
    print(("ok   " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""), flush=True)


# ---------------------------------------------------------------- 3) sahte Gemini
class FakeGemini:
    """llm.Gemini ile aynı arayüz. Üretimde her 3. çağrı 'lite' modeli sayılır (iki üretici türü de denensin)."""
    GEN = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

    def __init__(self, models, temperature, thinking=None):
        self.models = [models] if isinstance(models, str) else list(models)
        self.last_model = None
        self.calls = 0
        self.calls_by_model: dict = {}
        self.busy: dict = {}
        self.usage = {"prompt_tokens": 0, "output_tokens": 0}
        self.exhausted: set = set()
        self.force_exclude: set = set()
        self.n_doc = 0
        self.bad_level_done = False

    def generate_json(self, system, prompt, schema, exclude=None):
        self.calls += 1
        if "quality auditor" in system:
            return self._judge(prompt, exclude or set())
        self.last_model = self.GEN[1] if self.calls % 3 == 0 else self.GEN[0]
        self.calls_by_model[self.last_model] = self.calls_by_model.get(self.last_model, 0) + 1
        if "SOURCE DOCUMENT" in prompt:
            return self._doc(prompt)
        return self._refusal(prompt)

    @staticmethod
    def _words(text: str) -> list[str]:
        return text.split()

    def _doc(self, prompt: str) -> list[dict]:
        self.n_doc += 1
        text = prompt.split("\n---\n")[1]
        title = re.search(r"^Title: (.*)$", prompt, re.M).group(1)
        w = self._words(text)
        tasks = re.findall(r"^\d+\. task_type=(\w+), level=(\w+)$", prompt, re.M)
        out = []
        for k, (t, lv) in enumerate(tasks):
            i = (k * 53 + self.n_doc * 7) % max(1, len(w) - 40)
            ev = " ".join(w[i:i + 14])
            key = " ".join(re.findall(r"[A-Za-z]{4,}", " ".join(w[i:i + 30]))[:5]) or title
            tag = f"{title[:40]} ({self.n_doc}-{k}: {key})"
            ins = f"Please explain {tag} for a {lv} student in clear terms."
            resp = (f"Here is the explanation of {key}. {ev}. This idea matters in astronomy because it connects "
                    f"observations with physical understanding.")
            if t == "mcq_generation":
                # kaynaktaki retorik sorular ("...?") mcq_check'te içerik sorusu sayılır (doğru davranış, ayrı test
                # edilir); sahte pasajda iş reddine yol açmasın diye nokta yapılır
                passage = " ".join(w[i:i + 70]).replace("?", ".")
                ins = f"Write one four-option question from the passage below and return it as JSON. Passage: {passage}"
                q = {"question": f"Which statement about {key} is supported by the passage?",
                     "options": {"A": f"{key} statement one", "B": "an unrelated claim about comets",
                                 "C": "a claim about ocean tides", "D": "a claim about volcanoes"},
                     "answer": "A", "explanation": "The passage supports option A."}
                resp = json.dumps({"questions": [q]})
            elif t == "summarization":
                ins = f"Summarize the following text in two sentences for high school students: {' '.join(w[i:i + 160])}"
            elif t == "classification":
                ins = (f"Classify Mercury, Venus, Jupiter and Neptune ({tag}) as terrestrial or giant planets and "
                       f"explain each choice briefly.")
                resp = ("Mercury and Venus are terrestrial planets because they are small and rocky. Jupiter and "
                        "Neptune are giant planets because they are large and mostly made of gases and ices.")
            elif t == "step_by_step_problem_solving":
                resp = f"1. Identify the quantity: {key}.\n2. Use the fact that {ev}.\n3. Combine the steps to reach the result."
            # bilerek kusurlu örnekler
            if t == "definition_explanation" and k % 2 == 0:
                resp = "According to the text, " + resp          # -> response_references_unseen_text
            if t == "comparison" and k % 3 == 0:
                ev = "this quote was invented by the model and does not appear anywhere in the source document at all"
            out.append({"task_type": t, "level": lv, "instruction": ins, "response": resp, "supporting_evidence": ev})
        return out

    def _refusal(self, prompt: str) -> list[dict]:
        n = int(re.search(r"Produce (\d+) different", prompt).group(1))
        topics = ["my horoscope", "bitcoin price", "where the ISS is right now", "a medical diagnosis", "election odds",
                  "flat Earth proof", "UFO cover-ups", "my exam answers", "a cake recipe", "game cheats",
                  "stock tips", "tomorrow's weather", "celebrity gossip", "lottery numbers", "my future"]
        return [{"task_type": "out_of_scope_refusal", "level": "beginner",
                 "instruction": f"Hey, can you tell me about {topics[k % len(topics)]} ({self.calls}-{k}) please?",
                 "response": ("I'm sorry, I can't help with that because it is outside astronomy education and I have "
                              "no access to real-time or personal data. I'd be happy to explain a related astronomy topic."),
                 "supporting_evidence": ""} for k in range(n)]

    def _judge(self, prompt: str, exclude: set) -> list[dict]:
        cands = [m for m in self.models if m not in exclude]
        self.last_model = cands[0]
        lite = any("lite" in m for m in exclude)
        out = []
        for i, lv in re.findall(r"^\[(\d+)\] \(task type: \w+, level: (\w+)\)$", prompt, re.M):
            i = int(i)
            fail = lite and i % 4 == 1                       # lite: ~%25 başarısız -> tam kontrol
            level = lv
            if lv == "unassigned":
                level = ["beginner", "intermediate", "advanced"][i % 3]
                if not self.bad_level_done:                  # bir SE örneğinde geçersiz seviye -> level_unassigned
                    level, self.bad_level_done = "expert", True
            out.append({"index": i, "supported": not fail, "correct": True, "follows_instruction": True,
                        "instruction_clear": True, "fluent_english": True, "level": level,
                        "verdict": "fail" if fail else "pass", "issues": "fake: unsupported claim" if fail else ""})
        return out


llm.Gemini = FakeGemini


def run(module: str, *args: str) -> int:
    sys.argv = [module, *args]
    m = importlib.import_module(module)
    rc = m.main()
    return 0 if rc is None else rc


# ---------------------------------------------------------------- 4) zincir
print(f"Geçici klasör: {TMP}", flush=True)
for part in ("se_ref", "doc", "doc_supplement"):
    check(f"09 --part {part}", run("09_build_instruction_sources", "--part", part) == 0)
jobs = [json.loads(x) for x in open(TMP / "interim" / "instruction_jobs.jsonl", encoding="utf-8")]
kinds = Counter(j["kind"] for j in jobs)
check("iş türleri", set(kinds) == {"se", "refusal", "doc"}, str(dict(kinds)))
doc_jobs = [j for j in jobs if j["kind"] == "doc"]
check("doküman işleri yalnız 4 kaynaktan", {j["source_name"] for j in doc_jobs} <= set(SOURCES),
      str(Counter(j["source_name"] for j in doc_jobs)))
tax = set(cfg["instruction"]["taxonomy"])
check("görev türleri İngilizce taksonomide", all(t in tax for j in doc_jobs for t in j["task_types"]))
check("seviyeler İngilizce", all(lv in cfg["instruction"]["levels"] for j in doc_jobs for lv in j["levels"]))
check("arXiv işleri yalnız advanced", all(lv == "advanced" for j in doc_jobs if j["source_name"] == "arxiv_astro_ph"
                                          for lv in j["levels"]))

import pandas as pd  # noqa: E402

b9 = importlib.import_module("09_build_instruction_sources")
se_df = pd.read_parquet(ROOT / "data/raw/stackexchange_space_qa/data/stackexchange_space_qa.parquet")
orig = {f"SE_{r.site}_{r.qid}": (f"{r.question_title}\n\n{r.question_body or ''}".strip(),
                                  (r.answer_body if isinstance(r.answer_body, str) else "").strip())
        for r in se_df.itertuples(index=False)}
items = [it for j in jobs if j["kind"] == "se" for it in j["items"]]
check("SE metni birebir orijinal", all((it["question"], it["answer"]) == orig[it["rid"]] for it in items), f"{len(items)} kayıt")
check("SE kayıtlarında kural dışı öğe yok", all(b9.se_text_issue(it["question"], it["answer"]) is None for it in items))
check("SE kayıtları benzersiz", len({it["rid"] for it in items}) == len(items))
want_se = round(0.12 * 400)
check("SE sayısı hedefin ~%10 fazlası", want_se <= len(items) <= int(want_se * 1.1) + 3, f"{len(items)} (hedef {want_se})")

# Pilot benzetimi: üretim bitmeden 11 çalışırsa yargıç örneklemi ve grup kararı dosyaya SABİTLENMEMELİ
check("10 pilot (3 iş)", run("10_generate_instructions", "--limit", "3") == 0)
check("11 pilot (üretim bitmeden)", run("11_verify_instructions") == 2)
check("pilotta örneklem dosyası yazılmadı", not (TMP / "interim" / "instruction_judge_sample.json").exists())
check("pilotta grup kararı yazılmadı", not (TMP / "interim" / "instruction_judge_plan.json").exists())
check("10 üretim", run("10_generate_instructions") == 0)
raw = [json.loads(x) for x in open(TMP / "interim" / "instructions_raw.jsonl", encoding="utf-8")]
se_raw = [r for r in raw if r["source_name"] == "stackexchange_space_qa"]
check("SE ham örnekleri Gemini'siz", all(r["generator_model"] is None and r["level"] == "unassigned"
                                         and r["generation_method"] == "stackexchange_original_verbatim" for r in se_raw))
check("doküman örneklerinde model kaydı", all(r["generator_model"] for r in raw if r["source_name"] != "stackexchange_space_qa"))

rc = run("11_verify_instructions")
check("11 doğrulama (tüm yargıç işleri bitti)", rc == 0, f"çıkış kodu {rc}")
rem = list(csv.DictReader(open(TMP / "reports" / "removed_instructions.csv", encoding="utf-8")))
reasons = Counter(r["reason"].split(":")[0] for r in rem if r["stage"] == "verify")
for want in ("response_references_unseen_text", "evidence_not_in_source", "judge_fail", "level_unassigned"):
    check(f"kusur yakalandı: {want}", reasons.get(want, 0) > 0, str(reasons.get(want, 0)))
src_reasons = Counter(r["reason"] for r in rem if r["stage"] == "source")
check("SE kaynak elemeleri kayıtlı (not_usable_verbatim)", src_reasons.get("not_usable_verbatim", 0) > 0,
      str(dict(src_reasons.most_common(4))))
plan = json.load(open(TMP / "interim" / "instruction_judge_plan.json", encoding="utf-8"))
full = set(plan["full_check_groups"])
v11 = importlib.import_module("11_verify_instructions")
J = cfg["instruction"]["judge"]
rule = {g: (v11.upper_bound(s["fail"], s["judged"], J["confidence"]) >= J["full_check_fail_rate"])
        for g, s in plan["stage1_groups"].items()}
check("grup kararı kurala birebir uyuyor (üst güven sınırı >= eşik -> tam kontrol)",
      all((g in full) == want for g, want in rule.items()), str(plan["stage1_groups"]))
check("hata veren lite grupları tam kontrolde", any(g.startswith("lite") and s["fail"] for g, s in plan["stage1_groups"].items())
      and all(g in full for g, s in plan["stage1_groups"].items() if s["fail"]))
check("tam kontrole alınmayan grup var (aşamalı karar gerçekten ayırıyor)", any(not w for w in rule.values()))
ver = [json.loads(x) for x in open(TMP / "interim" / "instructions_verified.jsonl", encoding="utf-8")]
sample = set(json.load(open(TMP / "interim" / "instruction_judge_sample.json", encoding="utf-8")))
grp = lambda x: f"{v11.tier(x.get('generator_model'))}|{x['task_type']}"  # noqa: E731
unj_full = [x for x in ver if not x["llm_judged"] and grp(x) in full]
check("tam kontrol grubunda değerlendirilmemiş örnek yok", not unj_full, str(len(unj_full)))
unj_out = [x for x in ver if not x["llm_judged"] and x["job_id"] not in sample and grp(x) not in full]
check("durulan gruplarda değerlendirilmemiş örnekler var (aşamalı yargıç çalışıyor)", len(unj_out) > 0, str(len(unj_out)))
check("SE örneklerinin hepsi değerlendirildi ve seviyeli",
      all(x["llm_judged"] and x["level"] in cfg["instruction"]["levels"] and x.get("level_source") == "llm_judge"
          for x in ver if x["source_name"] == "stackexchange_space_qa"))
summ = json.load(open(TMP / "reports" / "instruction_verification_summary.json", encoding="utf-8"))
check("özet: tahmini kalan hata hesaplandı", summ["estimated_error_rate_remaining"] is not None,
      f"{summ['estimated_error_rate_remaining']} ({summ['judged_by_phase']})")
# yeniden çalıştırma aynı sonucu vermeli (plan ve örneklem dosyada sabit)
before = (TMP / "interim" / "instructions_verified.jsonl").read_bytes()
check("11 tekrar çalıştırma", run("11_verify_instructions") == 0)
check("11 tekrar çalıştırınca çıktı birebir aynı", (TMP / "interim" / "instructions_verified.jsonl").read_bytes() == before)

check("12 ayrım", run("12_split_instructions") == 0)
x_date = {f"SE_{r.site}_{r.qid}": r.answer_creation_date for r in se_df.itertuples(index=False)}
ins = [json.loads(x) for x in open(TMP / "final" / "instruction_v2.0.jsonl", encoding="utf-8")]
check("final örnek sayısı = doğrulanan", len(ins) == len(ver), f"{len(ins)}")
check("final seviyeleri geçerli", all(x["level"] in cfg["instruction"]["levels"] for x in ins))
check("final görev türleri taksonomide", all(x["task_type"] in tax for x in ins), str(Counter(x["task_type"] for x in ins)))
check("doküman örneği corpus kümesini miras aldı",
      all(x["split"] == CORPUS[x["source_document"]]["split"] for x in ins if x["source_document"] in CORPUS))
own = {}
check("bir kaynak doküman tek kümede", all(own.setdefault(x["source_document"], x["split"]) == x["split"] for x in ins))
check("messages biçimi", all([m["role"] for m in x["messages"]] == ["user", "assistant"] for x in ins))
check("SE lisansı tarihe göre ve verified_by", all(x["license"].split(" (")[0] == b9.se_license(x_date[x["source_document"]])
                                                   and x["verified_by"] == "rules+llm_judge"
                                       for x in ins if x["source_name"] == "stackexchange_space_qa"))
check("doküman örneklerinde kanıt kontrolü yazılı", all("evidence" in x["verified_by"] for x in ins
                                                        if x["generation_method"] == "llm_synthetic_from_source_document"))

check("13 inceleme örneklemi", run("13_sample_for_review", "--only", "instruction") == 0)
hdr = next(csv.reader(open(TMP / "qc" / "instruction_review.csv", encoding="utf-8-sig")))
check("inceleme tablosunda ingilizce_akici ölçütü", "claude_ingilizce_akici" in hdr and "claude_turkce_akici" not in hdr)
check("14 kalite raporu", run("14_qc_report") == 0)
check("validate (corpus + instruction)", run("validate_datasets") == 0,
      (TMP / "reports" / "validation_report.md").read_text(encoding="utf-8")[-600:])

print(f"\nhata: {bad}")
if not bad:
    shutil.rmtree(TMP, ignore_errors=True)
else:
    print(f"İnceleme için geçici klasör bırakıldı: {TMP}")
sys.exit(1 if bad else 0)
