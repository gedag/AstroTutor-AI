# Veri seti doğrulama raporu

- [x] Corpus boş değil — 16284 doküman
- [x] Corpus şeması tam — eksik alanlı 0
- [x] document_id benzersiz
- [x] Corpus split'leri arasında grup çakışması yok — çakışma=0
- [x] Instruction şeması tam — 3340 örnek, eksik alanlı 0
- [x] Instruction id benzersiz
- [x] Aynı kaynak dokümandan gelen örnekler tek kümede — çakışma=0
- [x] Instruction kümesi = kaynak dokümanın corpus kümesi (CPT↔SFT sızıntısı yok) — uyumsuz=0
- [x] instruction/train.jsonl mevcut — 3027 örnek
- [x] instruction/validation.jsonl mevcut — 159 örnek
- [x] instruction/test.jsonl mevcut — 154 örnek
- [x] Corpus HF datasets ile yükleniyor — {'train': 14660, 'validation': 819, 'test': 805}
- [x] Instruction HF datasets ile yükleniyor — {'train': 3027, 'validation': 159, 'test': 154}
- [x] Qwen2.5-7B-Instruct chat template uygulanabiliyor (talimat ve cevap şablonda birebir) — hatalı=0; örnek token uzunluğu medyan=231, p95=484, maks=971; 2048 token üzeri=0
- [x] Instruction ↔ değerlendirme setleri 8-gram örtüşmesi = 0 — örtüşen=0
- [i] Corpus'ta değerlendirme setleriyle ≥3 adet 8-gram paylaşan doküman: 75 (bilgi amaçlı; çoğu genel ifade, ör. "the big bang theory of the origin of the universe")
- [i] Corpus ile ≥3 adet 8-gram paylaşan değerlendirme sorusu: 60 (liste: reports/eval_contamination.csv; final dönemi karşılaştırmasında ayrıca raporlanacak)
