"""Kaybolmuş üs ifadelerini geri yazar: "1.5 × 108 km" -> "1.5 × 10^8 km".

24.10.2026: Wikipedia düz metin servisi (TextExtracts), HTML üst simgelerini (<sup>) siler; trafilatura (NASA
Science) ve PyMuPDF (OpenStax; üs yazı konumuyla verilmiş) de aynısını yapar. Sonuç "1.8×107 K", "~109 to 1011 T"
gibi anlamı değişmiş sayılar (Wikipedia EN'de 501, TR'de 117, OpenStax'ta 23, NASA Science'ta 17 doküman).
Yalnız belirsizliği olmayan kalıplar düzeltilir (01'den yeniden indirme yerine; gerekçe experiments.md):
  A) bilimsel gösterim: <sayı> × 10NN  (harf "x" ancak ondalıklı sayıdan sonra: "1024x1024 piksel" bozulmaz)
  B) aralık + birim   : 10NN–10NN <birim>   (ör. "105–109 solar masses", "1012–1013 kg")
  C) yaklaşık + birim : ~10NN <birim>       (ör. "~1024 W")
Üs 1-2 basamaklı (A'da 3'e kadar) ve 0 ile başlamaz; negatif üsler (−11) de düzeltilir.
"""
from __future__ import annotations

import re

UNIT = (r"(?:kg|g|t|m|km|cm|mm|nm|μm|J|W|erg|ergs|T|G|K|Hz|eV|keV|MeV|GeV|TeV|s|yr|yrs|years?|yıl|ly|pc|kpc|Mpc|AU|"
        r"M☉|L☉|R☉|M_sun|solar mass(?:es)?|Güneş kütlesi|watts?|joules?|kelvin|teslas?|gauss|kilograms?|grams?|"
        r"meters?|metres?|kilomet(?:er|re)s?|metre|kilometre|N|Pa|bar|atoms?|particles?|stars?|galaxies|"
        r"yıldız|galaksi|gökada|bits?|photons?|molecules?|molekül|cm−3|cm-3|m−3|kg/m3|g/cm3)")
# Aralık ve "~" kalıplarında negatif üs yalnız Unicode eksi (−) ile: "R ~ 10-11 kpc" = "10 ile 11 kpc" (arXiv)
EXP = r"(?:[1-9]\d{0,1}|−[1-9]\d{0,1})"
# A) ×: herhangi bir sayıdan sonra; x: yalnız ondalıklı sayıdan sonra (2.5 x 1024)
# Üssün arkasından ondalık gelemez: "1076.8 x 1057.4 x 1052.6 kilometers" bir boyut ifadesidir (NASA Science)
NO_DEC = r"(?![.,]\d)"
SCI = re.compile(r"(?P<m>(?:\d+[.,]\d+|\d+|\))(?:\s?±\s?\d+(?:[.,]\d+)?)?\)?)\s?(?P<op>×)\s?10(?P<e>[1-9]\d{0,2}|[−-][1-9]\d{0,2})\b" + NO_DEC +
                 r"|(?P<m2>\d{1,2}[.,]\d+)\s?(?P<op2>x)\s?10(?P<e2>[1-9]\d{0,2}|[−-][1-9]\d{0,2})\b" + NO_DEC)
RANGE = re.compile(r"(?<![\d.,^])10(?P<a>" + EXP + r")\s?(?P<sep>–|—|-|to|ile|ila|~)\s?10(?P<b>" + EXP + r")" + NO_DEC +
                   r"(?P<u>\s?" + UNIT + r")\b")
APPROX = re.compile(r"(?P<p>[~∼≈]\s?)10(?P<e>" + EXP + r")" + NO_DEC + r"(?P<u>\s" + UNIT + r")\b")


def _e(x: str) -> str:
    return x.replace("−", "-")


def fix_exponents(text: str) -> tuple[str, int]:
    n = 0

    def sci(m):
        nonlocal n
        # 3+ basamaklı ondalıksız katsayı bilimsel gösterim değil, boyuttur: "1024 × 1024 pixels", "103 × 104 miles"
        if m.group("m") is not None and re.fullmatch(r"\d{3,}", m.group("m")):
            return m.group(0)
        n += 1
        if m.group("m") is not None:
            return f"{m.group('m')} {m.group('op')} 10^{_e(m.group('e'))}"
        return f"{m.group('m2')} {m.group('op2')} 10^{_e(m.group('e2'))}"

    def rng(m):
        nonlocal n
        n += 1
        return f"10^{_e(m.group('a'))}{m.group('sep') if m.group('sep') in '–—-~' else ' ' + m.group('sep') + ' '}10^{_e(m.group('b'))}{m.group('u')}"

    def apx(m):
        nonlocal n
        n += 1
        return f"{m.group('p')}10^{_e(m.group('e'))}{m.group('u')}"

    # zincirleme çarpımlar ("6.7 × 10−8×10−18") için değişiklik kalmayana kadar (en fazla 3 tur)
    for _ in range(3):
        new = SCI.sub(sci, text)
        if new == text:
            break
        text = new
    text = RANGE.sub(rng, text)
    text = APPROX.sub(apx, text)
    return text, n


if __name__ == "__main__":
    tests = [
        ("distance is about 1.5 × 108 kilometers", "1.5 × 10^8 kilometers"),
        ("mass of (1.62±0.04)×109 M☉.", "×"),
        ("about 5.97 x 1024 kg", "5.97 x 10^24 kg"),
        ("image size is 1024x1024 pixels", "1024x1024 pixels"),
        ("IFOV: 75 x 75 mrad 105 x 105 km", "105 x 105 km"),
        ("magnetic field (~109 to 1011 T, ~1013 to 1015 G)", "10^9 to 10^11 T"),
        ("two black holes with masses of 105–109 solar masses", "10^5–10^9 solar masses"),
        ("7,22+0,34-0,40×109 M☉", "×"),
        ("(3,5 ± 0,8) × 109 M☉", "× 10^9 M☉"),
        ("The X-ray luminosity (Lx) of ~1024 W (1031 erg/s)", "~10^24 W"),
        ("hesaplanan 1,1×10−11 değeri", "10^-11"),
        ("in 1011 to 1012 the king", "in 1011 to 1012 the king"),
        ("between 1012–1013 kg mass range", "10^12–10^13 kg"),
        ("1012–1013 yılları arasında hüküm sürdü", "1012–1013 yılları"),
        ("Hubble 10^8 zaten düzgün", "10^8 zaten"),
        ("maneuvers 104-106. Tuesday", "maneuvers 104-106."),
        ("F106 | 3 | 1039 | 1021 - 1050 |", "1021 - 1050"),
        ("The CCD was 1024×1024 pixels", "1024×1024 pixels"),
        ("initial orbit was 103 × 104 miles", "103 × 104 miles"),
        ("shows a dip around R ~ 10-11 kpc, followed", "R ~ 10-11 kpc"),
        ("mass loss rate of around 10−4~10−3 solar masses per year", "10^-4~10^-3 solar masses"),
        ("3.85 × 1026 watts or 3.85 × 1033 ergs/sec", "3.85 × 10^33 ergs"),
        ("(10−7 to 105 Hz)", "10^-7 to 10^5 Hz"),
        ("dimensions 669 x 657 x 654 miles (1076.8 x 1057.4 x 1052.6 kilometers)", "1076.8 x 1057.4 x 1052.6"),
        ("time ~ 1/√(6.7 × 10−8×10−18 g/cm3)", "6.7 × 10^-8 × 10^-18 g"),
    ]
    bad = 0
    for src, _ in tests:  # tek geçişte kesinleşmeli (idempotent)
        once = fix_exponents(src)[0]
        if fix_exponents(once)[1]:
            bad += 1
            print("İKİNCİ GEÇİŞTE DEĞİŞTİ:", src)
    for src, want in tests:
        out, k = fix_exponents(src)
        ok = want in out
        bad += not ok
        print("OK " if ok else "HATA", k, "|", src, "->", out)
    print("hata:", bad)
