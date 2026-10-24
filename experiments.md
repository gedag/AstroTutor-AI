# Deney ve Karar Günlüğü

Tarih sırasıyla ne denendiği, ne sonuç alındığı ve hangi kararın verildiği.

## 20.10.2026 — Kaynak envanteri
Tasarım raporundaki kaynaklar (NASA Science, NASA Exoplanet Archive, StackExchange Space QA, Wikipedia) için
lisans koşulları incelendi; `reports/source_inventory.csv` ve `reports/source_notes.md` oluşturuldu.
`reports/nasa_seed_urls.csv` ile 6 temel NASA sayfası elle seçildi.

## 22.10.2026 — Ek kaynaklar ve lisans doğrulaması
- OpenStax API'si sorgulandı: **Astronomy 2e lisansı CC BY-NC-SA 4.0** (1. baskı CC BY 4.0). Daha güncel olduğu için
  2e kullanıldı; NC-SA koşulu kartlara yazıldı.
- arXiv OAI-PMH (`physics:astro-ph`) erişimi doğrulandı; metadata CC0.
- Değerlendirme setleri (Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ, Astrobench) Hugging Face'te doğrulandı.
- **Karar:** NASA Exoplanet Archive corpus'a alınmadı (yapılandırılmış, sürekli değişen veri → final döneminde RAG).

## 22.10.2026 — NASA APOD API'si çalışmıyor
- `api.nasa.gov/planetary/apod` tarih aralığı sorgularında HTTP 500, tekil tarihte yer tutucu metin döndürdü
  ("Discover the cosmos! ..."). `apod.nasa.gov/apod/apYYMMDD.html` adresleri science.nasa.gov'a yönleniyor.
- science.nasa.gov sitemap'inde 11.393 APOD sayfası (`/image-article/apod-YYYY-...`) bulundu.
- **Karar:** APOD açıklamaları science.nasa.gov sayfalarından alındı; her yıldan 85 sayfa (1995–2026, seed 42).

## 22.10.2026 — NASA Science URL seçimi
- Sitemap: topic/post/mission türlerinde 62.264 URL. 52.463'ü kapsam dışı yol (fotoğraf arşivi, Dünya bilimi,
  araştırmacı duyuruları vb.), 1.763'ü astronomi dışı görev (Landsat, Aura, NISAR...), 244'ü dışlama kalıbı.
- Hubble ve Cassini sayfaları çok fazla (2.499 ve 1.374 haber) → corpus'u domine etmemesi için **görev/bölüm başına
  en fazla 150 sayfa**. Sonuç: 3.108 URL (+ elle seçilmiş seed sayfalar).
- `nasa_seed_urls.csv` kontrolü: 6 URL'nin hepsi HTTP 200, içerikler notlarla uyumlu. Sütun adı `document_id` →
  `seed_id` (final DOC_ kimlikleriyle karışmasın), alt konu etiketleri taksonomiyle hizalandı, Tasarım kapsamında
  eksik kalan "gezegenler" ve "görevler" için 2 sayfa eklendi. Voyager ve uydular ana sayfaları (714 ve 877
  karakter) sadece yönlendirme içerdiği için eklenmedi.

## 22.10.2026 — PDF extraction aracı karşılaştırması
Rastgele 40 sayfa (seed 42), OpenStax Astronomy 2e:
| Araç | Süre | >200 karakter çıkan sayfa |
| --- | --- | --- |
| PyMuPDF | 0,06 sn | 40/40 |
| pdfplumber | 4,9 sn | 40/40 |

Çıktı kalitesi eşit, PyMuPDF ~70 kat hızlı. **Karar: PyMuPDF.** (02'nin son çalıştırmasındaki yeniden ölçüm:
0,06 sn / 8,89 sn, ~161 kat. Süreler makine yüküne göre değişiyor; kartlar oranı rapordan okur.) Ayrıntı: `reports/extraction_tool_comparison.md`.
PDF'te taranmış (metin katmanı olmayan) sayfa: 1.151 sayfadan 2 (kapak sayfaları) → OCR gerekmedi.

## 22.10.2026 — PDF okuma sırası hatası (sessiz bozulma)
- Varsayılan `get_text("text")` içerik akışı sırasını izliyor; "Learning Objectives" kutusu paragrafın ortasına
  karıştı: "...but this did not *Explain what determines the strength of gravity...* deter Isaac Newton".
  Rehber §6'daki "çok sütunlu sayfa yanlış okunmuş" örneğinin aynısı; hata vermeden çöp üretiyordu.
- **Çözüm:** Metin blokları sayfadaki dikey konuma göre sıralandı, her blok bir paragraf sayıldı.

## 22.10.2026 — Temizleme kuralları ayarı
- PDF header/footer: rakamlar `#` ile normalize edilip 5+ sayfada tekrar eden satırlar bulundu (167 aday). Yalnızca
  header/footer *biçimindekiler* siliniyor ("Access for free at openstax.org", "78 3 • Orbits and Gravity").
  Tek sayfalarda "3.3 • Newton's ... 79" başlıkları 5 sayfa eşiğinin altında kaldığı için ayrıca biçim kuralı eklendi.
- **NFKC üs sorunu:** NFKC `10²³`'ü `1023`'e çeviriyor (bilgi kaybı). Önce üs ifadeleri `10^23` biçimine alınıyor.
- **HTML tekrar eden satırlar:** İlk sürüm, 2+% dokümanda tekrar eden her satırı siliyordu. Bu, Jüpiter uydu
  gruplarının sayfalarında ortak olan *bilgi paragraflarını* da her yerden siliyordu. **Düzeltme:** 100+ karakterlik
  tekrarlar ilk geçtiği dokümanda korunur, diğerlerinden atılır; kısa olanlar (menü, "Share", "Keep Exploring") silinir.
- NASA hub sayfalarındaki "…" ile biten kesik tanıtım cümleleri silindi (yarım cümle, bilgi taşımıyor).

## 22.10.2026 — StackExchange verisinde üs kaybı
`juliensimon/stackexchange-space-qa` cevaplarında üslü sayılar düz yazılmış: "The mass of the sun is
1.989 × 1030 kg" (doğrusu 10^30). 09 numaralı script `sayı × 10NN` kalıbını `× 10^NN`'e çeviriyor (üs 0 ile
başlamıyorsa ve 1–3 basamaklıysa).

## 22.10.2026 — StackExchange seçimi
33.519 kayıt → 10.568 uygun aday. Elenenler: cevapsız 4.891, düşük puan 9.822, uzunluk dışı 2.880, kapsam dışı
etiket (roket mühendisliği, şirket, yazılım...) 4.444, görsele bağlı 522, alan dışı 392. Sitelere göre %65
Astronomy / %35 Space oranında, soru puanı en yüksek ~580 soru seçildi.

## 22.10.2026 — Gemini modeli ve kota
- `gemini-2.5-flash` yeni kullanıcılara kapalı (HTTP 404). Erişilebilir modeller listelendi; `gemini-3.6-flash`
  (2 sn, akıcı Türkçe) üretici, `gemini-3.7-flash` yargıç olarak seçildi (farklı model → kendi çıktısını kayırma
  eğilimi azalır).
- Ücretsiz katman: **model başına günde 20 istek** (`generate_content_free_tier_requests`, limit 20). Yoğunluk
  (503) hatası alan çağrıların da kotadan düştüğü görüldü; SDK'nın kendi otomatik tekrarı da kota harcıyordu.
- **Kararlar:** (1) dört Flash modeli havuz olarak kullanılır, gerçekte kullanılan model her örnekte kaydedilir;
  (2) SDK otomatik tekrarı kapatıldı, 503'te aynı modelde tekrar denenmez; üst üste 3 yoğunluk hatasında script
  durur; (3) çağrı başına örnek sayısı artırıldı (uzun dokümanda 12, StackExchange'te 10, kapsam dışında 12);
  (4) yargıç, örneği üreten modelden farklı seçilir.

## 22.10.2026 — Pilot üretim (prompt v1 taslağı)
11 örnek (5 StackExchange, 6 kapsam dışı) incelendi. Talimatlar doğal, cevaplar kaynağa sadık, ret örnekleri
çeşitli. Sorunlar ve düzeltmeler:
- StackExchange'teki MathJax aynen kopyalandı (`$1.255 \times 10^{21} {\rm J}$`) → prompt'a "LaTeX kullanma,
  düz yaz" kuralı ve doğrulamaya `latex_artifact` kontrolü eklendi.
- Kaynak metindeki süslü parantezler (`{\rm J}`) Python `str.format` şablon doldurmasını bozdu → tek geçişli
  güvenli `fill()` fonksiyonuna geçildi.
Pilot çıktıları eski prompt'la üretildiği için veri setine alınmadı (`data/interim/pilot_v1_eski_prompt/`).

## 23.10.2026 — Wikipedia hız sınırı ve kategori düzeltmeleri
- Wikipedia indirmesi dakikada ~8 maddeye düşmüştü. Neden: Wikimedia'nın 2026'da getirdiği kural; iletişim
  bilgisi olmayan User-Agent "tanımsız" sayılıp **10 istek/dk** ile sınırlanıyor (HTTP 429, `retry-after`).
  User-Agent'a iletişim e-postası eklenince sınır 200 istek/dk oldu; hız ~54 madde/dk. Eşzamanlı istek ≤ 3.
- Bulunamayan kategori adları düzeltildi: EN "Natural satellites" → "Moons"; TR "Gökadalar" → "Galaksiler",
  "Göktaşları" → "Meteoritler", "Güneş Sistemi gezegenleri" kaldırıldı ("Gezegenler" kapsıyor). Türkçe
  gökada maddeleri önceki seçimde neredeyse hiç yoktu.
- İlk EN seçiminde 2.600 madde sınırı kategori sırasına göre uygulandığı için listenin sonundaki 8 kategori
  (Telescopes, Astrophysics, Observational astronomy, Astronomical coordinate systems, Celestial mechanics,
  Eclipses, Meteoroids, Planetary science) hiç temsil edilmiyordu. Kapsam dengesi için bunlar da eklendi
  (EN toplam 3.576 aday). Mevcut seçim bozulmadan yalnız eksik kategoriler tamamlandı.

## 23.10.2026 — Instruction üretimi 1. gün
- Corpus beklenirken corpus'a bağlı olmayan işler üretildi: 45 Stack Exchange işi (449 soru) + 10 kapsam dışı
  işi → 571 örnek, 55 çağrı.
- **Sorun:** "Son başarılı modeli önce dene" kuralı, Flash modeller anlık yoğunken yedek lite modele geçip ona
  takıldı; 46 iş `gemini-3.5-flash-lite` ile üretildi. Ölçüm: lite cevaplar ortalama ~410 karakter (Flash
  ~1.050), kanıt kontrolünden geçme %68 (Flash %96), yazım hataları var.
- **Karar:** lite modeller yalnızca tüm Flash modellerinin günlük kotası bittiğinde kullanılır; anlık 503'te
  lite'a düşülmez. Lite ile üretilmiş Stack Exchange işleri, doküman işleri bittikten sonra kota kalırsa Flash
  ile yeniden üretilecek; kalmazsa yalnız tüm kontrolleri geçen lite örnekleri tutulup kartta belirtilecek.

## 23.10.2026 — Corpus ilk tam çalıştırma ve düzeltmeler
İlk tam çalıştırma: 17.520 ham → 16.797 doküman, 18,1 M token. Sonuçlar gözden geçirilince iki sorun bulundu:

**1. Kaynakça/yayın listesi sayfaları.** En uzun dokümanlar "Voyager Bibliography" (242 bin token), "LRO
Publications" gibi yüzlerce satırlık makale listeleriydi. Wikipedia metinlerinde de "Selected publications"
bölümleri ve kaynak listesi kalıntıları vardı. Doküman düzeyinde "atıf oranı" denemesi işe yaramadı: metin içi
atıflı düzgün düzyazıyı da ("Eridanus II": "...(Bechtol et al., 2015)") liste sanıyordu.
- **Çözüm:** satır düzeyinde kural: "Soyadı, A. B. (yıl). Başlık. Dergi, cilt, doi" biçimiyle *başlayan*
  satırlar silinir; metin içi atıflar korunur. 5.522 satır silindi; düzyazı dokümanlarından silinen 45 rastgele
  satırın 45'i de gerçek kaynakça girdisiydi. Satırlarının yarısından fazlası kaynakça olan 5 sayfa
  `reference_list` nedeniyle elendi. Wikipedia bölüm listesine "Publications", "Selected works", "Yayınları",
  "Eserleri" eklendi.

**2. Wikipedia'da alan dışı maddeler.** Kategori gezintisi alt kategorilere indiği ve en uzun maddeler önce
seçildiği için "Warhammer 40,000" (Milky Way in fiction), "Hanford Site" (Astrophysics altı), Doctor Who
bölümleri, bayraklar (yıldızlı bayrak kategorileri), genel spektroskopi ve jeomorfoloji maddeleri girmişti.
Terim yoğunluğu filtresi bunları yakalamıyordu: "space", "earth", "radio", "mission" gibi genel kelimeler
alan dışı metinlerde de geçiyor. Giriş paragrafında hiç astronomi terimi olmayan 272 madde vardı.
- **Çözüm:** her maddenin kendi Wikipedia kategorileri çekildi (`page_categories.json`) ve
  `out_of_domain_category` kuralı eklendi: en az bir kategori astronomi/uzay konulu olmalı; kurgu, film, oyun,
  bayrak, arma, mitoloji kategorileri sayılmaz; sözde bilim, ezoterik ve dinî kozmoloji kategorileri maddeyi
  doğrudan dışarıda bırakır. Çok kategorili maddede tek astronomi kategorisi varsa giriş paragrafına da bakılır
  (Hanford: 22 kategoriden yalnız biri, girişte astronomi yok). Kategorisi kendine özgü olan az kategorili
  maddelerde ("Viking programı", "Superbubbles") karar giriş paragrafına göre verilir.
- **Kalibrasyon sırasında yakalanan hatalar** (her turda elenen/tutulan farkı elle incelendi):
  - `re.IGNORECASE`, Türkçe "ı" ile "i"yi eşit sayıyor: "takımyıldızı" kalıbı "dizi"ye uydu ve "Kalp Bulutsusu"
    gibi maddeler eleniyordu. Bu yüzden büyük-küçük harf duyarlı eşleşmeye geçildi.
  - Türkçe "kozmoloji" "kozmolog" kalıbına uymuyordu ("Kozmoloji" maddesinin kendisi eleniyordu).
  - Alt dizgi tuzakları: "pluto" ⊂ "plutonium", "rover" ⊂ "controversies", "meteor" ⊂ "meteorology". Kelime
    sınırı ve olumsuz ileriye bakma ile düzeltildi.
  - "Astrology" kategorisini doğrudan dışlamak yanlıştı: Wikipedia ekliptik, tutulma, Ay evresi ve Tycho Brahe
    maddelerini de "Technical factors of astrology" altına koyuyor. Astroloji kategorileri yalnız *sayılmıyor*.
- Sonuç: 356 madde elendi. Bilinen sınır vakaları: "Albedo" (Wikipedia'da yalnız iklim kategorilerinde) elendi;
  "Spectral line", "Doppler effect" gibi genel fizik maddeleri de elendi (kategorileri yalnız spektroskopi/fizik).

**Son durum (Corpus v1.0):** 16.436 doküman, 16,29 M token (train 14.790 / val 828 / test 818). Önceki en uzun
doküman 242 bin token iken artık 58 bin token ("Dawn Mission Status", görev günlüğü, gerçek içerik).
İngilizce Wikipedia token'ların %48'i, dokümanların %20'si: maddeler uzun. Ansiklopedik kapsam için tutuldu;
CPT'de kaynak bazlı örnekleme yapılabilir (kartta not edildi).

## 23.10.2026 — Doküman işleri
- İlk iş oluşturma, kotayı doküman başına 12 örnek varsayarak doküman sayısına çeviriyordu. Gerçekleşen ortalama
  11,7 olunca 369 örnek açık kaldı. Bu yüzden aday doküman sayısı bilerek fazla tutuluyor ve kota dolunca duruluyor.
  Sonuç: 243 doküman, 2.856 örnek (kota tam). Henüz üretilmiş doküman örneği olmadığı için iş listesi yeniden
  kuruldu.
- APOD dokümanlarından iş çıkmadı: en uzun APOD metni ~350 token; bir işten 6–14 örnek için en az 3.000
  karakter gerekiyor.

## 23.10.2026 — Ücretsiz katman kapasitesi ve lite modeller
- 23.10 kota gününde (10:00–13:51) dört Flash modeli de "günlük kota doldu" (429, PerDay) yanıtı verdi. Kayıtlara
  göre model başına yalnız 7–13 istek yapılmıştı (başarılı + 503), yani 20'lik sınırdan az. SDK'nın gizli
  tekrar denemesi yapmadığı kontrol edildi (`HttpRetryOptions(attempts=1)` → `stop_after_attempt(1)`). Sonuç:
  503 ile geri çevrilen istekler de kotadan düşüyor ve sayım bizim gördüğümüzden hızlı ilerliyor. Bir günde
  Flash ile yalnız 15 iş başarıyla tamamlandı. Bu hızla kalan 237 doküman işi ~16 gün sürerdi.
- Lite modellerle 4 doküman işi ayrı bir dosyada denendi (veri setine alınmadı):

  | Model | Örnek | Kanıt kontrolü | Ort. cevap |
  | --- | --- | --- | --- |
  | Flash (mevcut 71 doküman örneği) | 71 | %100 | 745 karakter |
  | gemini-3.5-flash-lite | 24 | %100 | 406 karakter |
  | gemini-3.1-flash-lite | 10 | %100 | 349 karakter |

  Lite cevaplar kaynağa sadık ve akıcı ama daha kısa; tek tük yazım/terim hatası var ("bır", "inflaton" için
  "şişkin").
- **Karar (Eda):** ücretsiz katmanda kalınır; her gün önce Flash kullanılır, Flash'ın günlük kotası bitince lite
  modellerle devam edilir. Kodda bir eksik vardı: Flash kotası bir çağrının içinde bitince program lite'a
  geçmeden duruyordu (`llm.py` kademe mantığı). Bu düzeltildi ve sahte istemciyle 5 durum test edildi. Anlık 503'te
  yine lite'a inilmez. Her örneğin `generator_model` alanı kartta model dağılımı olarak raporlanır.
- **Kota sıfırlanma varsayımı yanlıştı.** Döngü yeniden başlatılınca, 13:51'de "günlük kota doldu" diyen
  gemini-3.7-flash 14:20'de normal yanıt verdi. Belgelere göre sınır Pasifik gece yarısı sıfırlanıyor, ama
  gözlenen davranış son 24 saati sayan kayan bir pencere. Önceki gün öğleden sonra yapılan istekler 24 saati
  doldurdukça hak geri geliyor. Kod buna göre değiştirildi:
  - kotası dolan model 30 dk sonra yeniden denenir (`quota_recheck_minutes`); reddedilen 429 istekleri kotadan
    düşmez;
  - tüm modeller doluysa döngü sabahı beklemez, 60 dk sonra yeniden dener;
  - teşhis için 429 hatasının kota kimliği ve değeri `logs/llm.log`'a yazılır.

## 23.10.2026 — Lite modelde Türkçe karakter kaybı
- Lite ile toplu üretimden sonra rastgele örnek okunurken bazı çıktıların ç, ğ, ı, ö, ş, ü olmadan yazıldığı
  görüldü: "Asagidaki metne gore baslangic duzeyinde bir coktan secmeli soru olustur", "Adim 1: ... dogrulanmis
  otegezegen". Dil tespiti bunları Türkçe saydığı için hiçbir kontrol yakalamıyordu.
- Ölçüm: gemini-3.5-flash-lite örneklerinin %19,7'si (225/1.140), Flash örneklerinin %0'ı (0/171). Sorun çağrı
  düzeyinde: kusurlu örneklerin 214/225'i, çıktısının ≥%70'i kusurlu 20 işten geliyor; 80/105 lite işi tamamen temiz.
- Tespit kuralı (`scripts/turkish_check.py`): (a) cevapta Türkçe'ye özgü harf oranı < %1,5 (doğal Türkçede
  ~%8–11; çoktan seçmeli JSON anahtarları sayılmaz) veya (b) doğru Türkçede kelime olarak geçmeyen
  karaktersiz biçimler ("icin", "gore", "yildiz", "olustur"...). Talimatın yalnız ilk 300 karakterine bakılır,
  çünkü özetleme talimatları İngilizce kaynak metin içerebilir. İlk sürümde "sonuc\w*" kalıbı doğru yazılmış
  "sonucu"/"sonucunda"yı da yakaladı (Flash'ta 1 yanlış alarm); kalıp yalnız "sonuc" olarak daraltıldı.
- **Çözüm:** üç katman:
  1. `10_generate_instructions.py`: bir işin örneklerinin ≥%30'u kusurluysa çıktı kaydedilmez ve iş yeniden
     denenir (3 başarısız denemeden sonra atlanır);
  2. `11_verify_instructions.py`: kalan tek tük kusurlu örnekler `turkish_chars_missing` ile elenir;
  3. `scripts/requeue_jobs.py`: önceden üretilmiş 24 kusurlu işin (239 örnek; 19 doküman, 4 Stack Exchange,
     1 kapsam dışı) örnekleri `data/interim/archive/`'e taşındı ve işler yeniden kuyruğa alındı
     (`removed_instructions.csv`, stage=regen).
- İlk yeniden denemede kuyruğa alınan 24 işin 14'ü temiz çıktı, 10'u yine kusurluydu. Yeni işlerde reddetme
  nadirdi. Yani bazı işler lite'ta tekrar tekrar kusur üretiyor. Üç başarısız denemede iş kalıcı olarak
  atlanacağı için kural eklendi: lite'ta iki kez Türkçe karakter kusuru veren iş yalnız Flash ile denenir. O an
  Flash kotası yoksa iş atlanmaz, ertelenir (`llm.force_exclude`, sahte istemciyle test edildi).

## 23.10.2026 (akşam) — Döngünün sürekliliği, geçici hata sınıflaması, ek paket
- **Döngü oturumla birlikte kapandı.** VS Code içinden arka planda başlatılan döngü, oturum kapanınca 16:17'deki
  45 dakikalık beklemede sonlandı ve 20:09'a kadar hiçbir şey üretilmedi. Döngü artık Windows Görev
  Zamanlayıcı ile oturumdan bağımsız çalışıyor (`AstroTutorInstructionLoop`, oturum açılınca da başlar;
  `scripts/windows/run_loop_hidden.vbs`). İki döngünün aynı dosyalara yazmaması için işletim sistemi kilidi
  (`logs/instruction_loop.lock`) eklendi. İş bitince `logs/instruction_loop.DONE` yazılır, sonraki
  tetiklemeler hiçbir şey yapmaz. Kilit iki süreçle test edildi.
- **Geçici hata kalıcı sanılıyordu.** `JOB_SE_0022` için iki Flash modeli 503, ikisi 429 (kota) verdi. İstemci
  yalnız son hatayı (429) bildirdiği için üretim script'i bunu kalıcı hata sayıp işi üçüncü denemede atladı.
  - `TransientError` eklendi: çağrıdaki bütün hatalar geçiciyse (503, kota, dakikalık sınır, bağlantı kopması
    WinError 10054) iş kalıcı hata sayılmaz.
  - Kalıcı sayılan tek durum, dört denemede de geçersiz JSON.
  - 12 durumla sahte istemci testi yapıldı.
  - `JOB_SE_0022`'nin yanlış "atlandı" ve 429 kayıtları geri alındı (yedek: scratchpad).
- **Ön doğrulama (yargıçsız, `11 --no-judge`).** 2.956 ham örnekten 2.806'sı kural ve kanıt kontrolünden geçti.
  Başlıca elenme nedenleri: Türkçe karakter eksik 51, bozuk çoktan seçmeli JSON 34, kaynakta olmayan kanıt 20,
  görülmeyen metne atıf 17. Tahmini toplam (kalan 36 Flash işiyle) ~3.190, yargıç ve insan kontrolünden önce.
  Çoktan seçmeli türde lite'ın verimi %74 (tahmini 368, hedef 476).
- **Karar: ek paket `ek1`.** 3.000 alt sınırı, 36 Flash işinin tamamlanmasına bağlı kalmasın ve tür dağılımı
  hedefe yaklaşsın diye, henüz işi olmayan 33 dokümandan 283 örneklik ek doküman işi eklendi (128 çoktan
  seçmeli; iş başına aynı türden en fazla 4). Kotalar `config.yaml: instruction.supplement`'te. Var olan işler
  değişmedi; aynı doküman iki kez kullanılmadı.
- Seviye alanında bir örnekte baş boşluğu (" ileri") görüldü. Doğrulamada normalleştiriliyor; geçersiz seviye
  `invalid_level` ile eleniyor.

## 24.10.2026 — Gece uykusu
- Bilgisayar 00:38'de uykuya geçti, 09:33'te uyandı ("Uyku Nedeni: Application API", yani açık bir uyku komutu;
  boşta kalma süresi zaten "asla"). Uykuda bekleme sayacı da durduğu için 9 saat hiçbir deneme yapılmadı. Döngü
  artık `SetThreadExecutionState` ile Windows'un kendiliğinden uykuya geçmesini engelliyor. Kullanıcının açık uyku
  komutu bununla engellenemez.

## 24.10.2026 — Near-duplicate eşiğinin incelenmesi ve ikinci geçiş (06b)
- 50 aday çift (25'i Jaccard ≥ 0.85, 25'i altı) tam metinleriyle karşılaştırıldı (Claude ön incelemesi,
  `reports/qc/near_dup_pairs_review.csv`; Eda'nın kararı ayrı sütunda):

  | | Gerçek tekrar | Farklı doküman |
  | --- | --- | --- |
  | Eşik üstü (elendi) | 25 | 0 |
  | Eşik altı (tutuldu) | 18 | 7 |

  (Son örneklem. 05 inceleme örneklemini LSH sorgu sonuçlarının sırasına göre seçiyordu; bu sıra çalıştırmadan
  çalıştırmaya değiştiği için aynı seed ile farklı çiftler çıkıyordu. Listeler örneklemeden önce sıralanınca
  örneklem tekrarlanabilir oldu (iki çalıştırmada aynı imza). Yeni örneklemin 12 çifti önceki incelemeyle
  ortaktı, 38 çift yeniden incelendi. Tekrar ayıklama kararları sıralı yapıldığı için bu sorundan etkilenmiyordu.)

  Eşik hiç yanlış eleme yapmadı, ama APOD'un aynı açıklamayı yıllar sonra küçük düzeltmelerle ("above" →
  "featured", başlık satırı, altbilgi) yeniden yayımladığı sayfaları ve NASA şablon sayfalarını kaçırdı. Kelime
  5-gram Jaccard'ı, kısa metinlerde dağınık küçük düzeltmelere çok duyarlı.
- Corpus taraması (LSH 0.5): Jaccard 0.6–0.85 aralığında 190 çift, bunların 46'sı farklı kümelerde (sızıntı riski).
  APOD'da 0.5–0.65 aralığındaki çiftler bile çoğunlukla aynı başlıklı yeniden yayın (karakter benzerliği 0.83–0.94).
- Genel eşik **düşürülmedi**: NASA'nın Jüpiter/Neptün uydu sayfaları ortak şablon paragrafına rağmen farklı uyduların
  keşif tarihi, keşfeden kişi ve boyut bilgisini taşıyor ve Jaccard 0.74'e kadar çıkıyor. Wikipedia'da da farklı
  NGC/uydu taslak maddeleri benzer şablonlu.
- **Çözüm (`scripts/06b_repost_dedup.py`):**
  - APOD: kelime Jaccard ≥ 0.5 ve karakter dizisi benzerliği (difflib) ≥ 0.85; NASA Science: ≥ 0.75 ve ≥ 0.90.
    Wikipedia'ya uygulanmaz.
  - 139 doküman çıkarıldı (136 APOD, 3 NASA Science); 33 çift farklı kümelerdeydi. Karakter benzerliği en düşük
    çıkarılan çiftler elle kontrol edildi, hepsi yeniden yayındı.
  - Çiftten en son yayımlanan tutuldu: yeniden yayında bilgiler güncelleniyor (Veil Nebula yaşı 2009'da "7,500",
    2012'de "9,000" yıl). İlk sürüm ilk yayımlananı tutuyordu, düzeltildi.
  - Ayrıca 84 APOD dokümanından site duyurusu satırları silindi ("Follow APOD on...", "Gallery: ...",
    "Open Science: Browse ...").
- **Neden ayrı adım:** bu sorunlar instruction üretimi başladıktan sonra bulundu. 03 veya 05 değiştirilseydi
  `DOC_` kimlikleri kayacak ve instruction örneklerinin kaynak bağı kopacaktı. 06b, 06'dan sonra çalışıyor,
  kimlikleri ve kümeleri değiştirmiyor, yalnız satır ve doküman çıkarıyor. Hiçbir instruction kaynağı çıkarılmadı
  (kontrol edildi: eksik kaynak 0). İkinci çalıştırmada değişiklik yapmıyor ve kayıtları ezmiyor.
- Corpus v1.0 (bu aşamada): 16.297 doküman, 16,26 M token. Son hâli için aşağıdaki bölümlere bakın.

## 24.10.2026 — Kaybolmuş üsler (corpus elle incelemesinde bulundu)
- İncelenen ilk dokümanlardan "Magnetar" (Wikipedia EN): "~109 to 1011 T". Doğrusu 10^9–10^11 T.
  Wikipedia'nın düz metin servisi (TextExtracts) HTML üst simgelerini (<sup>) siliyor; trafilatura (NASA Science)
  ve PyMuPDF (OpenStax, üs yazı konumuyla verilmiş) da aynısını yapıyor. 03'teki "üs koruma" kuralı yalnız Unicode
  üst simge karakterleri (²³) içindi ve bu durumu kapsamıyordu.
- Taramada etkilenen doküman: Wikipedia EN 602, TR 117, OpenStax 20, NASA Science 6, arXiv 2. Bilim öğreten bir
  model için ağır bir hata ("Güneş'e uzaklık 1.5 × 108 km").
- **Çözüm (`scripts/exponent_fix.py`, 06b adım 0):** yalnız belirsizliği olmayan kalıplar düzeltilir:
  (A) "<sayı> × 10NN" (harf "x" yalnız ondalıklı ve en fazla 2 basamaklı katsayıdan sonra),
  (B) "10NN–10NN <birim>", (C) "~10NN <birim>". 25 birim testi yazıldı. Bulunan yanlış pozitifler testlere eklendi:
  - "1024×1024 pixels" ve "103 × 104 miles": 3+ basamaklı ondalıksız katsayı bilimsel gösterim değil;
  - "1076.8 x 1057.4 x 1052.6 kilometers": üssün arkasından ondalık gelemez;
  - arXiv "R ~ 10-11 kpc" (10 ile 11 kpc): aralık ve "~" kalıplarında negatif üs yalnız Unicode eksi (−) ile kabul edilir.
  - Zincirleme çarpım ("6.7 × 10−8×10−18") ilk sürümde iki geçişte tamamlanıyordu. Artık tek çalıştırmada
    kesinleşiyor (tüm corpus'ta ikinci geçiş 0 değişiklik).
- Sonuç: 747 dokümanda 1.934 ifade düzeltildi. Belirsiz kalanlar (ör. "(1031 erg/s)", "10-16 ila 10-7 gram")
  düzeltilmedi.
- **Instruction verisine etkisi:** Gemini'ye bu metinler üssüz verilmişti. Taramada 3.305 ham örnekten yalnız 2'sinde
  üs kaybı vardı (ör. "Güneş'in kütlesi 1.99 x 1030 kg"); `11_verify`'a `exponent_loss` kuralı eklendi. Kanıt
  kontrolü "^" işaretini yok sayıyor, çünkü alıntılar eski metinden kopyalandı ("108" = "10^8").
- **NASA sözlük sayfalarında terim kaybı (corpus incelemesi).** "Glossary - B" yalnız tanımları içeriyordu; "biomass",
  "bow shock" gibi terimler yoktu. Neden: 03'teki "kısa yalnız satır" kuralı (rakamsız < 20 karakter) terim satırlarını
  da siliyordu. Sözlük sayfalarında bu kural artık uygulanmıyor ve "A | B | C | ..." harf dizini siliniyor.
  03–08 yeniden çalıştırıldı; kimlik kümesi, raw_id eşlemesi ve kümeler birebir aynı kaldı, yalnız 20 sözlük
  sayfasının metni değişti (yedekle karşılaştırıldı).
- **NASA basın bülteni künyeleri ve kişisel veri (corpus incelemesi).** NASA Science metinlerinin sonunda "Text
  credit: ...", "Media Contact: ⏎ <ad> ⏎ <merkez> ⏎ <telefon>", "For more information ... visit: <URL>" satırları
  vardı. Taramada **348 e-posta adresi ve 183 telefon numarası** bulundu. Bunlar kamuya açık basın iletişimleri,
  ama kişisel veri ve alan bilgisi taşımıyor.
  - Çözüm (`scripts/press_boilerplate.py`, 06b adım 1b; yalnız NASA kaynakları): iletişim blokları, e-posta/telefon
    içeren kısa satırlar, kredi satırları, kısa "daha fazla bilgi" çağrıları, yalnız bağlantı satırları, "###"
    ayraçları silinir. Uzun (düzyazı) satırlardaki e-posta/telefon "[e-posta]"/"[telefon]" ile maskelenir.
  - **Hata ve düzeltme:** ilk sürüm "Contact:" başlığından sonra boş satıra kadar bütün kısa satırları siliyordu.
    Satırları ~70 karakterde kırılmış ve boş satırı olmayan eski bir bültende (DOC_009307, Io) başlık ve tarih
    dışındaki bütün metni sildi. Rastgele 45 silinen satır incelenirken yakalandı. İletişim bloğu artık en fazla
    6 satır ve satır başına en fazla 8 kelime ile sınırlı; bu durum için test eklendi. 06b, bu adımda metninin
    %30'undan fazlasını kaybeden dokümanları uyarı olarak logluyor. Kalan tek doküman bir iletişim/bağlantı
    sayfası (DOC_011295, Lucy media resources).
  - Sonuç: 478 dokümanda künye/iletişim satırları silindi. NASA kaynaklarında kalan e-posta/telefon: 0.
    Instruction örneklerinde e-posta/telefon yoktu (tarandı); yine de `11_verify`'a `contains_pii` kuralı eklendi.
  - Künye satırları kalkınca bir APOD çifti daha yeniden yayın eşiğini geçti (toplam 140).
  - İnceleme sırasında iki kalıntı daha görüldü ve dar kurallarla eklendi: tek başına duran merkez künyesi satırı
    ("NASA's Goddard Space Flight Center, Greenbelt, Md."; en fazla 10 kelime; 160 satır) ve paragraf sonuna yapışmış
    "For the full text and image link to:". "## " ile işaretli başlıklar korunuyor (testli).
  - Temizlikten sonra içeriği yalnız iletişim kalan dizin sayfaları ("/media-contacts/", "/media-resources/",
    "/contact/"; 1000 karakterden kısa) `contact_page` nedeniyle çıkarıldı (7 doküman). Bu sayfalarda tablolarda
    personel adları kalıyordu. 1000 karakterden uzun "Eclipses media resources" sayfası gerçek içerik taşıdığı için
    tutuldu. 300 karakterin altına düşen 1 doküman `too_short_after_06b` ile çıktı.
- Corpus (bu aşamada): 16.288 doküman, 16,25 M token. Son hâli aşağıda.

## 24.10.2026 — Corpus elle incelemesi: ön tur, düzeltmeler ve final örneklem
- **Ön inceleme turu.** İlk örneklemin incelenmesi sırasında bulunan sorunlar corpus genelinde düzeltildi:
  kaybolmuş üsler, sözlük terimleri, NASA künye satırları ve kişisel veri, APOD yeniden yayınları, iletişim
  sayfaları. Hepsi 06b'de, kimlikler korunarak yapıldı (yukarıdaki bölümler). Ek olarak:
  - **Kurgu/eser maddeleri:** "Treasure Planet" (Disney filmi) ve 3 eser maddesi, kendi adlarını taşıyan tek bir
    "astronomi" kategorisiyle filtreyi geçiyordu. Madde bir eser kategorisi (film/roman/şarkı) taşıyor ve kendi
    adlı kategori dışında astronomi kategorisi yoksa çıkarılıyor (06b 1d; 4 madde). Kendi adlı kategoriyi genel
    olarak saymamak "Astronomi tarihi" ve "Light pollution" maddelerini de eleyeceği için yapılmadı.
  - **arXiv alt konuları:** 05'te arXiv kategorisi yalnız ek puandı; astro-ph.HE makalelerinin %92'si (kuasar ve
    blazarlar dahil) "stars", astro-ph.GA'nın 246'sı "stars" etiketi almıştı. 06b 1e: GA→galaxies, CO→cosmology,
    IM→observatories_telescopes doğrudan; SR (yıldız/Güneş), EP (ötegezegen/gezegen/Güneş Sistemi) kategoriye
    uygun alt konular arasında anahtar kelimeyle; HE için ayrı terimler (güçlü AGN işareti ≥ 2 → galaxies; yoksa
    kompakt nesne/AGN/kozmoloji puanı; sinyal yoksa general_astronomy). 1.307 arXiv dokümanı yeniden etiketlendi.
    Wikipedia'da tarama kategorisini belirleyici yapmak denendi ama örneklemde yeni hatalar üretti (Messier 13 →
    galaxies), uygulanmadı.
- **Örneklemin değişmesi.** 13 tabakalı örneklemi kaynak içindeki karıştırma sırasıyla seçtiği için corpus'tan
  doküman çıktıkça örneklem değişti. Final ölçüm, corpus dondurulduktan sonraki örneklem üzerinde yapıldı.
- **Corpus dondu** (24.10.2026 10:59): 16.284 doküman, 16,23 M token; train 14.660 / validation 819 / test 805;
  md5 (ilk 12): train `088a165bf97b`, validation `3f9a0eca2f20`, test `da9a92c050c8`.
- **Final örneklem (100 doküman), Claude ön incelemesi:** 88 uygun / 12 sorunlu.

  | Ölçüt | Başarılı |
  | --- | --- |
  | okunabilir | 100 |
  | doğru alan | 98 |
  | extraction doğru | 95 |
  | header/footer temiz | 100 |
  | bozuk karakter yok | 100 |
  | metadata doğru | 93 |

  Sorunların dağılımı:
  - alt konu hatası 7 (arXiv dışı kaynaklarda, anahtar kelime yöntemi);
  - Wikipedia formül kalıntısı (MathML'den başıboş rakam satırları) 2;
  - alan dışı 2 (Ay festivali maddesi, NASA'nın Yer bilimi kısaltma sözlüğü);
  - SSS sorularının çıkarılmaması 1;
  - tablo eksik liste sayfası 1.

  Ayrıca 5 küçük kelime birleşmesi/bölünmesi (APOD bağlantı metinleri) not edildi ama sorunlu sayılmadı. Nihai
  karar Eda'nın (`son_karar`).
- Bilinen küçük kusur (düzeltilmedi): kaynaktaki bozuk kodlanmış kesme işareti "¹" → "^1" ("Saturn^1s"; 4 örnek).
- 06b'nin tekrar çalıştırılması kayıtları iki kez ezdi (yedekten geri alındı). Sebebi, adımın işlenmiş veriye
  ikinci kez uygulanabilmesiydi. Artık her doküman `postprocess: "06b"` işareti taşıyor; işaretli veriye adım
  uygulanmıyor. 07 bu alanı koruyor.

### 24.10.2026 — Corpus ve near-duplicate incelemeleri: nihai karar
Eda, ön inceleme kararlarını onayladı: corpus örneklemi (100 doküman: 88 uygun / 12 sorunlu) ve near-duplicate
eşik tablosu (50 çift). `son_karar` / `son_karar_tekrar_mi` = ön inceleme kararı, `insan_notu` = "onay: ...".
14 ve 15 bunu "grup üyesinin onayı" olarak yazar; onaylanan kararlar için ayrıca uyuşma oranı hesaplanmaz.

## 24.10.2026 — Çoktan seçmeli örneklerde cevabı talimatta verilmiş örnekler
- Sunum için örnek seçerken bir çoktan seçmeli örneğin talimatının "Bu bilgilere dayanarak hazırlanan çoktan
  seçmeli soruyu cevapla: ... A) William Herschel - 1785 ..." biçiminde olduğu görüldü. Görev türü "metinden soru
  üretme" olduğu hâlde soru, şıklar ve bazen doğru cevap talimatın içindeydi; cevap talimatın JSON kopyasıydı.
  Böyle bir örnek modele soru üretmeyi değil, verilen soruyu kopyalamayı öğretir. Hiçbir kontrol yakalamıyordu
  (JSON geçerli, kanıt kaynakta var).
- Ölçüm (446 doğrulanmış çoktan seçmeli örnek): soru kökü talimatta 45, şıklar da talimatta 33, doğru cevap da
  talimatta (`"dogru_cevap": "B"`) 29 → toplam 107 (%24). 96'sı lite, 7'si Flash örneği.
- **Çözüm:**
  1. `11_verify_instructions.py`: `mcq_answer_in_instruction` kuralı (cevaptaki soru kökü ≥ 25 karakter
     normalize edilmiş hâliyle talimatta geçiyorsa, talimatta 3+ şık satırı veya doğru cevap anahtarı varsa elenir).
     Kuraldan geçen örneklerden rastgele 20'si okundu: 3'ü yine sorunluydu ("Soru: ..." etiketli kök farklı
     kelimelerle; soru olmadan "ilgili soruyu yanıtlayınız" diyen tutarsız talimat). Kural genişletildi (satır içi
     şıklar, "Soru:" etiketi, "soruyu/soruları ... yanıtla/cevapla" kalıbı; "soru hazırlayıp JSON formatında
     yanıtlayın" ve "bazı soruları yanıtlayamaz" gibi doğru ifadeler 11 durumlu testte yakalanmıyor). Ek elenen
     40 örneğin 40'ı da elle kontrol edildi, hepsi gerçek kusur. Yeni rastgele 20'lik örneklemde kusur yok.
     Ayrıca 12 talimatın sonundaki tek başına "{" artığı doğrulamada atılıyor (normalleştirme).
  2. Prompt `v1.1` (`prompts/v1.1/`): v1'in kopyası; yalnız çoktan seçmeli tanımına "talimatta soru, seçenek
     veya doğru cevap yer almaz" kuralı eklendi. Bundan sonraki üretimde (kalan 13 iş + ek2) v1.1 kullanılır;
     her örneğin `prompt_version` alanı hangi sürümle üretildiğini gösterir. ek2 başlar başlamaz lite'ın ilk 8
     çıktısı Türkçe karakterleri düşürülmüş olduğu için reddedildi (ret mekanizması çalıştı). Teşhis için aynı iş
     kaydedilmeden bir kez daha üretildi: bu kez 5 örneğin 5'i temiz. Kusur çağrıdan çağrıya değişiyor ve belli
     saatlerde yoğunlaşıyor (23.10'da 14-16 arası 90 ret). v1.1 sistem prompt'una ayrıca "Türkçeye özgü harfleri
     ASCII karşılıklarıyla değiştirme" kuralı (10. kural) eklendi.
  3. Doğrulanan örnek 3.308 → 3.180 (yargıçsız); çoktan seçmeli 446 → 305, payı %13,5 → %9,6 (hedef %14). Ürünün ana işlevi soru
     üretmek olduğu için **ek paket `ek2`**: henüz işi olmayan 34 dokümandan 170 çoktan seçmeli örnek
     (doküman başına en fazla 5; seed 13). Lite'ın bu türdeki verimi ~%57 (Flash ~%86) olduğu için kota hedefin
     üzerinde tutuldu. Var olan işler değişmedi; aynı doküman ikinci kez kullanılmadı.
- `09`: `supplement` artık paket listesi; tek türlü pakette aday doküman sayısı doküman başına kapasiteye göre
  hesaplanıyor (ek1 ve ana iş listesi için hesap değişmedi, yeniden üretilebilirlik korunuyor).
- **v1.1'in etkisi (ilk 100 ek2 örneği, lite):** kural kontrolünde temiz 89, talimatta soru 10, bozuk JSON 1
  (v1'de çoktan seçmeli lite örneklerinin ~%24'ü sızıntılıydı). 10 sızıntının 10'u 2 işten geliyor; sorun Türkçe
  karakter kaybı gibi çağrı düzeyinde. Bu yüzden:
  - kontrol `scripts/mcq_check.py` modülüne taşındı (10 ve 11 aynı kuralı kullanıyor);
  - `10_generate_instructions.py`: bir işin çoktan seçmeli örneklerinin ≥ %30'u sızıntılıysa çıktı kaydedilmez,
    iş yeniden denenir (3 başarısız denemede atlanır);
  - v1.1 ile üretilip sızıntılı çıkan 4 ek2 işi (20 örnek) `requeue_jobs.py --reason mcq --prompt-version v1.1`
    ile arşivlenip yeniden kuyruğa alındı (`removed_instructions.csv`, stage=regen). v1 ile üretilmiş 73 sızıntılı
    iş yeniden üretilmedi: bu işlerin ~600 sağlam örneği de atılacaktı; sızıntılı örnekler 11'de tek tek elenir.
- **Envanter ve özetler:** `reports/source_inventory.csv` 23.10'daki kısmi veriyle yazılmış kalmıştı (çoğu kaynak 0);
  15 her çalıştırmada final veriden yeniden yazıyor, ham doküman ve token sütunları eklendi. `split_summary.json`
  06b öncesi sayıları taşıyordu; 08 artık final kümelerle yeniden yazıyor. `instruction_sources_summary.json`
  ek paket eklenirken Stack Exchange eleme nedenlerini `{}` olarak yazıyordu (kayıtlar CSV'de duruyordu); düzeltildi.

## 24.10.2026 — Görünmeyen metne atıf (sınıflandırma ve cevaplar) ve ek paket ek3
- Görev türü uzunluk taraması: sınıflandırma talimatlarının çoğu kısa (medyan 150 karakter) ama "metinde geçen
  molekülleri sınıflandır" diyor; talimatta ne metin ne öğe listesi var. Kural, sınıflandırmayı "metin içeren tür"
  saydığı için yakalamıyordu. Ayrıca metin verilmeyen türlerde 52 cevap "Kaynakta verilen bilgiye göre ...",
  "Kaynak metne göre ..." diyordu (çoğu adım adım problem çözme). Eğitimde cevaplar öğrenildiği için model
  görünmeyen bir kaynağa atıf yapmayı öğrenirdi. Prompt'un 5. kuralı bunu yalnız talimatlar için yasaklıyordu.
- **Çözüm (11):** (a) sınıflandırmada talimat 300 karakterden kısa (pasaj yok), atıf ifadesi var ve 3'ten az öğe
  ayırıcısı varsa `references_unseen_text`; (b) metin içermeyen türlerde cevapta atıf ifadesi varsa
  `response_references_unseen_text`. Atıf kalıbına "kaynaktaki", "metindeki", "dokümandaki", "kaynak metin..."
  eklendi; "kaynaktan" eklenmedi (taramada çoğunlukla "ışık kaynağından" anlamında). Öğeleri sayan sınıflandırma
  talimatları ("Metinde adı geçen Uranüs, Neptün, Jüpiter ve Satürn'ü ... sınıflandır") cevapta atıf yoksa tutuldu.
  Elenenlerden rastgele 15'i okundu, hepsi gerçek kusur.
- Sonuç (yargıçsız): 3.184 doğrulanmış; sınıflandırma %2,2 (hedef %4), adım adım problem çözme %5,4 (hedef %7).
  Çoktan seçmeli ek2 ile %14,0'a çıktı.
- **Prompt v1.2** (`prompts/v1.2/`): v1.1 + kural 11 (cevaplarda da atıf ifadesi yok), kural 5'te sınıflandırma
  pasajlı türlerden çıkarıldı, sınıflandırma tanımına "öğeleri talimatta açıkça say", problem çözme tanımına
  "gerekli sayısal değerleri talimatta ver" eklendi. Bundan sonraki tüm üretim v1.2.
- **Ek paket ek3:** henüz işi olmayan 23 dokümandan 90 sınıflandırma + 75 problem çözme örneği (iş başına aynı
  türden en fazla 4; seed 14).

## 24.10.2026 — Değerlendirme seti sızıntı kontrolündeki hata
- Corpus ile değerlendirme setlerinin örtüşmesi ölçülürken toplam n-gram sayısı (5.853) dört set için az göründü.
  Neden: `eval_ngrams` yalnız `dtype == object` sütunlara bakıyordu; pandas 3.1'de metin sütunları `str` tipinde.
  Astrobench (3.846 soru), Hubble MCQ (1.052) ve Astro-mcqa (200) hiç okunmuyordu; yalnız astro-mcq'nun liste
  sütunları giriyordu. Yani Stack Exchange seçimi (09) ve instruction doğrulaması (11) sızıntıyı bir set için
  kontrol ediyordu.
- **Düzeltme:** metin tipi `is_object_dtype or is_string_dtype`; kimlik/etiket sütunları ve manifest dosyaları
  dışarıda; Hubble MCQ'nun soruların üretildiği bağlam pasajı (`source_document`) ayrı tutuluyor. Yeni toplam:
  203.375 soru/seçenek/açıklama 8-gram'ı (+65.771 bağlam 8-gram'ı).
- **Yeniden ölçüm:**
  - Instruction (doğrulanmış 3.184): 4 özetleme örneği 1–3 adet 8-gram paylaşıyor → 11'de `eval_overlap` ile elenir.
  - Örnekler Türkçe olduğu için n-gram kontrolü çeviriyi yakalayamaz; bu yüzden İngilizce kaynaklar da tarandı:
    449 Stack Exchange kaynak sorusundan 5'i yalnız 1–2 genel ifade paylaşıyor ("upper limit to the mass of a
    star", "black hole at the center of our galaxy"), aynı soru yok. 333 kaynak dokümandan 3'ü ≥ 3 paylaşıyor;
    biri "True anomaly" maddesinin bir değerlendirme sorusunda geçen tanım cümlesi, diğerleri genel ifadeler.
  - Corpus: 75 doküman ≥ 3 adet 8-gram paylaşıyor (52'si İngilizce Wikipedia; değerlendirme soruları kısmen
    Wikipedia'dan üretilmiş). Corpus'tan çıkarılmadı (meşru alan bilgisi: "Hubble Space Telescope" maddesi gibi);
    bunun yerine ters yönde, corpus ile ≥ 3 adet 8-gram paylaşan **60 değerlendirme sorusu** (~%1)
    `reports/eval_contamination.csv`'ye yazılıyor (`validate_datasets.py`). Final dönemi karşılaştırmasında
    bu sorular ayrıca raporlanacak.
