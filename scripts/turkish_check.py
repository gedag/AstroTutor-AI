"""Türkçe karakterleri düşürülmüş ("ASCII'leştirilmiş") metin tespiti.

23.10.2026: gemini-3.5-flash-lite bazı çağrılarda bütün çıktıyı ç, ğ, ı, ö, ş, ü olmadan yazdı
("Asagidaki metne gore baslangic duzeyinde bir coktan secmeli soru olustur"). Dil tespiti bunu yine Türkçe
saydığı için yakalanmıyordu. Ölçüm: lite örneklerinin %19,7'si, Flash örneklerinin %0'ı. Kusurlu örneklerin
214/225'i çıktısının ≥%70'i kusurlu 20 işten geliyordu (sorun çağrı düzeyinde).

Kullanım: 10_generate_instructions.py (iş çıktısının ≥ JOB_REJECT_RATIO'su kusurluysa iş yeniden denenir) ve
11_verify_instructions.py (tek tek kalan kusurlu örnekler 'turkish_chars_missing' ile elenir).
"""
from __future__ import annotations

import re

TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
# Doğru yazılmış Türkçede kelime olarak GEÇMEYEN, Türkçe karakterleri düşürülmüş sık kelimeler.
# ("sonucu", "sonucunda" doğru yazımdır, bu yüzden yalnız "sonuc" alınır.)
FOLDED = re.compile(r"\b(icin|gore|degil|cok|buyuk|kucuk|yildiz\w*|gunes\w*|dunya\w*|uzerinde|asagida\w*|"
                    r"olustur\w*|adim|sonuc|dogru\w*|yanlis\w*|baslangic\w*|seklinde|ozet\w*|ogrenci\w*|"
                    r"otegezegen\w*|gokada\w*|kutlecekim\w*|cozum\w*|tarafindan|arasinda|oldugu\w*|"
                    r"bulundugu\w*|sagla\w*|ogren\w*)\b")
# Çoktan seçmeli sorularda şema gereği ASCII olan JSON anahtarları sayılmaz
JSON_KEYS = re.compile(r"\"(sorular|soru|secenekler|dogru_cevap|aciklama|[A-D])\"\s*:")
MIN_LETTERS = 80
MIN_TR_RATIO = 0.015       # doğal Türkçede bu harflerin oranı ~%8-11
JOB_REJECT_RATIO = 0.3


def tr_char_ratio(text: str) -> tuple[float, int]:
    letters = [c for c in JSON_KEYS.sub("", text) if c.isalpha()]
    return sum(c in TR_CHARS for c in letters) / max(len(letters), 1), len(letters)


def missing_turkish_chars(instruction: str, response: str) -> str | None:
    """Kusur varsa kısa açıklama, yoksa None. Talimatın yalnız ilk 300 karakterine bakılır: özetleme
    talimatları İngilizce kaynak metin içerebilir (İngilizce kelimeler FOLDED listesine uymaz)."""
    ratio, n = tr_char_ratio(response)
    if n >= MIN_LETTERS and ratio < MIN_TR_RATIO:
        return f"yanit_tr_harf_orani={ratio:.3f}"
    fr = FOLDED.findall(JSON_KEYS.sub("", response))
    if len(fr) >= 2:
        return f"yanit_ascii_kelime={','.join(fr[:3])}"
    fi = FOLDED.findall(instruction[:300])
    if fi:
        return f"talimat_ascii_kelime={','.join(fi[:3])}"
    return None


def job_defect_ratio(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(1 for r in rows if missing_turkish_chars(r.get("instruction", ""), r.get("response", ""))) / len(rows)


if __name__ == "__main__":
    cases = [  # (talimat, cevap, kusurlu mu)
        ("Aşağıdaki metne göre başlangıç düzeyinde bir soru oluştur.", "Güneş Sistemi'nin en büyük gezegeni Jüpiter'dir; "
         "kütlesi diğer tüm gezegenlerin toplamından fazladır ve çok sayıda uydusu vardır.", False),
        ("Asagidaki metne gore baslangic duzeyinde bir soru olustur.", "Gunes Sistemi'nin en buyuk gezegeni Jupiter'dir; "
         "kutlesi diger tum gezegenlerin toplamindan fazladir ve cok sayida uydusu vardir.", True),
        ("Kara delik nedir?", "Kara delik, kütleçekimi o kadar güçlü bir bölgedir ki ışık bile kaçamaz. Sonucu olarak "
         "olay ufku içindeki hiçbir sinyal dışarı çıkamaz; bu sonucunda gözlemler dolaylı yapılır.", False),
        ("Summarize in Turkish: The Sun is a G-type main-sequence star at the centre of the Solar System.",
         "Güneş, Güneş Sistemi'nin merkezinde bulunan G tipi bir anakol yıldızıdır ve sistemin kütlesinin çoğunu taşır.",
         False),
    ]
    bad = 0
    for ins, resp, want in cases:
        got = bool(missing_turkish_chars(ins, resp))
        bad += got != want
        print("tamam" if got == want else "HATA", want, missing_turkish_chars(ins, resp), "|", ins[:50])
    print("hata:", bad)
