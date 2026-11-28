# AstroTutor AI İngilizce Instruction Dataset v2.0

## Amaç
Bu veri seti, yalnız İngilizce [Domain Corpus v2.0](DATASET_CARD.md) ile alana uyarlanacak **İngilizce konuşan** modele (AstroTutor AI; SFT uzunluk/şablon kontrolü: `Qwen/Qwen3-1.7B`) **supervised fine-tuning (SFT)** ile şu davranışları kazandırmak için hazırlanmıştır: kullanıcının seviyesine (`beginner` / `intermediate` / `advanced`) göre İngilizce konu anlatımı, verilen öğretim pasajından JSON biçiminde dört seçenekli soru üretme, astronomi terminolojisiyle doğru açıklama, kapsam dışı sorularda sınırını bildirme ve yanlış öncüllü astronomi sorularında öncülü nazikçe düzeltme.

Vizede teslim edilen Türkçe sürüm (`v1.0`, 3.388 örnek) Git etiketi `v1.0` ve [reports/archive_v1.0/INSTRUCTION_CARD_v1.0.md](reports/archive_v1.0/INSTRUCTION_CARD_v1.0.md) altında arşivlenmiştir; 09.11.2026 kararıyla model dili tamamen İngilizceye geçirilmiştir.

## Format
JSONL; her satır bir örnektir. SFT için `messages` alanı kullanılır (`user` / `assistant`; sistem mesajı Final SFT aşamasında eklenir). İzlenebilirlik alanları: `id`, `source_document` (corpus `document_id`'si veya Stack Exchange soru kimliği), `source_url`, `source_name`, `task_type`, `level`, `level_source` (`generation_plan` veya `llm_judge`), `supporting_evidence` (cevabı destekleyen kaynak alıntısı), `generation_method`, `generator_model`, `prompt_version`, `auto_verified`, `llm_judged`, `judge_model`, `human_verified`, `verified_by`, `license`, `split`, `raw_example_id`, `postprocess` (kural tabanlı metin düzeltmesi, ör. `unseen_reference_removed`; yoksa `null`).

Dosyalar: `data/final/instruction_v2.0.jsonl` (tamamı) ve `data/final/instruction/{train,validation,test}.jsonl`.

## Görev türü dağılımı

| Görev türü | Örnek | Oran | Hedef oran |
| --- | --- | --- | --- |
| Tanım ve açıklama (`definition_explanation`) | 530 | %16,0 | %16 |
| Seviyeye göre ders anlatımı (`leveled_explanation`) | 488 | %14,7 | %15 |
| Çoktan seçmeli soru üretimi (JSON) (`mcq_generation`) | 457 | %13,8 | %14 |
| Soru-cevap (Stack Exchange, orijinal İngilizce) (`question_answering`) | 387 | %11,7 | %12 |
| Karşılaştırma (`comparison`) | 324 | %9,8 | %10 |
| Neden-sonuç (`cause_effect`) | 340 | %10,2 | %10 |
| Özetleme (`summarization`) | 276 | %8,3 | %8 |
| Adım adım problem çözme (`step_by_step_problem_solving`) | 219 | %6,6 | %7 |
| Sınıflandırma (`classification`) | 120 | %3,6 | %4 |
| Kapsam dışı / bilgi yetersizliği ve yanlış öncül düzeltme (`out_of_scope_refusal`) | 178 | %5,4 | %4 |
| **Toplam** | **3.319** | %100 | |

Görev tanımları: [prompts/v2.0/task_types.json](prompts/v2.0/task_types.json).

Seviye dağılımı: orta (`intermediate`) 1.162 (%35,0), başlangıç (`beginner`) 1.091 (%32,9), ileri (`advanced`) 1.066 (%32,1).

## Örneklerin üretimi
- **Kaynaklar:** İngilizce Domain Corpus v2.0'dan 261 doküman (2.754 örnek: NASA Science, Wikipedia EN, OpenStax Astronomy 2e, arXiv astro-ph), Stack Exchange Space/Astronomy soru-cevapları (387 örnek; 502 seçilmiş soru) ve kaynak dokümansız kapsam dışı / yanlış öncül örnekleri (178).
- **Yöntem:** Üç kaynak türü ayrı ele alındı: (1) Corpus dokümanlarından LLM destekli sentetik İngilizce üretim — model yalnız kaynaktaki bilgiyi kullanır ve `supporting_evidence` alıntısını kaynaktan birebir kopyalar; (2) Stack Exchange örneklerinde **Gemini kullanılmaz**, orijinal İngilizce soru + en yüksek puanlı cevap metni değiştirilmeden alınır (LaTeX, URL, `@kullanıcı`, görsele bağımlı, forum/insan sesi içeren kayıtlar 09'da elenir; seviye 11'de yargıç tarafından atanır); (3) kapsam dışı işlerinde her 15 örneğin 5'i [prompts/v2.0/misconceptions.json](prompts/v2.0/misconceptions.json) listesindeki 60 astronomi yanlış kanısından (tekrarsız) üretilir.
- **Model:** Google Gemini API (ücretsiz katman; **yalnız Flash modelleri**, lite kapalı). Her örnekte gerçekte kullanılan model kaydedilmiştir: gemini-3.6-flash (1.648), gemini-3.5-flash (523), gemini-3.7-flash (427), Stack Exchange (orijinal, Gemini yok) (387), gemini-3.8-flash (334).
- **Parametreler:** sıcaklık 0,7, düşünme seviyesi `low`, en fazla 16.384 çıktı token'ı. Prompt sürümleri: `none (Stack Exchange)` (387), `v2.0` (2.932) ([prompts/v2.0/](prompts/v2.0/): `system_generate.txt`, `generate_doc.txt`, `generate_refusal.txt`, `task_types.json`, `misconceptions.json`, `judge.txt`, `judge_batch.txt`).
- Üretim yöntemlerine göre: `llm_synthetic_from_source_document` 2.754, `stackexchange_original_verbatim` 387, `llm_synthetic_out_of_scope` 178.

## Doğrulama
Toplam **3.609** ham örnek üretildi; doğrulama ve kalite kontrolünden sonra **3.319** örnek kaldı. Üretim sırasında çoktan seçmeli talimatında soru/şık/cevap sızıntısı yapan işler hemen reddedilip yeniden üretildi. Dört aşamalı kontrol uygulandı:

1. **Kural kontrolleri** (tüm örnekler): İngilizce dil tespiti (`lingua`), karakter uzunluğu, Final SFT token sınırı (`too_long_for_training`: `Qwen/Qwen3-1.7B` chat template, düşünme kapalı, sistem mesajı dahil ≤ 976 token; SFT 1.024 token sınırı için 48 token pay), görev türü ve hedef kitle–seviye tutarlılığı (`level_audience_mismatch`), çoktan seçmeli JSON şeması, soru sayısı ve talimatta sızıntı kontrolü, kaybolmuş üs (`exponent_loss`), URL, kişisel iletişim bilgisi (`contains_pii`), LaTeX artığı, bozuk kodlama, yer tutucu, eksik görsel atfı (`missing_media_reference`), başka cevaba atıf (`references_other_answer`, SE), yarım kalan cevap (`truncated_response`), yapay zekâ sorumluluk reddi, tekrar eden cümle, dengesiz markdown, kaynağı görmeyen kullanıcıya talimatta/cevapta metin atfı, kapsam dışı kaynak dokümanları (`out_of_scope_source`), birebir/yakın tekrar (MinHash, Jaccard ≥ 0,8) ve değerlendirme setleriyle 8-gram örtüşmesi (`eval_overlap`). Öğeleri talimatta sayılmış 7 sınıflandırma talimatındaki görünmeyen metin atfı temizlendi (örnek elenmedi; `postprocess` alanında işaretli).
2. **Kanıt kontrolü** (kaynak dokümanlı Gemini örnekleri): `supporting_evidence` alıntısının kelime 5-gram'larının en az %60'ı kaynak metinde bulunmalıdır (Stack Exchange ve kapsam dışı örneklerde kaynak doküman yok).
3. **Tam kapsamlı karma LLM yargıç** (`config: instruction.judge`; 3.441 örnek): örneği üreten modelden **farklı** bir Gemini Flash modeli, sıcaklık 0 ve `medium` düşünme bütçesiyle her örneği kaynağıyla birlikte beş ölçütte (`supported`, `correct`, `follows_instruction`, `instruction_clear`, `fluent_english`) değerlendirdi. Erken durdurma kapalıdır (`full_check_fail_rate: 0.0`): aşama 1 (%20 tabakalı örneklem) istatistikleri raporlandıktan sonra tüm grupların tamamı yargıçtan geçer. Doküman ve kapsam dışı işleri en fazla 3 iş/çağrı (aynı iş türü ve aynı üretici model; 504 süre aşımında tek tek düşüş), Stack Exchange işlerinin tamamı ise **tek tek** (`jobs_per_call_by_kind: {SE: 1}`) yargılanıp `beginner` / `intermediate` / `advanced` seviyesi yargıç tarafından atandı. Başarısız oranı: **%2,8**; başarısızlar elendi. Yargıçtan geçip final sette kalan 3.319 örneğin yargıç modelleri: gemini-3.5-flash (1.958), gemini-3.6-flash (1.137), gemini-3.8-flash (195), gemini-3.7-flash (29).
4. **Rastgele örneklem incelemesi:** 150 örnek (görev türü oranında tabakalı) kaynak metniyle karşılaştırılarak incelendi. Yapay zekâ destekli ön inceleme (Gemini) ölçüt bazında yapıldı; nihai kararı grup üyesi verdi. Ön incelemede uygun: %82,7; nihai kararda uygun: %82,7. Sorunlu bulunan 26 örnek setten çıkarıldı.

**Elenen örnekler** (nedenleriyle: [reports/removed_instructions.csv](reports/removed_instructions.csv)):

| Neden | Adet |
| --- | --- |
| judge_fail | 96 |
| eval_overlap | 42 |
| evidence_not_in_source | 40 |
| missing_media_reference | 31 |
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
| örneklem incelemesinde sorunlu | 26 |

## Veri ayrımı ve sızıntı önleme
train 3.011 · validation 175 · test 133.

- Corpus dokümanından üretilen örnekler, kaynak dokümanın **corpus'taki kümesini** miras alır. Böylece aynı dokümandan gelen örnekler farklı kümelere dağılmaz ve corpus test dokümanından üretilen bir örnek SFT eğitimine girmez (CPT ile SFT arasında da sızıntı yok).
- Stack Exchange örnekleri soru kimliğine, kapsam dışı örnekler kendi kimliğine göre gruplanır; her grubun kümesi seed 42 ve grup kimliğinin hash'inden belirlenir (bir grubun elenmesi diğerlerinin kümesini değiştirmez).
- Değerlendirme setleri (Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ, AstroMLab Astrobench) eğitime alınmadı; bunlarla 8-gram örtüşmesi olan tüm örnekler elendi (`eval_overlap = 0`).

## Değerlendirme planı (final dönemi)
Final aşamasında İngilizce model (`Qwen/Qwen3-1.7B` ailesi; nihai model seçimi Final deney günlüğünde kesinleştirilir) şu eksenlerde değerlendirilecek:
- **Dış alan değerlendirme setleri** (eğitime girmedi): AstroMLab Astrobench, Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ — çoktan seçmeli doğruluk. Corpus ile örtüşen sorular [reports/eval_contamination.csv](reports/eval_contamination.csv) dosyasında ayrıca raporlanır.
- **Genel yetenek korunumu (İngilizce):** İngilizce MMLU (`lm-eval mmlu`) ve İngilizce Wikipedia perplexity + %10 İngilizce replay.
- **Bu setin test kümesi** (133 örnek) + elle yazılmış ≥ 50 soru (görev türü başına en az 15): İngilizce talimat takibi, seviyeye uygunluk, yanlış öncül düzeltme ve JSON çoktan seçmeli soru üretimi.
- Karşılaştırma: temel model, CPT modeli, CPT + SFT (QLoRA) ve isteğe bağlı RAG katmanı.

## Sınırlılıklar
Doküman ve kapsam dışı örnekler sentetiktir ve kaynak dokümanlardaki bilgiyle sınırlıdır; güncel astronomik veriler (ör. ötegezegen sayısı) için birincil kaynakların yerine geçmez (Final'de RAG ile desteklenecektir). Tüm örnekler tek turlu (`user` → `assistant`) İngilizce diyaloglardır ve SFT 1.024 token sınırına uyacak biçimde filtrelenmiştir.

## Sürüm geçmişi
- v1.0 (24–26.10.2026): Vize teslimi Türkçe Instruction Dataset (3.388 örnek, Git etiketi `v1.0`, arşiv: `reports/archive_v1.0/`).
- v2.0 (Kasım 2026): Tamamen **İngilizce** yeniden üretim; yalnız Flash modelleri (lite kapalı), orijinal İngilizce Stack Exchange soru-cevapları (Gemini'siz, seviye yargıçtan), 60 yanlış öncüllü astronomi sorusu (`misconceptions.json`), Final SFT 1.024 token sınırı (`too_long_for_training`), genişletilmiş kural denetimi ve tam kapsamlı karma LLM yargıç (`DOC`/`REF` 3'lü toplu, `SE` tekli).

## Lisans
Her örnek kaynağının lisansını `license` alanında taşır. Stack Exchange örnekleri cevabın tarihine göre CC BY-SA 4.0 (195), CC BY-SA 3.0 (192) taşır (kaynak veri setinde yazar adı bulunmadığından atıf `source_url` ve lisansla yapılır); OpenStax türevleri CC BY-NC-SA 4.0, Wikipedia türevleri CC BY-SA 4.0 koşullarına tabidir. Veri seti akademik ve ticari olmayan amaçla hazırlanmıştır; sentetik örneklerde Google Gemini API kullanım koşulları da geçerlidir.

## Bilinen problemler
- **Toplu yargıç kalibrasyon riski:** Toplu çağrının (3 iş/çağrı) tekli çağrıyla uyumu önceden test edildi ([reports/judge_calibration.md](reports/judge_calibration.md); 171 örnek): genel uyum %94,7, ancak tekli yargıcın elediği örneklerin %40'ı toplu yargıçta yakalandı (ölçüt 2 sağlanmadı). En büyük fark Stack Exchange'de görüldüğü için (uyum %66,7) **SE işleri tekli yargıca** alındı (`SE: 1`); doküman (%97,2 uyum) ve kapsam dışı (%100 uyum) işlerinde süre nedeniyle 3'lü toplu yargıç kullanıldı. Doküman örneklerinde ~%2–3 düzeyinde artık hata riski bu nedenle bilinçli olarak kabul edilmiş ve burada açıkça belgelenmiştir.
- Kanıt kontrolü cevabın tamamını değil, modelin gösterdiği alıntıyı doğrular; tam kapsamlı LLM yargıç ve örneklem incelemesiyle kalan hata oranı en aza indirilmiştir ancak sıfır olduğu garanti edilemez.
- Örnekler dört farklı Gemini Flash modeliyle üretildiği için üslupta küçük farklılıklar olabilir.
- Stack Exchange örnekleri forumdan birebir alınan insan cevaplarıdır; kural + tekli yargıçla temizlense de üslup sentetik ders anlatımlarına göre daha konuşma diline yakın olabilir.
- Kapsam dışı ve yanlış öncül örnekleri kaynak dokümansızdır; doğrulukları yargıç ve incelemeyle kontrol edildi.
- `step_by_step_problem_solving` türünde incelenen 10 örneğin 3 tanesi sorunlu bulunup çıkarılmıştır.

## Hazırlayan
Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. Danışman: Asim Sinan Yüksel.
