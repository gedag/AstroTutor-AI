"""16 — Git deposuna girecek küçük örnek veriler -> data/samples/

Büyük veri dosyaları (data/final/) depoya konmaz (Rehber §13); biçimi göstermek için her veri setinden küçük,
rastgele (seed 42) ve gerçek örnekler alınır. Örnekler final dosyalardan değiştirilmeden kopyalanır.

- corpus_sample.jsonl       : her kaynaktan 3 doküman (train), 6.000 karakterden kısa olanlar arasından
- chunks_sample.jsonl       : train chunk'larından 5 örnek
- instruction_sample.jsonl  : her görev türünden 2 örnek (instruction_v1.0.jsonl varsa)
"""
from __future__ import annotations

from collections import defaultdict

from common import get_logger, p, read_jsonl, rng, write_jsonl

log = get_logger("16_make_samples")
PER_SOURCE, MAX_CHARS, N_CHUNKS, PER_TASK = 3, 6000, 5, 2


def main() -> None:
    out = p("samples")
    out.mkdir(parents=True, exist_ok=True)
    r = rng(16)

    by_src = defaultdict(list)
    for d in read_jsonl(p("final") / "train.jsonl"):
        if len(d["text"]) <= MAX_CHARS:
            by_src[d["source"]].append(d)
    corpus = []
    for src in sorted(by_src):
        corpus += r.sample(by_src[src], min(PER_SOURCE, len(by_src[src])))
    n = write_jsonl(out / "corpus_sample.jsonl", corpus)
    log.info(f"corpus_sample.jsonl: {n} doküman ({len(by_src)} kaynak)")

    chunks = list(read_jsonl(p("final") / "chunks" / "train.jsonl"))
    n = write_jsonl(out / "chunks_sample.jsonl", r.sample(chunks, min(N_CHUNKS, len(chunks))))
    log.info(f"chunks_sample.jsonl: {n} chunk")

    ins_f = p("final") / "instruction_v1.0.jsonl"
    if ins_f.exists():
        by_task = defaultdict(list)
        for x in read_jsonl(ins_f):
            if x.get("split") == "train":
                by_task[x["task_type"]].append(x)
        ins = []
        for t in sorted(by_task):
            ins += r.sample(by_task[t], min(PER_TASK, len(by_task[t])))
        n = write_jsonl(out / "instruction_sample.jsonl", ins)
        log.info(f"instruction_sample.jsonl: {n} örnek ({len(by_task)} görev türü)")
    else:
        log.warning("instruction_v1.0.jsonl yok; instruction örneği 12 çalıştıktan sonra üretilecek")


if __name__ == "__main__":
    main()
