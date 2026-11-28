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

## A. Otomatik kontroller — Instruction Dataset v2.0

Elle incelemede sorunlu bulunan örnekler çıkarıldıktan sonraki final set üzerinde.

| Kontrol | Sonuç |
| --- | --- |
| Örnek sayısı (final) | 3.319 |
| Benzersiz id | evet |
| messages biçimi hatalı | 0 |
| Kaynak bilgisi eksik | 0 |
| Çoktan seçmeli JSON geçerli | 457/457 |
| Aynı kaynak doküman birden fazla kümede | 0 |
| LLM yargıç örneklemi (örnek) | 3.441 |
| LLM yargıç başarısızlık oranı (tahmini hata oranı) | %2,8 |

Doğrulama ve kalite kontrolünde elenme nedenleri (`qc_fail(insan)` = elle incelemede sorunlu):

| Neden | Adet |
| --- | --- |
| judge_fail | 96 |
| eval_overlap | 42 |
| evidence_not_in_source | 40 |
| missing_media_reference | 31 |
| qc_fail(insan) | 26 |
| response_references_unseen_text | 9 |
| latex_artifact | 8 |
| truncated_response | 6 |
| duplicate | 6 |
| references_other_answer | 5 |
| level_audience_mismatch | 5 |
| invalid_mcq_json | 4 |
| references_unseen_text | 4 |
| near_duplicate | 3 |
| wrong_language | 2 |
| too_long_for_training | 1 |
| mcq_count_mismatch | 1 |
| repeated_sentence | 1 |
| **Toplam** | **290** |

LLM yargıcın başarısız bulduğu ölçütler: supported=63, follows_instruction=18, fluent_english=7, correct=8

## B. Rastgele örneklem incelemesi

İnceleme iki aşamalıdır: (1) yapay zekâ destekli ön inceleme (Domain Corpus v2.0 ve near-duplicate çiftlerinde Claude; Instruction Dataset v2.0'da Gemini), her örneği kaynak metniyle karşılaştırıp ölçüt bazında karar ve gerekçe yazar; (2) grup üyesi ön incelemeyi gözden geçirip nihai kararı verir. İki aşama ayrı raporlanır.

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

Örneklem: **150** · Gemini ön incelemesi yapılan: 150 · grup üyesi nihai kararı verilen: **150**

**Ölçüt bazında sonuçlar (yapay zekâ destekli ön inceleme, Gemini):**

| Kontrol | Başarılı | Oran |
| --- | --- | --- |
| talimat_anlasilir | 144/150 | %96,0 |
| kaynakla_tutarli | 142/150 | %94,7 |
| talimati_karsiliyor | 145/150 | %96,7 |
| gorev_turu_dogru | 146/150 | %97,3 |
| ingilizce_akici | 139/150 | %92,7 |
| **Ön incelemede uygun** | 124/150 | **%82,7** |

**Nihai karar (grup üyesi):**

| Sonuç | Adet | Oran |
| --- | --- | --- |
| Uygun | 124 | %82,7 |
| Sorunlu | 26 | %17,3 |

Nihai kararların 150/150'si grup üyesinin ön inceleme kararlarını onaylamasıyla verilmiştir.

**Hata türleri** (nihai karar, yoksa ön inceleme):

| Hata türü | Adet | Örneklemdeki oranı |
| --- | --- | --- |
| bilimsel_hata | 7 | %4,7 |
| dil_akicilik | 5 | %3,3 |
| dis_atif | 5 | %3,3 |
| gorev_turu_uyumsuz | 3 | %2,0 |
| talimat_belirsiz | 2 | %1,3 |
| eksik_cevap | 1 | %0,7 |
| kaynakla_tutarsiz | 1 | %0,7 |
| mcq_hatali | 1 | %0,7 |
| seviye_uyumsuz | 1 | %0,7 |

Örneklem incelemesinde sorunlu bulunan **26** instruction örneği setten çıkarıldı (kalan: 3319).

### Near-duplicate eşiğinin doğrulanması

50 aday çift (yarısı Jaccard ≥ 0,85, yarısı altı) incelendi. 'Eşik hatalı eledi' = eşik üstü ama gerçekte tekrar değil; 'eşik kaçırdı' = eşik altı ama gerçekte tekrar.

| İnceleme | Çift | Eşikle uyum | Eşik hatalı eledi | Eşik kaçırdı |
| --- | --- | --- | --- | --- |
| yapay zekâ destekli ön inceleme (Claude) | 50 | 32/50 (%64,0) | 0 | 18 |
| nihai karar (grup üyesi onayı) | 50 | 32/50 (%64,0) | 0 | 18 |

