# AstroTutor AI Türkçe Instruction Dataset v1.0

## Amaç
Bu veri seti, [Domain Corpus](DATASET_CARD.md) ile alana uyarlanacak modele **supervised fine-tuning (SFT)** ile şu davranışları kazandırmak için hazırlanmıştır: kullanıcının seviyesine (başlangıç / orta / ileri) göre Türkçe konu anlatımı, verilen öğretim metninden JSON biçiminde dört seçenekli soru üretme, astronomi terminolojisiyle doğru açıklama ve bilgisi/kapsamı dışındaki sorularda sınırını bildirme.

## Format
JSONL; her satır bir örnektir. SFT için `messages` alanı kullanılır (`user` / `assistant`). İzlenebilirlik alanları: `id`, `source_document` (corpus `document_id`'si veya Stack Exchange soru kimliği), `source_url`, `task_type`, `level`, `supporting_evidence` (cevabı destekleyen kaynak alıntısı), `generation_method`, `generator_model`, `prompt_version`, `auto_verified`, `llm_judged`, `judge_model`, `human_verified`, `verified_by`, `license`, `split`, `raw_example_id` (üretim kaydı), `postprocess` (kural tabanlı metin düzeltmesi, ör. `kaynak_atfi_silindi`; yoksa boş).

Dosyalar: `data/final/instruction_v1.0.jsonl` (tamamı) ve `data/final/instruction/{train,validation,test}.jsonl`.

## Görev türü dağılımı

| Görev türü | Örnek | Oran | Hedef oran |
| --- | --- | --- | --- |
| Tanım ve açıklama (`tanim_aciklama`) | 538 | %15,9 | %16 |
| Seviyeye göre ders anlatımı (`seviyeli_anlatim`) | 507 | %15,0 | %15 |
| Çoktan seçmeli soru üretimi (JSON) (`coktan_secmeli_soru_uretimi`) | 451 | %13,3 | %14 |
| Soru-cevap (Stack Exchange) (`soru_cevap`) | 401 | %11,8 | %12 |
| Karşılaştırma (`karsilastirma`) | 333 | %9,8 | %10 |
| Neden-sonuç (`neden_sonuc`) | 344 | %10,2 | %10 |
| Özetleme (`ozetleme`) | 267 | %7,9 | %8 |
| Adım adım problem çözme (`adim_adim_problem_cozme`) | 248 | %7,3 | %7 |
| Sınıflandırma (`siniflandirma`) | 152 | %4,5 | %4 |
| Bilgi yetersizliği / kapsam dışı (`bilgi_yetersizligi_kapsam_disi`) | 147 | %4,3 | %4 |
| **Toplam** | **3.388** | %100 | |

Taksonominin gerekçesi ve her türden örnekler: [reports/instruction_taxonomy.md](reports/instruction_taxonomy.md).

Seviye dağılımı: başlangıç (`baslangic`) 1.188 (%35,1), orta (`orta`) 1.129 (%33,3), ileri (`ileri`) 1.071 (%31,6).

## Örneklerin üretimi
- **Kaynaklar:** Domain Corpus'tan 320 doküman (2.840 örnek), Stack Exchange Space/Astronomy soru-cevapları (401 örnek; 449 seçilmiş soru) ve kaynak dokümansız kapsam dışı örnekler (147).
- **Yöntem:** LLM destekli sentetik üretim. Her çağrıda tek bir kaynak doküman ve o dokümana atanmış görev türleri/seviyeler verilir; model yalnızca kaynaktaki bilgiyi kullanmak ve cevabı destekleyen alıntıyı kaynaktan kelimesi kelimesine kopyalamak zorundadır. Stack Exchange örneklerinde soru ve kabul edilmiş/en yüksek puanlı cevap Türkçeye aktarılıp düzenlenmiştir (kullanıcı adı, bağlantı ve kişisel yorumlar çıkarıldı).
- **Model:** Google Gemini API (ücretsiz katman). Katmanın model başına günlük istek sınırı nedeniyle aynı aileden birden fazla Flash modeli havuz olarak kullanılmış, her örnekte gerçekte kullanılan model kaydedilmiştir: gemini-3.5-flash-lite (2.592), gemini-3.1-flash-lite (251), gemini-3.7-flash (220), gemini-3.6-flash (177), gemini-3.5-flash (108), gemini-3.8-flash (40).
- **Parametreler:** sıcaklık 0,7, düşünme seviyesi `low`, en fazla 16.384 çıktı token'ı. Prompt sürümleri (örnek sayısı): `v1` (2.964), `v1.1` (138), `v1.2` (286). Prompt metinleri: [prompts/v1/](prompts/v1/), [prompts/v1.1/](prompts/v1.1/), [prompts/v1.2/](prompts/v1.2/) (`system_generate.txt`, `generate_doc.txt`, `generate_se.txt`, `generate_refusal.txt`, `task_types.json`). Sürümler, doğrulamada bulunan kusurların kaynağında önlenmesi için eklendi: **v1.1** çoktan seçmeli görev tanımına 'talimatta soru, şık veya doğru cevap yer almaz', sistem prompt'una 'Türkçeye özgü harfleri (ç, ğ, ı, ö, ş, ü) ASCII karşılıklarıyla değiştirme'; **v1.2** ayrıca 'kullanıcı kaynağı görmediği için cevaplarda da "metne göre", "kaynakta" deme' ve sınıflandırmada öğelerin talimatta açıkça sayılması kurallarını ekler.
- Üretim yöntemlerine göre: `llm_sentetik_kaynak_dokumandan` 2.840, `llm_ceviri_duzenleme_stackexchange` 401, `llm_sentetik_kapsam_disi` 147.

## Doğrulama
Toplam **3.962** örnek üretildi; doğrulamadan sonra **3.388** örnek kaldı. Ayrıca çıktısı iş düzeyinde kusurlu bulunan 28 iş (Türkçe karakter kaybı veya çoktan seçmeli talimatta soru verilmesi) arşivlenip yeniden üretildi; üretim sırasında aynı nedenlerle reddedilen çıktılar hiç kaydedilmedi. Bir LLM'in ürettiği cevap doğru kabul edilmedi; dört aşamalı kontrol uygulandı:

1. **Kural kontrolleri** (tüm örnekler): Türkçe dil tespiti, uzunluk sınırları, görev türü tutarlılığı, çoktan seçmeli JSON şeması (4 seçenek, tek doğru cevap), talimatta öğretim metninin bulunması ve sorunun, şıkların, doğru cevabın veya öğrenciye sorulacak sorunun verilmemesi, Türkçe karakter eksikliği ('ı' harfinin düşmesi dahil), kaybolmuş üs, kişisel iletişim bilgisi, LaTeX artığı, URL, kaynağı görmeyen kullanıcıya talimatta veya cevapta 'metne göre' gibi atıf, birebir ve yakın tekrar (MinHash, Jaccard ≥ 0,8), değerlendirme setleriyle 8-gram örtüşmesi. Öğeleri talimatta sayılmış 35 sınıflandırma talimatının başındaki "Metinde adı geçen" gibi atıf ifadesi silindi (örnek elenmedi; `postprocess` alanında işaretli). 20 cevapta "Adim" yazımı "Adım" olarak düzeltildi; 1 tanesi sonradan elendiği için final sette 19.
2. **Kanıt kontrolü** (kaynağı olan tüm örnekler): `supporting_evidence` alıntısının kelime 5-gram'larının en az %60'ı kaynak metinde bulunmalıdır; bulunmayan örnek uydurma kaynak riski nedeniyle elenir.
3. **LLM yargıç** (işlerin %10'luk tabakalı rastgele örneklemi, 348 örnek): örneği üreten modelden **farklı** bir model, sıcaklık 0 ile her örneği kaynağıyla birlikte desteklenme, doğruluk, talimata uyma, anlaşılırlık ve Türkçe akıcılık açısından değerlendirdi. Başarısız oranı: **%11,5** (tüm set için tahmini hata oranı); başarısızlar elendi. Yargıç modelleri: gemini-3.8-flash (112), gemini-3.5-flash (84), gemini-3.6-flash (73), gemini-3.7-flash (37). Örneklem ilk çalıştırmada sabitlendi (sonradan eklenen kurallar örneklemi değiştirmesin diye). Lite üretimlerinde başarısız: 40/318 (%12,6); Flash üretimlerinde başarısız: 0/30 (%0,0).
4. **Rastgele örneklem incelemesi:** 150 örnek (görev türü oranında tabakalı) kaynak metniyle karşılaştırılarak incelendi. Yapay zekâ destekli ön inceleme ölçüt bazında yapıldı; nihai kararı grup üyesi verdi. Ön incelemede uygun: %84,0; nihai kararda uygun: %84,0. Sorunlu bulunan 24 örnek setten çıkarıldı.

**Elenen örnekler** (nedenleriyle: [reports/removed_instructions.csv](reports/removed_instructions.csv)):

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
| örneklem incelemesinde sorunlu | 24 |

## Veri ayrımı ve sızıntı önleme
train 3.078 · validation 146 · test 164.

- Corpus dokümanından üretilen örnekler, kaynak dokümanın **corpus'taki kümesini** miras alır. Böylece aynı dokümandan gelen örnekler farklı kümelere dağılmaz ve corpus test dokümanından üretilen bir örnek SFT eğitimine girmez (CPT ile SFT arasında da sızıntı yok).
- Stack Exchange örnekleri soru kimliğine, kapsam dışı örnekler kendi kimliğine göre gruplanır; her grubun kümesi seed 42 ve grup kimliğinin hash'inden belirlenir (bir grubun elenmesi diğerlerinin kümesini değiştirmez).
- Değerlendirme setleri (Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ, AstroMLab Astrobench) eğitime alınmadı; bunlarla 8-gram örtüşmesi olan örnekler elendi. Örnekler Türkçe olduğu için İngilizce kaynaklar (Stack Exchange soruları, kaynak doküman pasajları) da değerlendirme setleriyle karşılaştırıldı; aynı soru bulunmadı, yalnız genel ifadeler örtüşüyor (bkz. experiments.md).

## Değerlendirme planı (final dönemi)
Vize kapsamında ayrı bir değerlendirme seti hazırlanmadı; başarı şu şekilde ölçülecek:
- **Dış değerlendirme setleri** (eğitime girmedi): AstroMLab Astrobench, Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ — çoktan seçmeli doğruluk. Corpus ile örtüşen sorular [reports/eval_contamination.csv](reports/eval_contamination.csv) dosyasında listelidir ve ayrıca raporlanacaktır.
- **Bu setin test kümesi** (164 örnek; corpus kaynaklı olanlar yalnız corpus test dokümanlarından üretildi): Türkçe talimat takibi, seviyeye uygunluk ve JSON soru üretiminin geçerliliği (şema, tek doğru cevap, kaynakla tutarlılık).
- Üç sistem karşılaştırılacak: hazır instruct model, alana uyarlanmış (CPT) model, CPT + SFT.

## Sınırlılıklar
Örnekler sentetiktir ve kaynak dokümanlardaki bilgiyle sınırlıdır; güncel astronomik veriler (ör. ötegezegen sayısı) için birincil kaynakların yerine geçmez. Seviye etiketleri üretim sırasında atanmıştır; seviyeye uygunluk yalnız yargıç ve örneklem incelemesiyle kontrol edilmiştir. Tüm örnekler tek turlu (kullanıcı → asistan) diyaloglardır.

## Sürüm geçmişi
- v0.1 (22.10.2026): Pilot üretim (11 örnek, eski prompt; veri setine alınmadı).
- v0.9 (23.10.2026): Stack Exchange, kapsam dışı ve doküman işleri; Türkçe karakter kontrolü.
- v1.0 (24–26.10.2026): ek paketler (ek1–ek3), prompt v1.1/v1.2, çoktan seçmeli sızıntı ve görünmeyen metne atıf kuralları, LLM yargıç örneklemi, 150 örneklik inceleme.
- Planlanan v1.1 (final dönemi öncesi): yargıcın örneklem dışındaki bütün lite üretimi işlere genişletilmesi (`11_verify_instructions.py --extended`); elenenler `judge_ext_fail` nedeniyle ayrı kaydedilir.

## Lisans
Her örnek kaynağının lisansını `license` alanında taşır. Stack Exchange türevleri CC BY-SA 4.0, OpenStax türevleri CC BY-NC-SA 4.0, Wikipedia türevleri CC BY-SA 4.0 koşullarına tabidir; veri seti akademik ve ticari olmayan amaçla hazırlanmıştır. Örnekler Gemini API ile üretildiği için Google'ın Gemini API kullanım koşulları da geçerlidir (koşullar, Gemini ile rekabet eden model geliştirmeyi kısıtlar; bu çalışma küçük ölçekli, akademik bir alan modelidir).

## Bilinen problemler
- Sentetik üretim nedeniyle bazı cevaplarda çeviri kokan ifadeler veya küçük yazım hataları kalabilir; örneklem incelemesindeki hata türleri kalite raporundadır.
- Kanıt kontrolü cevabın tamamını değil, modelin gösterdiği alıntıyı doğrular; alıntı dışındaki bir cümlede hata kalma olasılığı LLM yargıç ve örneklem incelemesiyle ölçülmüştür, sıfır değildir.
- Örnekler birden fazla Gemini modeliyle üretildiği için üslupta küçük farklılıklar olabilir. Ücretsiz katmanın Flash kotası yetmediği için örneklerin %83,9'u lite modellerle üretildi; lite cevaplar daha kısadır (ortalama 414 karakter, Flash 781) ve Türkçe karakter kaybı, talimatta soru verme gibi kusurlar lite çıktılarında yoğunlaştı (bu kusurlu örnekler elendi).
- Stack Exchange cevaplarının bir kısmı uzay mühendisliği ağırlıklıdır; kaynak verideki kaybolmuş üsler ("× 1030 kg") otomatik düzeltildi, ancak benzer biçim bozuklukları tamamen dışlanamaz.
- Kapsam dışı örnekler kaynak dokümansızdır; doğrulukları yalnız yargıç ve inceleme ile kontrol edildi.
- Örnekler kaynağa sadıktır; kaynaktaki hata da örneğe geçebilir. Örneklem incelemesinde bu türden bulunan hatalar: Türkçe Wikipedia'daki "1921'de Birleşmiş Milletler Radyum Kurumu" (BM 1945'te kuruldu), Büyük Patlama'nın "birkaç milimetrelik bir noktadan patlama" diye anlatılması, bilimsel olarak eksik bir Stack Exchange cevabı (Titan atmosferi). Bu örnekler çıkarıldı; benzerleri yargıç ve incelemenin dışında kalan örneklerde bulunabilir.
- `adim_adim_problem_cozme` türü en zayıf türdür: incelenen 11 örneğin 5 tanesi sorunluydu; çoğunda çözülecek bir hesap veya süreç yoktu, bilgiler adım gibi sıralanmıştı (yargıç da bu örnekleri eledi).
- Yargıç yalnız %10'luk örneklemde çalıştı; örneklem dışındaki lite üretimi örneklerin bir kısmında benzer kusurlar kalmış olabilir (tahmini oran yukarıda). Final dönemi eğitiminden önce ek yargıçla temizlenmesi planlanmıştır (v1.1).

## Hazırlayan
Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. Danışman: Asim Sinan Yüksel.
