# PDF extraction aracı karşılaştırması

Dosya: `astronomy-2e.pdf` — rastgele 40 sayfa (seed 42).

| Araç | Süre (sn) | >200 karakter çıkan sayfa | Toplam karakter | Boşluk kaybı şüphesi (25+ harf) |
| --- | --- | --- | --- | --- |
| PyMuPDF | 0.06 | 40/40 | 115,080 | 0 |
| pdfplumber | 5.05 | 40/40 | 113,452 | 0 |

PyMuPDF pdfplumber'dan yaklaşık 86 kat hızlı.

## Örnek sayfa (ilk 600 karakter)

### PyMuPDF
```
Watch this brief PBS animation (https://openstax.org/l/30scinotation) that explains how scientific notation 
works and why it’s useful. 
A common unit astronomers use to describe distances in the universe is a light-year, which is the distance light 
travels during one year. Because light always travels at the same speed, and because its speed turns out to be 
the fastest possible speed in the universe, it makes a good standard for keeping track of distances. You might 
be confused because a “light-year” seems to imply that we are measuring time, but this mix-up of time and 
distance is common
```
### pdfplumber
```
16 1 • Science and the Universe: A Brief Tour
LINK TO LEARNING
Watch this brief PBS animation (https://openstax.org/l/30scinotation) that explains how scientific notation
works and why it’s useful.
A common unit astronomers use to describe distances in the universe is a light-year, which is the distance light
travels during one year. Because light always travels at the same speed, and because its speed turns out to be
the fastest possible speed in the universe, it makes a good standard for keeping track of distances. You might
be confused because a “light-year” seems to imply that we are measu
```