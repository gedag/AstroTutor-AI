"""07 — Token sayımı ve (split'ten sonra) anlamsal sınırlara saygılı chunk üretimi (Vize Rehberi §10).

Tokenizer: config tokenizer.name (Qwen/Qwen2.5-7B — Tasarım raporundaki model ailesi; base ve instruct aynı tokenizer).
Her dokümana token_count eklenir; min/medyan/ortalama/p95/maks raporlanır.

Chunk stratejisi (başlangıç önerisi, final döneminde kesinleşecek):
  - Paragraf sınırında kes; '## ' başlıkları yeni chunk başlatır (chunk doluluğu > %25 ise)
  - max_tokens'ı aşan tek paragraf cümle sınırında bölünür
  - Chunk'lar her split için ayrı üretilir -> doküman parçaları kümeler arasında karışmaz
Çıktı: data/final/{split}.jsonl (token_count eklenmiş), data/final/chunks/{split}.jsonl, reports/token_stats.json
"""
from __future__ import annotations

import json
import re
import statistics

from common import CFG, get_logger, p, read_jsonl, write_jsonl

log = get_logger("07_token_count")
MAX = CFG["chunking"]["max_tokens"]


def pct(xs: list[int], q: float) -> int:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def describe(xs: list[int]) -> dict:
    if not xs:
        return {}
    return {"count": len(xs), "total": sum(xs), "min": min(xs), "median": int(statistics.median(xs)),
            "mean": round(statistics.mean(xs), 1), "p95": pct(xs, 0.95), "max": max(xs)}


def chunk_doc(d: dict, tok) -> list[dict]:
    """Chunk metni dokümanın BİREBİR alt dizisidir (paragraf ayırıcıları korunur; RAG'de kaynak gösterilebilir).
    24.10.2026 denetimi: ilk sürüm satırları tek '\\n' ile birleştiriyordu; paragraflar arasındaki boş satır
    kayboluyor ve chunk metni dokümanda aranınca bulunamıyordu."""
    text = d["text"]
    units = []  # (başlangıç, bitiş, token)
    for m in re.finditer(r"[^\n]+", text):
        if not m.group(0).strip():
            continue
        n = len(tok.encode(m.group(0), add_special_tokens=False))
        if n <= MAX:
            units.append((m.start(), m.end(), n))
        else:  # çok uzun paragraf: cümle sınırında böl
            for s in re.finditer(r".+?(?:[.!?](?=\s)|$)", m.group(0)):
                if s.group(0).strip():
                    a = m.start() + s.start() + (len(s.group(0)) - len(s.group(0).lstrip()))
                    units.append((a, m.start() + s.end(), len(tok.encode(s.group(0), add_special_tokens=False))))
    spans, cur, cur_n = [], [], 0
    for a, b, n in units:
        new_section = text.startswith("## ", a) and cur_n > 0.25 * MAX
        if cur and (cur_n + n + 1 > MAX or new_section):  # +1: birimler arası ayırıcı token payı
            spans.append((cur[0][0], cur[-1][1]))
            cur, cur_n = [], 0
        cur.append((a, b))
        cur_n += n + 1
    if cur:
        spans.append((cur[0][0], cur[-1][1]))
    out = []
    for i, (a, b) in enumerate(spans):
        t = text[a:b]
        out.append({"chunk_id": f"{d['document_id']}_C{i:03d}", "document_id": d["document_id"], "chunk_index": i,
                    "char_start": a, "char_end": b, "source": d["source"], "language": d["language"],
                    "subtopic": d["subtopic"], "split": d["split"],
                    "token_count": len(tok.encode(t, add_special_tokens=False)), "text": t})
    return out


def main() -> None:
    from transformers import AutoTokenizer

    name = CFG["tokenizer"]["name"]
    tok = AutoTokenizer.from_pretrained(name)
    log.info(f"Tokenizer: {name} (vocab {tok.vocab_size})")
    all_tokens, per_source, per_split, per_lang = [], {}, {}, {}
    chunk_tokens = []
    for split in ("train", "validation", "test"):
        docs = list(read_jsonl(p("final") / f"{split}.jsonl"))
        enc = tok([d["text"] for d in docs], add_special_tokens=False)["input_ids"]
        chunks = []
        for d, ids in zip(docs, enc):
            d["token_count"] = len(ids)
            all_tokens.append(len(ids))
            per_source.setdefault(d["source"], []).append(len(ids))
            per_split.setdefault(split, []).append(len(ids))
            per_lang.setdefault(d["language"], []).append(len(ids))
            chunks += chunk_doc(d, tok)
        # alan sırası Rehber §9 örneğiyle aynı
        order = ["document_id", "title", "source", "url", "language", "document_type", "publication_year",
                 "subtopic", "license", "retrieved_at", "raw_id", "group_key", "split", "postprocess", "char_count",
                 "word_count", "token_count", "text"]
        write_jsonl(p("final") / f"{split}.jsonl", [{k: d.get(k) for k in order} for d in docs])
        write_jsonl(p("final") / "chunks" / f"{split}.jsonl", chunks)
        chunk_tokens += [c["token_count"] for c in chunks]
        log.info(f"{split}: {len(docs)} doküman, {sum(len(x) for x in enc):,} token, {len(chunks)} chunk")
    stats = {"tokenizer": name, "documents": describe(all_tokens),
             "per_source": {k: describe(v) for k, v in per_source.items()},
             "per_split": {k: describe(v) for k, v in per_split.items()},
             "per_language": {k: describe(v) for k, v in per_lang.items()},
             "chunks": {"max_tokens": MAX, **describe(chunk_tokens)}}
    (p("reports") / "token_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    log.info(f"Toplam token: {sum(all_tokens):,}")


if __name__ == "__main__":
    main()
