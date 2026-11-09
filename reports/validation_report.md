# Veri seti doğrulama raporu

Domain Corpus v2.0

- [x] Corpus boş değil — 14683 doküman
- [x] Corpus şeması tam — eksik alanlı 0
- [x] document_id benzersiz
- [x] Corpus dili yalnız en — dışında kalan=0
- [x] Corpus split'leri arasında grup çakışması yok — çakışma=0
- [i] Yalnız corpus doğrulandı (--corpus-only): Instruction Dataset v2.0 henüz üretilmedi
- [x] Corpus HF datasets ile yükleniyor — {'train': 13223, 'validation': 735, 'test': 725}
- [i] Corpus'ta değerlendirme setleriyle ≥3 adet 8-gram paylaşan doküman: 75 (bilgi amaçlı; çoğu genel ifade, ör. "the big bang theory of the origin of the universe")
- [i] Corpus ile ≥3 adet 8-gram paylaşan değerlendirme sorusu: 60 (liste: reports/eval_contamination.csv; final dönemi karşılaştırmasında ayrıca raporlanacak)
