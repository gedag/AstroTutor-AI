"""Toplu yargıç (config judge.jobs_per_call) birim testleri — API çağrısı yok.

Kontrol edilenler: işlerin gruplanması (tür + üretici model), tek iş isteminin önceki biçimle birebir aynı olması,
toplu istemde her örneğin kendi kaynağının altında ve numaraların benzersiz olması, yargıç cevabının doğru örneğe
eşlenmesi, toplu şablonun ölçüt metninin tekli şablonla birebir aynı olması.

    python scripts/tests/test_judge_batch.py
"""
import importlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
v11 = importlib.import_module("11_verify_instructions")
from common import fill  # noqa: E402

bad = 0


def check(name, got, want):
    global bad
    ok = got == want
    bad += not ok
    print("ok  " if ok else "FAIL", name, "| beklenen:", want, "| bulunan:", got)


def ex(job, k, model, kind="doc"):
    src = {"doc": "nasa_science", "refusal": "none", "se": "stackexchange_space_qa"}[kind]
    method = v11.SE_METHOD if kind == "se" else "llm_synthetic_from_source_document"
    return {"raw_example_id": f"{job}_{k}", "job_id": job, "task_type": "comparison", "level": "beginner",
            "instruction": f"Compare things in {job} number {k}.", "response": f"Answer for {job} number {k}.",
            "generator_model": model, "source_name": src, "source_document": job.replace("JOB_DOC_", ""),
            "generation_method": method}


M1, M2 = "gemini-3.6-flash", "gemini-3.5-flash"
by_job = {
    "JOB_DOC_DOC_A": [ex("JOB_DOC_DOC_A", k, M1) for k in range(3)],
    "JOB_DOC_DOC_B": [ex("JOB_DOC_DOC_B", k, M2) for k in range(2)],
    "JOB_DOC_DOC_C": [ex("JOB_DOC_DOC_C", k, M1) for k in range(4)],
    "JOB_DOC_DOC_D": [ex("JOB_DOC_DOC_D", k, M1) for k in range(2)],
    "JOB_DOC_DOC_E": [ex("JOB_DOC_DOC_E", k, M1) for k in range(1)],
    "JOB_REFUSAL_0001": [ex("JOB_REFUSAL_0001", k, M1, "refusal") for k in range(2)],
    "JOB_SE_0000": [ex("JOB_SE_0000", k, None, "se") for k in range(2)],
    "JOB_SE_0001": [ex("JOB_SE_0001", k, None, "se") for k in range(3)],
}
docs = {j.replace("JOB_DOC_", ""): {"title": f"Title {j[-1]}", "text": f"Source text of document {j[-1]}. " * 5}
        for j in by_job if j.startswith("JOB_DOC_")}
jids = sorted(by_job)

# 1) gruplama
check("size=1: her iş ayrı, sıra aynen", v11.make_batches(jids, by_job, 1), [[j] for j in jids])
b3 = v11.make_batches(jids, by_job, 3)
check("size=3: her iş tam bir kez", sorted(j for b in b3 for j in b), jids)
check("size=3: çağrı başına en fazla 3 iş", max(len(b) for b in b3), 3)
check("size=3: bir çağrıda tek iş türü", all(len({j.split("_")[1] for j in b}) == 1 for b in b3), True)
check("size=3: bir çağrıda tek üretici model",
      all(len({v11.job_models(by_job[j]) for j in b}) == 1 for b in b3), True)
check("size=3: M1 doküman işleri birlikte", ["JOB_DOC_DOC_A", "JOB_DOC_DOC_C", "JOB_DOC_DOC_D"] in b3, True)
check("size=3: M2 işi ayrı çağrıda", ["JOB_DOC_DOC_B"] in b3, True)
check("size=3: SE işleri birlikte, refusal ile karışmadan", ["JOB_SE_0000", "JOB_SE_0001"] in b3, True)
check("job_models: SE boş", v11.job_models(by_job["JOB_SE_0000"]), frozenset())

# 2) tek iş istemi: önceki kodun ürettiği metnin birebir aynısı
tmpl = (v11.PD / "judge.txt").read_text(encoding="utf-8")
tmpl_b = (v11.PD / "judge_batch.txt").read_text(encoding="utf-8")
rs = by_job["JOB_DOC_DOC_A"]
old_exs = "\n\n".join(f"[{i}] (task type: {x['task_type']}, level: {x['level']})\nINSTRUCTION:\n"
                      f"{x['instruction']}\nRESPONSE:\n{x['response']}" for i, x in enumerate(rs))
old_prompt = fill(tmpl, task_hint="the task type given at the start of each example",
                  source=v11.source_for(rs, docs), examples=old_exs)
p1, flat1 = v11.judge_prompt(["JOB_DOC_DOC_A"], by_job, docs, tmpl, tmpl_b)
check("tek iş istemi önceki biçimle birebir aynı", p1 == old_prompt, True)
check("tek iş örnek sırası", [x["raw_example_id"] for x in flat1], [x["raw_example_id"] for x in rs])

# 3) toplu istem
batch = ["JOB_DOC_DOC_A", "JOB_DOC_DOC_C", "JOB_DOC_DOC_D"]
pb, flat = v11.judge_prompt(batch, by_job, docs, tmpl, tmpl_b)
idx = [int(i) for i in re.findall(r"^\[(\d+)\] \(task type:", pb, re.M)]
check("toplu: numaralar 0..N-1 kesintisiz ve benzersiz", idx, list(range(9)))
check("toplu: örnek listesi işlerin sırasıyla", [x["job_id"] for x in flat],
      ["JOB_DOC_DOC_A"] * 3 + ["JOB_DOC_DOC_C"] * 4 + ["JOB_DOC_DOC_D"] * 2)
check("toplu: yer tutucu kalmadı", re.findall(r"\{(?:n_groups|groups|task_hint|source|examples)\}", pb), [])
check("toplu: grup sayısı başlıkta", "Below are 3 GROUPS" in pb, True)
# her örnek kendi işinin kaynağının altında: örneğin metni, o işin SOURCE başlığından sonra, bir sonraki GROUP'tan önce
parts = re.split(r"^=== GROUP \d+ of 3 ===$", pb, flags=re.M)[1:]
check("toplu: 3 GROUP bloğu", len(parts), 3)
for g, (jid, part) in enumerate(zip(batch, parts), 1):
    d = docs[jid.replace("JOB_DOC_", "")]
    check(f"GROUP {g}: kendi kaynağı var", f"Title: {d['title']}" in part, True)
    others = [docs[o.replace("JOB_DOC_", "")]["title"] for o in batch if o != jid]
    check(f"GROUP {g}: başka kaynak yok", any(f"Title: {t}\n" in part for t in others), False)
    check(f"GROUP {g}: yalnız kendi örnekleri", all((x["instruction"] in part) == (x["job_id"] == jid) for x in flat), True)
    check(f"GROUP {g}: kaynak örneklerden önce", part.index("SOURCE (GROUP") < part.index("EXAMPLES (GROUP"), True)

# 4) cevap eşleme
res = [{"index": 4, "supported": True, "correct": True, "follows_instruction": True, "instruction_clear": True,
        "fluent_english": True, "level": " Beginner", "verdict": "PASS ", "issues": ""},
       {"index": 4, "supported": False, "correct": True, "follows_instruction": True, "instruction_clear": True,
        "fluent_english": True, "level": "beginner", "verdict": "fail", "issues": "dup"},      # tekrar: yok sayılır
       {"index": 9, "supported": True, "correct": True, "follows_instruction": True, "instruction_clear": True,
        "fluent_english": True, "level": "beginner", "verdict": "pass", "issues": ""},        # aralık dışı
       {"index": -1, "supported": True, "correct": True, "follows_instruction": True, "instruction_clear": True,
        "fluent_english": True, "level": "beginner", "verdict": "pass", "issues": ""},        # aralık dışı
       {"index": 8, "supported": False, "correct": True, "follows_instruction": True, "instruction_clear": True,
        "fluent_english": True, "level": "beginner", "verdict": "fail", "issues": "x"}]
pj = v11.parse_judgments(res, flat)
check("eşleme: yalnız geçerli ve ilk index'ler", [(x["raw_example_id"], jd["verdict"]) for x, jd in pj],
      [("JOB_DOC_DOC_C_1", "pass"), ("JOB_DOC_DOC_D_1", "fail")])
check("eşleme: seviye normalize", pj[0][1]["level"], "beginner")
check("eşleme: pydantic nesnesi de kabul",
      v11.parse_judgments([v11.Judgment(**res[0])], flat)[0][0]["raw_example_id"], "JOB_DOC_DOC_C_1")
check("eşleme: boş cevap", v11.parse_judgments(None, flat), [])

# 5) toplu şablonun ölçütleri tekli şablonla birebir aynı (iki yöntem aynı ölçütle yargılar)
crit_1 = tmpl[tmpl.index("Criteria (each true/false):"):tmpl.index("\n\nSOURCE\n---")]
crit_b = tmpl_b[tmpl_b.index("Criteria (each true/false):"):tmpl_b.index("\n\n{groups}")]
check("ölçüt metni iki şablonda aynı", crit_b == crit_1, True)
check("toplu şablon 'yalnız kendi GROUP kaynağı' kuralını içeriyor", "ONLY the SOURCE of its own GROUP" in tmpl_b, True)

# 6) yapılandırma: varsayılan davranış değişmedi
check("config jobs_per_call varsayılan 1", v11.J.get("jobs_per_call"), 1)

print("hata:", bad)
sys.exit(1 if bad else 0)
