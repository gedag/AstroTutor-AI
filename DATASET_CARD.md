# Uzay ve Astronomi Domain Corpus v1.0 (AstroTutor AI)

## Amaç
Bu veri seti, uzay ve astronomi eğitiminde kullanıcının seviyesine göre Türkçe konu anlatımı yapan ve anlattığı içerikten çoktan seçmeli soru üreten alana özel bir dil modelinin (AstroTutor AI) **continued pretraining (CPT / DAPT)** aşamasında kullanılmak üzere hazırlanmıştır. Model ailesi olarak Qwen2.5-7B hedeflenmektedir. Genel amaçlı bir corpus değildir; soru-cevap davranışı için ayrı hazırlanan [Instruction Dataset](INSTRUCTION_CARD.md) kullanılır.

## Kapsam
**Kapsam içi:** Güneş Sistemi; gezegenler ve uydular; yıldızların özellikleri ve yıldız evrimi; gökadalar; temel kozmoloji; ötegezegenler; uzay araçları ve keşif görevleri; gözlemevleri ve teleskoplar.

**Kapsam dışı:** ileri matematiksel astrofizik türetmeleri, ham teleskop görüntüsü işleme, bilimsel simülasyon, roket mühendisliği ayrıntıları, Dünya bilimleri, uzay şirketlerinin ticari konuları, astroloji.

**Hedef kullanıcı:** ortaokul–lisans arası öğrenciler ve meraklılar (başlangıç / orta / ileri seviye).

## Veri kaynakları

| Kaynak | Tür | Dil | Ham doküman | Final doküman | Token payı | Lisans / kullanım |
| --- | --- | --- | --- | --- | --- | --- |
| NASA Science (science.nasa.gov) | HTML | en | 3.109 | 2.849 | %16,3 | NASA medya/içerik yönergeleri (kamuya açık, atıf) |
| NASA APOD açıklamaları | HTML | en | 2.720 | 2.445 | %2,9 | NASA hizmeti; yalnız açıklama metni, görseller alınmadı |
| OpenStax Astronomy 2e (ders kitabı) | PDF | en | 243 | 238 | %3,1 | CC BY-NC-SA 4.0 |
| arXiv astro-ph (başlık + özet) | XML | en | 6.000 | 5.953 | %12,4 | CC0 1.0 (arXiv metadata) |
| Wikipedia (İngilizce) | API/JSON | en | 3.576 | 3.238 | %48,5 | CC BY-SA 4.0 |
| Wikipedia (Türkçe) | API/JSON | tr | 1.737 | 1.561 | %16,9 | CC BY-SA 4.0 |
| **Toplam** | | | **17.520** | **16.284** | %100 | |

Kaynakların neden seçildiği, lisans ayrıntıları ve kullanılmayan kaynaklar (NASA Exoplanet Archive: final dönemde RAG; Stack Exchange: yalnız instruction verisi) için: [reports/source_notes.md](reports/source_notes.md), [reports/source_inventory.csv](reports/source_inventory.csv).

İngilizce kaynaklar bilinçli olarak çoğunluktadır: alanın güvenilir ve açık lisanslı birincil kaynakları (NASA, ders kitabı, makale özetleri) İngilizcedir. Türkçe Wikipedia, modelin Türkçe astronomi terminolojisini görmesi için eklenmiştir ve token'ların %16,9'unu oluşturur.

## Veri toplama
Dokümanlar 2026-10-22 – 2026-10-23 tarihleri arasında `scripts/01_download.py` ile indirildi. science.nasa.gov `robots.txt` kurallarına uyuldu (istekler arası 1,2 sn); Wikipedia isteklerinde iletişim bilgili User-Agent kullanıldı ve Wikimedia hız sınırlarına uyuldu; arXiv OAI-PMH'de istekler arası 4,0 sn beklendi. Ham dosyalar `data/raw/` altında değiştirilmeden saklanır; her dosya için URL, SHA-256, erişim zamanı ve lisans `manifest.jsonl` dosyalarında kayıtlıdır.

NASA Science'ta tek bir görevin (ör. Hubble, Cassini) corpus'u domine etmemesi için görev/bölüm başına en fazla 150 sayfa alındı; APOD'dan 1995–2026 arasında her yıldan 85 açıklama örneklendi (seed 42).

## İşleme adımları
- **Extraction:** HTML için Trafilatura (başarısız olursa BeautifulSoup), PDF için PyMuPDF ([pdfplumber ile karşılaştırma](reports/extraction_tool_comparison.md): eşit kalite, PyMuPDF yaklaşık 161 kat hızlı). PDF metin blokları sayfa konumuna göre sıralandı (kenar kutularının paragraflara karışması önlendi). 51 doküman boş/çok kısa çıktı verdiği için elendi; OpenStax'ta 135 bölüm (alıştırma, kaynakça, ekler) içerik dışı sayıldı. Toplam başarısız extraction: 186 / 17.520 (%1,1).
- **Cleaning:** HTML etiket/entity kalıntıları (`<sup>x</sup>` → `^x`), Unicode NFKC (üs ifadeleri önce `10^23` biçimine alınarak), whitespace normalizasyonu, PDF header/footer ve bölüm başlığı satırları, site menüleri ve tekrar eden şablon satırları, kesik tanıtım cümleleri, Wikipedia kaynakça/yayın listesi bölümleri, 'Soyadı, A. B. (yıl). Başlık. Dergi' biçimiyle başlayan kaynakça girdisi satırları (metin içi atıflar korunarak), görsel kredileri, 20 karakterden kısa yalnız satırlar. Sayılar ve formüller silinmedi. Kural listesi ve uygulama sayıları: [reports/cleaning_rules.md](reports/cleaning_rules.md); öncesi/sonrası örnekleri: [reports/cleaning_examples.md](reports/cleaning_examples.md). Elle incelemede bulunan üç sorun ikinci bir geçişte (`scripts/06b_repost_dedup.py`) düzeltildi: (1) Wikipedia düz metin servisi, trafilatura ve PyMuPDF HTML/PDF üst simgelerini sildiği için kaybolan üsler geri yazıldı (1.934 ifade; "1.5 × 108 km" → "1.5 × 10^8 km"); (2) NASA basın bültenlerindeki künye, kredi ve iletişim satırları ile **kişisel iletişim bilgileri (e-posta, telefon)** silindi (531 doküman; kalan e-posta/telefon: 0); (3) NASA sözlük sayfalarında kısa satır kuralının sildiği terimler geri getirildi.
- **Filtering:** 300 karakterden kısa (242), bozuk karakter oranı %15'i aşan veya çoğu simgeden oluşan (3), İngilizce/Türkçe dışındaki (6), satırlarının yarısından fazlası kaynakça girdisi olan yayın listesi (5) ve alan dışı (150) dokümanlar elendi. Alan tespiti astronomi terim sözlüğü yoğunluğu ile yapıldı (`scripts/domain_lexicon.py`). Wikipedia'da kategori gezintisi alt kategorilere indiği için kurgu, film, oyun, bayrak, genel spektroskopi ve jeoloji maddeleri de seçilmişti; her maddenin kendi Wikipedia kategorilerine dayanan ek kuralla 356 madde elendi (kalibrasyonu: [experiments.md](experiments.md)).
- **Deduplication:** exact duplicate SHA-256 ile (46 doküman), near duplicate MinHash LSH (kelime 5-gram, 128 permütasyon) + Jaccard ≥ 0,85 ile (90 doküman). Eşik, 50 aday çift (25'i Jaccard ≥ eşik, 25'i altı) yapay zekâ destekli ön inceleme ve grup üyesinin onayıyla kontrol edildi ([reports/qc/near_dup_pairs_review.csv](reports/qc/near_dup_pairs_review.csv)): eşik üstü 25 çiftin 25'i gerçek tekrardı (hatalı eleme 0); eşik altı 25 çiftin 18'i de tekrardı. Yani eşik yanlış eleme yapmıyor ama kısa metinlerde dağınık küçük düzeltmeleri olan tekrarları kaçırıyor. Eşik incelemesi, APOD'un aynı açıklamayı yıllar sonra küçük düzeltmelerle yeniden yayımladığı sayfaları kaçırdığını gösterdi; ikinci bir geçişte (`scripts/06b_repost_dedup.py`: kelime Jaccard ≥ 0,5 ve karakter dizisi benzerliği ≥ 0,85) 140 yeniden yayın tekrarı çıkarıldı (33 çift farklı kümelerdeydi, yani sızıntı riski taşıyordu). Genel eşik düşürülmedi, çünkü NASA'nın uydu sayfaları ortak şablona rağmen farklı uyduların bilgisini taşıyor (Jaccard 0,74'e kadar). Bu adım doküman kimliklerini ve kümeleri değiştirmez.

Her çıkarılan doküman nedeniyle birlikte kayıtlıdır: [reports/removed_documents.csv](reports/removed_documents.csv), [reports/extraction_failures.csv](reports/extraction_failures.csv).

## Format
JSONL; her satır bir dokümandır. Alanlar: `document_id`, `title`, `source`, `url`, `language`, `document_type`, `publication_year`, `subtopic`, `license`, `retrieved_at`, `raw_id`, `group_key`, `split`, `postprocess` (06b ikinci geçişinden geçtiğini gösterir), `char_count`, `word_count`, `token_count`, `text`. Dosyalar: `data/final/train.jsonl`, `validation.jsonl`, `test.jsonl`; paragraf/başlık sınırında üretilmiş chunk'lar `data/final/chunks/` (en fazla 1024 token; alanlar `chunk_id`, `document_id`, `chunk_index`, `char_start`, `char_end`, `token_count`, `text`; chunk metni dokümanın birebir alt dizisidir).

## İstatistikler

| Ölçüt | Değer |
| --- | --- |
| Final doküman sayısı | 16.284 |
| Toplam kelime | 10.494.610 |
| Toplam token (Qwen/Qwen2.5-7B tokenizer) | 16.231.969 (16,2M) |
| Ortalama doküman uzunluğu | 997 token |
| Medyan doküman uzunluğu | 391 token |
| 95. yüzdelik / en uzun | 3.978 / 57.979 token |
| İngilizce / Türkçe (token) | %83,1 / %16,9 |

Alt konu dağılımı (doküman): stars_stellar_evolution %25, galaxies %18, planets_moons %14, solar_system %12, observatories_telescopes %9, missions_spacecraft %8, cosmology %7, exoplanets %5, general_astronomy %2.

Ayrıntılı istatistikler ve grafikler: [reports/statistics.md](reports/statistics.md).

## Veri ayrımı
Doküman düzeyinde %90 train (14.660), %5 validation (819), %5 test (805). Bölme `scripts/06_split.py` içinde `random_seed = 42` ile, kaynak bazında tabakalı yapılır. Chunk'lar bölmeden SONRA üretildiği için aynı dokümanın parçaları tek kümede kalır; aynı Wikipedia maddesinin İngilizce ve Türkçe sürümleri (aynı Wikidata kimliği) de aynı kümeye düşer. Kümeler arası grup çakışması: 0.

## Kalite kontrolü
Rastgele 100 doküman (kaynak oranında tabakalı) incelendi: yapay zekâ destekli ön inceleme ölçüt bazında yapıldı, nihai karar, grup üyesinin ön inceleme kararlarını onaylamasıyla verildi. Ön incelemede uygun: %88,0; nihai kararda uygun: %88,0. Ayrıntı: [reports/quality_control_report.md](reports/quality_control_report.md).

## Lisans ve kullanım
Veri seti yalnızca açık erişimli veya açık lisanslı kaynaklardan oluşur; her dokümanın lisansı `license` alanındadır. **Akademik ve ticari olmayan** amaçla hazırlanmıştır. OpenStax Astronomy 2e (CC BY-NC-SA 4.0) ve Wikipedia (CC BY-SA 4.0) türevleri aynı koşullarla paylaşılmalıdır. **Kişisel veri:** arXiv yazar adları saklanmadı, APOD görsel kredi satırları temizlendi. NASA basın bültenlerinde kamuya açık basın iletişim bilgileri (ad, e-posta, telefon) bulundu ve silindi (NASA kaynaklarında kalan e-posta/telefon: 0). Metinlerde bilimcilerin ve kamusal kişilerin adları, ansiklopedik/haber içeriğinin parçası olarak geçer. NASA içeriği NASA'nın onayını ima edecek biçimde kullanılmaz.

## Bilinen problemler
- Kaynak dağılımı dengesizdir: dokümanların %36,6'sı arXiv astro-ph (başlık + özet) kaynağından, token'ların en büyük payı Wikipedia (İngilizce) kaynağından gelir.
- Corpus büyük ölçüde İngilizcedir (token'ların %83,1'i); hedef kullanıcı Türkçe konuştuğu için Türkçe davranış ağırlıklı olarak Instruction Dataset ile kazandırılacaktır.
- PDF'teki matematiksel ifadeler görsel/MathML olarak gömülü olduğu için bazı formüller metne çıkmadı (ör. "the force would be , or as large"). Tablolar düz metne dönüştüğünde sütun yapısı kaybolur.
- Wikipedia ikincil kaynaktır; güncel sayısal bilgilerde (ör. ötegezegen sayısı) zamanla eskiyebilir. Bu tür bilgiler final döneminde RAG katmanından (NASA Exoplanet Archive) sağlanacaktır.
- arXiv özetleri araştırma dilindedir ve başlangıç seviyesindeki kullanıcı için ağırdır; ileri seviye terminoloji için tutulmuştur.
- Alt konu etiketleri anahtar kelime ve kaynak kategorisine dayalı kural tabanlı bir yöntemle atanmıştır; birden fazla konuyu kapsayan dokümanlarda tek etiket yetersiz kalabilir (ör. yöntem/yazılım makalelerine sık sık `observatories_telescopes` atanır). Elle incelenen 100 dokümanın 7 tanesinde etiket hatalı bulundu (ör. ötegezegen sayfasına `stars_stellar_evolution`); bu dokümanların çoğunda metnin kendisi sorunsuzdu. Etiket yalnız dağılım analizinde ve instruction kaynak dokümanlarının alt konuya göre dengeli seçiminde kullanılır; eğitim metnini değiştirmez.
- Wikipedia düz metin servisi tabloları çıkarmaz; bazı maddelerde "aşağıda listelenmektedir" gibi var olmayan bir listeye atıf kalır. Wikipedia formülleri `{\displaystyle ...}` biçiminde LaTeX olarak korunur.
- Kaybolan üslerin yalnız belirsizliği olmayan kalıpları düzeltildi; işaretsiz kalanlar (ör. "(1031 erg/s)") olduğu gibi duruyor.
- Birkaç APOD sayfasında bağlantı metninden kaynaklanan kelime birleşmeleri vardır ("Galacticwar", "PerseidMeteorShower").
- 300–500 karakter aralığında 283 doküman vardır; çoğu kısa ama bilgi taşıyan sayfalardır (Türkçe Wikipedia taslak maddeleri, NASA uydu sayfaları), ancak bir kısmı değeri düşük video/sosyal medya sayfalarıdır (ör. "Watch Online"). Türkçe metin kıt olduğu için alt sınır 500 yerine 300 tutuldu.
- Kaynakta bozuk kodlanmış kesme işareti 4 yerde "^1" olarak kalmıştır ("Saturn^1s"); 1 APOD sayfasında (DOC_007977) kaynaktan gelen bir U+FFFD karakteri vardır ("Don�t").
- Son denetimde (26–27.10.2026) bilgi taşımayan 7 liste/galeri sayfası bulundu: NASA'nın "Archived Nuggets", "Nuggets", "Graphics", "Posters and Infographics", "Europa Clipper Mission Identifier", "Gallery: Moonscapes" sayfaları ve Türkçe Wikipedia'nın "Astronomik nesneler listeleri" maddesi (toplam ~7.200 token, corpus'un %0,04'ü; "Archived Nuggets" sayfasında `publication_year` da boştur). Etkisi ihmal edilebilir olduğu için v1.0 değiştirilmedi; bir sonraki sürümde liste sayfası filtresiyle çıkarılacak. Kısa satırlı ama bilgi taşıyan sayfalar (formül ağırlıklı maddeler, asteroit yörünge bilgileri, sözlük sayfaları) bu kapsamda değildir.
- Değerlendirme setlerinin 60 sorusu corpus ile en az 3 adet 8-gram paylaşır (çoğu genel ifade veya tanım cümlesi, ör. "the big bang theory of the origin of the universe"). Bu dokümanlar meşru alan bilgisi olduğu için çıkarılmadı; sorular [reports/eval_contamination.csv](reports/eval_contamination.csv) dosyasında listelidir ve final dönemi karşılaştırmasında ayrıca raporlanacaktır.

## Sınırlılıklar
Bu corpus bir bilgi tabanı veya doğruluk garantisi değildir; üzerinde eğitilen model güncel astronomik veriler için birincil kaynakların yerine geçmez. Kapsam, Tasarım raporundaki eğitim konularıyla sınırlıdır.

## Sürüm geçmişi
- v0.5 (22.10.2026): İlk extraction ve cleaning denemesi (kısmi veri).
- v0.9 (23.10.2026): Tüm kaynaklar, filtreleme, deduplication ve metadata.
- v0.9.1 (23.10.2026): Kaynakça satırları, yayın listesi sayfaları ve Wikipedia kategori kuralı (alan dışı 356 madde) eklendi.
- v1.0 (24.10.2026): Token sayımı, split; elle kalite kontrolünde bulunan kaybolmuş üsler, NASA künye/kişisel veri satırları, sözlük terimleri ve APOD yeniden yayın tekrarları düzeltildi (06b; doküman kimlikleri ve kümeler korunarak).

## Yeniden üretme
`pip install -r requirements.txt` ardından `python run_pipeline.py --corpus`. Ayrıntı: [README.md](README.md).

## Hazırlayan
Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. Danışman: Asim Sinan Yüksel.
