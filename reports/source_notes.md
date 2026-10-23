# AstroTutor AI — Veri Kaynağı Notları (lisans, etik, neden seçildi)

Her kaynak için: kullanım amacı, lisans/kullanım koşulu, neden seçildiği ve dikkat edilen noktalar.
Doküman sayıları ve erişim tarihleri `reports/source_inventory.csv` dosyasındadır.

## NASA Science (science.nasa.gov) — Domain Corpus, birincil kaynak
- **Amaç:** Güneş Sistemi, gezegen/uydu, yıldız, gökada, kozmoloji, ötegezegen ve görev sayfalarından güvenilir, öğretici İngilizce metin.
- **Lisans:** NASA içerikleri genel olarak telif kısıtlamasına tabi değildir (NASA Images and Media Usage Guidelines); NASA kaynak olarak belirtilir, NASA'nın onayı ima edilmez. Üçüncü taraf görselleri alınmadı (yalnız metin).
- **Toplama:** `robots.txt` tüm yollara izin veriyor (Crawl-delay: 1); istekler arası 1,2 sn beklendi. URL'ler WordPress sitemap'inden alındı; kapsam dışı bölümler (Dünya bilimi, araştırmacı duyuruları, fotoğraf arşivi, etkinlik, kariyer vb.) URL kurallarıyla dışlandı (`config.yaml → sources.nasa_science`). Tek bir görevin (ör. Hubble, Cassini) corpus'u domine etmemesi için görev başına en fazla 150 sayfa alındı.
- **Elle seçilmiş tohum sayfalar:** `reports/nasa_seed_urls.csv` (her zaman dahil).

## NASA APOD (Astronomy Picture of the Day) — Domain Corpus
- **Amaç:** Profesyonel astronomların yazdığı kısa, popüler bilim düzeyinde açıklamalar (başlangıç/orta seviye dil).
- **Not:** `api.nasa.gov/planetary/apod` servisi 22.10.2026'da tarih aralığı sorgularında HTTP 500 ve tekil sorgularda yer tutucu metin döndürdü; APOD arşivi science.nasa.gov altına (`/image-article/apod-YYYY-...`) taşınmış. Bu nedenle APOD açıklamaları science.nasa.gov sayfalarından alındı (bkz. experiments.md).
- **Örnekleme:** 1995–2026 arası her yıldan 85 sayfa (seed 42) → zamansal çeşitlilik.
- **Lisans:** Açıklama metni NASA hizmeti olarak yayımlanır; görsellerin telifleri farklı sahiplerdedir ve görseller alınmadı. Görsel kredi satırları temizlemede çıkarıldı.

## OpenStax Astronomy 2e — Domain Corpus (PDF)
- **Amaç:** Hakemli, eğitim amaçlı yazılmış tam bir astronomi ders kitabı; kavramsal bütünlüğü en yüksek kaynak. Ayrıca PDF extraction adımını gerçek veriyle göstermek.
- **Lisans:** **CC BY-NC-SA 4.0** (OpenStax API'sinden doğrulandı; 1. baskı CC BY 4.0 idi). Akademik ve ticari olmayan kullanım için uygun; türevler aynı lisansla paylaşılmalı. Atıf: "Fraknoi, Morrison, Wolff — Astronomy 2e, OpenStax, 2022".
- **Doküman tanımı:** PDF içindekilerinin 2. seviyesi (ör. "3.3 Newton's Universal Law of Gravitation") = 1 doküman. Alıştırma, kaynakça, grup etkinliği, ekler ve dizin içerik dışı sayıldı.

## arXiv astro-ph özetleri — Domain Corpus (ileri seviye)
- **Amaç:** Güncel araştırma terminolojisi; ileri seviye anlatım ve kavramlar.
- **Lisans:** arXiv metadata'sı (başlık, özet) CC0 1.0 ile yayımlanır. Makalelerin tam metni alınmadı. Yazar adları kişisel veri en aza indirilsin diye saklanmadı.
- **Toplama:** OAI-PMH, `physics:astro-ph` seti, 2025-10-01 sonrası güncellenenler; yalnızca **birincil kategorisi** astro-ph olanlar (çapraz listelenenler alınmadı). İstekler arası 4 sn.
- **Neden sınırlı pay:** Özetler kısa ve araştırma diline sahip; corpus'u hedef kullanıcı seviyesinden uzaklaştırmaması için 6.000 kayıtla sınırlandı.

## Wikipedia (İngilizce) — Domain Corpus, ikincil kaynak
- **Amaç:** Birincil kaynakların kapsamadığı temel ve görece durağan ansiklopedik bilgi.
- **Lisans:** CC BY-SA 4.0; madde URL'si ve revizyon kimliği (`revid`) saklanır.
- **Seçim:** 30 astronomi kategorisi ve doğrudan alt kategorileri; liste/zaman çizelgesi maddeleri ve 6.000 bayttan kısa taslaklar dışarıda; kategori başına en uzun 140 madde.
- **Not:** Güncel sayısal veriler için Wikipedia değil NASA/IPAC birincil kaynakları tercih edilecek (Tasarım raporu).

## Wikipedia (Türkçe) — Domain Corpus, Türkçe terminoloji
- **Amaç:** Modelin Türkçe astronomi terimlerini (gökada, ötegezegen, kırmızıya kayma...) görmesi; Türkçe kullanıcıya hizmet edecek modelin Türkçe alan dilini kazanması.
- **Lisans:** CC BY-SA 4.0.
- **Neden payı küçük:** Türkçe astronomi maddeleri sayıca ve uzunlukça sınırlı; corpus'un çoğunluğunun İngilizce olması bilinçli bir tercih (dil dağılımı kartta raporlanır). Aynı maddenin EN ve TR sürümleri Wikidata kimliği ile eşleştirilip aynı split'e konur.

## Stack Exchange Space/Astronomy (juliensimon/stackexchange-space-qa) — Instruction Dataset kaynağı
- **Amaç:** Gerçek kullanıcı soruları ve uzman cevapları → `soru_cevap` görev türü (Türkçeleştirilerek).
- **Lisans:** CC BY-SA 4.0 (veri kartı); orijinal gönderilerin URL'si her örnekte `source_url` alanında saklanır. Kullanıcı adları alınmadı.
- **Neden corpus'a girmedi:** Instruction verisiyle aynı metnin CPT corpus'unda da bulunması gereksiz tekrar olurdu; ayrıca forum dili ansiklopedik metinden farklı ve kapsam dışı (roket mühendisliği, şirket, yazılım) içerik oranı yüksek.
- **Fark edilen sorun:** Veri kümesinde üslü sayılar kaybolmuş ("1.989 × 1030 kg" = 1.989 × 10^30 kg). 09 numaralı script bu kalıbı düzeltir.

## NASA Exoplanet Archive — final dönemi RAG kaynağı (corpus'a girmedi)
- Yapılandırılmış ve sürekli güncellenen tablo verisi (ps, pscomppars, toi). Tasarım raporuna göre bu tür güncel sayısal bilgiler model ağırlıklarına ezberletilmeyecek, RAG katmanında tutulacak. Kullanımda Archive'a ve ilgili yayınlara atıf yapılacak.

## Değerlendirme setleri — eğitime GİRMEZ
- patrickfleith/Astro-mcqa (CC BY 4.0), patrickfleith/astro-mcq (CC BY 4.0), patrickfleith/HubbleSpaceTelescope-MCQ, AstroMLab/Astrobench_MCQ_v1_Public.
- Yalnızca `data/eval_reference/` altına indirilir ve instruction verisiyle 8-gram örtüşmesi olan örneklerin elenmesi için kullanılır.
