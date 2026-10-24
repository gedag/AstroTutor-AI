"""Metinde kalan HTML etiketi ve HTML entity kalıntıları (03 temizleme kuralı + 06b düzeltmesi).

24.10.2026 denetimi: final corpus'ta 1 `<br>` (NASA Science), 2 `<sub id="...">⊕</sub>` (Türkçe Wikipedia) ve
4 `&amp;` (Türkçe Wikipedia) kalmıştı. Yalnız belirsizliği olmayan kalıplar düzeltilir:
  - `<sup>x</sup>` -> `^x` (üs korunur); bilinen satır içi etiketler (br, sub, span, small, b, i, em, strong, a href) silinir, içerikleri korunur;
    `<br>` boşlukla değiştirilir (yeni satır üretmez, böylece 03'teki satır kuralları farklı sonuç vermez);
  - adlandırılmış/sayısal HTML entity'leri karşılıklarına çevrilir.
Matematik gösterimi (ör. "1.338<p<1.746", "<A>= 2.33") etiket sayılmaz.
"""
from __future__ import annotations

import html
import re

TAG = re.compile(r"</?(?:sub|span|small|b|i|em|strong)(?:\s+[a-z-]+=\"[^\"<>]{0,100}\")*\s*>|</a>|"
                 r"<a\s+href=\"[^\"<>]{0,300}\"[^<>]{0,100}>", re.I)
SUP = re.compile(r"<sup(?:\s+[a-z-]+=\"[^\"<>]{0,100}\")*\s*>([^<>]{1,20})</sup>", re.I)
BR = re.compile(r"\s*<br\s*/?>\s*", re.I)
ENTITY = re.compile(r"&(?:nbsp|amp|lt|gt|quot|apos|#\d{1,6}|#x[0-9a-f]{1,6});", re.I)


def strip_html_residue(text: str) -> tuple[str, int]:
    n = len(SUP.findall(text)) + len(BR.findall(text)) + len(TAG.findall(text)) + len(ENTITY.findall(text))
    if not n:
        return text, 0
    text = SUP.sub(lambda m: "^" + m.group(1), text)  # 10<sup>23</sup> -> 10^23 (üs kaybolmasın)
    text = BR.sub(" ", text)
    text = TAG.sub("", text)
    text = ENTITY.sub(lambda m: html.unescape(m.group(0)).replace("\xa0", " "), text)
    return text, n


if __name__ == "__main__":
    cases = [
        ("spectrometer.<br>CTX provides", "spectrometer. CTX provides"),
        ('Yaklaşık 1,6 R <sub id="mwARs">⊕</sub> yarıçapı', "Yaklaşık 1,6 R ⊕ yarıçapı"),
        ("Harvard &amp; Smithsonian", "Harvard & Smithsonian"),
        ("with $1.338<p<1.746$, to", "with $1.338<p<1.746$, to"),
        ("almost constant (<A>= 2.33)", "almost constant (<A>= 2.33)"),
        ("a < b and c > d", "a < b and c > d"),
        ("10<sup>23</sup> m", "10^23 m"),
    ]
    bad = 0
    for src, want in cases:
        got, _ = strip_html_residue(src)
        ok = got == want
        bad += not ok
        print("tamam" if ok else "HATA", repr(src), "->", repr(got))
    print("hata:", bad)
