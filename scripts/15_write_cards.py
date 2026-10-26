"""15 — DATASET_CARD.md ve INSTRUCTION_CARD.md dosyalarını üretir (Vize Rehberi §13).

Kartlardaki tüm sayılar pipeline raporlarından ve final veri dosyalarından OKUNUR, elle yazılmaz.
Veri değiştiğinde (ör. kalite kontrol sonrası) bu script yeniden çalıştırılarak kartlar güncellenir.
"""
from __future__ import annotations

import csv
import json
from collections import Counter

from common import CFG, ROOT, get_logger, p, read_jsonl, tr_ek

log = get_logger("15_write_cards")
R = p("reports")

SRC = {  # final 'source' alanı -> (görünen ad, tür, extraction anahtarı)
    "nasa_science": ("NASA Science (science.nasa.gov)", "HTML", "nasa_science"),
    "nasa_apod": ("NASA APOD açıklamaları", "HTML", "nasa_apod"),
    "openstax_astronomy_2e": ("OpenStax Astronomy 2e (ders kitabı)", "PDF", "openstax"),
    "arxiv_astro_ph": ("arXiv astro-ph (başlık + özet)", "XML", "arxiv_astro_ph"),
    "wikipedia_en": ("Wikipedia (İngilizce)", "API/JSON", "wikipedia_en"),
    "wikipedia_tr": ("Wikipedia (Türkçe)", "API/JSON", "wikipedia_tr"),
}
LICENSE = {
    "nasa_science": "NASA medya/içerik yönergeleri (kamuya açık, atıf)",
    "nasa_apod": "NASA hizmeti; yalnız açıklama metni, görseller alınmadı",
    "openstax_astronomy_2e": "CC BY-NC-SA 4.0",
    "arxiv_astro_ph": "CC0 1.0 (arXiv metadata)",
    "wikipedia_en": "CC BY-SA 4.0",
    "wikipedia_tr": "CC BY-SA 4.0",
}
TASK_TR = {
    "tanim_aciklama": "Tanım ve açıklama", "seviyeli_anlatim": "Seviyeye göre ders anlatımı",
    "coktan_secmeli_soru_uretimi": "Çoktan seçmeli soru üretimi (JSON)", "soru_cevap": "Soru-cevap (Stack Exchange)",
    "karsilastirma": "Karşılaştırma", "neden_sonuc": "Neden-sonuç", "ozetleme": "Özetleme",
    "adim_adim_problem_cozme": "Adım adım problem çözme", "siniflandirma": "Sınıflandırma",
    "bilgi_yetersizligi_kapsam_disi": "Bilgi yetersizliği / kapsam dışı",
}


def j(name: str) -> dict:
    f = R / name
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def n(x) -> str:
    return f"{x:,}".replace(",", ".") if isinstance(x, int) else str(x)


def pc(a, b, d=1) -> str:
    return ("%" + f"{100 * a / b:.{d}f}".replace(".", ",")) if b else "-"


def mtok(x: int) -> str:
    return f"{x / 1e6:.1f}M".replace(".", ",")


def removed_rows(name: str) -> list[dict]:
    f = R / name
    if not f.exists():
        return []
    with open(f, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def speedup() -> str:
    """PyMuPDF/pdfplumber hız oranı: sabit sayı yazmak yerine 02'nin ürettiği karşılaştırma raporundan okunur."""
    import re
    f = R / "extraction_tool_comparison.md"
    m = re.search(r"yaklaşık (\d+) kat hızlı", f.read_text(encoding="utf-8")) if f.exists() else None
    return f"PyMuPDF yaklaşık {m.group(1)} kat hızlı" if m else "PyMuPDF daha hızlı"


def near_dup_sentence(qc: dict) -> str:
    """Eşiğin doğrulanması hakkında yalnız GERÇEKTEN yapılmış incelemeyi yazar."""
    link = "[reports/qc/near_dup_pairs_review.csv](reports/qc/near_dup_pairs_review.csv)"
    hum, pre = qc.get("near_dup_threshold_agreement_human"), qc.get("near_dup_threshold_agreement_pre")
    c = qc.get("near_dup_human") or qc.get("near_dup_pre")
    if c:
        how = ("yapay zekâ destekli ön inceleme ve grup üyesinin onayıyla" if qc.get("near_dup_human_is_approval")
               else "grup üyesinin incelemesiyle" if qc.get("near_dup_human") else
               "yapay zekâ destekli ön incelemeyle (grup üyesi kontrolü henüz tamamlanmadı)")
        return (f"Eşik, {c['pairs']} aday çift ({tr_ek(str(c['above']))} Jaccard ≥ eşik, {tr_ek(str(c['below']))} altı) {how} kontrol "
                f"edildi ({link}): eşik üstü {c['above']} çiftin {tr_ek(str(c['above'] - c['false_removals']))} gerçek tekrardı "
                f"(hatalı eleme {c['false_removals']}); eşik altı {c['below']} çiftin {tr_ek(str(c['missed']))} de tekrardı. "
                "Yani eşik yanlış eleme yapmıyor ama kısa metinlerde dağınık küçük düzeltmeleri olan tekrarları kaçırıyor.")
    if hum is not None:
        s = f"Eşik, 50 aday çiftin incelenmesiyle doğrulandı ({link}): grup üyesinin kararıyla uyum %{100 * hum:.0f}"
        return s + (f", yapay zekâ destekli ön incelemeyle uyum %{100 * pre:.0f}." if pre is not None else ".")
    if pre is not None:
        return (f"Eşik, 50 aday çiftin yapay zekâ destekli ön incelemesinde (Claude) %{100 * pre:.0f} uyum gösterdi "
                f"({link}); grup üyesi kontrolü henüz tamamlanmadı.")
    return f"Eşik inceleme tablosu: {link} (inceleme henüz yapılmadı)."


def dataset_card() -> None:
    docs = [d for s in ("train", "validation", "test") for d in read_jsonl(p("final") / f"{s}.jsonl")]
    if not docs:
        log.warning("Corpus yok, DATASET_CARD atlandı")
        return
    ext, ded, tok, st = j("extraction_summary.json"), j("dedup_summary.json"), j("token_stats.json"), \
        j("statistics_summary.json")
    qc = j("qc_summary.json")
    d2 = j("dedup2_summary.json")
    rem = removed_rows("removed_documents.csv") + removed_rows("extraction_failures.csv")
    reasons = Counter(r["reason"] for r in rem)
    by = {s: [d for d in docs if d["source"] == s] for s in SRC}
    total_tok = sum(d["token_count"] for d in docs)
    short_band = sum(1 for d in docs if CFG["filtering"]["min_chars"] <= d["char_count"] < 500)
    lang_tok = Counter()
    for d in docs:
        lang_tok[d["language"]] += d["token_count"]
    dates = sorted(d["retrieved_at"][:10] for d in docs if d.get("retrieved_at"))
    top_src, top_n = max(((s, len(v)) for s, v in by.items()), key=lambda kv: kv[1])
    top_tok_src = max(by, key=lambda s: sum(d["token_count"] for d in by[s]))
    sub = Counter(d["subtopic"] for d in docs)
    sp = Counter(d["split"] for d in docs)
    td = tok.get("documents", {})
    raw_total = st.get("raw")

    md = [f"# Uzay ve Astronomi Domain Corpus v{CFG['project']['corpus_version']} (AstroTutor AI)", "",
          "## Amaç",
          "Bu veri seti, uzay ve astronomi eğitiminde kullanıcının seviyesine göre Türkçe konu anlatımı yapan ve "
          "anlattığı içerikten çoktan seçmeli soru üreten alana özel bir dil modelinin (AstroTutor AI) **continued "
          "pretraining (CPT / DAPT)** aşamasında kullanılmak üzere hazırlanmıştır. Model ailesi olarak Qwen2.5-7B "
          "hedeflenmektedir. Genel amaçlı bir corpus değildir; soru-cevap davranışı için ayrı hazırlanan "
          "[Instruction Dataset](INSTRUCTION_CARD.md) kullanılır.", "",
          "## Kapsam",
          "**Kapsam içi:** Güneş Sistemi; gezegenler ve uydular; yıldızların özellikleri ve yıldız evrimi; gökadalar; "
          "temel kozmoloji; ötegezegenler; uzay araçları ve keşif görevleri; gözlemevleri ve teleskoplar.", "",
          "**Kapsam dışı:** ileri matematiksel astrofizik türetmeleri, ham teleskop görüntüsü işleme, bilimsel "
          "simülasyon, roket mühendisliği ayrıntıları, Dünya bilimleri, uzay şirketlerinin ticari konuları, astroloji.", "",
          "**Hedef kullanıcı:** ortaokul–lisans arası öğrenciler ve meraklılar (başlangıç / orta / ileri seviye).", "",
          "## Veri kaynakları", "",
          "| Kaynak | Tür | Dil | Ham doküman | Final doküman | Token payı | Lisans / kullanım |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for s, (name, typ, ek) in SRC.items():
        raw = ext.get("per_source", {}).get(ek, {}).get("raw", 0)
        lang = Counter(d["language"] for d in by[s]).most_common(1)[0][0] if by[s] else "-"
        md.append(f"| {name} | {typ} | {lang} | {n(raw)} | {n(len(by[s]))} | "
                  f"{pc(sum(d['token_count'] for d in by[s]), total_tok)} | {LICENSE[s]} |")
    md += [f"| **Toplam** | | | **{n(raw_total)}** | **{n(len(docs))}** | %100 | |", "",
           "Kaynakların neden seçildiği, lisans ayrıntıları ve kullanılmayan kaynaklar (NASA Exoplanet Archive: "
           "final dönemde RAG; Stack Exchange: yalnız instruction verisi) için: "
           "[reports/source_notes.md](reports/source_notes.md), [reports/source_inventory.csv](reports/source_inventory.csv).",
           "",
           f"İngilizce kaynaklar bilinçli olarak çoğunluktadır: alanın güvenilir ve açık lisanslı birincil kaynakları "
           f"(NASA, ders kitabı, makale özetleri) İngilizcedir. Türkçe Wikipedia, modelin Türkçe astronomi "
           f"terminolojisini görmesi için eklenmiştir ve token'ların {tr_ek(pc(lang_tok.get('tr', 0), total_tok), 'iyelik_belirtme')} oluşturur.", "",
           "## Veri toplama",
           f"Dokümanlar {dates[0] if dates else '-'} – {dates[-1] if dates else '-'} tarihleri arasında "
           "`scripts/01_download.py` ile indirildi. science.nasa.gov `robots.txt` kurallarına uyuldu (istekler arası "
           f"{CFG['http']['delay_seconds']} sn); Wikipedia isteklerinde iletişim bilgili User-Agent kullanıldı ve "
           "Wikimedia hız sınırlarına uyuldu; arXiv OAI-PMH'de istekler arası "
           f"{CFG['http']['arxiv_delay_seconds']} sn beklendi. Ham dosyalar `data/raw/` altında değiştirilmeden saklanır; "
           "her dosya için URL, SHA-256, erişim zamanı ve lisans `manifest.jsonl` dosyalarında kayıtlıdır.", "",
           "NASA Science'ta tek bir görevin (ör. Hubble, Cassini) corpus'u domine etmemesi için görev/bölüm başına en "
           f"fazla {CFG['sources']['nasa_science']['max_per_group']} sayfa alındı; APOD'dan 1995–2026 arasında her yıldan "
           f"{CFG['sources']['nasa_apod']['per_year']} açıklama örneklendi (seed {CFG['project']['random_seed']}).", "",
           "## İşleme adımları",
           f"- **Extraction:** HTML için Trafilatura (başarısız olursa BeautifulSoup), PDF için PyMuPDF "
           f"([pdfplumber ile karşılaştırma](reports/extraction_tool_comparison.md): eşit kalite, {speedup()}). PDF "
           f"metin blokları sayfa konumuna göre sıralandı (kenar kutularının paragraflara karışması önlendi). "
           f"{n(reasons.get('extraction_error', 0))} doküman boş/çok kısa çıktı verdiği için"
           + (f", {n(reasons['download_error'])} doküman indirme hatası nedeniyle" if reasons.get("download_error") else "")
           + " elendi; OpenStax'ta "
           f"{n(reasons.get('non_content_section', 0))} bölüm (alıştırma, kaynakça, ekler) içerik dışı sayıldı. Toplam başarısız extraction: "
           f"{n(st.get('extraction_failed', 0))} / {n(st.get('raw', 0))} ({pc(st.get('extraction_failed', 0), st.get('raw', 1))}).",
           "- **Cleaning:** HTML etiket/entity kalıntıları (`<sup>x</sup>` → `^x`), Unicode NFKC (üs ifadeleri önce `10^23` "
           "biçimine alınarak), whitespace normalizasyonu, PDF "
           "header/footer ve bölüm başlığı satırları, site menüleri ve tekrar eden şablon satırları, kesik tanıtım "
           "cümleleri, Wikipedia kaynakça/yayın listesi bölümleri, 'Soyadı, A. B. (yıl). Başlık. Dergi' biçimiyle başlayan "
           "kaynakça girdisi satırları (metin içi atıflar korunarak), görsel kredileri, 20 karakterden kısa yalnız satırlar. Sayılar ve "
           "formüller silinmedi. Kural listesi ve uygulama sayıları: [reports/cleaning_rules.md](reports/cleaning_rules.md); "
           "öncesi/sonrası örnekleri: [reports/cleaning_examples.md](reports/cleaning_examples.md)." +
           (f" Elle incelemede bulunan üç sorun ikinci bir geçişte (`scripts/06b_repost_dedup.py`) düzeltildi: "
            f"(1) Wikipedia düz metin servisi, trafilatura ve PyMuPDF HTML/PDF üst simgelerini sildiği için kaybolan "
            f"üsler geri yazıldı ({n(d2.get('exponent_fixes', 0))} ifade; \"1.5 × 108 km\" → \"1.5 × 10^8 km\"); "
            f"(2) NASA basın bültenlerindeki künye, kredi ve iletişim satırları ile **kişisel iletişim bilgileri "
            f"(e-posta, telefon)** silindi ({n(d2.get('press_docs_touched', 0))} doküman; kalan e-posta/telefon: 0); "
            f"(3) NASA sözlük sayfalarında kısa satır kuralının sildiği terimler geri getirildi."
            if d2 else ""),
           f"- **Filtering:** {CFG['filtering']['min_chars']} karakterden kısa ({n(reasons.get('too_short', 0))}), bozuk "
           f"karakter oranı {tr_ek('%' + str(int(100 * CFG['filtering']['max_garbled_ratio'])), 'belirtme')} aşan veya çoğu simgeden oluşan "
           f"({n(reasons.get('garbled', 0))}), İngilizce/Türkçe dışındaki ({n(reasons.get('wrong_language', 0))}), "
           f"satırlarının yarısından fazlası kaynakça girdisi olan yayın listesi ({n(reasons.get('reference_list', 0))}) ve "
           f"alan dışı ({n(reasons.get('out_of_domain', 0))}) dokümanlar elendi. Alan tespiti astronomi terim sözlüğü "
           "yoğunluğu ile yapıldı (`scripts/domain_lexicon.py`). Wikipedia'da kategori gezintisi alt kategorilere indiği "
           "için kurgu, film, oyun, bayrak, genel spektroskopi ve jeoloji maddeleri de seçilmişti; her maddenin kendi "
           f"Wikipedia kategorilerine dayanan ek kuralla {n(reasons.get('out_of_domain_category', 0))} madde elendi "
           "(kalibrasyonu: [experiments.md](experiments.md)).",
           f"- **Deduplication:** exact duplicate SHA-256 ile ({n(ded.get('exact_duplicates', 0))} doküman), near "
           f"duplicate MinHash LSH (kelime {ded.get('shingle_words')}-gram, {ded.get('num_perm')} permütasyon) + Jaccard ≥ "
           f"{ded.get('threshold')} ile ({n(ded.get('near_duplicates', 0))} doküman). " + near_dup_sentence(qc) +
           (f" Eşik incelemesi, APOD'un aynı açıklamayı yıllar sonra küçük düzeltmelerle yeniden yayımladığı "
            f"sayfaları kaçırdığını gösterdi; ikinci bir geçişte (`scripts/06b_repost_dedup.py`: kelime Jaccard ≥ 0,5 "
            f"ve karakter dizisi benzerliği ≥ 0,85) {n(d2.get('repost_removed', 0))} yeniden yayın tekrarı çıkarıldı "
            f"({n(d2.get('removed_pairs_across_splits', 0))} çift farklı kümelerdeydi, yani sızıntı riski "
            f"taşıyordu). Genel eşik düşürülmedi, çünkü NASA'nın uydu sayfaları ortak şablona rağmen farklı uyduların "
            f"bilgisini taşıyor (Jaccard 0,74'e kadar). Bu adım doküman kimliklerini ve kümeleri değiştirmez."
            if d2 else ""),
           "", "Her çıkarılan doküman nedeniyle birlikte kayıtlıdır: [reports/removed_documents.csv](reports/removed_documents.csv), "
           "[reports/extraction_failures.csv](reports/extraction_failures.csv).", "",
           "## Format",
           "JSONL; her satır bir dokümandır. Alanlar: `document_id`, `title`, `source`, `url`, `language`, "
           "`document_type`, `publication_year`, `subtopic`, `license`, `retrieved_at`, `raw_id`, `group_key`, `split`, "
           "`postprocess` (06b ikinci geçişinden geçtiğini gösterir), "
           "`char_count`, `word_count`, `token_count`, `text`. Dosyalar: `data/final/train.jsonl`, `validation.jsonl`, "
           "`test.jsonl`; paragraf/başlık sınırında üretilmiş chunk'lar `data/final/chunks/` (en fazla "
           f"{CFG['chunking']['max_tokens']} token; alanlar `chunk_id`, `document_id`, `chunk_index`, `char_start`, "
           "`char_end`, `token_count`, `text`; chunk metni dokümanın birebir alt dizisidir).", "",
           "## İstatistikler", "", "| Ölçüt | Değer |", "| --- | --- |",
           f"| Final doküman sayısı | {n(len(docs))} |",
           f"| Toplam kelime | {n(sum(d['word_count'] for d in docs))} |",
           f"| Toplam token ({CFG['tokenizer']['name']} tokenizer) | {n(total_tok)} ({mtok(total_tok)}) |",
           f"| Ortalama doküman uzunluğu | {n(int(td.get('mean', 0)))} token |",
           f"| Medyan doküman uzunluğu | {n(td.get('median', 0))} token |",
           f"| 95. yüzdelik / en uzun | {n(td.get('p95', 0))} / {n(td.get('max', 0))} token |",
           f"| İngilizce / Türkçe (token) | {pc(lang_tok.get('en', 0), total_tok)} / {pc(lang_tok.get('tr', 0), total_tok)} |",
           "", "Alt konu dağılımı (doküman): " + ", ".join(f"{k} {pc(v, len(docs), 0)}" for k, v in sub.most_common()) + ".",
           "", "Ayrıntılı istatistikler ve grafikler: [reports/statistics.md](reports/statistics.md).", "",
           "## Veri ayrımı",
           f"Doküman düzeyinde %{int(100 * CFG['split']['train'])} train ({n(sp['train'])}), "
           f"%{int(100 * CFG['split']['validation'])} validation ({n(sp['validation'])}), "
           f"%{int(100 * CFG['split']['test'])} test ({n(sp['test'])}). Bölme `scripts/06_split.py` içinde "
           f"`random_seed = {CFG['project']['random_seed']}` ile, kaynak bazında tabakalı yapılır. Chunk'lar bölmeden "
           "SONRA üretildiği için aynı dokümanın parçaları tek kümede kalır; aynı Wikipedia maddesinin İngilizce ve "
           "Türkçe sürümleri (aynı Wikidata kimliği) de aynı kümeye düşer. Kümeler arası grup çakışması: 0.", "",
           "## Kalite kontrolü"]
    cr = qc.get("corpus_review", {})
    if cr.get("pre_reviewed") or cr.get("human_reviewed"):
        who = ("nihai karar, grup üyesinin ön inceleme kararlarını onaylamasıyla verildi"
               if cr.get("human_approved_pre") else "nihai karar grup üyesi tarafından verildi")
        md.append(f"Rastgele {cr.get('sample')} doküman (kaynak oranında tabakalı) incelendi: yapay zekâ destekli ön "
                  f"inceleme ölçüt bazında yapıldı, {who}. Ön incelemede uygun: "
                  f"{pc(cr.get('pre_pass_rate', 0), 1)}; nihai kararda uygun: "
                  f"{pc(cr.get('human_pass_rate', 0), 1) if cr.get('human_reviewed') else 'bekleniyor'}. "
                  "Ayrıntı: [reports/quality_control_report.md](reports/quality_control_report.md).")
    else:
        md.append("Rastgele örneklem incelemesi: [reports/quality_control_report.md](reports/quality_control_report.md).")
    md += ["", "## Lisans ve kullanım",
           "Veri seti yalnızca açık erişimli veya açık lisanslı kaynaklardan oluşur; her dokümanın lisansı `license` "
           "alanındadır. **Akademik ve ticari olmayan** amaçla hazırlanmıştır. OpenStax Astronomy 2e (CC BY-NC-SA 4.0) "
           "ve Wikipedia (CC BY-SA 4.0) türevleri aynı koşullarla paylaşılmalıdır. **Kişisel veri:** arXiv yazar adları "
           "saklanmadı, APOD görsel kredi satırları temizlendi. NASA basın bültenlerinde kamuya açık basın iletişim "
           "bilgileri (ad, e-posta, telefon) bulundu ve silindi (NASA kaynaklarında kalan e-posta/telefon: 0). Metinlerde "
           "bilimcilerin ve kamusal kişilerin adları, ansiklopedik/haber içeriğinin parçası olarak geçer. NASA içeriği "
           "NASA'nın onayını ima edecek biçimde kullanılmaz.", "",
           "## Bilinen problemler",
           f"- Kaynak dağılımı dengesizdir: dokümanların {tr_ek(pc(top_n, len(docs)))} {SRC[top_src][0]} kaynağından, "
           f"token'ların en büyük payı {SRC[top_tok_src][0]} kaynağından gelir.",
           f"- Corpus büyük ölçüde İngilizcedir (token'ların {tr_ek(pc(lang_tok.get('en', 0), total_tok))}); hedef kullanıcı "
           "Türkçe konuştuğu için Türkçe davranış ağırlıklı olarak Instruction Dataset ile kazandırılacaktır.",
           "- PDF'teki matematiksel ifadeler görsel/MathML olarak gömülü olduğu için bazı formüller metne çıkmadı "
           "(ör. \"the force would be , or as large\"). Tablolar düz metne dönüştüğünde sütun yapısı kaybolur.",
           "- Wikipedia ikincil kaynaktır; güncel sayısal bilgilerde (ör. ötegezegen sayısı) zamanla eskiyebilir. Bu tür "
           "bilgiler final döneminde RAG katmanından (NASA Exoplanet Archive) sağlanacaktır.",
           "- arXiv özetleri araştırma dilindedir ve başlangıç seviyesindeki kullanıcı için ağırdır; ileri seviye "
           "terminoloji için tutulmuştur.",
           "- Alt konu etiketleri anahtar kelime ve kaynak kategorisine dayalı kural tabanlı bir yöntemle atanmıştır; "
           "birden fazla konuyu kapsayan dokümanlarda tek etiket yetersiz kalabilir (ör. yöntem/yazılım makalelerine "
           "sık sık `observatories_telescopes` atanır)."
           + (f" Elle incelenen {cr['sample']} dokümanın {cr['error_types']['alt_konu_hatali']} tanesinde etiket hatalı "
              "bulundu (ör. ötegezegen sayfasına `stars_stellar_evolution`); bu dokümanların çoğunda metnin kendisi "
              "sorunsuzdu. Etiket yalnız dağılım analizinde ve instruction kaynak dokümanlarının alt konuya göre dengeli "
              "seçiminde kullanılır; eğitim metnini değiştirmez."
              if cr.get("error_types", {}).get("alt_konu_hatali") else ""),
           "- Wikipedia düz metin servisi tabloları çıkarmaz; bazı maddelerde \"aşağıda listelenmektedir\" gibi var olmayan "
           "bir listeye atıf kalır. Wikipedia formülleri `{\\displaystyle ...}` biçiminde LaTeX olarak korunur.",
           "- Kaybolan üslerin yalnız belirsizliği olmayan kalıpları düzeltildi; işaretsiz kalanlar (ör. \"(1031 erg/s)\") "
           "olduğu gibi duruyor.",
           "- Birkaç APOD sayfasında bağlantı metninden kaynaklanan kelime birleşmeleri vardır (\"Galacticwar\", "
           "\"PerseidMeteorShower\").",
           f"- 300–500 karakter aralığında {n(short_band)} doküman vardır; çoğu kısa ama bilgi taşıyan sayfalardır "
           "(Türkçe Wikipedia taslak maddeleri, NASA uydu sayfaları), ancak bir kısmı değeri düşük video/sosyal medya "
           "sayfalarıdır (ör. \"Watch Online\"). Türkçe metin kıt olduğu için alt sınır 500 yerine 300 tutuldu.",
           "- Kaynakta bozuk kodlanmış kesme işareti 4 yerde \"^1\" olarak kalmıştır (\"Saturn^1s\"); 1 APOD sayfasında "
           "(DOC_007977) kaynaktan gelen bir U+FFFD karakteri vardır (\"Don�t\")."]
    ec = R / "eval_contamination.csv"
    if ec.exists():
        with open(ec, encoding="utf-8-sig") as f:
            n_ec = sum(1 for _ in csv.DictReader(f))
        md.append(f"- Değerlendirme setlerinin {n(n_ec)} sorusu corpus ile en az 3 adet 8-gram paylaşır (çoğu genel ifade "
                  "veya tanım cümlesi, ör. \"the big bang theory of the origin of the universe\"). Bu dokümanlar meşru alan "
                  "bilgisi olduğu için çıkarılmadı; sorular [reports/eval_contamination.csv](reports/eval_contamination.csv) "
                  "dosyasında listelidir ve final dönemi karşılaştırmasında ayrıca raporlanacaktır.")
    md += ["",
           "## Sınırlılıklar",
           "Bu corpus bir bilgi tabanı veya doğruluk garantisi değildir; üzerinde eğitilen model güncel astronomik "
           "veriler için birincil kaynakların yerine geçmez. Kapsam, Tasarım raporundaki eğitim konularıyla sınırlıdır.", "",
           "## Sürüm geçmişi",
           "- v0.5 (22.10.2026): İlk extraction ve cleaning denemesi (kısmi veri).",
           "- v0.9 (23.10.2026): Tüm kaynaklar, filtreleme, deduplication ve metadata.",
           "- v0.9.1 (23.10.2026): Kaynakça satırları, yayın listesi sayfaları ve Wikipedia kategori kuralı (alan dışı "
           "356 madde) eklendi.",
           f"- v{CFG['project']['corpus_version']} (24.10.2026): Token sayımı, split; elle kalite kontrolünde bulunan "
           "kaybolmuş üsler, NASA künye/kişisel veri satırları, sözlük terimleri ve APOD yeniden yayın tekrarları "
           "düzeltildi (06b; doküman kimlikleri ve kümeler korunarak).", "",
           "## Yeniden üretme",
           "`pip install -r requirements.txt` ardından `python run_pipeline.py --corpus`. Ayrıntı: [README.md](README.md).", "",
           "## Hazırlayan",
           "Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. "
           "Danışman: Asim Sinan Yüksel."]
    (ROOT / "DATASET_CARD.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log.info("DATASET_CARD.md yazıldı")


def instruction_card() -> None:
    ins = list(read_jsonl(p("final") / "instruction_v1.0.jsonl"))
    if not ins:
        log.warning("Instruction dataset yok, INSTRUCTION_CARD atlandı")
        return
    vs, src_s, qc = j("instruction_verification_summary.json"), j("instruction_sources_summary.json"), j("qc_summary.json")
    I = CFG["instruction"]
    raw = {}
    for r in read_jsonl(p("interim") / "instructions_raw.jsonl"):
        raw[r["raw_example_id"]] = r
    rem = removed_rows("removed_instructions.csv")
    rem_v = Counter(r["reason"].split(":")[0] if not r["reason"].startswith("judge_fail") else "judge_fail"
                    for r in rem if r["stage"] == "verify")
    rem_qc = sum(1 for r in rem if r["stage"] == "qc")
    regen = {r["id"] for r in rem if r["stage"] == "regen"}
    tt = Counter(x["task_type"] for x in ins)
    lv = Counter(x["level"] for x in ins)
    sp = Counter(x["split"] for x in ins)
    meth = Counter(x["generation_method"] for x in ins)
    gm = Counter(x["generator_model"] for x in ins)
    lite = [x for x in ins if "lite" in (x.get("generator_model") or "")]
    flash = [x for x in ins if "lite" not in (x.get("generator_model") or "")]
    lite_n = len(lite)
    lite_len = round(sum(len(x["response"]) for x in lite) / max(len(lite), 1))
    flash_len = round(sum(len(x["response"]) for x in flash) / max(len(flash), 1))
    pv = Counter(x.get("prompt_version") or "v1" for x in ins)
    jm = Counter(x["judge_model"] for x in ins if x.get("judge_model"))
    srcn = Counter(x["source_name"] for x in ins)
    n_docs = len({x["source_document"] for x in ins if x["source_name"] not in ("stackexchange_space_qa", "none")})
    target = I["taxonomy"]
    md = [f"# AstroTutor AI Türkçe Instruction Dataset v{CFG['project']['instruction_version']}", "",
          "## Amaç",
          "Bu veri seti, [Domain Corpus](DATASET_CARD.md) ile alana uyarlanacak modele **supervised fine-tuning (SFT)** "
          "ile şu davranışları kazandırmak için hazırlanmıştır: kullanıcının seviyesine (başlangıç / orta / ileri) "
          "göre Türkçe konu anlatımı, verilen öğretim metninden JSON biçiminde dört seçenekli soru üretme, astronomi "
          "terminolojisiyle doğru açıklama ve bilgisi/kapsamı dışındaki sorularda sınırını bildirme.", "",
          "## Format",
          "JSONL; her satır bir örnektir. SFT için `messages` alanı kullanılır (`user` / `assistant`). İzlenebilirlik "
          "alanları: `id`, `source_document` (corpus `document_id`'si veya Stack Exchange soru kimliği), `source_url`, "
          "`task_type`, `level`, `supporting_evidence` (cevabı destekleyen kaynak alıntısı), `generation_method`, "
          "`generator_model`, `prompt_version`, `auto_verified`, `llm_judged`, `judge_model`, `human_verified`, "
          "`verified_by`, `license`, `split`, `raw_example_id` (üretim kaydı), `postprocess` (kural tabanlı metin düzeltmesi, ör. `kaynak_atfi_silindi`; yoksa boş).", "",
          "Dosyalar: `data/final/instruction_v1.0.jsonl` (tamamı) ve `data/final/instruction/{train,validation,test}.jsonl`.", "",
          "## Görev türü dağılımı", "", "| Görev türü | Örnek | Oran | Hedef oran |", "| --- | --- | --- | --- |"]
    for t in target:
        md.append(f"| {TASK_TR.get(t, t)} (`{t}`) | {n(tt.get(t, 0))} | {pc(tt.get(t, 0), len(ins))} | "
                  f"{pc(target[t], 1, 0)} |")
    md += [f"| **Toplam** | **{n(len(ins))}** | %100 | |", "",
           "Taksonominin gerekçesi ve her türden örnekler: [reports/instruction_taxonomy.md](reports/instruction_taxonomy.md).", "",
           "Seviye dağılımı: " + ", ".join(
               f"{ {'baslangic': 'başlangıç', 'orta': 'orta', 'ileri': 'ileri'}.get(k, k)} (`{k}`) {n(v)} ({pc(v, len(ins), 1)})"
               for k, v in lv.most_common()) + ".", "",
           "## Örneklerin üretimi",
           f"- **Kaynaklar:** Domain Corpus'tan {n(n_docs)} doküman ({n(srcn.get('openstax_astronomy_2e', 0) + srcn.get('nasa_science', 0) + srcn.get('wikipedia_en', 0) + srcn.get('wikipedia_tr', 0) + srcn.get('nasa_apod', 0) + srcn.get('arxiv_astro_ph', 0))} örnek), "
           f"Stack Exchange Space/Astronomy soru-cevapları ({n(srcn.get('stackexchange_space_qa', 0))} örnek; "
           f"{n(src_s.get('stackexchange_candidates_selected', 0))} seçilmiş soru) ve kaynak dokümansız kapsam dışı "
           f"örnekler ({n(srcn.get('none', 0))}).",
           "- **Yöntem:** LLM destekli sentetik üretim. Her çağrıda tek bir kaynak doküman ve o dokümana atanmış görev "
           "türleri/seviyeler verilir; model yalnızca kaynaktaki bilgiyi kullanmak ve cevabı destekleyen alıntıyı "
           "kaynaktan kelimesi kelimesine kopyalamak zorundadır. Stack Exchange örneklerinde soru ve kabul edilmiş/en "
           "yüksek puanlı cevap Türkçeye aktarılıp düzenlenmiştir (kullanıcı adı, bağlantı ve kişisel yorumlar çıkarıldı).",
           "- **Model:** Google Gemini API (ücretsiz katman). Katmanın model başına günlük istek sınırı nedeniyle aynı "
           "aileden birden fazla Flash modeli havuz olarak kullanılmış, her örnekte gerçekte kullanılan model "
           "kaydedilmiştir: " + ", ".join(f"{k} ({n(v)})" for k, v in gm.most_common()) + ".",
           f"- **Parametreler:** sıcaklık {I['temperature']}, düşünme seviyesi `{I.get('generator_thinking_budget')}`, "
           f"en fazla {n(I['max_output_tokens'])} çıktı token'ı. Prompt sürümleri (örnek sayısı): "
           + ", ".join(f"`{k}` ({n(v)})" for k, v in sorted(pv.items())) + ". Prompt metinleri: "
           + ", ".join(f"[prompts/{k}/](prompts/{k}/)" for k in sorted(pv)) + " (`system_generate.txt`, "
           "`generate_doc.txt`, `generate_se.txt`, `generate_refusal.txt`, `task_types.json`). Sürümler, doğrulamada "
           "bulunan kusurların kaynağında önlenmesi için eklendi: **v1.1** çoktan seçmeli görev tanımına 'talimatta "
           "soru, şık veya doğru cevap yer almaz', sistem prompt'una 'Türkçeye özgü harfleri (ç, ğ, ı, ö, ş, ü) ASCII "
           "karşılıklarıyla değiştirme'; **v1.2** ayrıca 'kullanıcı kaynağı görmediği için cevaplarda da \"metne "
           "göre\", \"kaynakta\" deme' ve sınıflandırmada öğelerin talimatta açıkça sayılması kurallarını ekler.",
           "- Üretim yöntemlerine göre: " + ", ".join(f"`{k}` {n(v)}" for k, v in meth.most_common()) + ".", "",
           "## Doğrulama",
           f"Toplam **{n(len(raw))}** örnek üretildi; doğrulamadan sonra **{n(len(ins))}** örnek kaldı. "
           f"Ayrıca çıktısı iş düzeyinde kusurlu bulunan {n(len(regen))} iş (Türkçe karakter kaybı veya çoktan seçmeli "
           "talimatta soru verilmesi) arşivlenip yeniden üretildi; üretim sırasında aynı nedenlerle reddedilen çıktılar "
           "hiç kaydedilmedi. Bir LLM'in ürettiği cevap doğru kabul edilmedi; dört aşamalı kontrol uygulandı:", "",
           "1. **Kural kontrolleri** (tüm örnekler): Türkçe dil tespiti, uzunluk sınırları, görev türü tutarlılığı, "
           "çoktan seçmeli JSON şeması (4 seçenek, tek doğru cevap), talimatta öğretim metninin bulunması ve sorunun, "
           "şıkların, doğru cevabın veya öğrenciye sorulacak sorunun verilmemesi, Türkçe karakter eksikliği ('ı' "
           "harfinin düşmesi dahil), kaybolmuş üs, kişisel iletişim bilgisi, LaTeX artığı, URL, kaynağı "
           "görmeyen kullanıcıya talimatta veya cevapta 'metne göre' gibi atıf, birebir ve yakın tekrar (MinHash, "
           f"Jaccard ≥ 0,8), değerlendirme setleriyle {I['decontam_ngram']}-gram örtüşmesi."
           + (f" Öğeleri talimatta sayılmış {n(vs['rule_fixes']['kaynak_atfi_silindi'])} sınıflandırma talimatının "
              "başındaki \"Metinde adı geçen\" gibi atıf ifadesi silindi (örnek elenmedi; `postprocess` alanında "
              "işaretli)." if vs.get("rule_fixes", {}).get("kaynak_atfi_silindi") else "")
           + (f" {n(vs['rule_fixes']['adim_yazimi_duzeltildi'])} cevapta \"Adim\" yazımı \"Adım\" olarak düzeltildi."
              if vs.get("rule_fixes", {}).get("adim_yazimi_duzeltildi") else ""),
           f"2. **Kanıt kontrolü** (kaynağı olan tüm örnekler): `supporting_evidence` alıntısının kelime 5-gram'larının en "
           f"az {tr_ek('%' + str(int(100 * I['evidence_min_overlap'])))} kaynak metinde bulunmalıdır; bulunmayan örnek uydurma kaynak "
           "riski nedeniyle elenir.",
           f"3. **LLM yargıç** (işlerin %{int(100 * I['judge_sample_fraction'])}'luk tabakalı rastgele örneklemi, "
           f"{n(vs.get('judged_examples', 0))} örnek): örneği üreten modelden **farklı** bir model, sıcaklık 0 ile her "
           "örneği kaynağıyla birlikte desteklenme, doğruluk, talimata uyma, anlaşılırlık ve Türkçe akıcılık açısından "
           f"değerlendirdi. Başarısız oranı: **{pc(vs.get('judge_fail', 0), vs.get('judged_examples') or 0)}** "
           "(tüm set için tahmini hata oranı); başarısızlar elendi. Yargıç modelleri: "
           + (", ".join(f"{k} ({n(v)})" for k, v in jm.most_common()) or "-") + "."
           + (" Örneklem ilk çalıştırmada sabitlendi (sonradan eklenen kurallar örneklemi değiştirmesin diye)."
              + "".join(f" {lab} üretimlerinde başarısız: {n(g['fail'])}/{n(g['judged'])}"
                        f" ({pc(g['fail'], g['judged'])});" for lab, g in
                        (("Lite", vs['judge_by_generator']['lite']), ("Flash", vs['judge_by_generator']['flash']))
                        if g['judged']).rstrip(";") + "."
              if vs.get("judge_by_generator") else "")
           + (f" Örneklemdeki {n(vs['judge_gave_up_jobs'])} işte yargıç iki denemede tüm örnekleri değerlendiremedi; "
              f"bu işlerin değerlendirilmeyen {n(vs.get('judge_unjudged_examples_in_sample', 0))} örneği yalnız kural ve "
              "kanıt kontrolüyle sette kaldı (`llm_judged=false`)." if vs.get("judge_gave_up_jobs") else ""),
           "4. **Rastgele örneklem incelemesi:** "]
    ir = qc.get("instruction_review", {})
    rev_f = p("qc") / "instruction_review.csv"
    rev_rows = list(csv.DictReader(open(rev_f, encoding="utf-8-sig"))) if rev_f.exists() else []
    adim = [r for r in rev_rows if r["task_type"] == "adim_adim_problem_cozme"]
    adim_rev = (len(adim), sum(1 for r in adim if (r.get("son_karar") or r.get("claude_karar")) == "sorunlu"))
    if ir.get("pre_reviewed") or ir.get("human_reviewed"):
        md[-1] += (f"{ir.get('sample')} örnek (görev türü oranında tabakalı) kaynak metniyle karşılaştırılarak incelendi. "
                   f"Yapay zekâ destekli ön inceleme ölçüt bazında yapıldı; nihai kararı grup üyesi verdi. Ön incelemede "
                   f"uygun: {pc(ir.get('pre_pass_rate', 0), 1)}; nihai kararda uygun: "
                   f"{pc(ir.get('human_pass_rate', 0), 1) if ir.get('human_reviewed') else 'bekleniyor'}"
                   + (f"; iki aşamanın uyuşma oranı {pc(ir.get('agreement', 0), 1)}" if ir.get("agreement") is not None else "")
                   + f". Sorunlu bulunan {n(qc.get('instruction_removed_in_qc', 0))} örnek setten çıkarıldı.")
    else:
        md[-1] += "bkz. [reports/quality_control_report.md](reports/quality_control_report.md)."
    md += ["", "**Elenen örnekler** (nedenleriyle: [reports/removed_instructions.csv](reports/removed_instructions.csv)):", "",
           "| Neden | Adet |", "| --- | --- |"]
    md += [f"| {k} | {n(v)} |" for k, v in rem_v.most_common()]
    if rem_qc:
        md.append(f"| örneklem incelemesinde sorunlu | {n(rem_qc)} |")
    md += ["", "## Veri ayrımı ve sızıntı önleme",
           f"train {n(sp['train'])} · validation {n(sp['validation'])} · test {n(sp['test'])}.", "",
           "- Corpus dokümanından üretilen örnekler, kaynak dokümanın **corpus'taki kümesini** miras alır. Böylece aynı "
           "dokümandan gelen örnekler farklı kümelere dağılmaz ve corpus test dokümanından üretilen bir örnek SFT "
           "eğitimine girmez (CPT ile SFT arasında da sızıntı yok).",
           f"- Stack Exchange örnekleri soru kimliğine, kapsam dışı örnekler kendi kimliğine göre gruplanır; her grubun "
           f"kümesi seed {CFG['project']['random_seed']} ve grup kimliğinin hash'inden belirlenir (bir grubun elenmesi "
           "diğerlerinin kümesini değiştirmez).",
           "- Değerlendirme setleri (Astro-mcqa, astro-mcq, HubbleSpaceTelescope-MCQ, AstroMLab Astrobench) eğitime "
           f"alınmadı; bunlarla {I['decontam_ngram']}-gram örtüşmesi olan örnekler elendi. Örnekler Türkçe olduğu için "
           "İngilizce kaynaklar (Stack Exchange soruları, kaynak doküman pasajları) da değerlendirme setleriyle "
           "karşılaştırıldı; aynı soru bulunmadı, yalnız genel ifadeler örtüşüyor (bkz. experiments.md).", "",
           "## Değerlendirme planı (final dönemi)",
           "Vize kapsamında ayrı bir değerlendirme seti hazırlanmadı; başarı şu şekilde ölçülecek:",
           "- **Dış değerlendirme setleri** (eğitime girmedi): AstroMLab Astrobench, Astro-mcqa, astro-mcq, "
           "HubbleSpaceTelescope-MCQ — çoktan seçmeli doğruluk. Corpus ile örtüşen sorular "
           "[reports/eval_contamination.csv](reports/eval_contamination.csv) dosyasında listelidir ve ayrıca raporlanacaktır.",
           f"- **Bu setin test kümesi** ({n(sp['test'])} örnek; corpus kaynaklı olanlar yalnız corpus test dokümanlarından üretildi): Türkçe "
           "talimat takibi, seviyeye uygunluk ve JSON soru üretiminin geçerliliği (şema, tek doğru cevap, kaynakla tutarlılık).",
           "- Üç sistem karşılaştırılacak: hazır instruct model, alana uyarlanmış (CPT) model, CPT + SFT.", "",
           "## Sınırlılıklar",
           "Örnekler sentetiktir ve kaynak dokümanlardaki bilgiyle sınırlıdır; güncel astronomik veriler (ör. "
           "ötegezegen sayısı) için birincil kaynakların yerine geçmez. Seviye etiketleri üretim sırasında atanmıştır; "
           "seviyeye uygunluk yalnız yargıç ve örneklem incelemesiyle kontrol edilmiştir. Tüm örnekler tek turlu "
           "(kullanıcı → asistan) diyaloglardır.", "",
           "## Sürüm geçmişi",
           "- v0.1 (22.10.2026): Pilot üretim (11 örnek, eski prompt; veri setine alınmadı).",
           "- v0.9 (23.10.2026): Stack Exchange, kapsam dışı ve doküman işleri; Türkçe karakter kontrolü.",
           "- v1.0 (24–26.10.2026): ek paketler (ek1–ek3), prompt v1.1/v1.2, çoktan seçmeli sızıntı ve görünmeyen metne "
           "atıf kuralları, LLM yargıç örneklemi, 150 örneklik inceleme.",
           "- Planlanan v1.1 (final dönemi öncesi): yargıcın örneklem dışındaki bütün lite üretimi işlere genişletilmesi "
           "(`11_verify_instructions.py --extended`); elenenler `judge_ext_fail` nedeniyle ayrı kaydedilir.", "",
           "## Lisans",
           "Her örnek kaynağının lisansını `license` alanında taşır. Stack Exchange türevleri CC BY-SA 4.0, OpenStax "
           "türevleri CC BY-NC-SA 4.0, Wikipedia türevleri CC BY-SA 4.0 koşullarına tabidir; veri seti akademik ve "
           "ticari olmayan amaçla hazırlanmıştır. Örnekler Gemini API ile üretildiği için Google'ın Gemini API kullanım "
           "koşulları da geçerlidir (koşullar, Gemini ile rekabet eden model geliştirmeyi kısıtlar; bu çalışma küçük "
           "ölçekli, akademik bir alan modelidir).", "",
           "## Bilinen problemler",
           "- Sentetik üretim nedeniyle bazı cevaplarda çeviri kokan ifadeler veya küçük yazım hataları kalabilir; "
           "örneklem incelemesindeki hata türleri kalite raporundadır.",
           "- Kanıt kontrolü cevabın tamamını değil, modelin gösterdiği alıntıyı doğrular; alıntı dışındaki bir cümlede "
           "hata kalma olasılığı LLM yargıç ve örneklem incelemesiyle ölçülmüştür, sıfır değildir.",
           "- Örnekler birden fazla Gemini modeliyle üretildiği için üslupta küçük farklılıklar olabilir. Ücretsiz "
           f"katmanın Flash kotası yetmediği için örneklerin {tr_ek(pc(lite_n, len(ins)))} lite modellerle üretildi; lite "
           f"cevaplar daha kısadır (ortalama {n(lite_len)} karakter, Flash {n(flash_len)}) ve Türkçe karakter kaybı, "
           "talimatta soru verme gibi kusurlar lite çıktılarında yoğunlaştı (bu kusurlu örnekler elendi).",
           "- Stack Exchange cevaplarının bir kısmı uzay mühendisliği ağırlıklıdır; kaynak verideki kaybolmuş üsler "
           "(\"× 1030 kg\") otomatik düzeltildi, ancak benzer biçim bozuklukları tamamen dışlanamaz.",
           "- Kapsam dışı örnekler kaynak dokümansızdır; doğrulukları yalnız yargıç ve inceleme ile kontrol edildi.",
           "- Örnekler kaynağa sadıktır; kaynaktaki hata da örneğe geçebilir. Örneklem incelemesinde bu türden bulunan "
           "hatalar: Türkçe Wikipedia'daki \"1921'de Birleşmiş Milletler Radyum Kurumu\" (BM 1945'te kuruldu), Büyük "
           "Patlama'nın \"birkaç milimetrelik bir noktadan patlama\" diye anlatılması, bilimsel olarak eksik bir Stack "
           "Exchange cevabı (Titan atmosferi). Bu örnekler çıkarıldı; benzerleri yargıç ve incelemenin dışında kalan "
           "örneklerde bulunabilir.",
           (f"- `adim_adim_problem_cozme` türü en zayıf türdür: incelenen {n(adim_rev[0])} örneğin "
            f"{n(adim_rev[1])} tanesi sorunluydu; çoğunda çözülecek bir hesap veya süreç yoktu, bilgiler adım gibi "
            "sıralanmıştı (yargıç da bu örnekleri eledi)." if adim_rev[1] else
            "- `adim_adim_problem_cozme` örneklerinde bilgilerin adım gibi sıralandığı, çözülecek hesap içermeyen "
            "örnekler bulunabilir."),
           "- Yargıç yalnız %10'luk örneklemde çalıştı; örneklem dışındaki lite üretimi örneklerin bir kısmında benzer "
           "kusurlar kalmış olabilir (tahmini oran yukarıda). Final dönemi eğitiminden önce ek yargıçla temizlenmesi "
           "planlanmıştır (v1.1).", "",
           "## Hazırlayan",
           "Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. "
           "Danışman: Asim Sinan Yüksel."]
    (ROOT / "INSTRUCTION_CARD.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log.info("INSTRUCTION_CARD.md yazıldı")


def source_inventory() -> None:
    """reports/source_inventory.csv — Rehber §4 sütunları; doküman sayıları final veriden."""
    docs = [d for s in ("train", "validation", "test") for d in read_jsonl(p("final") / f"{s}.jsonl")]
    ins = list(read_jsonl(p("final") / "instruction_v1.0.jsonl"))
    by = Counter(d["source"] for d in docs)
    first = {}
    for d in docs:
        if d.get("retrieved_at"):
            first[d["source"]] = min(first.get(d["source"], "9999"), d["retrieved_at"][:10])
    se_n = sum(1 for x in ins if x["source_name"] == "stackexchange_space_qa")
    tok = Counter()
    for d in docs:
        tok[d["source"]] += d.get("token_count") or 0
    ext = json.loads((R / "extraction_summary.json").read_text(encoding="utf-8"))["per_source"]
    raw_n = {("openstax_astronomy_2e" if k == "openstax" else k): v["raw"] for k, v in ext.items()}
    se_sum = json.loads((R / "instruction_sources_summary.json").read_text(encoding="utf-8"))
    rows = [
        ("nasa_science", "https://science.nasa.gov/", "HTML", "en", "Domain Corpus: güvenilir birincil kaynak; görev başına en fazla 150 sayfa"),
        ("nasa_apod", "https://science.nasa.gov/apod/archive/", "HTML", "en", "Domain Corpus: popüler bilim düzeyinde kısa açıklamalar; yıl başına 85 örnek (API çalışmadığı için site sayfalarından)"),
        ("openstax_astronomy_2e", "https://openstax.org/details/books/astronomy-2e", "PDF", "en", "Domain Corpus: hakemli açık ders kitabı; kavramsal bütünlük"),
        ("arxiv_astro_ph", "https://arxiv.org/archive/astro-ph", "XML", "en", "Domain Corpus: ileri seviye terminoloji; yalnız başlık+özet"),
        ("wikipedia_en", "https://en.wikipedia.org/", "HTML/API", "en", "Domain Corpus: ikincil, durağan ansiklopedik bilgi"),
        ("wikipedia_tr", "https://tr.wikipedia.org/", "HTML/API", "tr", "Domain Corpus: Türkçe astronomi terminolojisi"),
    ]
    out = R / "source_inventory.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_name", "url", "type", "language", "raw_document_count", "document_count", "token_count",
                    "access_date", "license", "notes"])
        for s, url, typ, lang, note in rows:
            w.writerow([s, url, typ, lang, raw_n.get(s, ""), by.get(s, 0), tok.get(s, 0), first.get(s, ""),
                        LICENSE[s], note])
        w.writerow(["stackexchange_space_qa", "https://huggingface.co/datasets/juliensimon/stackexchange-space-qa",
                    "dataset", "en", se_sum.get("stackexchange_total", ""), se_n, "", "2026-10-22", "CC BY-SA 4.0",
                    "Yalnız Instruction Dataset (soru_cevap); raw = veri setindeki kayıt, document_count = final "
                    "instruction örneği"])
        w.writerow(["nasa_exoplanet_archive", "https://exoplanetarchive.ipac.caltech.edu/", "structured_data", "en",
                    "", 0, "", "", "Atıf gerekli",
                    "Corpus'a alınmadı; final dönemde RAG kaynağı (güncel, değişken tablo verisi)"])
        for repo in CFG["sources"]["eval_reference"]:
            w.writerow(eval_reference_row(repo))
    log.info("source_inventory.csv yazıldı")


def eval_reference_row(repo: str) -> list:
    """Değerlendirme seti satırı: soru sayısı, erişim tarihi ve lisans indirilen dosyalardan okunur."""
    import glob
    import re

    import pandas as pd

    d = p("eval_reference") / repo.replace("/", "__")
    n_rows = 0
    for f in glob.glob(str(d / "**" / "*"), recursive=True):
        if f.endswith(".parquet"):
            n_rows += len(pd.read_parquet(f))
        elif f.endswith(".csv"):
            n_rows += len(pd.read_csv(f))
    man = d / "manifest.jsonl"
    date = json.loads(man.read_text(encoding="utf-8").splitlines()[0])["retrieved_at"][:10] if man.exists() else ""
    card = (d / "README.md").read_text(encoding="utf-8") if (d / "README.md").exists() else ""
    m = re.search(r"^license:\s*(\S+)", card, re.M) or re.search(r"\*\*License\*\*:\s*([^\n]+)", card)
    lic = m.group(1).strip().upper().replace("CC-BY-", "CC BY ") if m else "Veri kartında lisans belirtilmemiş"
    return [repo.split("/")[-1], f"https://huggingface.co/datasets/{repo}", "dataset", "en", n_rows or "", 0, "", date,
            lic, "Yalnız değerlendirme ve sızıntı (8-gram) kontrolü; eğitime girmez, dağıtılmaz"]


if __name__ == "__main__":
    dataset_card()
    instruction_card()
    source_inventory()
