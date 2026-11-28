# Veri seti doğrulama raporu

Domain Corpus v2.0 · Instruction Dataset v2.0

- [x] Corpus boş değil — 14683 doküman
- [x] Corpus şeması tam — eksik alanlı 0
- [x] document_id benzersiz
- [x] Corpus dili yalnız en — dışında kalan=0
- [x] Corpus split'leri arasında grup çakışması yok — çakışma=0
- [x] Instruction şeması tam — 3319 örnek, eksik alanlı 0
- [x] Instruction id benzersiz
- [x] Instruction görev türleri İngilizce taksonomide — dışında=0
- [x] Instruction seviyeleri geçerli — geçersiz=0
- [x] Aynı kaynak dokümandan gelen örnekler tek kümede — çakışma=0
- [x] Instruction kümesi = kaynak dokümanın corpus kümesi (CPT↔SFT sızıntısı yok) — uyumsuz=0
- [x] instruction/train.jsonl mevcut — 3011 örnek
- [x] instruction/validation.jsonl mevcut — 175 örnek
- [x] instruction/test.jsonl mevcut — 133 örnek
- [x] Corpus HF datasets ile yükleniyor — {'train': 13223, 'validation': 735, 'test': 725}
- [x] Instruction HF datasets ile yükleniyor — {'train': 3011, 'validation': 175, 'test': 133}
- [x] Qwen/Qwen3-1.7B chat template uygulanabiliyor ve ≤ 1024 token (Final SFT'ye hazır) — hatalı=0; medyan=242, p95=505, maks=934; 1024 üzeri=0
- [x] Instruction ↔ değerlendirme setleri 8-gram örtüşmesi = 0 — örtüşen=0
- [i] Corpus'ta değerlendirme setleriyle ≥3 adet 8-gram paylaşan doküman: 75 (bilgi amaçlı; çoğu genel ifade, ör. "the big bang theory of the origin of the universe")
- [i] Corpus ile ≥3 adet 8-gram paylaşan değerlendirme sorusu: 60 (liste: reports/eval_contamination.csv; final dönemi karşılaştırmasında ayrıca raporlanacak)
