# Kalite Kontrol Raporu

Bu rapor `scripts/14_qc_report.py` tarafından üretilir.

## A. Otomatik kontroller — Domain Corpus v1.0

| Kontrol | Sonuç |
| --- | --- |
| Doküman sayısı | 16.284 |
| Boş metin | 0 |
| 300 karakterden kısa | 0 |
| Benzersiz document_id | evet |
| Kaynak / URL / lisans eksik | 0 |
| Dil en/tr dışında | 0 |
| Bozuk karakter (U+FFFD) içeren | 1 |
| token_count eksik | 0 |
| Aynı grup birden fazla kümede | 0 |

## A. Otomatik kontroller — Instruction Dataset v1.0

| Kontrol | Sonuç |
| --- | --- |
| Örnek sayısı | 3.412 |
| Benzersiz id | evet |
| messages biçimi hatalı | 0 |
| Kaynak bilgisi eksik | 0 |
| Çoktan seçmeli JSON geçerli | 455/455 |
| Aynı kaynak doküman birden fazla kümede | 0 |
| LLM yargıç örneklemi (örnek) | 348 |
| LLM yargıç başarısızlık oranı (tahmini hata oranı) | %11,5 |

Doğrulama ve kalite kontrolünde elenme nedenleri:

| Neden | Adet |
| --- | --- |
| mcq_answer_in_instruction | 160 |
| response_references_unseen_text | 80 |
| invalid_mcq_json | 69 |
| references_unseen_text | 67 |
| turkish_chars_missing | 64 |
| judge_fail | 40 |
| evidence_not_in_source | 34 |
| length | 8 |
| llm_skipped | 5 |
| wrong_language | 5 |
| latex_artifact | 4 |
| eval_overlap | 4 |
| near_duplicate | 4 |
| duplicate | 3 |
| exponent_loss | 2 |
| task_type_mismatch | 1 |

LLM yargıcın başarısız bulduğu ölçütler: correct=7, fluent_turkish=12, supported=12, follows_instruction=6, instruction_clear=3

## B. Rastgele örneklem incelemesi

İnceleme iki aşamalıdır: (1) yapay zekâ destekli ön inceleme (Claude; örneği üreten Gemini'den farklı bir model), her örneği kaynak metniyle karşılaştırıp ölçüt bazında karar ve gerekçe yazar; (2) grup üyesi ön incelemeyi gözden geçirip nihai kararı verir. İki aşama ayrı raporlanır.

### Domain Corpus

Örneklem: **100** · Claude ön incelemesi yapılan: 100 · grup üyesi nihai kararı verilen: **100**

**Ölçüt bazında sonuçlar (yapay zekâ destekli ön inceleme, Claude):**

| Kontrol | Başarılı | Oran |
| --- | --- | --- |
| okunabilir | 100/100 | %100,0 |
| dogru_domain | 98/100 | %98,0 |
| extraction_dogru | 95/100 | %95,0 |
| header_footer_temiz | 100/100 | %100,0 |
| bozuk_karakter_yok | 100/100 | %100,0 |
| metadata_dogru | 93/100 | %93,0 |
| **Ön incelemede uygun** | 88/100 | **%88,0** |

**Nihai karar (grup üyesi):**

| Sonuç | Adet | Oran |
| --- | --- | --- |
| Uygun | 88 | %88,0 |
| Sorunlu | 12 | %12,0 |

Nihai kararların 100/100'ü grup üyesinin ön inceleme kararlarını onaylamasıyla verilmiştir.

**Hata türleri** (nihai karar, yoksa ön inceleme):

| Hata türü | Adet | Örneklemdeki oranı |
| --- | --- | --- |
| alt_konu_hatali | 7 | %7,0 |
| extraction_eksik | 2 | %2,0 |
| alan_disi | 2 | %2,0 |
| formul_kalintisi | 2 | %2,0 |
| liste_sayfasi | 1 | %1,0 |
| tablo_eksik | 1 | %1,0 |

### Instruction Dataset

Örneklem: **150** · Claude ön incelemesi yapılan: 150 · grup üyesi nihai kararı verilen: **150**

**Ölçüt bazında sonuçlar (yapay zekâ destekli ön inceleme, Claude):**

| Kontrol | Başarılı | Oran |
| --- | --- | --- |
| talimat_anlasilir | 149/150 | %99,3 |
| kaynakla_tutarli | 141/150 | %94,0 |
| talimati_karsiliyor | 142/150 | %94,7 |
| gorev_turu_dogru | 147/150 | %98,0 |
| turkce_akici | 146/150 | %97,3 |
| **Ön incelemede uygun** | 126/150 | **%84,0** |

**Nihai karar (grup üyesi):**

| Sonuç | Adet | Oran |
| --- | --- | --- |
| Uygun | 126 | %84,0 |
| Sorunlu | 24 | %16,0 |

Nihai kararların 150/150'si grup üyesinin ön inceleme kararlarını onaylamasıyla verilmiştir.

**Hata türleri** (nihai karar, yoksa ön inceleme):

| Hata türü | Adet | Örneklemdeki oranı |
| --- | --- | --- |
| dil_hatasi | 4 | %2,7 |
| talimata_uymuyor | 4 | %2,7 |
| kaynakta_olgusal_hata | 4 | %2,7 |
| kaynakta_olmayan_iddia | 3 | %2,0 |
| olgusal_hata | 3 | %2,0 |
| gorev_turu_hatali | 3 | %2,0 |
| alan_disi | 2 | %1,3 |
| talimat_belirsiz | 1 | %0,7 |
| sayisal_hata | 1 | %0,7 |
| yaniltici_cevap | 1 | %0,7 |

Örneklem incelemesinde sorunlu bulunan **24** instruction örneği setten çıkarıldı (kalan: 3388).

### Near-duplicate eşiğinin doğrulanması

50 aday çift (yarısı Jaccard ≥ 0.85, yarısı altı) incelendi. 'Eşik hatalı eledi' = eşik üstü ama gerçekte tekrar değil; 'eşik kaçırdı' = eşik altı ama gerçekte tekrar.

| İnceleme | Çift | Eşikle uyum | Eşik hatalı eledi | Eşik kaçırdı |
| --- | --- | --- | --- | --- |
| yapay zekâ destekli ön inceleme (Claude) | 50 | 32/50 (%64,0) | 0 | 18 |
| nihai karar (grup üyesi onayı) | 50 | 32/50 (%64,0) | 0 | 18 |

