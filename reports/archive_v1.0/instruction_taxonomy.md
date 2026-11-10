# Instruction Dataset v1.0 — Görev Türü Taksonomisi

Taksonomi, Tasarım raporundaki hedef davranışlardan türetildi: **seviyeye göre konu anlatımı**, **anlatılan
içerikten dört seçenekli soru üretme (JSON)**, astronomi terminolojisiyle doğru açıklama ve bilmediği/kapsamı
dışındaki konularda sınırını söyleme. Rehber'in önerdiği genel görev türleri (açıklama, karşılaştırma,
sınıflandırma, özetleme, neden-sonuç, adım adım anlatım, bilgi yetersizliği) bu hedeflere uyarlandı.

Hedef oranlar `config.yaml → instruction.taxonomy` içindedir; gerçekleşen dağılım `INSTRUCTION_CARD.md` ve
`reports/instruction_summary.json` dosyalarında raporlanır.

| task_type | Ne yapar | Neden var (AstroTutor hedefi) | Hedef oran |
| --- | --- | --- | --- |
| `tanim_aciklama` | Bir kavramı, gök cismini veya aracı açıklar | Temel bilgi aktarımı, terminoloji | %16 |
| `seviyeli_anlatim` | Talimatta belirtilen seviyede (başlangıç/orta/ileri) yapılandırılmış ders anlatımı | Ana ürün davranışı: seviye duyarlı ders | %15 |
| `coktan_secmeli_soru_uretimi` | Talimattaki öğretim metninden 1–3 adet 4 şıklı soru, **JSON** | Ana ürün davranışı: quiz modülü ve REST şeması | %14 |
| `soru_cevap` | Gerçek kullanıcı sorularına cevap (Stack Exchange'ten Türkçeleştirilmiş) | Gerçek soru dağılımı, doğal soru biçimleri | %12 |
| `karsilastirma` | İki/üç kavram, cisim veya görevi karşılaştırır | Kavramlar arası ilişki (orta seviye) | %10 |
| `neden_sonuc` | Bir olgunun nedenini/sonucunu mekanizmasıyla açıklar | Anlamaya dayalı öğrenme | %10 |
| `ozetleme` | Verilen (İngilizce veya Türkçe) pasajı hedef kitleye göre Türkçe özetler | İngilizce NASA kaynaklarını Türkçe kullanıcıya aktarma (RAG senaryosu) | %8 |
| `adim_adim_problem_cozme` | Basit astronomi hesabı veya bir süreci numaralı adımlarla anlatır | Sayısal okuryazarlık, adım adım anlatım | %7 |
| `siniflandirma` | Verilen öğeleri kategorilere ayırır ve gerekçelendirir | Kavram ayrımı (gezegen/cüce gezegen/uydu vb.) | %4 |
| `bilgi_yetersizligi_kapsam_disi` | Gerçek zamanlı veri, astroloji, fiyat, tıbbi vb. sorularda sınırını bildirir | Uydurma (halüsinasyon) yerine sınır bildirme davranışı | %4 |

**Seviye tanımları** (tüm görev türlerinde `level` alanı):

- `baslangic`: ortaokul/lise; günlük dil, her terim ilk geçtiğinde açıklanır, benzetme kullanılabilir.
- `orta`: genel okur; kavramlar arası ilişki, temel sayısal bilgiler.
- `ileri`: lisans öğrencisi; terminoloji, ölçüm yöntemleri, sayısal ayrıntı; ileri matematiksel türetme yok.

## Biçim örnekleri

Aşağıdaki örnekler prompt tasarımında hedef biçimi tanımlamak için yazıldı ve OpenStax *Astronomy 2e*
bilgileriyle tutarlıdır. **Veri setine dahil edilmemiştir** (veri setindeki her örnek bir kaynak dokümandan
üretilip doğrulanır).

### tanim_aciklama
```json
{"messages":[
 {"role":"user","content":"Işık yılı bir zaman birimi mi?"},
 {"role":"assistant","content":"Hayır, ışık yılı bir uzaklık birimidir. Işığın bir yılda boşlukta kat ettiği mesafeyi ifade eder ve yaklaşık 9,5 trilyon kilometreye karşılık gelir. Yıldızlar arasındaki mesafeler çok büyük olduğu için astronomlar kilometre yerine ışık yılı gibi daha kullanışlı birimler tercih eder."}]}
```
```json
{"messages":[
 {"role":"user","content":"Beyaz cüce nedir, ileri seviyede açıklar mısın?"},
 {"role":"assistant","content":"Beyaz cüce, Güneş benzeri bir yıldızın nükleer yakıtını tükettikten ve dış katmanlarını kaybettikten sonra geriye kalan sıcak, yoğun çekirdektir. Kütlesi Güneş'inkiyle kıyaslanabilir olduğu hâlde boyutu Dünya'ya yakındır; bu yüzden yoğunluğu son derece yüksektir. İçinde artık füzyon gerçekleşmez; kütleçekimsel çöküşe karşı denge, sıkışmış elektronların oluşturduğu dejenere elektron basıncıyla sağlanır. Bu dengenin sürebileceği üst kütle sınırı Chandrasekhar limiti olarak bilinir ve yaklaşık 1,4 Güneş kütlesidir."}]}
```

### seviyeli_anlatim
```json
{"messages":[
 {"role":"user","content":"Başlangıç seviyesindeki bir öğrenciye mevsimlerin neden oluştuğunu anlatan kısa bir ders hazırlar mısın?"},
 {"role":"assistant","content":"**Mevsimler Neden Oluşur?**\n\nBirçok kişi yazın Dünya'nın Güneş'e daha yakın olduğunu düşünür, ama asıl neden bu değildir.\n\n- **Eksen eğikliği:** Dünya'nın dönme ekseni yaklaşık 23,5 derece eğiktir.\n- **Işığın geliş açısı:** Yıl boyunca bir yarımküre Güneş'e doğru eğik durur. O yarımkürede Güneş gökyüzünde daha yükseğe çıkar, ışınlar yere daha dik gelir ve günler uzar. Bu da yaz demektir.\n- **Diğer yarımküre:** Aynı anda diğer yarımkürede ışınlar daha eğik gelir ve günler kısalır; orada kış yaşanır.\n\nKısacası mevsimleri Güneş'e olan uzaklık değil, Dünya'nın eğik ekseni belirler."}]}
```

### coktan_secmeli_soru_uretimi
```json
{"messages":[
 {"role":"user","content":"Aşağıdaki öğretim metninden 1 adet dört seçenekli soru üret ve sonucu JSON olarak ver.\n\nMetin: Jüpiter, Güneş Sistemi'nin en büyük gezegenidir ve büyük ölçüde hidrojen ile helyumdan oluşur. Bu nedenle bir gaz devi olarak sınıflandırılır. Gezegenin atmosferindeki Büyük Kırmızı Leke, yüzyıllardır gözlenen dev bir fırtınadır."},
 {"role":"assistant","content":"{\"sorular\": [{\"soru\": \"Jüpiter'in gaz devi olarak sınıflandırılmasının nedeni nedir?\", \"secenekler\": {\"A\": \"Yüzeyinin kayalardan oluşması\", \"B\": \"Büyük ölçüde hidrojen ve helyumdan oluşması\", \"C\": \"Güneş'e en yakın gezegen olması\", \"D\": \"Hiç uydusunun bulunmaması\"}, \"dogru_cevap\": \"B\", \"aciklama\": \"Metne göre Jüpiter büyük ölçüde hidrojen ve helyumdan oluştuğu için gaz devi sayılır.\"}]}"}]}
```

### karsilastirma
```json
{"messages":[
 {"role":"user","content":"Kuyruklu yıldızlarla asteroitler arasındaki temel fark ne?"},
 {"role":"assistant","content":"İkisi de Güneş Sistemi'nin oluşumundan kalan küçük cisimlerdir, ancak yapıları farklıdır:\n\n- **Asteroitler** kayalık veya metaliktir ve kolayca buharlaşan (uçucu) madde içermez.\n- **Kuyruklu yıldızlar** donmuş su ve diğer uçucu maddeleri içeren buzlu cisimlerdir; Güneş'e yaklaştıklarında buzları buharlaşır ve kuyruk oluşur."}]}
```

### neden_sonuc
```json
{"messages":[
 {"role":"user","content":"500 ışık yılı uzaklıktaki bir yıldıza baktığımızda neden onun geçmişini görüyoruz?"},
 {"role":"assistant","content":"Çünkü ışığın hızı sonludur. Yıldızdan çıkan ışık bize ulaşana kadar 500 yıl yol alır. Bu gece gözümüze ulaşan ışık yıldızdan 500 yıl önce ayrılmıştır; yani yıldızı bugünkü hâliyle değil, 500 yıl önceki hâliyle görürüz. Bu durum astronomlar için bir avantajdır: çok uzaktaki cisimleri gözleyerek evrenin geçmiş dönemlerine dair kanıt toplayabilirler."}]}
```

### ozetleme
```json
{"messages":[
 {"role":"user","content":"Aşağıdaki İngilizce metni lise öğrencilerine yönelik 2-3 cümleyle Türkçe özetle:\n\nAsteroids are rocky or metallic and contain little volatile material. Comets are small icy objects that contain frozen water and other volatile materials but with solid grains mixed in."},
 {"role":"assistant","content":"Asteroitler kayalık ya da metalik yapıda küçük cisimlerdir ve kolay buharlaşan madde neredeyse içermez. Kuyruklu yıldızlar ise içinde katı tanecikler bulunan, donmuş su ve başka uçucu maddelerden oluşan küçük buzlu cisimlerdir."}]}
```

### adim_adim_problem_cozme
```json
{"messages":[
 {"role":"user","content":"Işık saniyede yaklaşık 300.000 km yol alıyorsa, Güneş ışığının yaklaşık 150 milyon km uzaklıktaki Dünya'ya ulaşması ne kadar sürer? Adım adım hesaplar mısın?"},
 {"role":"assistant","content":"1. Süre = uzaklık / hız formülünü kullanırız.\n2. Uzaklık = 150.000.000 km, hız = 300.000 km/s.\n3. 150.000.000 / 300.000 = 500 saniye.\n4. 500 saniye = 8 dakika 20 saniye.\n\nSonuç: Güneş ışığı Dünya'ya yaklaşık 8 dakika 20 saniyede ulaşır."}]}
```

### siniflandirma
```json
{"messages":[
 {"role":"user","content":"Şunları gezegen, cüce gezegen ve uydu olarak sınıflandırır mısın: Mars, Plüton, Titan, Neptün, Ceres, Ay."},
 {"role":"assistant","content":"- **Gezegen:** Mars, Neptün\n- **Cüce gezegen:** Plüton, Ceres\n- **Uydu:** Titan (Satürn'ün uydusu), Ay (Dünya'nın uydusu)\n\nGezegenler Güneş'in etrafında dolanır ve yörüngelerini temizlemiş büyük cisimlerdir; cüce gezegenler de Güneş'in etrafında dolanır ancak yörüngelerini temizleyememiştir; uydular ise bir gezegenin etrafında dolanır."}]}
```

### bilgi_yetersizligi_kapsam_disi
```json
{"messages":[
 {"role":"user","content":"Satürn'ün bu ayki konumu burcumu nasıl etkiler?"},
 {"role":"assistant","content":"Bu konuda yardımcı olamam; burç yorumları astrolojiye dayanır ve bilimsel bir yöntem değildir. Astronomi ise gök cisimlerinin konumunu, hareketini ve fiziksel özelliklerini gözlem ve ölçümle inceler. İstersen Satürn'ün halkalarını, uydularını ya da gökyüzünde nasıl gözlemlenebileceğini birlikte inceleyebiliriz."}]}
```
```json
{"messages":[
 {"role":"user","content":"Uluslararası Uzay İstasyonu şu an tam olarak nerede?"},
 {"role":"assistant","content":"Gerçek zamanlı verilere erişimim olmadığı için istasyonun şu anki konumunu söyleyemem. Genel bilgi olarak, istasyon Dünya'nın etrafını yaklaşık 90 dakikada bir dolanır; bu yüzden konumu sürekli değişir. Anlık konum için resmî uzay ajanslarının güncel takip sayfalarına bakabilirsin."}]}
```
