# Raw Data

Bu klasör AstroTutor AI projesinde kullanılan ham/orijinal verileri içerir.

## Kural

Bu klasördeki orijinal veriler **değiştirilmez**. Temizleme, filtreleme ve dönüştürme işlemleri
`data/extracted/`, `data/cleaned/`, `data/interim/` ve `data/final/` klasörlerinde yapılır. Böylece cleaning
kodunda hata bulunduğunda veri seti sıfırdan yeniden üretilebilir.

Her kaynak klasöründe bir `manifest.jsonl` bulunur: `raw_id`, `url`, `file`, `sha256`, `retrieved_at`,
`http_status`, `license`. Dosyalar `scripts/01_download.py` ile indirilir; bu klasör Git'e yüklenmez.

**Not (24.10.2026 denetimi):** `nasa_science/manifest.jsonl`'de 862 `raw_id` iki kez yer alır: 22.10'da iki indirme
süreci aynı URL'leri aynı anda indirdi ve 265 satırda SHA-256, dosya henüz yazılmadan hesaplandı (boş dosya hash'i
`e3b0c442…`). Her `raw_id`'nin **son başarılı (200) kaydı** diskteki dosyayla eşleşir; `02_extract.py` de bu kaydı
kullanır. Ham kayıtlar değiştirilmedi.

## Kaynaklar

| Klasör | İçerik | Biçim |
| --- | --- | --- |
| `nasa_science/` | NASA Science astronomi sayfaları (+ `sitemaps/`) | HTML |
| `nasa_apod/` | NASA APOD açıklama sayfaları (science.nasa.gov) | HTML |
| `openstax/` | OpenStax Astronomy 2e ders kitabı | PDF |
| `arxiv_astro_ph/` | arXiv astro-ph OAI-PMH yanıtları (başlık + özet) | XML |
| `wikipedia/en/`, `wikipedia/tr/` | Wikipedia API yanıtları (+ `candidates.json` seçim listesi) | JSON |
| `stackexchange_space_qa/` | Stack Exchange Space/Astronomy Q&A (Hugging Face) | Parquet |
