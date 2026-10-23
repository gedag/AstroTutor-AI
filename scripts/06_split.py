"""06 — Doküman düzeyinde train / validation / test ayrımı (Vize Rehberi §10).

- Ayırma DOKÜMAN (grup) düzeyinde yapılır; chunk'lar ancak bundan SONRA 07_token_count.py'de üretilir.
  Böylece aynı dokümanın parçaları farklı kümelere düşmez (data leakage önlenir).
- group_key: Wikipedia'da Wikidata QID -> aynı maddenin İngilizce ve Türkçe sürümü aynı kümeye düşer.
- Kaynak bazında tabakalı: her kaynağın %90/%5/%5'i ayrı ayrı ayrılır, böylece test kümesi tüm kaynakları temsil eder.
- Sabit seed: project.random_seed (42).

Girdi : data/interim/corpus_v0.9.jsonl
Çıktı : data/final/{train,validation,test}.jsonl (token_count 07'de eklenir)
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from common import CFG, get_logger, p, read_jsonl, rng, write_jsonl

log = get_logger("06_split")
S = CFG["split"]


def main() -> None:
    docs = list(read_jsonl(p("interim") / "corpus_v0.9.jsonl"))
    groups: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        groups[d["group_key"]].append(d)
    # grubun tabakası = grubun ilk dokümanının kaynağı
    strata: dict[str, list[str]] = defaultdict(list)
    for g, ds in groups.items():
        strata[sorted(ds, key=lambda x: x["document_id"])[0]["source"]].append(g)
    r = rng(6)
    assign: dict[str, str] = {}
    for src in sorted(strata):
        gs = sorted(strata[src])
        r.shuffle(gs)
        n = len(gs)
        n_test = max(1, round(n * S["test"]))
        n_val = max(1, round(n * S["validation"]))
        for i, g in enumerate(gs):
            assign[g] = "test" if i < n_test else "validation" if i < n_test + n_val else "train"
    out = defaultdict(list)
    for d in docs:
        d["split"] = assign[d["group_key"]]
        out[d["split"]].append(d)
    for split in ("train", "validation", "test"):
        write_jsonl(p("final") / f"{split}.jsonl", sorted(out[split], key=lambda x: x["document_id"]))
    # sızıntı kontrolü
    seen = {}
    for split, ds in out.items():
        for d in ds:
            assert seen.setdefault(d["group_key"], split) == split, f"grup iki kümede: {d['group_key']}"
    summary = {s: {"documents": len(ds), "by_source": dict(Counter(d["source"] for d in ds))} for s, ds in out.items()}
    (p("reports") / "split_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("Split: " + ", ".join(f"{s}={len(ds)}" for s, ds in out.items()) + " — grup çakışması yok")


if __name__ == "__main__":
    main()
