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

Çıktı kalitesi eşit, PyMuPDF ~70 kat hızlı. **Karar: PyMuPDF.** Ayrıntı: `reports/extraction_tool_comparison.md`.
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
