# Uzay ve Astronomi Domain Corpus v2.0 (AstroTutor AI)

## Amaç
Bu veri seti, uzay ve astronomi eğitiminde kullanıcının seviyesine göre **İngilizce** konu anlatımı yapan ve anlattığı içerikten çoktan seçmeli soru üreten alana özel bir dil modelinin (AstroTutor AI) **continued pretraining (CPT / DAPT)** aşamasında kullanılmak üzere hazırlanmıştır. Model ailesi olarak Qwen2.5-7B hedeflenmektedir. Genel amaçlı bir corpus değildir; soru-cevap davranışı için ayrı hazırlanan Instruction Dataset kullanılır (İngilizce v2.0 hazırlanıyor; vizede teslim edilen Türkçe v1.0: [reports/archive_v1.0/INSTRUCTION_CARD_v1.0.md](reports/archive_v1.0/INSTRUCTION_CARD_v1.0.md), Git etiketi `v1.0`).

## Kapsam
**Kapsam içi:** Güneş Sistemi; gezegenler ve uydular; yıldızların özellikleri ve yıldız evrimi; gökadalar; temel kozmoloji; ötegezegenler; uzay araçları ve keşif görevleri; gözlemevleri ve teleskoplar.

**Kapsam dışı:** ileri matematiksel astrofizik türetmeleri, ham teleskop görüntüsü işleme, bilimsel simülasyon, roket mühendisliği ayrıntıları, Dünya bilimleri, uzay şirketlerinin ticari konuları, astroloji.

**Hedef kullanıcı:** ortaokul–lisans arası öğrenciler ve meraklılar (başlangıç / orta / ileri seviye).

## Veri kaynakları

| Kaynak | Tür | Dil | Ham doküman | Final doküman | Token payı | Lisans / kullanım |
| --- | --- | --- | --- | --- | --- | --- |
| NASA Science (science.nasa.gov) | HTML | en | 3.109 | 2.809 | %19,4 | NASA medya/içerik yönergeleri (kamuya açık, atıf) |
| NASA APOD açıklamaları | HTML | en | 2.720 | 2.445 | %3,4 | NASA hizmeti; yalnız açıklama metni, görseller alınmadı |
| OpenStax Astronomy 2e (ders kitabı) | PDF | en | 243 | 238 | %3,7 | CC BY-NC-SA 4.0 |
| arXiv astro-ph (başlık + özet) | XML | en | 6.000 | 5.953 | %14,9 | CC0 1.0 (arXiv metadata) |
| Wikipedia (İngilizce) | API/JSON | en | 3.576 | 3.238 | %58,6 | CC BY-SA 4.0 |
| **Toplam** | | | **15.783** | **14.683** | %100 | |

Kaynakların neden seçildiği, lisans ayrıntıları ve kullanılmayan kaynaklar (NASA Exoplanet Archive: final dönemde RAG; Stack Exchange: yalnız instruction verisi) için: [reports/source_notes.md](reports/source_notes.md), [reports/source_inventory.csv](reports/source_inventory.csv).

Corpus v2.0 yalnız İngilizcedir: AstroTutor AI İngilizce konuşan bir eğitim asistanı olarak geliştirilmektedir (09.11.2026 kararı) ve alanın güvenilir, açık lisanslı birincil kaynakları (NASA, ders kitabı, makale özetleri) İngilizcedir. v1.0'da modelin Türkçe terminolojiyi görmesi için eklenen Türkçe Wikipedia (token'ların %16,9'u) bu sürümde çıkarıldı; İngilizce dokümanların kimlikleri ve kümeleri değişmedi.

## Veri toplama
Dokümanlar 2026-10-22 – 2026-10-23 tarihleri arasında `scripts/01_download.py` ile indirildi. science.nasa.gov `robots.txt` kurallarına uyuldu (istekler arası 1,2 sn); Wikipedia isteklerinde iletişim bilgili User-Agent kullanıldı ve Wikimedia hız sınırlarına uyuldu; arXiv OAI-PMH'de istekler arası 4,0 sn beklendi. Ham dosyalar `data/raw/` altında değiştirilmeden saklanır; her dosya için URL, SHA-256, erişim zamanı ve lisans `manifest.jsonl` dosyalarında kayıtlıdır.

NASA Science'ta tek bir görevin (ör. Hubble, Cassini) corpus'u domine etmemesi için görev/bölüm başına en fazla 150 sayfa alındı; APOD'dan 1995–2026 arasında her yıldan 85 açıklama örneklendi (seed 42).

## İşleme adımları
- **Extraction:** HTML için Trafilatura (başarısız olursa BeautifulSoup), PDF için PyMuPDF ([pdfplumber ile karşılaştırma](reports/extraction_tool_comparison.md): eşit kalite, PyMuPDF yaklaşık 64 kat hızlı). PDF metin blokları sayfa konumuna göre sıralandı (kenar kutularının paragraflara karışması önlendi). 46 doküman boş/çok kısa çıktı verdiği için elendi; OpenStax'ta 135 bölüm (alıştırma, kaynakça, ekler) içerik dışı sayıldı. Toplam başarısız extraction: 181 / 15.783 (%1,1).
- **Cleaning:** HTML etiket/entity kalıntıları (`<sup>x</sup>` → `^x`), Unicode NFKC (üs ifadeleri önce `10^23` biçimine alınarak), whitespace normalizasyonu, PDF header/footer ve bölüm başlığı satırları, site menüleri ve tekrar eden şablon satırları, kesik tanıtım cümleleri, Wikipedia kaynakça/yayın listesi bölümleri, 'Soyadı, A. B. (yıl). Başlık. Dergi' biçimiyle başlayan kaynakça girdisi satırları (metin içi atıflar korunarak), görsel kredileri, 20 karakterden kısa yalnız satırlar. Sayılar ve formüller silinmedi. Kural listesi ve uygulama sayıları: [reports/cleaning_rules.md](reports/cleaning_rules.md); öncesi/sonrası örnekleri: [reports/cleaning_examples.md](reports/cleaning_examples.md). Elle incelemede bulunan üç sorun ikinci bir geçişte (`scripts/06b_repost_dedup.py`) düzeltildi: (1) Wikipedia düz metin servisi, trafilatura ve PyMuPDF HTML/PDF üst simgelerini sildiği için kaybolan üsler geri yazıldı (1.605 ifade; "1.5 × 108 km" → "1.5 × 10^8 km"); (2) NASA basın bültenlerindeki künye, kredi ve iletişim satırları ile **kişisel iletişim bilgileri (e-posta, telefon)** silindi (kalan telefon ve gerçek e-posta adresi: 0, ayrıntı Lisans bölümünde); (3) NASA sözlük sayfalarında kısa satır kuralının sildiği terimler geri getirildi. Corpus v2.0'da (09.11.2026) iki düzeltme daha yapıldı: (4) OpenStax'ın "Key Terms" sözlük bölümleri PDF yazı tipi bilgisiyle (kalın terim) her terim ayrı paragraf olacak biçimde "terim: tanım" olarak çıkarıldı (26 bölüm; önceden terimler bir önceki tanıma yapışıyor, sayfa başlığında kesilen terimler (ör. "Wien's law", "X-rays") kayboluyordu); (5) basın bültenlerinin sonundaki yalnız kişi adından oluşan satırlar (38), "Learn more / Visit …" gibi yönlendirme satırları (72) ve yalnız bağlantı taşıyan cümleler (106) silindi; aynı satırdaki bilgi taşıyan cümleler korundu (testler: `scripts/press_boilerplate.py`). Basın temizliğinden (2, 5) etkilenen doküman: 661.
- **Filtering:** 300 karakterden kısa (183), bozuk karakter oranı %15'i aşan veya çoğu simgeden oluşan (3), İngilizce dışındaki (6), satırlarının yarısından fazlası kaynakça girdisi olan yayın listesi (5) ve alan dışı (123) dokümanlar elendi. Alan tespiti astronomi terim sözlüğü yoğunluğu ile yapıldı (`scripts/domain_lexicon.py`). Wikipedia'da kategori gezintisi alt kategorilere indiği için kurgu, film, oyun, bayrak, genel spektroskopi ve jeoloji maddeleri de seçilmişti; her maddenin kendi Wikipedia kategorilerine dayanan ek kuralla 272 madde elendi (kalibrasyonu: [experiments.md](experiments.md)).
- **Deduplication:** exact duplicate SHA-256 ile (46 doküman), near duplicate MinHash LSH (kelime 5-gram, 128 permütasyon) + Jaccard ≥ 0,85 ile (90 doküman). Eşik, 50 aday çift (25'i Jaccard ≥ eşik, 25'i altı) yapay zekâ destekli ön inceleme ve grup üyesinin onayıyla kontrol edildi ([reports/qc/near_dup_pairs_review.csv](reports/qc/near_dup_pairs_review.csv)): eşik üstü 25 çiftin 25'i gerçek tekrardı (hatalı eleme 0); eşik altı 25 çiftin 18'i de tekrardı. Yani eşik yanlış eleme yapmıyor ama kısa metinlerde dağınık küçük düzeltmeleri olan tekrarları kaçırıyor. Eşik incelemesi, APOD'un aynı açıklamayı yıllar sonra küçük düzeltmelerle yeniden yayımladığı sayfaları kaçırdığını gösterdi; ikinci bir geçişte (`scripts/06b_repost_dedup.py`; APOD için kelime Jaccard ≥ 0,5 ve karakter dizisi benzerliği ≥ 0,85; NASA Science için kelime Jaccard ≥ 0,75 ve karakter dizisi benzerliği ≥ 0,9) 140 yeniden yayın tekrarı çıkarıldı (33 çift farklı kümelerdeydi, yani sızıntı riski taşıyordu). Genel eşik düşürülmedi, çünkü NASA'nın uydu sayfaları ortak şablona rağmen farklı uyduların bilgisini taşıyor (Jaccard 0,74'e kadar). Aynı geçişte 51 doküman daha elendi (iletişim sayfası 7, temizlik sonrası alt uzunluk sınırının altına düşen 3, kurgu/eser maddesi 3, liste/haber sayfası 38). Bu adım doküman kimliklerini ve kümeleri değiştirmez.
- **Liste/haber sayfaları (v2.0):** NASA Science ve APOD'da cümle oranı (noktalı cümle içeren satırlardaki kelimelerin payı) 0,25 altında kalan sayfalar ve elle eklenen 1 galeri sayfası, toplam 57 aday, yapay zekâ destekli ön incelemeyle tek tek değerlendirildi ve grup üyesinin onayıyla karar verildi ([reports/qc/list_page_review.csv](reports/qc/list_page_review.csv); adaylar `scripts/list_page_candidates.py`, çıkarma 06b). Bilgi taşımayan 40 sayfa (okul müfredatı standart tabloları, araştırma fonu çağrıları, haber başlığı, dosya ve broşür listeleri, indirme ve galeri sayfaları) çıkarıldı (38 tanesi bu nedenle; 2 tanesi temizlik sonrası çok kısa kaldığı için zaten elenmişti); bilgi taşıyan 17 tablo sayfası (uydu tabloları, Ay görevleri, Cassini yakın geçiş verileri ve haftalık raporları) tutuldu. Eşik tek başına karar vermez; yalnız aday bulur.

Her çıkarılan doküman nedeniyle birlikte kayıtlıdır: [reports/removed_documents.csv](reports/removed_documents.csv), [reports/extraction_failures.csv](reports/extraction_failures.csv).

## Format
JSONL; her satır bir dokümandır. Alanlar: `document_id`, `title`, `source`, `url`, `language`, `document_type`, `publication_year`, `subtopic`, `license`, `retrieved_at`, `raw_id`, `group_key`, `split`, `postprocess` (06b ikinci geçişinden geçtiğini gösterir), `char_count`, `word_count`, `token_count`, `text`. Dosyalar: `data/final/train.jsonl`, `validation.jsonl`, `test.jsonl`; paragraf/başlık sınırında üretilmiş chunk'lar `data/final/chunks/` (en fazla 1024 token; alanlar `chunk_id`, `document_id`, `chunk_index`, `char_start`, `char_end`, `token_count`, `text`; chunk metni dokümanın birebir alt dizisidir).

## İstatistikler

| Ölçüt | Değer |
| --- | --- |
| Final doküman sayısı | 14.683 |
| Toplam kelime | 9.440.259 |
| Toplam token (Qwen/Qwen2.5-7B tokenizer) | 13.438.685 (13,4M) |
| Ortalama doküman uzunluğu | 915 token |
| Medyan doküman uzunluğu | 379 token |
| 95. yüzdelik / en uzun | 3.593 / 57.979 token |
| Dil (token payı) | İngilizce %100,0 |

Alt konu dağılımı (doküman): stars_stellar_evolution %24, galaxies %19, planets_moons %14, solar_system %11, observatories_telescopes %10, missions_spacecraft %9, cosmology %8, exoplanets %5, general_astronomy %2.

Ayrıntılı istatistikler ve grafikler: [reports/statistics.md](reports/statistics.md).

## Veri ayrımı
Doküman düzeyinde %90 train (13.223), %5 validation (735), %5 test (725). Bölme `scripts/06_split.py` içinde `random_seed = 42` ile, kaynak bazında tabakalı yapılır. Chunk'lar bölmeden SONRA üretildiği için aynı dokümanın parçaları tek kümede kalır. Kümeler arası grup çakışması: 0. v2.0'da Türkçe dokümanlar çıkarıldığında İngilizce dokümanların kümeleri v1.0 ile aynı kaldı (kaynak bazında tabakalı bölme; Türkçe kaynak sıralamada en sondaydı).

## Kalite kontrolü
Rastgele 100 doküman (kaynak oranında tabakalı) incelendi: yapay zekâ destekli ön inceleme ölçüt bazında yapıldı, nihai karar, grup üyesinin ön inceleme kararlarını onaylamasıyla verildi. Ön incelemede uygun: %89,0; nihai kararda uygun: %89,0. v2.0'da v1.0 örnekleminin İngilizce dokümanları ve kararları korundu; çıkarılan Türkçe dokümanların yerine aynı yöntemle (kaynak oranında, seed'li) yeni İngilizce dokümanlar eklenip incelendi (`scripts/13_sample_for_review.py --corpus-topup`). Ayrıntı: [reports/quality_control_report.md](reports/quality_control_report.md).

## Lisans ve kullanım
Veri seti yalnızca açık erişimli veya açık lisanslı kaynaklardan oluşur; her dokümanın lisansı `license` alanındadır. **Akademik ve ticari olmayan** amaçla hazırlanmıştır. OpenStax Astronomy 2e (CC BY-NC-SA 4.0) ve Wikipedia (CC BY-SA 4.0) türevleri aynı koşullarla paylaşılmalıdır. **Kişisel veri:** arXiv yazar adları saklanmadı, APOD görsel kredi satırları temizlendi. NASA basın bültenlerinde kamuya açık basın iletişim bilgileri (ad, e-posta, telefon) bulundu ve silindi; cümle sonunda kalan 5 kurumsal basın numarası 30.10.2026 düzeltmesiyle maskelendi (`[telefon]`). Final corpus'ta telefon numarası 0; e-posta biçiminde tek eşleşme, bir Wikipedia biyografisinde (David J. Tholen) maddenin konusu olarak geçen, bilerek bozulmuş ve çalışmayan bir Usenet takma adıdır. Metinlerde bilimcilerin ve kamusal kişilerin adları, ansiklopedik/haber içeriğinin parçası olarak geçer. NASA içeriği NASA'nın onayını ima edecek biçimde kullanılmaz.

## Bilinen problemler
- Kaynak dağılımı dengesizdir: dokümanların %40,5'i arXiv astro-ph (başlık + özet) kaynağından, token'ların en büyük payı Wikipedia (İngilizce) kaynağından gelir.
- PDF'teki matematiksel ifadeler görsel/MathML olarak gömülü olduğu için bazı formüller metne çıkmadı (ör. "the force would be , or as large"). Tablolar düz metne dönüştüğünde sütun yapısı kaybolur.
- Wikipedia ikincil kaynaktır; güncel sayısal bilgilerde (ör. ötegezegen sayısı) zamanla eskiyebilir. Bu tür bilgiler final döneminde RAG katmanından (NASA Exoplanet Archive) sağlanacaktır.
- arXiv özetleri araştırma dilindedir ve başlangıç seviyesindeki kullanıcı için ağırdır; ileri seviye terminoloji için tutulmuştur.
- Alt konu etiketleri anahtar kelime ve kaynak kategorisine dayalı kural tabanlı bir yöntemle atanmıştır; birden fazla konuyu kapsayan dokümanlarda tek etiket yetersiz kalabilir (ör. yöntem/yazılım makalelerine sık sık `observatories_telescopes` atanır). Elle incelenen 100 dokümanın 6 tanesinde etiket hatalı bulundu (ör. ötegezegen sayfasına `stars_stellar_evolution`); bu dokümanların çoğunda metnin kendisi sorunsuzdu. Etiket yalnız dağılım analizinde ve instruction kaynak dokümanlarının alt konuya göre dengeli seçiminde kullanılır; eğitim metnini değiştirmez.
- Wikipedia düz metin servisi tabloları çıkarmaz; bazı maddelerde var olmayan bir tabloya atıf kalır (ör. "Orbital period" maddesi "The following table lists the synodic periods of some planets…" cümlesiyle biter). Wikipedia formülleri `{\displaystyle ...}` biçiminde LaTeX olarak korunur.
- Kaybolan üslerin yalnız belirsizliği olmayan kalıpları düzeltildi; işaretsiz kalanlar (ör. "(1031 erg/s)") olduğu gibi duruyor.
- Birkaç APOD sayfasında bağlantı metninden kaynaklanan kelime birleşmeleri vardır ("Galacticwar", "PerseidMeteorShower").
- 300–500 karakter aralığında 168 doküman vardır (NASA Science (science.nasa.gov) 110, NASA APOD açıklamaları 29, arXiv astro-ph (başlık + özet) 18, Wikipedia (İngilizce) 8, OpenStax Astronomy 2e (ders kitabı) 3); çoğu kısa ama bilgi taşıyan sayfalardır (APOD açıklamaları, uydu ve yakın geçiş sayfaları, makale özetleri), ancak bir kısmı değeri düşük video ve indirme sayfalarıdır (ör. "To view this video please enable JavaScript" metinli görev animasyonları). v2.0'da alt sınır yeniden değerlendirildi ve 300'de tutuldu: 500'e çıkarmak bu aralıktaki bilgi taşıyan kısa sayfaları da toplu olarak atardı.
- Kaynakta bozuk kodlanmış kesme işareti 4 yerde "^1" olarak kalmıştır ("Saturn^1s"); 1 APOD sayfasında (DOC_007977) kaynaktan gelen bir U+FFFD karakteri vardır ("Don�t").
- Liste/haber sayfası incelemesi yalnız NASA Science ve APOD'a uygulandı. Wikipedia'da cümle oranı düşük maddeler çoğunlukla formül ağırlıklı veya tablo içerikli ve bilgi taşıyan maddeler olduğu için kapsam dışı tutuldu. Tutulan tablo sayfalarında (ör. uydu tabloları) satırlar düz metne dönüştüğü için sütun ilişkisi kaybolur.
- Değerlendirme setlerinin 60 sorusu corpus ile en az 3 adet 8-gram paylaşır (çoğu genel ifade veya tanım cümlesi, ör. "the big bang theory of the origin of the universe"). Bu dokümanlar meşru alan bilgisi olduğu için çıkarılmadı; sorular [reports/eval_contamination.csv](reports/eval_contamination.csv) dosyasında listelidir ve final dönemi karşılaştırmasında ayrıca raporlanacaktır.

## Sınırlılıklar
Bu corpus bir bilgi tabanı veya doğruluk garantisi değildir; üzerinde eğitilen model güncel astronomik veriler için birincil kaynakların yerine geçmez. Kapsam, Tasarım raporundaki eğitim konularıyla sınırlıdır.

## Sürüm geçmişi
- v0.5 (22.10.2026): İlk extraction ve cleaning denemesi (kısmi veri).
- v0.9 (23.10.2026): Tüm kaynaklar, filtreleme, deduplication ve metadata.
- v0.9.1 (23.10.2026): Kaynakça satırları, yayın listesi sayfaları ve Wikipedia kategori kuralı (alan dışı 356 madde) eklendi.
- v1.0 (24.10.2026): Token sayımı, split; elle kalite kontrolünde bulunan kaybolmuş üsler, NASA künye/kişisel veri satırları, sözlük terimleri ve APOD yeniden yayın tekrarları düzeltildi (06b; doküman kimlikleri ve kümeler korunarak).
- v1.0 düzeltmesi (30.10.2026): Telefon kuralı, numaradan hemen sonra cümle noktası gelen 5 kurumsal basın numarasını kaçırıyordu; kural düzeltildi (testli) ve corpus 06 → 06b (iki geçiş) → 07 ile yeniden üretildi. Yalnız bu 5 dokümanın metni değişti (numara → `[telefon]`, toplam −53 token); doküman sayısı, kimlikler ve kümeler aynı. Vizede teslim edilen sürüm (İngilizce + Türkçe, 16.284 doküman); Git etiketi `v1.0`.
- v2.0 (09.11.2026): AstroTutor AI İngilizce konuşan bir model olarak geliştirileceği için Türkçe Wikipedia çıkarıldı (corpus yalnız İngilizce). OpenStax "Key Terms" bölümleri "terim: tanım" biçiminde yeniden çıkarıldı; basın bültenlerinin sonundaki ad, yönlendirme ve bağlantı satırları silindi; 38 liste/haber sayfası grup üyesinin onayıyla çıkarıldı. Final: 14.683 doküman, 13,4M token. İngilizce dokümanların kimlikleri ve kümeleri v1.0 ile aynı; tüm zincir (02 → 07) yeniden çalıştırıldığında çıktı birebir aynı.

## Yeniden üretme
`pip install -r requirements.txt` ardından `python run_pipeline.py --corpus`. Ayrıntı: [README.md](README.md).

## Hazırlayan
Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. Danışman: Asim Sinan Yüksel.
