# Kalite Kontrol Raporu

Bu rapor `scripts/14_qc_report.py` tarafından üretilir.

## A. Otomatik kontroller — Domain Corpus v2.0

| Kontrol | Sonuç |
| --- | --- |
| Doküman sayısı | 14.683 |
| Boş metin | 0 |
| 300 karakterden kısa | 0 |
| Benzersiz document_id | evet |
| Kaynak / URL / lisans eksik | 0 |
| Dil en dışında | 0 |
| Bozuk karakter (U+FFFD) içeren | 1 |
| token_count eksik | 0 |
| Aynı grup birden fazla kümede | 0 |

## B. Rastgele örneklem incelemesi

İnceleme iki aşamalıdır: (1) yapay zekâ destekli ön inceleme (Claude; örneği üreten Gemini'den farklı bir model), her örneği kaynak metniyle karşılaştırıp ölçüt bazında karar ve gerekçe yazar; (2) grup üyesi ön incelemeyi gözden geçirip nihai kararı verir. İki aşama ayrı raporlanır.

### Domain Corpus v2.0

Örneklem: **100** · Claude ön incelemesi yapılan: 100 · grup üyesi nihai kararı verilen: **100**

**Ölçüt bazında sonuçlar (yapay zekâ destekli ön inceleme, Claude):**

| Kontrol | Başarılı | Oran |
| --- | --- | --- |
| okunabilir | 100/100 | %100,0 |
| dogru_domain | 98/100 | %98,0 |
| extraction_dogru | 95/100 | %95,0 |
| header_footer_temiz | 100/100 | %100,0 |
| bozuk_karakter_yok | 100/100 | %100,0 |
| metadata_dogru | 94/100 | %94,0 |
| **Ön incelemede uygun** | 89/100 | **%89,0** |

**Nihai karar (grup üyesi):**

| Sonuç | Adet | Oran |
| --- | --- | --- |
| Uygun | 89 | %89,0 |
| Sorunlu | 11 | %11,0 |

Nihai kararların 100/100'ü grup üyesinin ön inceleme kararlarını onaylamasıyla verilmiştir.

**Hata türleri** (nihai karar, yoksa ön inceleme):

| Hata türü | Adet | Örneklemdeki oranı |
| --- | --- | --- |
| alt_konu_hatali | 6 | %6,0 |
| extraction_eksik | 2 | %2,0 |
| alan_disi | 2 | %2,0 |
| formul_kalintisi | 2 | %2,0 |
| us_kaybi | 1 | %1,0 |

### Instruction Dataset v2.0

*Henüz üretilmedi (`instruction_v2.0.jsonl` yok); inceleme set üretildikten sonra yapılacak.*

### Near-duplicate eşiğinin doğrulanması

50 aday çift (yarısı Jaccard ≥ 0,85, yarısı altı) incelendi. 'Eşik hatalı eledi' = eşik üstü ama gerçekte tekrar değil; 'eşik kaçırdı' = eşik altı ama gerçekte tekrar.

| İnceleme | Çift | Eşikle uyum | Eşik hatalı eledi | Eşik kaçırdı |
| --- | --- | --- | --- | --- |
| yapay zekâ destekli ön inceleme (Claude) | 50 | 32/50 (%64,0) | 0 | 18 |
| nihai karar (grup üyesi onayı) | 50 | 32/50 (%64,0) | 0 | 18 |

