# AstroTutor AI — Vize Sunumu Taslağı

Rehber §16 akışına göre slayt slayt içerik. Sayıların hepsi veri setlerinden ve raporlardan alınmıştır
(`reports/statistics.md`, `reports/quality_control_report.md`, kartlar); sunumdan önce son hâllerinden kontrol edin.
Her slaytın altında konuşma notu (Not) ve beklenen "neden?" sorusuna hazır cevap var.

---

## 1. Proje ve hazırlayan
- **AstroTutor AI** — Uzay ve Astronomi Eğitiminde SLM ve RAG Tabanlı Etkileşimli Öğrenme ve Test Sistemi
- Eda GÖGEBAKAN (2211012069) · Danışman: Asim Sinan YÜKSEL · SDÜ Bilgisayar Mühendisliği
- Vize hedefi: iki eğitime hazır veri seti — **Domain Corpus v1.0** (CPT/DAPT) ve **Instruction Dataset v1.0** (SFT)

## 2. Alan ve amaç
- **Problem:** Türkçe konuşan öğrencilerin astronomiyi kendi seviyelerinde öğrenebileceği, anlatılan içerikten soru
  üreterek öğrenmeyi ölçen, kaynağı izlenebilir bir yardımcı yok.
- **Hedef:** Başlangıç / orta / ileri seviyeye göre Türkçe konu anlatan ve anlattığı içerikten 4 seçenekli soru üreten
  alana özel model (ana aday: Qwen2.5-7B ailesi).
- **Kapsam içi:** Güneş Sistemi, gezegen ve uydular, yıldızlar ve yıldız evrimi, gökadalar, temel kozmoloji,
  ötegezegenler, uzay araçları ve görevler, gözlemevleri/teleskoplar.
- **Kapsam dışı:** ileri matematiksel türetme, ham görüntü işleme, simülasyon, roket mühendisliği, ticari konular, astroloji.

## 3. Veri ihtiyacı
| İhtiyaç | Neden | Karşılayan veri |
| --- | --- | --- |
| Alanın dili ve bilgisi (düz metin) | CPT/DAPT: model terimleri ve bilgi örüntüsünü öğrenir | Domain Corpus v1.0 |
| Türkçe talimat takip etme, seviyeli anlatım, soru üretme | SFT: asistan davranışı | Instruction Dataset v1.0 |
| Değerlendirme | Final dönemi karşılaştırması | Astro-mcqa, astro-mcq, Hubble MCQ, Astrobench — **eğitime girmez**, yalnız sızıntı kontrolü |

## 4. Veri kaynakları
| Kaynak | Tür | Dil | Ham → final doküman | Lisans | Neden |
| --- | --- | --- | --- | --- | --- |
| NASA Science | HTML | en | 3.109 → 2.849 | NASA kullanım yönergeleri | Güvenilir birincil kaynak; görev başına en fazla 150 sayfa |
| NASA APOD | HTML | en | 2.720 → 2.445 | NASA (yalnız metin) | Popüler bilim dili; her yıldan 85 açıklama |
| OpenStax Astronomy 2e | PDF | en | 243 → 238 | CC BY-NC-SA 4.0 | Hakemli ders kitabı; PDF extraction |
| arXiv astro-ph | XML | en | 6.000 → 5.953 | CC0 (metadata) | İleri seviye terminoloji (başlık + özet) |
| Wikipedia EN | API | en | 3.576 → 3.238 | CC BY-SA 4.0 | Ansiklopedik kapsam |
| Wikipedia TR | API | tr | 1.737 → 1.561 | CC BY-SA 4.0 | Türkçe terminoloji |
| Stack Exchange Space/Astronomy | HF dataset | en | 33.519 kayıt → 449 soru | CC BY-SA 4.0 | Yalnız instruction (gerçek kullanıcı soruları) |

Not: NASA Exoplanet Archive bilerek alınmadı (sürekli değişen tablo verisi → final dönemde RAG).
**Neden İngilizce çoğunlukta?** Alanın açık lisanslı birincil kaynakları İngilizce; Türkçe astronomi metni sınırlı.
Türkçe Wikipedia terminoloji için eklendi (token'ların %16,9'u). Türkçe davranışı Instruction Dataset kazandırır
(örneklerin tamamı Türkçe; özetleme görevi İngilizce kaynağı Türkçe aktarmayı öğretir).

## 5. Pipeline
```
01_download → 02_extract → 03_clean → 04_filter → 05_deduplicate → 06_split → 06b (ikinci geçiş) → 07_token_count → 08_statistics
                                                                                    │
            09_build_instruction_sources → 10_generate (Gemini) → 11_verify → 12_split → 13–14 kalite kontrol → 15 kartlar
```
- Her adım ayrı script, `config.yaml` (yollar, eşikler, seed 42), `logs/` altında log, sonunda özet sayılar.
- `python run_pipeline.py --all` baştan sona yeniden üretir; indirme ve üretim kaldığı yerden devam eder.
- Kod, kartlar, raporlar, küçük örnekler Git'te; büyük veri `data/` altında (README'de açıklandı).

## 6. Extraction ve cleaning — gerçek öncesi/sonrası
**PDF okuma sırası (sessiz bozulma, OpenStax):** varsayılan okuma "Learning Objectives" kutusunu paragrafın ortasına
karıştırıyordu: "...but this did not *Explain what determines the strength of gravity...* deter Isaac Newton".
→ Metin blokları sayfadaki dikey konuma göre sıralandı.

**Kaybolmuş üsler (elle incelemede bulundu):**
| Önce | Sonra |
| --- | --- |
| "Güneş'e uzaklık 1.5 × 108 km" | "1.5 × 10^8 km" |
| "~109 to 1011 T" (Magnetar) | "~10^9 to 10^11 T" |
Wikipedia düz metin servisi, trafilatura ve PyMuPDF üst simgeleri siliyordu; 747 dokümanda 1.934 ifade
belirsizliği olmayan kalıplarla geri yazıldı (25 birim testi; "1024×1024 pixels" gibi yanlış pozitifler testli).

**NASA basın künyeleri ve kişisel veri:** "Media Contact: ⏎ ‹ad soyad› ⏎ ‹merkez, şehir› ⏎ ‹telefon›" blokları;
348 e-posta ve 183 telefon numarası silindi (kalan: 0).

Diğer örnekler: [reports/cleaning_examples.md](cleaning_examples.md) (20 öncesi/sonrası), kural tablosu:
[reports/cleaning_rules.md](cleaning_rules.md).

## 7. Tekrar ayıklama
| Yöntem | Bulunan |
| --- | --- |
| Exact (SHA-256) | 46 |
| Near duplicate (MinHash LSH, kelime 5-gram, 128 permütasyon, Jaccard ≥ 0,85) | 90 |
| Yeniden yayın tekrarı (06b; APOD Jaccard ≥ 0,5 + karakter benzerliği ≥ 0,85) | 140 (33'ü farklı kümelerde → sızıntı) |

- **Eşik doğrulaması:** 50 aday çift (25'i eşik üstü, 25'i altı). Eşik üstü 25 çiftin 25'i gerçek tekrar
  (hatalı eleme 0); eşik altı 25 çiftin 18'i de tekrardı (çoğu APOD yeniden yayını).
- **Neden genel eşik düşürülmedi?** NASA'nın Jüpiter/Neptün uydu sayfaları ortak şablon paragrafına rağmen farklı
  uyduların keşif tarihi ve boyutunu taşıyor; Jaccard 0,74'e kadar çıkıyor. Eşik düşerse bu bilgiler silinirdi.
  Bunun yerine yalnız APOD/NASA için iki ölçütlü ikinci geçiş eklendi; çiftten en son yayımlanan tutuldu
  (yeniden yayında bilgiler güncelleniyor: Veil Nebula yaşı 7.500 → 9.000 yıl).
- **Neden MinHash?** 16 bin doküman için tüm çiftleri karşılaştırmak ~1,3 × 10^8 karşılaştırma; LSH yalnız aday
  çiftleri getiriyor. Kelime 5-gram, cümle düzeyinde yeniden yazımlara duyarlı.

## 8. Final corpus istatistikleri — veri erimesi
**17.520 ham → 17.334 extraction sonrası → 16.572 temizleme ve filtre sonrası → 16.284 tekrar ayıklama ve ikinci geçiş sonrası**

| Özellik | Değer |
| --- | --- |
| Veri kaynağı (corpus) | 6 |
| Ham doküman | 17.520 |
| Extraction başarısız / içerik dışı | 186 |
| Filtre ile elenen | 762 (alan dışı kategori 356, kısa 242, alan dışı 150, dil 6, kaynakça listesi 5, bozuk 3) |
| Exact / near / yeniden yayın tekrarı | 46 / 90 / 140 |
| İkinci geçişte çıkarılan diğer (iletişim sayfası 7, kurgu/eser maddesi 4, çok kısa 1) | 12 |
| Final doküman | 16.284 |
| Toplam kelime / token (Qwen2.5-7B) | 10,5 M / 16,2 M |
| Chunk (en fazla 1.024 token, paragraf sınırında) | 33.997 |
| İngilizce / Türkçe (token) | %83,1 / %16,9 |
| Train / validation / test (doküman) | 14.660 / 819 / 805 |
| Manuel kontrol (100 doküman) | %88 uygun |

Grafikler: `reports/figures/funnel.png`, `sources.png`, `subtopics.png`, `token_length.png`.
Alt konular: yıldızlar %24,9, gökadalar %17,8, gezegen-uydular %14,0, Güneş Sistemi %12,0, gözlemevleri %9,1,
görevler %8,1, kozmoloji %7,4, ötegezegenler %4,9, genel %1,6.

**Neden 300 karakter alt sınırı?** 300'ün altı çoğunlukla yönlendirme/menü kalıntısı (242 doküman elendi). 300–500
aralığında 283 doküman var: 110'u Türkçe Wikipedia (Türkçe maddelerin %7'si; "Süper kütleli kara delik", "2I/Borisov"
gibi kısa ama bilgi taşıyan maddeler), 115'i NASA Science (ör. Uranüs'ün uydusu Puck'ın keşif ve boyut bilgisi).
Türkçe metin zaten kıt olduğu için 500 yerine 300 seçildi. Bedeli: bu aralıkta az sayıda değeri düşük sayfa da
kaldı (video/sosyal medya sayfaları; kartta "bilinen problem").

**Veri ayrımı:** doküman (grup) düzeyinde %90/5/5, seed 42, kaynak bazında tabakalı; aynı Wikipedia maddesinin EN/TR
sürümleri (aynı Wikidata kimliği) aynı kümede; chunk'lar bölmeden **sonra** üretildi. Kümeler arası grup çakışması: 0.

## 9. Instruction Dataset — örnekler
⟨Üretim ve doğrulama bitince doldurulacak: toplam örnek, görev dağılımı, train/val/test, model dağılımı.⟩

Örnek 1 — `coktan_secmeli_soru_uretimi`: ⟨final setten seçilecek⟩
Örnek 2 — `seviyeli_anlatim` (başlangıç): ⟨final setten seçilecek⟩
Örnek 3 — `bilgi_yetersizligi_kapsam_disi`: "Bugün hava durumu nasıl olacak, pikniğe gidebilir miyim?" →
"Meteorolojik tahminler ve günlük hava durumu verilerine erişimim yoktur ... Gökyüzü gözlemi yapmak istiyorsanız
yıldızlı geceler için astronomik koşullar hakkında konuşabiliriz."

**Neden bu kategoriler?** Tasarım raporundaki iki ana davranıştan türetildi: seviyeye göre anlatım (`seviyeli_anlatim`)
ve anlatılan içerikten JSON biçiminde soru üretme (`coktan_secmeli_soru_uretimi`; quiz modülü ve REST şeması).
`bilgi_yetersizligi_kapsam_disi` uydurma yerine sınır bildirmeyi öğretir; `ozetleme` İngilizce NASA kaynağını
Türkçe kullanıcıya aktarmayı (final dönemindeki RAG senaryosu) öğretir.

## 10. Kalite kontrolü
**Corpus (100 rastgele doküman, kaynak oranında tabakalı):**
| Kontrol | Başarılı |
| --- | --- |
| okunabilir | 100/100 |
| doğru alan | 98/100 |
| extraction doğru | 95/100 |
| header/footer temiz | 100/100 |
| bozuk karakter yok | 100/100 |
| metadata doğru | 93/100 |
| **genel uygun** | **88/100** |
Hata türleri: alt konu etiketi 7, formül kalıntısı 2, alan dışı 2, SSS kalıntısı 1, tablo eksik 1.
Yöntem: yapay zekâ destekli ön inceleme ölçüt bazında yapıldı, nihai kararı ben verdim.

**Instruction:** ⟨150 örnek incelemesi ve LLM yargıç sonuçları — doldurulacak⟩
- Doğrulama dört katmanlı: kural kontrolleri → kaynakta kanıt kontrolü (alıntının kelime 5-gram'ları kaynakta
  aranır) → %10 LLM yargıç (üreten modelden farklı model) → 150 örneklik elle inceleme.

## 11. Karşılaşılan problemler ve çözümler
| Problem | Nasıl fark edildi | Çözüm |
| --- | --- | --- |
| PDF'te kutular paragrafa karışıyordu | Çıktı okunurken | Bloklar sayfa konumuna göre sıralandı |
| Üs kaybı ("× 108 km") | Elle inceleme | `exponent_fix.py`, 1.934 ifade, testli |
| Wikipedia'da kurgu/film/bayrak maddeleri ("Warhammer 40,000") | En uzun dokümanlar incelenirken | Maddenin kendi kategorilerine dayanan filtre (356 madde); Türkçe "ı/i" büyük-küçük harf tuzağı yakalandı |
| APOD yeniden yayınları train/test arasında | Near-dup eşik incelemesi | İki ölçütlü ikinci geçiş (140 doküman) |
| NASA bültenlerinde kişisel iletişim bilgisi | Elle inceleme | Künye temizliği; e-posta/telefon 0 |
| Wikimedia hız sınırı (dakikada 8 madde) | İndirme yavaşladı | İletişim bilgili User-Agent → 200 istek/dk |
| Ücretsiz Gemini kotası (model başına günde 20 istek; 503'ler de kotadan düşüyor) | Loglar | 4 Flash modeli havuz, Flash bitince lite; kayan pencere için 30 dk yeniden deneme; Görev Zamanlayıcı ile kesintisiz döngü |
| Lite modelde Türkçe karakter kaybı ("Asagidaki metne gore") | Rastgele örnek okunurken | Türkçe karakter kontrolü; iş düzeyinde ret ve yeniden üretim |
| Çoktan seçmeli talimatta sorunun/cevabın verilmesi | Sunum için örnek seçerken | Kural + prompt v1.1 + iş düzeyinde ret |
| Kaynağı görmeyen kullanıcıya "metne göre" diyen cevaplar | Görev türü taraması | Kural + prompt v1.2 |

## 12. Final dönemi planı
1. Qwen2.5-7B base üzerinde Domain Corpus ile CPT/DAPT (QLoRA).
2. Instruction Dataset ile SFT.
3. Üç sistem karşılaştırması: hazır instruct model / alana uyarlanmış model / alana uyarlanmış + SFT;
   değerlendirme setleri (eğitime girmedi) ile ölçüm.
4. RAG: NASA Exoplanet Archive ve corpus chunk'ları ile vektör veritabanı; REST API ve arayüz.

---

## "Neden?" sorularına hazırlık
- **Neden PyMuPDF?** 40 rastgele sayfada pdfplumber ile eşit kalite (40/40 sayfa, karakter sayıları yakın), çok daha
  hızlı (iki ölçümde ~70 ve ~161 kat). Taranmış sayfa yalnız 2 kapak sayfası → OCR gerekmedi.
- **Neden 300 karakter?** Bkz. slayt 8.
- **Neden MinHash ve 0,85?** Bkz. slayt 7; eşik 50 çiftle doğrulandı, hatalı eleme 0.
- **Neden İngilizce doküman?** Bkz. slayt 4.
- **Neden bu metadata alanları?** `source`, `url`, `license`, `retrieved_at` izlenebilirlik ve lisans için;
  `group_key` sızıntısız bölme için (EN/TR aynı madde); `subtopic` kapsam dengesi analizi için; `token_count`
  eğitim bütçesi için; `postprocess` hangi dokümanın ikinci geçişten geçtiğini göstermek için.
- **Sentetik veri nasıl doğrulandı?** LLM cevabı doğru kabul edilmedi: kural kontrolleri, alıntı-kaynak kanıt
  kontrolü, ayrı modelle yargıç, elle inceleme; elenen her örnek nedeniyle `reports/removed_instructions.csv`'de.
- **Instruction seti nasıl ayrıldı?** Kaynak dokümana göre gruplu; corpus'ta test/validation olan dokümanlardan
  üretilen örnekler aynı kümede kalır → aynı dokümandan gelen örnekler farklı kümelere düşmez.
- **Pipeline yeniden çalıştırılabilir mi?** Evet: `run_pipeline.py`, sabit seed, config'te eşikler, kaldığı yerden
  devam; ikinci geçiş (06b) işlenmiş veriye tekrar uygulanmaz.
- **Bilinen eksikler?** Kartlardaki "Bilinen problemler" bölümü: kaynak dengesizliği (Wikipedia EN token'ların
  %48,5'i), corpus'un çoğunlukla İngilizce olması, alt konu etiketlerinde anahtar kelime yöntemi hataları (~%7),
  instruction örneklerinin çoğunun lite modelle üretilmiş olması.
- **Bu veri finalde gerçekten kullanılabilir mi?** `scripts/validate_datasets.py`: şema, kimlik benzersizliği,
  kümeler arası sızıntı 0, Hugging Face `datasets` ile yükleme ve Qwen chat template'ine uygulanma testi.
- **Yapay zekâ araçlarını nasıl kullandın?** Kod geliştirmede ve kalite kontrol ön incelemesinde yapay zekâ desteği
  aldım; instruction örnekleri Gemini ile üretildi (kartta model ve prompt'larıyla belirtildi). Kararları ve
  kodun ne yaptığını açıklayabiliyorum; her karar `experiments.md`'de gerekçesiyle kayıtlı.
