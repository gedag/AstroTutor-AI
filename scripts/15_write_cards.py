"""15 — DATASET_CARD.md ve INSTRUCTION_CARD.md dosyalarını üretir (Vize Rehberi §13).

Kartlardaki tüm sayılar pipeline raporlarından ve final veri dosyalarından OKUNUR, elle yazılmaz.
Veri değiştiğinde (ör. kalite kontrol sonrası) bu script yeniden çalıştırılarak kartlar güncellenir.
"""
from __future__ import annotations

import csv
import json
from collections import Counter

from common import CFG, CORPUS_SOURCES, ROOT, get_logger, instruction_file, p, read_jsonl, tr_ek, tr_num

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
    # v2.0 (İngilizce)
    "definition_explanation": "Tanım ve açıklama",
    "leveled_explanation": "Seviyeye göre ders anlatımı",
    "mcq_generation": "Çoktan seçmeli soru üretimi (JSON)",
    "question_answering": "Soru-cevap (Stack Exchange, orijinal İngilizce)",
    "comparison": "Karşılaştırma",
    "cause_effect": "Neden-sonuç",
    "summarization": "Özetleme",
    "step_by_step_problem_solving": "Adım adım problem çözme",
    "classification": "Sınıflandırma",
    "out_of_scope_refusal": "Kapsam dışı / bilgi yetersizliği ve yanlış öncül düzeltme",
    # v1.0 (Türkçe arşiv uyumluluğu)
    "tanim_aciklama": "Tanım ve açıklama", "seviyeli_anlatim": "Seviyeye göre ders anlatımı",
    "coktan_secmeli_soru_uretimi": "Çoktan seçmeli soru üretimi (JSON)", "soru_cevap": "Soru-cevap (Stack Exchange)",
    "karsilastirma": "Karşılaştırma", "neden_sonuc": "Neden-sonuç", "ozetleme": "Özetleme",
    "adim_adim_problem_cozme": "Adım adım problem çözme", "siniflandirma": "Sınıflandırma",
    "bilgi_yetersizligi_kapsam_disi": "Bilgi yetersizliği / kapsam dışı",
}
LEVEL_TR = {
    "beginner": "başlangıç", "intermediate": "orta", "advanced": "ileri",
    "baslangic": "başlangıç", "orta": "orta", "ileri": "ileri",
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


SRC_LABEL = {"nasa_apod": "APOD", "nasa_science": "NASA Science"}


def repost_rules(d2: dict) -> str:
    """06b yeniden yayın kurallarını kaynak bazında yazar (eşikler 06b'nin özetinden okunur)."""
    r = d2.get("rules", {})
    parts = [f"{SRC_LABEL.get(s, s)} için kelime Jaccard ≥ {tr_num(v['jaccard'])} ve karakter dizisi benzerliği "
             f"≥ {tr_num(v['char_ratio'])}" for s, v in r.items()]
    return "; ".join(parts) if parts else "kelime Jaccard ve karakter dizisi benzerliği"


OTHER_LABEL = {"contact_page": "iletişim sayfası", "fiction_work_06b": "kurgu/eser maddesi",
               "too_short_after_06b": "temizlik sonrası alt uzunluk sınırının altına düşen",
               "list_page_06b": "liste/haber sayfası"}
LANG_NAME = {"en": "İngilizce", "tr": "Türkçe"}


def list_page_sentence(d2: dict) -> str:
    """Liste/haber sayfası incelemesi (Corpus v2.0): sayılar inceleme tablosundan ve 06b özetinden okunur."""
    f = ROOT / CFG["corpus"]["list_page_review_file"]
    if not f.exists():
        return ""
    with open(f, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    thr = CFG["corpus"]["list_page_candidate_ratio"]
    dec = Counter((r.get("son_karar") or "").strip() for r in rows)
    if not dec.get("cikar"):
        return ""
    manual = sum(1 for r in rows if float(r["cumle_orani"]) >= thr)
    # "cikar" kararı verilen bazı sayfalar 06b'de daha önce "temizlik sonrası çok kısa" nedeniyle elenir
    removed_here = d2.get("other_removed", {}).get("list_page_06b", 0)
    earlier = dec["cikar"] - removed_here
    return (f"- **Liste/haber sayfaları (v2.0):** NASA Science ve APOD'da cümle oranı (noktalı cümle içeren satırlardaki "
            f"kelimelerin payı) {tr_num(thr)} altında kalan sayfalar"
            + (f" ve elle eklenen {manual} galeri sayfası" if manual else "")
            + f", toplam {len(rows)} aday, yapay zekâ destekli ön incelemeyle tek tek değerlendirildi ve grup üyesinin "
            f"onayıyla karar verildi ([reports/qc/list_page_review.csv](reports/qc/list_page_review.csv); adaylar "
            f"`scripts/list_page_candidates.py`, çıkarma 06b). Bilgi taşımayan {dec['cikar']} sayfa (okul müfredatı "
            f"standart tabloları, araştırma fonu çağrıları, haber başlığı, dosya ve broşür listeleri, indirme ve galeri "
            f"sayfaları) çıkarıldı"
            + (f" ({removed_here} tanesi bu nedenle; {earlier} tanesi temizlik sonrası çok kısa kaldığı için zaten "
               f"elenmişti)" if earlier else "")
            + f"; bilgi taşıyan {dec.get('tut', 0)} tablo sayfası (uydu tabloları, Ay görevleri, "
            f"Cassini yakın geçiş verileri ve haftalık raporları) tutuldu. Eşik tek başına karar vermez; yalnız aday "
            f"bulur.")


def other_removed_sentence(d2: dict) -> str:
    o = {k: v for k, v in d2.get("other_removed", {}).items() if v}
    if not o:
        return ""
    det = ", ".join(f"{OTHER_LABEL.get(k, k)} {v}" for k, v in o.items())
    return f" Aynı geçişte {n(sum(o.values()))} doküman daha elendi ({det})."


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
    # yalnız bu sürümde corpus'a giren kaynaklar (v2.0: wikipedia_tr yok)
    by = {s: [d for d in docs if d["source"] == s] for s, (_, _, ek) in SRC.items() if ek in CORPUS_SOURCES}
    total_tok = sum(d["token_count"] for d in docs)
    short_docs = [d for d in docs if CFG["filtering"]["min_chars"] <= d["char_count"] < 500]
    short_band = len(short_docs)
    short_src = Counter(d["source"] for d in short_docs)
    n_keyterms = sum(1 for d in docs if d["source"] == "openstax_astronomy_2e" and d["title"].startswith("Key Terms"))
    pb = d2.get("press_boilerplate_lines", {})
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
          "Bu veri seti, uzay ve astronomi eğitiminde kullanıcının seviyesine göre **İngilizce** konu anlatımı yapan ve "
          "anlattığı içerikten çoktan seçmeli soru üreten alana özel bir dil modelinin (AstroTutor AI) **continued "
          "pretraining (CPT / DAPT)** aşamasında kullanılmak üzere hazırlanmıştır. Final aşamasında "
          f"`{CFG['instruction']['train_tokenizer']}` ailesi hedeflenmektedir. Genel amaçlı bir corpus değildir; "
          "soru-cevap davranışı için ayrı hazırlanan Instruction Dataset kullanılır ("
          + (f"İngilizce v{CFG['project']['instruction_version']}: [INSTRUCTION_CARD.md](INSTRUCTION_CARD.md); "
             if instruction_file().exists() else f"İngilizce v{CFG['project']['instruction_version']} hazırlanıyor; ")
          + "vizede teslim edilen Türkçe v1.0: "
          "[reports/archive_v1.0/INSTRUCTION_CARD_v1.0.md](reports/archive_v1.0/INSTRUCTION_CARD_v1.0.md), Git etiketi "
          "`v1.0`).", "",
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
        if s not in by:
            continue
        raw = ext.get("per_source", {}).get(ek, {}).get("raw", 0)
        lang = Counter(d["language"] for d in by[s]).most_common(1)[0][0] if by[s] else "-"
        md.append(f"| {name} | {typ} | {lang} | {n(raw)} | {n(len(by[s]))} | "
                  f"{pc(sum(d['token_count'] for d in by[s]), total_tok)} | {LICENSE[s]} |")
    md += [f"| **Toplam** | | | **{n(raw_total)}** | **{n(len(docs))}** | %100 | |", "",
           "Kaynakların neden seçildiği, lisans ayrıntıları ve kullanılmayan kaynaklar (NASA Exoplanet Archive: "
           "final dönemde RAG; Stack Exchange: yalnız instruction verisi) için: "
           "[reports/source_notes.md](reports/source_notes.md), [reports/source_inventory.csv](reports/source_inventory.csv).",
           "",
           "Corpus v2.0 yalnız İngilizcedir: AstroTutor AI İngilizce konuşan bir eğitim asistanı olarak geliştirilmektedir "
           "(09.11.2026 kararı) ve alanın güvenilir, açık lisanslı birincil kaynakları (NASA, ders kitabı, makale özetleri) "
           "İngilizcedir. v1.0'da modelin Türkçe terminolojiyi görmesi için eklenen Türkçe Wikipedia (token'ların "
           "%16,9'u) bu sürümde çıkarıldı; İngilizce dokümanların kimlikleri ve kümeleri değişmedi.", "",
           "## Veri toplama",
           f"Dokümanlar {dates[0] if dates else '-'} – {dates[-1] if dates else '-'} tarihleri arasında "
           "`scripts/01_download.py` ile indirildi. science.nasa.gov `robots.txt` kurallarına uyuldu (istekler arası "
           f"{tr_num(CFG['http']['delay_seconds'])} sn); Wikipedia isteklerinde iletişim bilgili User-Agent kullanıldı ve "
           "Wikimedia hız sınırlarına uyuldu; arXiv OAI-PMH'de istekler arası "
           f"{tr_num(CFG['http']['arxiv_delay_seconds'])} sn beklendi. Ham dosyalar `data/raw/` altında değiştirilmeden saklanır; "
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
            f"(e-posta, telefon)** silindi (kalan telefon ve gerçek e-posta adresi: 0, ayrıntı Lisans bölümünde); "
            f"(3) NASA sözlük sayfalarında kısa satır kuralının sildiği terimler geri getirildi. "
            f"Corpus v2.0'da (09.11.2026) iki düzeltme daha yapıldı: (4) OpenStax'ın \"Key Terms\" sözlük bölümleri "
            f"PDF yazı tipi bilgisiyle (kalın terim) her terim ayrı paragraf olacak biçimde \"terim: tanım\" olarak "
            f"çıkarıldı ({n(n_keyterms)} bölüm; önceden terimler bir önceki tanıma yapışıyor, sayfa başlığında kesilen "
            f"terimler (ör. \"Wien's law\", \"X-rays\") kayboluyordu); (5) basın bültenlerinin sonundaki yalnız kişi "
            f"adından oluşan satırlar ({n(pb.get('press_names', 0))}), \"Learn more / Visit …\" gibi yönlendirme "
            f"satırları ({n(pb.get('cta_tail', 0))}) ve yalnız bağlantı taşıyan cümleler ({n(pb.get('url_tail', 0))}) "
            f"silindi; aynı satırdaki bilgi taşıyan cümleler korundu (testler: `scripts/press_boilerplate.py`). "
            f"Basın temizliğinden (2, 5) etkilenen doküman: {n(d2.get('press_docs_touched', 0))}."
            if d2 else ""),
           f"- **Filtering:** {CFG['filtering']['min_chars']} karakterden kısa ({n(reasons.get('too_short', 0))}), bozuk "
           f"karakter oranı {tr_ek('%' + str(int(100 * CFG['filtering']['max_garbled_ratio'])), 'belirtme')} aşan veya çoğu simgeden oluşan "
           f"({n(reasons.get('garbled', 0))}), "
           f"{'/'.join(LANG_NAME.get(x, x) for x in CFG['filtering']['allowed_languages'])} dışındaki "
           f"({n(reasons.get('wrong_language', 0))}), "
           f"satırlarının yarısından fazlası kaynakça girdisi olan yayın listesi ({n(reasons.get('reference_list', 0))}) ve "
           f"alan dışı ({n(reasons.get('out_of_domain', 0))}) dokümanlar elendi. Alan tespiti astronomi terim sözlüğü "
           "yoğunluğu ile yapıldı (`scripts/domain_lexicon.py`). Wikipedia'da kategori gezintisi alt kategorilere indiği "
           "için kurgu, film, oyun, bayrak, genel spektroskopi ve jeoloji maddeleri de seçilmişti; her maddenin kendi "
           f"Wikipedia kategorilerine dayanan ek kuralla {n(reasons.get('out_of_domain_category', 0))} madde elendi "
           "(kalibrasyonu: [experiments.md](experiments.md)).",
           f"- **Deduplication:** exact duplicate SHA-256 ile ({n(ded.get('exact_duplicates', 0))} doküman), near "
           f"duplicate MinHash LSH (kelime {ded.get('shingle_words')}-gram, {ded.get('num_perm')} permütasyon) + Jaccard ≥ "
           f"{tr_num(ded.get('threshold'))} ile ({n(ded.get('near_duplicates', 0))} doküman). " + near_dup_sentence(qc) +
           (f" Eşik incelemesi, APOD'un aynı açıklamayı yıllar sonra küçük düzeltmelerle yeniden yayımladığı "
            f"sayfaları kaçırdığını gösterdi; ikinci bir geçişte (`scripts/06b_repost_dedup.py`; " + repost_rules(d2)
            + f") {n(d2.get('repost_removed', 0))} yeniden yayın tekrarı çıkarıldı "
            f"({n(d2.get('removed_pairs_across_splits', 0))} çift farklı kümelerdeydi, yani sızıntı riski "
            f"taşıyordu). Genel eşik düşürülmedi, çünkü NASA'nın uydu sayfaları ortak şablona rağmen farklı uyduların "
            f"bilgisini taşıyor (Jaccard 0,74'e kadar)." + other_removed_sentence(d2)
            + " Bu adım doküman kimliklerini ve kümeleri değiştirmez."
            if d2 else ""),
           *([list_page_sentence(d2)] if list_page_sentence(d2) else []),
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
           f"| Ortalama doküman uzunluğu | {n(round(td.get('mean', 0)))} token |",
           f"| Medyan doküman uzunluğu | {n(td.get('median', 0))} token |",
           f"| 95. yüzdelik / en uzun | {n(td.get('p95', 0))} / {n(td.get('max', 0))} token |",
           "| Dil (token payı) | " + ", ".join(f"{LANG_NAME.get(k, k)} {pc(v, total_tok)}"
                                                for k, v in lang_tok.most_common()) + " |",
           "", "Alt konu dağılımı (doküman): " + ", ".join(f"{k} {pc(v, len(docs), 0)}" for k, v in sub.most_common()) + ".",
           "", "Ayrıntılı istatistikler ve grafikler: [reports/statistics.md](reports/statistics.md).", "",
           "## Veri ayrımı",
           f"Doküman düzeyinde %{int(100 * CFG['split']['train'])} train ({n(sp['train'])}), "
           f"%{int(100 * CFG['split']['validation'])} validation ({n(sp['validation'])}), "
           f"%{int(100 * CFG['split']['test'])} test ({n(sp['test'])}). Bölme `scripts/06_split.py` içinde "
           f"`random_seed = {CFG['project']['random_seed']}` ile, kaynak bazında tabakalı yapılır. Chunk'lar bölmeden "
           "SONRA üretildiği için aynı dokümanın parçaları tek kümede kalır. Kümeler arası grup çakışması: 0. "
           "v2.0'da Türkçe dokümanlar çıkarıldığında İngilizce dokümanların kümeleri v1.0 ile aynı kaldı (kaynak bazında "
           "tabakalı bölme; Türkçe kaynak sıralamada en sondaydı).", "",
           "## Kalite kontrolü"]
    cr = qc.get("corpus_review", {})
    if cr.get("pre_reviewed") or cr.get("human_reviewed"):
        who = ("nihai karar, grup üyesinin ön inceleme kararlarını onaylamasıyla verildi"
               if cr.get("human_approved_pre") else "nihai karar grup üyesi tarafından verildi")
        md.append(f"Rastgele {cr.get('sample')} doküman (kaynak oranında tabakalı) incelendi: yapay zekâ destekli ön "
                  f"inceleme ölçüt bazında yapıldı, {who}. Ön incelemede uygun: "
                  f"{pc(cr.get('pre_pass_rate', 0), 1)}; nihai kararda uygun: "
                  f"{pc(cr.get('human_pass_rate', 0), 1) if cr.get('human_reviewed') else 'bekleniyor'}. "
                  "v2.0'da v1.0 örnekleminin İngilizce dokümanları ve kararları korundu; çıkarılan Türkçe dokümanların "
                  "yerine aynı yöntemle (kaynak oranında, seed'li) yeni İngilizce dokümanlar eklenip incelendi "
                  "(`scripts/13_sample_for_review.py --corpus-topup`). "
                  "Ayrıntı: [reports/quality_control_report.md](reports/quality_control_report.md).")
    else:
        md.append("Rastgele örneklem incelemesi: [reports/quality_control_report.md](reports/quality_control_report.md).")
    md += ["", "## Lisans ve kullanım",
           "Veri seti yalnızca açık erişimli veya açık lisanslı kaynaklardan oluşur; her dokümanın lisansı `license` "
           "alanındadır. **Akademik ve ticari olmayan** amaçla hazırlanmıştır. OpenStax Astronomy 2e (CC BY-NC-SA 4.0) "
           "ve Wikipedia (CC BY-SA 4.0) türevleri aynı koşullarla paylaşılmalıdır. **Kişisel veri:** arXiv yazar adları "
           "saklanmadı, APOD görsel kredi satırları temizlendi. NASA basın bültenlerinde kamuya açık basın iletişim "
           "bilgileri (ad, e-posta, telefon) bulundu ve silindi; cümle sonunda kalan 5 kurumsal basın numarası 30.10.2026 "
           "düzeltmesiyle maskelendi (`[telefon]`). Final corpus'ta telefon numarası 0; e-posta biçiminde tek eşleşme, "
           "bir Wikipedia biyografisinde (David J. Tholen) maddenin konusu olarak geçen, bilerek bozulmuş ve çalışmayan bir "
           "Usenet takma adıdır. Metinlerde bilimcilerin ve kamusal kişilerin adları, ansiklopedik/haber içeriğinin "
           "parçası olarak geçer. NASA içeriği NASA'nın onayını ima edecek biçimde kullanılmaz.", "",
           "## Bilinen problemler",
           f"- Kaynak dağılımı dengesizdir: dokümanların {tr_ek(pc(top_n, len(docs)))} {SRC[top_src][0]} kaynağından, "
           f"token'ların en büyük payı {SRC[top_tok_src][0]} kaynağından gelir.",
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
           "- Wikipedia düz metin servisi tabloları çıkarmaz; bazı maddelerde var olmayan bir tabloya atıf kalır (ör. "
           "\"Orbital period\" maddesi \"The following table lists the synodic periods of some planets…\" cümlesiyle "
           "biter). Wikipedia formülleri `{\\displaystyle ...}` biçiminde LaTeX olarak korunur.",
           "- Kaybolan üslerin yalnız belirsizliği olmayan kalıpları düzeltildi; işaretsiz kalanlar (ör. \"(1031 erg/s)\") "
           "olduğu gibi duruyor.",
           "- Birkaç APOD sayfasında bağlantı metninden kaynaklanan kelime birleşmeleri vardır (\"Galacticwar\", "
           "\"PerseidMeteorShower\").",
           f"- {CFG['filtering']['min_chars']}–500 karakter aralığında {n(short_band)} doküman vardır ("
           + ", ".join(f"{SRC[k][0]} {n(v)}" for k, v in short_src.most_common()) + "); çoğu kısa ama bilgi taşıyan "
           "sayfalardır (APOD açıklamaları, uydu ve yakın geçiş sayfaları, makale özetleri), ancak bir kısmı değeri düşük "
           "video ve indirme sayfalarıdır (ör. \"To view this video please enable JavaScript\" metinli görev animasyonları). "
           "v2.0'da alt sınır yeniden değerlendirildi ve 300'de tutuldu: 500'e çıkarmak bu aralıktaki bilgi taşıyan kısa "
           "sayfaları da toplu olarak atardı.",
           "- Kaynakta bozuk kodlanmış kesme işareti 4 yerde \"^1\" olarak kalmıştır (\"Saturn^1s\"); 1 APOD sayfasında "
           "(DOC_007977) kaynaktan gelen bir U+FFFD karakteri vardır (\"Don�t\").",
           "- Liste/haber sayfası incelemesi yalnız NASA Science ve APOD'a uygulandı. Wikipedia'da cümle oranı düşük "
           "maddeler çoğunlukla formül ağırlıklı veya tablo içerikli ve bilgi taşıyan maddeler olduğu için kapsam dışı "
           "tutuldu. Tutulan tablo sayfalarında (ör. uydu tabloları) satırlar düz metne dönüştüğü için sütun ilişkisi "
           "kaybolur."]
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
           "- v1.0 (24.10.2026): Token sayımı, split; elle kalite kontrolünde bulunan "
           "kaybolmuş üsler, NASA künye/kişisel veri satırları, sözlük terimleri ve APOD yeniden yayın tekrarları "
           "düzeltildi (06b; doküman kimlikleri ve kümeler korunarak).",
           "- v1.0 düzeltmesi (30.10.2026): Telefon kuralı, numaradan hemen sonra cümle "
           "noktası gelen 5 kurumsal basın numarasını kaçırıyordu; kural düzeltildi (testli) ve corpus 06 → 06b (iki geçiş) → 07 ile "
           "yeniden üretildi. Yalnız bu 5 dokümanın metni değişti (numara → `[telefon]`, toplam −53 token); doküman "
           "sayısı, kimlikler ve kümeler aynı. Vizede teslim edilen sürüm (İngilizce + Türkçe, 16.284 doküman); Git "
           "etiketi `v1.0`.",
           f"- v{CFG['project']['corpus_version']} (09.11.2026): AstroTutor AI İngilizce konuşan bir model olarak "
           "geliştirileceği için Türkçe Wikipedia çıkarıldı (corpus yalnız İngilizce). OpenStax \"Key Terms\" bölümleri "
           "\"terim: tanım\" biçiminde yeniden çıkarıldı; basın bültenlerinin sonundaki ad, yönlendirme ve bağlantı "
           f"satırları silindi; {n(d2.get('other_removed', {}).get('list_page_06b', 0))} liste/haber sayfası grup "
           f"üyesinin onayıyla çıkarıldı. Final: {n(len(docs))} doküman, {mtok(total_tok)} token. İngilizce dokümanların "
           "kimlikleri ve kümeleri v1.0 ile aynı; tüm zincir (02 → 07) yeniden çalıştırıldığında çıktı birebir aynı.", "",
           "## Yeniden üretme",
           "`pip install -r requirements.txt` ardından `python run_pipeline.py --corpus`. Ayrıntı: [README.md](README.md).", "",
           "## Hazırlayan",
           "Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. "
           "Danışman: Asim Sinan Yüksel."]
    (ROOT / "DATASET_CARD.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log.info("DATASET_CARD.md yazıldı")


def instruction_card(out_dir=None) -> None:
    # Geçerli sürüm (config.yaml) üretilmediyse kart DEĞİŞTİRİLMEZ: v2.0 (İngilizce) yokken eski dosyadan yeni sürüm
    # numarasıyla kart üretilmemeli. out_dir yalnız testlerde geçici klasör vermek için kullanılır.
    if not instruction_file().exists():
        log.warning(f"{instruction_file().name} yok; INSTRUCTION_CARD.md değiştirilmedi")
        return
    ins = list(read_jsonl(instruction_file()))
    if not ins:
        log.warning("Instruction dataset boş, INSTRUCTION_CARD atlandı")
        return
    vs, src_s, qc = j("instruction_verification_summary.json"), j("instruction_sources_summary.json"), j("qc_summary.json")
    cal = j("judge_calibration.json")
    I = CFG["instruction"]
    J = I.get("judge", {})
    iv = CFG["project"]["instruction_version"]
    raw = {}
    for r in read_jsonl(p("interim") / "instructions_raw.jsonl"):
        raw[r["raw_example_id"]] = r
    rem = removed_rows("removed_instructions.csv")
    rem_v = Counter(r["reason"].split(":")[0] if not r["reason"].startswith("judge_fail") else "judge_fail"
                    for r in rem if r["stage"] == "verify")
    rem_qc = sum(1 for r in rem if r["stage"] == "qc")
    tt = Counter(x["task_type"] for x in ins)
    lv = Counter(x["level"] for x in ins)
    sp = Counter(x["split"] for x in ins)
    meth = Counter(x["generation_method"] for x in ins)
    gm = Counter(x["generator_model"] or "Stack Exchange (orijinal, Gemini yok)" for x in ins)
    pp_final = Counter(x.get("postprocess") for x in ins)

    def fix_note(kind: str) -> str:
        # Düzeltilen bir örnek sonradan (ör. kalite kontrolünde) elendiyse final setteki sayıyı ayrıca belirt
        done, left = vs.get("rule_fixes", {}).get(kind, 0), pp_final.get(kind, 0)
        return f"; {n(done - left)} tanesi sonradan elendiği için final sette {n(left)}" if left < done else ""

    pv = Counter(x.get("prompt_version") or "none (Stack Exchange)" for x in ins)
    jm = Counter(x["judge_model"] for x in ins if x.get("judge_model"))
    srcn = Counter(x["source_name"] for x in ins)
    n_docs = len({x["source_document"] for x in ins if x["source_name"] not in ("stackexchange_space_qa", "none")})
    n_corpus_ex = sum(v for k, v in srcn.items() if k not in ("stackexchange_space_qa", "none"))
    se_lics = Counter(x["license"].split(" (")[0] for x in ins if x["source_name"] == "stackexchange_space_qa" and x.get("license"))
    target = I["taxonomy"]
    full_cov = J.get("full_check_fail_rate", 0.05) == 0.0
    jpc = int(J.get("jobs_per_call", 1))
    jpc_kind = J.get("jobs_per_call_by_kind") or {}
    train_limit = I["train_max_tokens"] - I["train_token_margin"]
    tax_ref = ("[reports/instruction_taxonomy.md](reports/instruction_taxonomy.md)"
               if (R / "instruction_taxonomy.md").exists()
               else f"[prompts/{I['prompt_version']}/task_types.json](prompts/{I['prompt_version']}/task_types.json)")

    judge_desc = (
        f"3. **Tam kapsamlı karma LLM yargıç** (`config: instruction.judge`; {n(vs.get('judged_examples', 0))} örnek): "
        "örneği üreten modelden **farklı** bir Gemini Flash modeli, sıcaklık 0 ve `medium` düşünme bütçesiyle her "
        "örneği kaynağıyla birlikte beş ölçütte (`supported`, `correct`, `follows_instruction`, `instruction_clear`, "
        "`fluent_english`) değerlendirdi. "
        + ("Erken durdurma kapalıdır (`full_check_fail_rate: 0.0`): aşama 1 (%20 tabakalı örneklem) istatistikleri "
           "raporlandıktan sonra tüm grupların tamamı yargıçtan geçer. " if full_cov else
           f"Aşamalı kontrol: önce işlerin %{int(100 * J.get('initial_fraction', 0.2))}'i değerlendirilir; "
           f"hata oranının %{int(100 * J.get('confidence', 0.95))} Clopper-Pearson üst güven sınırı "
           f"%{100 * J.get('full_check_fail_rate', 0.05):.0f}'in altında olmayan grupların tamamı kontrol edilir. ")
        + (f"Doküman ve kapsam dışı işleri en fazla {jpc} iş/çağrı (aynı iş türü ve aynı üretici model; 504 süre "
           "aşımında tek tek düşüş), " if jpc > 1 else "Her iş ayrı çağrıda değerlendirildi; ")
        + ("Stack Exchange işlerinin tamamı ise **tek tek** (`jobs_per_call_by_kind: {SE: 1}`) yargılanıp "
           "`beginner` / `intermediate` / `advanced` seviyesi yargıç tarafından atandı. "
           if jpc_kind.get("SE") == 1 else "Stack Exchange işlerinin tamamı değerlendirilip seviyesi yargıç tarafından atandı. ")
        + f"Başarısız oranı: **{pc(vs.get('judge_fail', 0), vs.get('judged_examples') or 0)}**; başarısızlar elendi. "
        + f"Yargıçtan geçip final sette kalan {n(sum(jm.values()))} örneğin yargıç modelleri: "
        + (", ".join(f"{k} ({n(v)})" for k, v in jm.most_common()) or "-") + "."
        + (f" {n(vs['judge_gave_up_jobs'])} işte yargıç iki denemede tüm örnekleri değerlendiremedi."
           if vs.get("judge_gave_up_jobs") else "")
    )
    cal_note = ""
    if jpc > 1 and cal:
        bk = cal.get("by_kind") or {}
        cal_note = (
            f"- **Toplu yargıç kalibrasyon riski:** Toplu çağrının ({jpc} iş/çağrı) tekli çağrıyla uyumu önceden test edildi "
            f"([reports/judge_calibration.md](reports/judge_calibration.md); {n(cal.get('examples_compared', 0))} örnek): "
            f"genel uyum {pc(cal.get('agreement', 0), 1)}, ancak tekli yargıcın elediği örneklerin "
            f"{pc(cal.get('fail_recall', 0), 1, 0)}'ı toplu yargıçta yakalandı (ölçüt 2 sağlanmadı). "
            f"En büyük fark Stack Exchange'de görüldüğü için (uyum {pc(bk.get('SE', {}).get('agreement', 0), 1)}) "
            f"**SE işleri tekli yargıca** alındı (`SE: 1`); doküman ({pc(bk.get('DOC', {}).get('agreement', 0), 1)} uyum) "
            f"ve kapsam dışı ({pc(bk.get('REF', {}).get('agreement', 0), 1, 0)} uyum) işlerinde süre nedeniyle {jpc}'lü "
            "toplu yargıç kullanıldı. Doküman örneklerinde ~%2–3 düzeyinde artık hata riski bu nedenle bilinçli olarak "
            "kabul edilmiş ve burada açıkça belgelenmiştir."
        )

    tok_model = I["train_tokenizer"]
    md = [f"# AstroTutor AI İngilizce Instruction Dataset v{iv}", "",
          "## Amaç",
          "Bu veri seti, yalnız İngilizce [Domain Corpus v2.0](DATASET_CARD.md) ile alana uyarlanacak **İngilizce "
          f"konuşan** modele (AstroTutor AI; SFT uzunluk/şablon kontrolü: `{tok_model}`) **supervised fine-tuning (SFT)** "
          "ile şu davranışları kazandırmak için hazırlanmıştır: kullanıcının seviyesine (`beginner` / `intermediate` / "
          "`advanced`) göre İngilizce konu anlatımı, verilen öğretim pasajından JSON biçiminde dört seçenekli soru "
          "üretme, astronomi terminolojisiyle doğru açıklama, kapsam dışı sorularda sınırını bildirme ve yanlış "
          "öncüllü astronomi sorularında öncülü nazikçe düzeltme.", "",
          "Vizede teslim edilen Türkçe sürüm (`v1.0`, 3.388 örnek) Git etiketi `v1.0` ve "
          "[reports/archive_v1.0/INSTRUCTION_CARD_v1.0.md](reports/archive_v1.0/INSTRUCTION_CARD_v1.0.md) altında "
          "arşivlenmiştir; 09.11.2026 kararıyla model dili tamamen İngilizceye geçirilmiştir.", "",
          "## Format",
          "JSONL; her satır bir örnektir. SFT için `messages` alanı kullanılır (`user` / `assistant`; sistem mesajı "
          "Final SFT aşamasında eklenir). İzlenebilirlik alanları: `id`, `source_document` (corpus `document_id`'si "
          "veya Stack Exchange soru kimliği), `source_url`, `source_name`, `task_type`, `level`, `level_source` "
          "(`generation_plan` veya `llm_judge`), `supporting_evidence` (cevabı destekleyen kaynak alıntısı), "
          "`generation_method`, `generator_model`, `prompt_version`, `auto_verified`, `llm_judged`, `judge_model`, "
          "`human_verified`, `verified_by`, `license`, `split`, `raw_example_id`, `postprocess` (kural tabanlı metin "
          "düzeltmesi, ör. `unseen_reference_removed`; yoksa `null`).", "",
          f"Dosyalar: `data/final/{instruction_file().name}` (tamamı) ve "
          "`data/final/instruction/{train,validation,test}.jsonl`.", "",
          "## Görev türü dağılımı", "", "| Görev türü | Örnek | Oran | Hedef oran |", "| --- | --- | --- | --- |"]
    for t in target:
        md.append(f"| {TASK_TR.get(t, t)} (`{t}`) | {n(tt.get(t, 0))} | {pc(tt.get(t, 0), len(ins))} | "
                  f"{pc(target[t], 1, 0)} |")
    md += [f"| **Toplam** | **{n(len(ins))}** | %100 | |", "",
           f"Görev tanımları: {tax_ref}.", "",
           "Seviye dağılımı: " + ", ".join(
               f"{LEVEL_TR.get(k, k)} (`{k}`) {n(v)} ({pc(v, len(ins), 1)})"
               for k, v in lv.most_common()) + ".", "",
           "## Örneklerin üretimi",
           f"- **Kaynaklar:** İngilizce Domain Corpus v{CFG['project']['corpus_version']}'dan {n(n_docs)} doküman "
           f"({n(n_corpus_ex)} örnek: NASA Science, Wikipedia EN, OpenStax Astronomy 2e, arXiv astro-ph), "
           f"Stack Exchange Space/Astronomy soru-cevapları ({n(srcn.get('stackexchange_space_qa', 0))} örnek; "
           f"{n(src_s.get('stackexchange_candidates_selected', 0))} seçilmiş soru) ve kaynak dokümansız kapsam dışı / "
           f"yanlış öncül örnekleri ({n(srcn.get('none', 0))}).",
           "- **Yöntem:** Üç kaynak türü ayrı ele alındı: (1) Corpus dokümanlarından LLM destekli sentetik İngilizce "
           "üretim — model yalnız kaynaktaki bilgiyi kullanır ve `supporting_evidence` alıntısını kaynaktan birebir "
           "kopyalar; (2) Stack Exchange örneklerinde **Gemini kullanılmaz**, orijinal İngilizce soru + en yüksek "
           "puanlı cevap metni değiştirilmeden alınır (LaTeX, URL, `@kullanıcı`, görsele bağımlı, forum/insan sesi "
           "içeren kayıtlar 09'da elenir; seviye 11'de yargıç tarafından atanır); (3) kapsam dışı işlerinde her 15 "
           "örneğin 5'i [prompts/v2.0/misconceptions.json](prompts/v2.0/misconceptions.json) listesindeki 60 "
           "astronomi yanlış kanısından (tekrarsız) üretilir.",
           "- **Model:** Google Gemini API (ücretsiz katman; **yalnız Flash modelleri**, lite kapalı). Her örnekte "
           "gerçekte kullanılan model kaydedilmiştir: " + ", ".join(f"{k} ({n(v)})" for k, v in gm.most_common()) + ".",
           f"- **Parametreler:** sıcaklık {tr_num(I['temperature'])}, düşünme seviyesi `{I.get('generator_thinking_budget')}`, "
           f"en fazla {n(I['max_output_tokens'])} çıktı token'ı. Prompt sürümleri: "
           + ", ".join(f"`{k}` ({n(v)})" for k, v in sorted(pv.items()))
           + f" ([prompts/{I['prompt_version']}/](prompts/{I['prompt_version']}/): `system_generate.txt`, "
           "`generate_doc.txt`, `generate_refusal.txt`, `task_types.json`, `misconceptions.json`, `judge.txt`, "
           "`judge_batch.txt`).",
           "- Üretim yöntemlerine göre: " + ", ".join(f"`{k}` {n(v)}" for k, v in meth.most_common()) + ".", "",
           "## Doğrulama",
           f"Toplam **{n(len(raw))}** ham örnek üretildi; doğrulama ve kalite kontrolünden sonra **{n(len(ins))}** "
           "örnek kaldı. Üretim sırasında çoktan seçmeli talimatında soru/şık/cevap sızıntısı yapan işler hemen "
           "reddedilip yeniden üretildi. Dört aşamalı kontrol uygulandı:", "",
           "1. **Kural kontrolleri** (tüm örnekler): İngilizce dil tespiti (`lingua`), karakter uzunluğu, Final SFT "
           f"token sınırı (`too_long_for_training`: `{tok_model}` chat template, düşünme kapalı, sistem "
           f"mesajı dahil ≤ {n(train_limit)} token; SFT {n(I['train_max_tokens'])} token sınırı için {I['train_token_margin']} token pay), "
           "görev türü ve hedef kitle–seviye tutarlılığı (`level_audience_mismatch`), çoktan seçmeli JSON şeması, "
           "soru sayısı ve talimatta sızıntı kontrolü, kaybolmuş üs (`exponent_loss`), URL, kişisel iletişim bilgisi "
           "(`contains_pii`), LaTeX artığı, bozuk kodlama, yer tutucu, eksik görsel atfı (`missing_media_reference`), "
           "başka cevaba atıf (`references_other_answer`, SE), yarım kalan cevap (`truncated_response`), yapay zekâ "
           "sorumluluk reddi, tekrar eden cümle, dengesiz markdown, kaynağı görmeyen kullanıcıya talimatta/cevapta "
           "metin atfı, kapsam dışı kaynak dokümanları (`out_of_scope_source`), birebir/yakın tekrar (MinHash, "
           f"Jaccard ≥ 0,8) ve değerlendirme setleriyle {I['decontam_ngram']}-gram örtüşmesi (`eval_overlap`)."
           + (f" Öğeleri talimatta sayılmış {n(vs['rule_fixes']['unseen_reference_removed'])} sınıflandırma "
              "talimatındaki görünmeyen metin atfı temizlendi (örnek elenmedi; `postprocess` alanında işaretli)"
              + fix_note("unseen_reference_removed") + "."
              if vs.get("rule_fixes", {}).get("unseen_reference_removed") else ""),
           f"2. **Kanıt kontrolü** (kaynak dokümanlı Gemini örnekleri): `supporting_evidence` alıntısının kelime "
           f"5-gram'larının en az {tr_ek('%' + str(int(100 * I['evidence_min_overlap'])))} kaynak metinde "
           "bulunmalıdır (Stack Exchange ve kapsam dışı örneklerde kaynak doküman yok).",
           judge_desc,
           "4. **Rastgele örneklem incelemesi:** "]
    ir = qc.get("instruction_review", {})
    rev_f = p("qc") / "instruction_review.csv"
    rev_rows = list(csv.DictReader(open(rev_f, encoding="utf-8-sig"))) if rev_f.exists() else []
    sbs = [r for r in rev_rows if r["task_type"] == "step_by_step_problem_solving"]
    sbs_rev = (len(sbs), sum(1 for r in sbs if (r.get("son_karar") or r.get("claude_karar")) == "sorunlu"))
    if ir.get("pre_reviewed") or ir.get("human_reviewed"):
        pre_rev = ir.get("pre_reviewer") or "yapay zekâ"
        md[-1] += (f"{ir.get('sample')} örnek (görev türü oranında tabakalı) kaynak metniyle karşılaştırılarak incelendi. "
                   f"Yapay zekâ destekli ön inceleme ({pre_rev}) ölçüt bazında yapıldı; nihai kararı grup üyesi verdi. Ön incelemede "
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
           f"alınmadı; bunlarla {I['decontam_ngram']}-gram örtüşmesi olan tüm örnekler elendi (`eval_overlap = 0`).", "",
           "## Değerlendirme planı (final dönemi)",
           f"Final aşamasında İngilizce model (`{tok_model}` ailesi; nihai model seçimi Final deney günlüğünde "
           "kesinleştirilir) şu eksenlerde değerlendirilecek:",
           "- **Dış alan değerlendirme setleri** (eğitime girmedi): AstroMLab Astrobench, Astro-mcqa, astro-mcq, "
           "HubbleSpaceTelescope-MCQ — çoktan seçmeli doğruluk. Corpus ile örtüşen sorular "
           "[reports/eval_contamination.csv](reports/eval_contamination.csv) dosyasında ayrıca raporlanır.",
           "- **Genel yetenek korunumu (İngilizce):** İngilizce MMLU (`lm-eval mmlu`) ve İngilizce Wikipedia "
           "perplexity + %10 İngilizce replay.",
           f"- **Bu setin test kümesi** ({n(sp['test'])} örnek) + elle yazılmış ≥ 50 soru (görev türü başına en az 15): "
           "İngilizce talimat takibi, seviyeye uygunluk, yanlış öncül düzeltme ve JSON çoktan seçmeli soru üretimi.",
           "- Karşılaştırma: temel model, CPT modeli, CPT + SFT (QLoRA) ve isteğe bağlı RAG katmanı.", "",
           "## Sınırlılıklar",
           "Doküman ve kapsam dışı örnekler sentetiktir ve kaynak dokümanlardaki bilgiyle sınırlıdır; güncel astronomik "
           "veriler (ör. ötegezegen sayısı) için birincil kaynakların yerine geçmez (Final'de RAG ile desteklenecektir). "
           f"Tüm örnekler tek turlu (`user` → `assistant`) İngilizce diyaloglardır ve SFT {n(I['train_max_tokens'])} "
           "token sınırına uyacak biçimde filtrelenmiştir.", "",
           "## Sürüm geçmişi",
           "- v1.0 (24–26.10.2026): Vize teslimi Türkçe Instruction Dataset (3.388 örnek, Git etiketi `v1.0`, "
           "arşiv: `reports/archive_v1.0/`).",
           f"- v{iv} (Kasım 2026): Tamamen **İngilizce** yeniden üretim; yalnız Flash modelleri (lite kapalı), "
           "orijinal İngilizce Stack Exchange soru-cevapları (Gemini'siz, seviye yargıçtan), 60 yanlış öncüllü "
           f"astronomi sorusu (`misconceptions.json`), Final SFT {n(I['train_max_tokens'])} token sınırı "
           "(`too_long_for_training`), genişletilmiş kural denetimi ve tam kapsamlı karma LLM yargıç (`DOC`/`REF` "
           f"{jpc}'lü toplu, `SE` tekli).", "",
           "## Lisans",
           "Her örnek kaynağının lisansını `license` alanında taşır. Stack Exchange örnekleri cevabın tarihine göre "
           + (", ".join(f"{k} ({n(v)})" for k, v in se_lics.most_common()) or "CC BY-SA 3.0 / 4.0")
           + " taşır (kaynak veri setinde yazar adı bulunmadığından atıf `source_url` ve lisansla yapılır); OpenStax "
           "türevleri CC BY-NC-SA 4.0, Wikipedia türevleri CC BY-SA 4.0 koşullarına tabidir. Veri seti akademik ve "
           "ticari olmayan amaçla hazırlanmıştır; sentetik örneklerde Google Gemini API kullanım koşulları da geçerlidir.", "",
           "## Bilinen problemler",
           *([cal_note] if cal_note else []),
           "- Kanıt kontrolü cevabın tamamını değil, modelin gösterdiği alıntıyı doğrular; tam kapsamlı LLM yargıç ve "
           "örneklem incelemesiyle kalan hata oranı en aza indirilmiştir ancak sıfır olduğu garanti edilemez.",
           "- Örnekler dört farklı Gemini Flash modeliyle üretildiği için üslupta küçük farklılıklar olabilir.",
           "- Stack Exchange örnekleri forumdan birebir alınan insan cevaplarıdır; kural + tekli yargıçla temizlense de "
           "üslup sentetik ders anlatımlarına göre daha konuşma diline yakın olabilir.",
           "- Kapsam dışı ve yanlış öncül örnekleri kaynak dokümansızdır; doğrulukları yargıç ve incelemeyle kontrol edildi.",
           (f"- `step_by_step_problem_solving` türünde incelenen {n(sbs_rev[0])} örneğin {n(sbs_rev[1])} tanesi "
            "sorunlu bulunup çıkarılmıştır." if sbs_rev[1] else
            "- `step_by_step_problem_solving` örneklerinde sayısal hesap yerine kavramsal adım sıralaması görülebilir."), "",
           "## Hazırlayan",
           "Eda Gögebakan (2211012069) — Süleyman Demirel Üniversitesi, Bilgisayar Mühendisliği. "
           "Danışman: Asim Sinan Yüksel."]
    target_dir = ROOT if out_dir is None else out_dir
    (target_dir / "INSTRUCTION_CARD.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log.info("INSTRUCTION_CARD.md yazıldı")


def source_inventory() -> None:
    """reports/source_inventory.csv — Rehber §4 sütunları; doküman sayıları final veriden."""
    docs = [d for s in ("train", "validation", "test") for d in read_jsonl(p("final") / f"{s}.jsonl")]
    ins = list(read_jsonl(instruction_file())) if instruction_file().exists() else []
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
    se_f = R / "instruction_sources_summary.json"
    se_sum = json.loads(se_f.read_text(encoding="utf-8")) if se_f.exists() else {}
    if not se_sum.get("stackexchange_total"):  # özet henüz yoksa kayıt sayısı doğrudan ham dosyadan
        import pyarrow.parquet as pq

        se_raw = ROOT / "data/raw/stackexchange_space_qa/data/stackexchange_space_qa.parquet"
        se_sum["stackexchange_total"] = pq.ParquetFile(se_raw).metadata.num_rows if se_raw.exists() else ""
    rows = [
        ("nasa_science", "https://science.nasa.gov/", "HTML", "en", "Domain Corpus: güvenilir birincil kaynak; görev başına en fazla 150 sayfa"),
        ("nasa_apod", "https://science.nasa.gov/apod/archive/", "HTML", "en", "Domain Corpus: popüler bilim düzeyinde kısa açıklamalar; yıl başına 85 örnek (API çalışmadığı için site sayfalarından)"),
        ("openstax_astronomy_2e", "https://openstax.org/details/books/astronomy-2e", "PDF", "en", "Domain Corpus: hakemli açık ders kitabı; kavramsal bütünlük"),
        ("arxiv_astro_ph", "https://arxiv.org/archive/astro-ph", "XML", "en", "Domain Corpus: ileri seviye terminoloji; yalnız başlık+özet"),
        ("wikipedia_en", "https://en.wikipedia.org/", "HTML/API", "en", "Domain Corpus: ikincil, durağan ansiklopedik bilgi"),
        ("wikipedia_tr", "https://tr.wikipedia.org/", "HTML/API", "tr",
         "v1.0'da Domain Corpus kaynağıydı (Türkçe terminoloji); v2.0'da çıkarıldı: AstroTutor AI İngilizce konuşan "
         "bir model (09.11.2026). v1.0 Git etiketi v1.0'da"),
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
                    "dataset", "en", se_sum.get("stackexchange_total", ""), se_n if ins else "", "", "2026-10-22",
                    "CC BY-SA 3.0 / 4.0",
                    "Yalnız Instruction Dataset (question_answering, orijinal İngilizce); raw = veri setindeki kayıt, "
                    "document_count = final instruction örneği" + ("" if ins else
                                            f" (Instruction v{CFG['project']['instruction_version']} henüz üretilmedi)")])
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
