# Temizleme Kuralları

Bu dosya `scripts/03_clean.py` tarafından üretilir. Kurallar bilgiyi koruyacak şekilde dar tutuldu: **sayılar, birimler, formüller, LaTeX ve 'CO2', 'Alternaria solani' türü terimler silinmez** (Vize Rehberi §7: `re.sub(r'\d+', '', text)` gibi kaba kurallar kullanılmadı).

| Kural | Ne yapar | Neden | Uygulama sayısı |
| --- | --- | --- | --- |
| Üs koruma (NFKC öncesi) | 10²³ -> 10^23, s⁻¹ -> s^-1 | NFKC üst simgeleri düz rakama çevirir (10²³ -> 1023) ve sayının anlamı bozulur | 261 |
| Unicode NFKC | Karakter varyantlarını tek biçime çeker (ﬁ -> fi, tam genişlikli karakterler) | Aynı kelime farklı kodlamalarla yazılmış olabilir; PDF bağlaçları (ligature) çözülür | tüm metin |
| Görünmez/kontrol karakterleri | Yumuşak tire, sıfır genişlikli boşluk, BOM, kontrol karakterleri silinir | Tokenizer'da gereksiz token üretir, görünmez olduğu için fark edilmez | tüm metin |
| PDF tekrarlayan satır | Rakamlar normalize edildiğinde 5+ sayfada tekrar eden ve header/footer biçimindeki satırları siler | Sayfa başlığı/altbilgi ('Access for free at openstax.org') | 1,388 |
| PDF bölüm başlığı satırı | '78 3 • Orbits and Gravity' biçimli satırlar | Tek sayfalardaki bölüm başlıkları 5 sayfa eşiğinin altında kalıyordu | 345 |
| PDF kutu etiketleri | 'LINK TO LEARNING', 'Learning Objectives' gibi etiket satırları | Bilgi taşımayan düzen etiketi | 436 |
| Link to Learning paragrafları | openstax.org/l/ kısa bağlantısı içeren paragraflar | Dış video/animasyon yönlendirmesi; alan bilgisi değil | 175 |
| Görsel kredisi | '(credit: ...)' parantezleri | Görsel sahibi bilgisi; metin bilgisi değil (görseller zaten alınmadı) | 416 |
| Satır sonu tirelemesi | 'distri-\nbution' -> 'distribution' (yalnız küçük harfle devam ederse) | PDF satır kaydırması kelimeyi böler; 'X-ray' gibi gerçek tireler korunur | 123 |
| Sayfa sonu paragraf birleştirme | Cümle sonu olmadan biten paragraf + küçük harfle başlayan devamı birleştirilir | Sayfa sınırı paragrafı ikiye bölüyordu | 756 |
| Alt başlık işaretleme | Kısa, noktalama ile bitmeyen satırlar '## ' başlığı olur | Başlık sonraki paragrafa yapışıyordu; başlıklar chunk sınırı olarak da kullanılır | 1,643 |
| Wikipedia kaynakça bölümleri | References, See also, External links, Kaynakça, Dış bağlantılar... bölümleri atılır | Kaynak listesi ve bağlantılar alan metni değil | 14,217 |
| Kaynakça girdisi satırı | 'Soyadı, A. B. (yıl). Başlık. Dergi, cilt, doi' biçimiyle BAŞLAYAN satırlar (NASA Science ve Wikipedia) | Yayın listesi alan metni değil; düzyazıdaki metin içi atıflar ('(Bechtol et al., 2015)') korunur | 5,522 |
| Boş başlık | Altında içerik kalmayan başlıklar silinir | Bölüm atımından sonra kalan artık | 801 |
| Site menüsü / şablon satırı | Kaynağın %2'sinden (en az 5) fazla dokümanında tekrar eden 100 karakterden kısa satırlar | 'Share', 'Keep Exploring', 'Discover More Topics From NASA' gibi menüler | 2,260 |
| Tekrarlanan bilgi paragrafı | Çok dokümanda geçen 100+ karakterlik paragraf yalnız ilk geçtiği dokümanda tutulur | Bilgi korunur ama aynı paragraf corpus'ta defalarca yer almaz | 627 |
| Kesik tanıtım cümlesi | '…' veya '...' ile biten satırlar | Hub sayfalarındaki yarım cümleler; bilgi taşımaz | 892 |
| HTML alt başlık koruma | Kısa başlık satırı, ardından uzun paragraf geliyorsa '## ' ile korunur | Kısa satır kuralının başlıkları silmesini önler | 7,421 |
| APOD kredi/altbilgi | 'Image Credit', 'Copyright', 'Tomorrow's picture' satırları | Kişi adı içeren kredi satırı ve site altbilgisi | 50 |
| Kısa yalnız satır | 20 karakterden kısa, rakam içermeyen, başlık olmayan satırlar (NASA sözlük sayfaları hariç) | Menü ve sayfa numarası kalıntıları; rakamlı bilgi satırları (ör. '5,97 × 10^24 kg') korunur | 179,452 |
| Sözlük terimleri korunur | NASA sözlük sayfalarında kısa satır kuralı uygulanmaz (sayfa sayısı) | Sözlükte kısa satırlar terimdir ('biomass', 'bow shock'); ilk sürüm terimleri silip yalnız tanımları bırakıyordu | 26 |
| Sözlük harf dizini | 'A | B | C | ...' satırları | Navigasyon; bilgi taşımaz | 20 |
| Whitespace normalizasyonu | Ardışık boşluklar teke, 3+ boş satır ikiye indirilir | PDF sütun hizalaması bozuk boşluk üretir | tüm metin |

## Kaynak bazında etki

| Kaynak | Doküman | Karakter (önce) | Karakter (sonra) | Silinen oran |
| --- | --- | --- | --- | --- |
| nasa_science | 3,068 | 13,834,165 | 12,350,811 | %10.7 |
| nasa_apod | 2,717 | 2,498,790 | 2,359,168 | %5.6 |
| openstax | 242 | 2,505,866 | 2,346,107 | %6.4 |
| arxiv_astro_ph | 6,000 | 9,176,505 | 9,176,505 | %0.0 |
| wikipedia_en | 3,575 | 49,168,159 | 40,347,366 | %17.9 |
| wikipedia_tr | 1,732 | 10,367,405 | 8,832,932 | %14.8 |

Öncesi/sonrası örnekleri: [cleaning_examples.md](cleaning_examples.md)
