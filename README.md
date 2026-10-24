# AstroTutor AI — Veri Hazırlama (Vize)

Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği — Tasarım / Bitirme Projesi
**Proje:** Uzay ve Astronomi Eğitiminde SLM ve RAG Tabanlı Etkileşimli Öğrenme ve Test Sistemi (AstroTutor AI)
**Hazırlayan:** Eda GÖGEBAKAN (2211012069) · **Danışman:** Asim Sinan YÜKSEL

Bu depo, vize döneminin iki çıktısını üreten yeniden çalıştırılabilir pipeline'ı içerir:

| Veri seti | Amaç | Eğitim aşaması | Belge |
| --- | --- | --- | --- |
| **Domain Corpus v1.0** | Modele astronomi/uzay alanının dilini ve bilgisini öğretmek (düz metin) | CPT / DAPT | [DATASET_CARD.md](DATASET_CARD.md) |
| **Instruction Dataset v1.0** | Modele Türkçe talimat takip etme, seviyeye göre anlatım ve çoktan seçmeli soru üretme davranışı kazandırmak | SFT (QLoRA) | [INSTRUCTION_CARD.md](INSTRUCTION_CARD.md) |

Değerlendirme (evaluation) setleri (Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ, AstroMLab Astrobench) **eğitime girmez**; yalnızca sızıntı kontrolü için indirilir.

## Problem ve kapsam

- **Problem:** Türkçe konuşan öğrencilerin uzay ve astronomi konularını kendi seviyelerinde öğrenebileceği, anlatılan içerikten soru üreterek öğrenmeyi ölçebilen, kaynağı izlenebilir bir yardımcı yok.
- **Hedef:** Başlangıç / orta / ileri seviyeye göre Türkçe konu anlatımı yapan ve anlattığı içerikten dört seçenekli soru üreten alana özel bir dil modeli (ana aday: Qwen2.5-7B ailesi).
- **Kapsam içi:** Güneş Sistemi, gezegenler ve uydular, yıldızlar ve yıldız evrimi, gökadalar, temel kozmoloji, ötegezegenler, uzay araçları ve keşif görevleri, gözlemevleri/teleskoplar.
- **Kapsam dışı:** İleri matematiksel astrofizik türetmeleri, ham teleskop görüntüsü işleme, bilimsel simülasyon, roket mühendisliği ayrıntıları, uzay şirketlerinin ticari konuları, astroloji.
- **Kullanıcı:** Ortaokul–lisans arası öğrenciler ve meraklılar; cevaplar seviyeye göre sadeleşir veya derinleşir.

## Klasör yapısı

```
data/
  raw/            indirilen orijinal dosyalar (değiştirilmez)       [Git'e girmez]
  extracted/      çıkarılmış metinler (.jsonl + doküman başına .txt) [Git'e girmez]
  cleaned/        temizlenmiş metinler                               [Git'e girmez]
  interim/        filtre, tekrar ayıklama ve instruction ara çıktıları [Git'e girmez]
  final/          train/validation/test.jsonl, chunks/, instruction_v1.0.jsonl, instruction/ [Git'e girmez]
  eval_reference/ değerlendirme setleri (yalnız sızıntı kontrolü)   [Git'e girmez]
  samples/        her veri setinden küçük örnekler                   [Git'te]
scripts/          01_download.py … 16_make_samples.py, validate_datasets.py
prompts/v1/       instruction üretimi ve LLM yargıç prompt'ları (sürümlü)
reports/          kaynak envanteri, istatistikler, kalite kontrol, temizleme örnekleri, grafikler
notebooks/        keşifsel analiz
config.yaml       tüm yollar, eşikler, seed ve model adları
experiments.md    tarihli deney ve karar günlüğü
```

Büyük veri dosyaları depoya konmaz. Ham veri ve üretilen veri setleri yerelde `data/` altında durur ve pipeline ile
yeniden üretilebilir; teslim kopyası ayrıca paylaşılır (bkz. `data/samples/` içindeki örnekler).

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # GEMINI_API_KEY yalnızca instruction üretimi için gerekir
```

Python 3.13 ile test edilmiştir. PyTorch gerekmez (tokenizer'lar yeterli).

## Pipeline'ı çalıştırma

```bash
python run_pipeline.py --corpus          # 01-08: indirme → extraction → cleaning → filter → dedup → split → 06b → token → istatistik
python run_pipeline.py --instructions    # 09-12: kaynak hazırlama → Gemini ile üretim → doğrulama → split
python run_pipeline.py --qc              # 13-16 + validate_datasets.py
python run_pipeline.py --all
```

Her adım tek başına da çalıştırılabilir (`python scripts/05_deduplicate.py`). Her script `logs/<ad>.log` dosyasına
log yazar ve sonunda kaç dokümanın işlendiğini özetler. Rastgelelik içeren tüm adımlar `config.yaml` içindeki
`random_seed: 42` ile sabittir. İndirme ve LLM üretimi kaldığı yerden devam eder.

| Script | Yaptığı iş | Ana çıktı |
| --- | --- | --- |
| `01_download.py` | Kaynakları indirir, her dosya için URL/SHA-256/tarih/lisans manifesti tutar | `data/raw/*/manifest.jsonl` |
| `02_extract.py` | HTML: Trafilatura; PDF: PyMuPDF (blok sıralı); XML/JSON alanları | `data/extracted/`, `reports/extraction_failures.csv` |
| `03_clean.py` | NFKC (üs korumalı), header/footer, menü, kesik tanıtım, kaynakça girdisi satırları, kısa satır temizliği | `data/cleaned/`, `reports/cleaning_examples.md`, `reports/cleaning_rules.md` |
| `04_filter.py` | too_short, reference_list, garbled, wrong_language, out_of_domain, out_of_domain_category (Wikipedia kategorileri) | `data/interim/filtered.jsonl`, `reports/removed_documents.csv` |
| `05_deduplicate.py` | SHA-256 exact + MinHash/Jaccard ≥ 0.85 near duplicate, metadata | `data/interim/corpus_v0.9.jsonl` |
| `06_split.py` | Doküman (grup) düzeyinde %90/5/5, kaynak bazında tabakalı | `data/final/{train,validation,test}.jsonl` |
| `06b_repost_dedup.py` | APOD duyuru satırları + yeniden yayın tekrarları (kimlik ve kümeler korunur; kalite kontrolünde bulundu) | `data/final/*.jsonl`, `reports/dedup2_summary.json` |
| `07_token_count.py` | Qwen2.5 tokenizer ile token sayımı + split sonrası chunk | `reports/token_stats.json`, `data/final/chunks/` |
| `08_statistics.py` | Sayısal özet, veri erimesi, dağılımlar, grafikler | `reports/statistics.md` |
| `09_build_instruction_sources.py` | StackExchange temizliği, kaynak doküman seçimi, görev kotaları (`--part se_ref / doc / doc_supplement`) | `data/interim/instruction_jobs.jsonl` |
| `10_generate_instructions.py` | Gemini ile Türkçe örnek üretimi; Türkçe karakteri eksik iş çıktısı reddedilir | `data/interim/instructions_raw.jsonl` |
| `11_verify_instructions.py` | Kural kontrolleri + kanıt kontrolü + %10 LLM yargıç + sızıntı kontrolü | `data/interim/instructions_verified.jsonl` |
| `12_split_instructions.py` | Kaynak dokümana göre gruplu ayrım | `data/final/instruction_v1.0.jsonl` |
| `13_sample_for_review.py` | Manuel kontrol için 100 corpus + 150 instruction rastgele örnek | `reports/qc/*_review.csv` |
| `14_qc_report.py` | Otomatik + manuel kalite raporu | `reports/quality_control_report.md` |
| `15_write_cards.py` | Kartları gerçek sayılarla üretir | `DATASET_CARD.md`, `INSTRUCTION_CARD.md` |
| `16_make_samples.py` | Depoya girecek küçük örnekler (seed 42; final dosyalardan değiştirilmeden) | `data/samples/*.jsonl` |
| `validate_datasets.py` | Şema, sızıntı, HF yükleme, chat template testi | `reports/validation_report.md` |
| `requeue_jobs.py` | Türkçe karakteri eksik (`--reason turkce`) veya çoktan seçmeli sorusu talimatta verilmiş (`--reason mcq`) işleri arşivleyip yeniden kuyruğa alır (bakım; döngü dururken) | `data/interim/archive/` |

Yardımcı modüller: `common.py` (config, log, JSONL, RemovalLog), `llm.py` (Gemini istemcisi: model kademeleri,
kota/yoğunluk yönetimi), `domain_lexicon.py` (alan terimleri, Wikipedia kategori kuralı), `turkish_check.py`
(Türkçe karakter kontrolü), `mcq_check.py` (çoktan seçmeli talimatta soru/şık/cevap sızıntısı), `exponent_fix.py` (kaybolmuş üsler; `python scripts/exponent_fix.py` testleri çalıştırır),
`press_boilerplate.py` (NASA basın künyesi ve kişisel iletişim bilgisi temizliği; testli).

### Instruction üretimini arka planda sürdürme (Windows)

Ücretsiz Gemini katmanında üretim birkaç güne yayıldığı için `run_instruction_loop.py` kota/yoğunluk
durumlarında kendisi bekleyip yeniden dener (10 → 11 → 12 → 13). VS Code veya terminal kapansa da sürmesi için
Görev Zamanlayıcı'ya kaydedilir (oturum açılınca da başlar; aynı anda yalnız bir döngü çalışır):

```powershell
$vbs = (Resolve-Path "scripts\windows\run_loop_hidden.vbs").Path
Register-ScheduledTask -TaskName "AstroTutorInstructionLoop" -Action (New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbs`"") `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) `
  -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 -MultipleInstances IgnoreNew)
Start-ScheduledTask -TaskName "AstroTutorInstructionLoop"
# İlerleme: logs/instruction_loop.log, logs/10_generate_instructions.log
# İş bitince kaldırma:
Unregister-ScheduledTask -TaskName "AstroTutorInstructionLoop" -Confirm:$false
```

## Raporlar

- [reports/source_inventory.csv](reports/source_inventory.csv) — kaynak listesi (ad, URL, tür, dil, doküman sayısı, erişim tarihi, lisans, gerekçe)
- [reports/statistics.md](reports/statistics.md) — istatistik raporu
- [reports/quality_control_report.md](reports/quality_control_report.md) — kalite kontrol raporu
- [reports/cleaning_rules.md](reports/cleaning_rules.md), [reports/cleaning_examples.md](reports/cleaning_examples.md) — temizleme kuralları ve öncesi/sonrası
- [reports/extraction_tool_comparison.md](reports/extraction_tool_comparison.md) — PyMuPDF / pdfplumber karşılaştırması
- [reports/instruction_taxonomy.md](reports/instruction_taxonomy.md) — görev türü taksonomisi
- [reports/sunum_taslagi.md](reports/sunum_taslagi.md) — vize sunumu taslağı
- [experiments.md](experiments.md) — karar günlüğü

## Lisans ve etik

Her doküman ve örnek kendi kaynağının lisansını `license` alanında taşır (bkz. kartlar). Veri setleri akademik,
ticari olmayan amaçla hazırlanmıştır; OpenStax Astronomy 2e (CC BY-NC-SA 4.0) ve Wikipedia/Stack Exchange
(CC BY-SA 4.0) içeriklerinin türevleri aynı koşullarla paylaşılmalıdır. Kişisel veri toplanmamıştır (arXiv yazar
adları ve Stack Exchange kullanıcı adları alınmamıştır).
