# AstroTutor AI Türkçe Instruction Dataset v1.0

## Amaç
Bu veri seti, [Domain Corpus](DATASET_CARD.md) ile alana uyarlanacak modele **supervised fine-tuning (SFT)** ile şu davranışları kazandırmak için hazırlanmıştır: kullanıcının seviyesine (başlangıç / orta / ileri) göre Türkçe konu anlatımı, verilen öğretim metninden JSON biçiminde dört seçenekli soru üretme, astronomi terminolojisiyle doğru açıklama ve bilgisi/kapsamı dışındaki sorularda sınırını bildirme.

## Format
JSONL; her satır bir örnektir. SFT için `messages` alanı kullanılır (`user` / `assistant`). İzlenebilirlik alanları: `id`, `source_document` (corpus `document_id`'si veya Stack Exchange soru kimliği), `source_url`, `task_type`, `level`, `supporting_evidence` (cevabı destekleyen kaynak alıntısı), `generation_method`, `generator_model`, `prompt_version`, `auto_verified`, `llm_judged`, `judge_model`, `human_verified`, `verified_by`, `license`, `split`.

Dosyalar: `data/final/instruction_v1.0.jsonl` (tamamı) ve `data/final/instruction/{train,validation,test}.jsonl`.

## Görev türü dağılımı

| Görev türü | Örnek | Oran | Hedef oran |
| --- | --- | --- | --- |
| Tanım ve açıklama (`tanim_aciklama`) | 520 | %15,6 | %16 |
| Seviyeye göre ders anlatımı (`seviyeli_anlatim`) | 497 | %14,9 | %15 |
| Çoktan seçmeli soru üretimi (JSON) (`coktan_secmeli_soru_uretimi`) | 451 | %13,5 | %14 |
| Soru-cevap (Stack Exchange) (`soru_cevap`) | 407 | %12,2 | %12 |
| Karşılaştırma (`karsilastirma`) | 324 | %9,7 | %10 |
| Neden-sonuç (`neden_sonuc`) | 336 | %10,1 | %10 |
| Özetleme (`ozetleme`) | 260 | %7,8 | %8 |
| Adım adım problem çözme (`adim_adim_problem_cozme`) | 247 | %7,4 | %7 |
| Sınıflandırma (`siniflandirma`) | 151 | %4,5 | %4 |
| Bilgi yetersizliği / kapsam dışı (`bilgi_yetersizligi_kapsam_disi`) | 147 | %4,4 | %4 |
| **Toplam** | **3.340** | %100 | |

Taksonominin gerekçesi ve her türden örnekler: [reports/instruction_taxonomy.md](reports/instruction_taxonomy.md).

Seviye dağılımı: baslangic 1.181 (%35), orta 1.110 (%33), ileri 1.049 (%31).

## Örneklerin üretimi
- **Kaynaklar:** Domain Corpus'tan 311 doküman (2.786 örnek), Stack Exchange Space/Astronomy soru-cevapları (407 örnek; 449 seçilmiş soru) ve kaynak dokümansız kapsam dışı örnekler (147).
- **Yöntem:** LLM destekli sentetik üretim. Her çağrıda tek bir kaynak doküman ve o dokümana atanmış görev türleri/seviyeler verilir; model yalnızca kaynaktaki bilgiyi kullanmak ve cevabı destekleyen alıntıyı kaynaktan kelimesi kelimesine kopyalamak zorundadır. Stack Exchange örneklerinde soru ve kabul edilmiş/en yüksek puanlı cevap Türkçeye aktarılıp düzenlenmiştir (kullanıcı adı, bağlantı ve kişisel yorumlar çıkarıldı).
- **Model:** Google Gemini API (ücretsiz katman). Katmanın model başına günlük istek sınırı nedeniyle aynı aileden birden fazla Flash modeli havuz olarak kullanılmış, her örnekte gerçekte kullanılan model kaydedilmiştir: gemini-3.5-flash-lite (2.667), gemini-3.1-flash-lite (256), gemini-3.7-flash (161), gemini-3.6-flash (154), gemini-3.5-flash (62), gemini-3.8-flash (40).
- **Parametreler:** sıcaklık 0.7, düşünme seviyesi `low`, en fazla 16.384 çıktı token'ı. Prompt sürümleri (örnek sayısı): `v1` (3.034), `v1.1` (146), `v1.2` (160). Prompt metinleri: [prompts/v1/](prompts/v1/), [prompts/v1.1/](prompts/v1.1/), [prompts/v1.2/](prompts/v1.2/) (`system_generate.txt`, `generate_doc.txt`, `generate_se.txt`, `generate_refusal.txt`, `task_types.json`). Sürümler, doğrulamada bulunan kusurların kaynağında önlenmesi için eklendi: **v1.1** çoktan seçmeli görev tanımına 'talimatta soru, şık veya doğru cevap yer almaz', sistem prompt'una 'Türkçeye özgü harfleri (ç, ğ, ı, ö, ş, ü) ASCII karşılıklarıyla değiştirme'; **v1.2** ayrıca 'kullanıcı kaynağı görmediği için cevaplarda da "metne göre", "kaynakta" deme' ve sınıflandırmada öğelerin talimatta açıkça sayılması kurallarını ekler.
- Üretim yöntemlerine göre: `llm_sentetik_kaynak_dokumandan` 2.786, `llm_ceviri_duzenleme_stackexchange` 407, `llm_sentetik_kapsam_disi` 147.

## Doğrulama
Toplam **3.831** örnek üretildi; doğrulamadan sonra **3.340** örnek kaldı. Ayrıca çıktısı iş düzeyinde kusurlu bulunan 28 iş (Türkçe karakter kaybı veya çoktan seçmeli talimatta soru verilmesi) arşivlenip yeniden üretildi; üretim sırasında aynı nedenlerle reddedilen çıktılar hiç kaydedilmedi. Bir LLM'in ürettiği cevap doğru kabul edilmedi; dört aşamalı kontrol uygulandı:

1. **Kural kontrolleri** (tüm örnekler): Türkçe dil tespiti, uzunluk sınırları, görev türü tutarlılığı, çoktan seçmeli JSON şeması (4 seçenek, tek doğru cevap) ve talimatta sorunun, şıkların veya doğru cevabın verilmemesi, Türkçe karakter eksikliği, kaybolmuş üs, kişisel iletişim bilgisi, LaTeX artığı, URL, kaynağı görmeyen kullanıcıya talimatta veya cevapta 'metne göre' gibi atıf, birebir ve yakın tekrar (MinHash, Jaccard ≥ 0,8), değerlendirme setleriyle 8-gram örtüşmesi.
2. **Kanıt kontrolü** (kaynağı olan tüm örnekler): `supporting_evidence` alıntısının kelime 5-gram'larının en az %60'i kaynak metinde bulunmalıdır; bulunmayan örnek uydurma kaynak riski nedeniyle elenir.
3. **LLM yargıç** (işlerin %10'luk tabakalı rastgele örneklemi, 0 örnek): örneği üreten modelden **farklı** bir model, sıcaklık 0 ile her örneği kaynağıyla birlikte desteklenme, doğruluk, talimata uyma, anlaşılırlık ve Türkçe akıcılık açısından değerlendirdi. Başarısız oranı: **-** (tüm set için tahmini hata oranı); başarısızlar elendi. Yargıç modelleri: -.
4. **Rastgele örneklem incelemesi:** bkz. [reports/quality_control_report.md](reports/quality_control_report.md).

**Elenen örnekler** (nedenleriyle: [reports/removed_instructions.csv](reports/removed_instructions.csv)):

| Neden | Adet |
| --- | --- |
| mcq_answer_in_instruction | 154 |
| response_references_unseen_text | 80 |
| references_unseen_text | 67 |
| invalid_mcq_json | 64 |
| turkish_chars_missing | 55 |
| evidence_not_in_source | 34 |
| length | 8 |
| llm_skipped | 5 |
| wrong_language | 5 |
| latex_artifact | 4 |
| eval_overlap | 4 |
| near_duplicate | 4 |
| duplicate | 3 |
| exponent_loss | 2 |
| task_type_mismatch | 2 |

## Veri ayrımı ve sızıntı önleme
train 3.027 · validation 159 · test 154.

- Corpus dokümanından üretilen örnekler, kaynak dokümanın **corpus'taki kümesini** miras alır. Böylece aynı dokümandan gelen örnekler farklı kümelere dağılmaz ve corpus test dokümanından üretilen bir örnek SFT eğitimine girmez (CPT ile SFT arasında da sızıntı yok).
- Stack Exchange örnekleri soru kimliğine, kapsam dışı örnekler kendi kimliğine göre gruplanır; her grubun kümesi seed 42 ve grup kimliğinin hash'inden belirlenir (bir grubun elenmesi diğerlerinin kümesini değiştirmez).
- Değerlendirme setleri (Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ, AstroMLab Astrobench) eğitime alınmadı; bunlarla 8-gram örtüşmesi olan örnekler elendi. Örnekler Türkçe olduğu için İngilizce kaynaklar (Stack Exchange soruları, kaynak doküman pasajları) da değerlendirme setleriyle karşılaştırıldı; aynı soru bulunmadı, yalnız genel ifadeler örtüşüyor (bkz. experiments.md).

## Değerlendirme planı (final dönemi)
Vize kapsamında ayrı bir değerlendirme seti hazırlanmadı; başarı şu şekilde ölçülecek:
- **Dış değerlendirme setleri** (eğitime girmedi): AstroMLab Astrobench, Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ — çoktan seçmeli doğruluk. Corpus ile örtüşen sorular [reports/eval_contamination.csv](reports/eval_contamination.csv) dosyasında listelidir ve ayrıca raporlanacaktır.
- **Bu setin test kümesi** (154 örnek; corpus kaynaklı olanlar yalnız corpus test dokümanlarından üretildi): Türkçe talimat takibi, seviyeye uygunluk ve JSON soru üretiminin geçerliliği (şema, tek doğru cevap, kaynakla tutarlılık).
- Üç sistem karşılaştırılacak: hazır instruct model, alana uyarlanmış (CPT) model, CPT + SFT.

## Sınırlılıklar
Örnekler sentetiktir ve kaynak dokümanlardaki bilgiyle sınırlıdır; güncel astronomik veriler (ör. ötegezegen sayısı) için birincil kaynakların yerine geçmez. Seviye etiketleri üretim sırasında atanmıştır; seviyeye uygunluk yalnız yargıç ve örneklem incelemesiyle kontrol edilmiştir. Tüm örnekler tek turlu (kullanıcı → asistan) diyaloglardır.

## Sürüm geçmişi
- v0.1 (22.10.2026): Pilot üretim (11 örnek, eski prompt; veri setine alınmadı).
- v0.9 (23.10.2026): Stack Exchange, kapsam dışı ve doküman işleri; Türkçe karakter kontrolü.
- v1.0 (24–25.10.2026): ek paketler (ek1–ek3), prompt v1.1/v1.2, çoktan seçmeli sızıntı ve görünmeyen metne atıf kuralları, LLM yargıç örneklemi, 150 örneklik inceleme.

## Lisans
Her örnek kaynağının lisansını `license` alanında taşır. Stack Exchange türevleri CC BY-SA 4.0, OpenStax türevleri CC BY-NC-SA 4.0, Wikipedia türevleri CC BY-SA 4.0 koşullarına tabidir; veri seti akademik ve ticari olmayan amaçla hazırlanmıştır. Örnekler Gemini API ile üretildiği için Google'ın Gemini API kullanım koşulları da geçerlidir (koşullar, Gemini ile rekabet eden model geliştirmeyi kısıtlar; bu çalışma küçük ölçekli, akademik bir alan modelidir).

## Bilinen problemler
- Sentetik üretim nedeniyle bazı cevaplarda çeviri kokan ifadeler veya küçük yazım hataları kalabilir; örneklem incelemesindeki hata türleri kalite raporundadır.
- Kanıt kontrolü cevabın tamamını değil, modelin gösterdiği alıntıyı doğrular; alıntı dışındaki bir cümlede hata kalma olasılığı LLM yargıç ve örneklem incelemesiyle ölçülmüştür, sıfır değildir.
- Örnekler birden fazla Gemini modeliyle üretildiği için üslupta küçük farklılıklar olabilir. Ücretsiz katmanın Flash kotası yetmediği için örneklerin %87,5'i lite modellerle üretildi; lite cevaplar daha kısadır (ortalama 414 karakter, Flash 801) ve Türkçe karakter kaybı, talimatta soru verme gibi kusurlar lite çıktılarında yoğunlaştı (bu kusurlu örnekler elendi).
- Stack Exchange cevaplarının bir kısmı uzay mühendisliği ağırlıklıdır; kaynak verideki kaybolmuş üsler ("× 1030 kg") otomatik düzeltildi, ancak benzer biçim bozuklukları tamamen dışlanamaz.
- Kapsam dışı örnekler kaynak dokümansızdır; doğrulukları yalnız yargıç ve inceleme ile kontrol edildi.

## Hazırlayan
Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. Danışman: Asim Sinan Yüksel.
