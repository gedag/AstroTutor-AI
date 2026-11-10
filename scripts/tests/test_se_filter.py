"""09'daki Stack Exchange "metni değiştirmeden kullanılabilir mi?" filtresi testleri (API çağrısı yok).

    python scripts/tests/test_se_filter.py
"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
b9 = importlib.import_module("09_build_instruction_sources")
A = "A pulsar is a rotating neutron star that emits beams of radiation."
cases = [
    ("What is a pulsar?", A, None),
    ("Q", "The energy is $E=mc^2$ here.", "latex"),
    ("Q", "As @JohnDoe said, it spins.", "user_mention"),
    ("Q", "See https://nasa.gov for more.", "url"),
    ("Q", "Use the <b>bold</b> text", "markup"),
    ("Q", "> quoted line\nanswer", "markup"),
    ("Q", "This is known [1].", "footnote"),
    ("Q", "As this answer explains, it spins.", "dangling_reference"),
    ("Q", "EDIT: corrected value.", "dangling_reference"),
    ("Q", "The Sun has mass 1.989 × 1030 kg.", "exponent_loss"),
    ("Q", "The Sun has mass 1.989 × 10^30 kg.", None),
    ("Q", "Comet tails point away from the Sun.", None),
    ("Q", "see the comments for details", "dangling_reference"),
    ("Contact me at x@y.com", "A", "email"),
    ("Q", "The Earth is 1.5 x 10^8 km from the Sun; 3 > 2 holds.", None),
    # soruda boşta atıf (10.11.2026 pilotunda bulundu)
    ("Milky Way\n\nI have seen pictures of the Milky Way such as this:\n\n...but what is the ribbon?", A,
     "dangling_reference_in_question"),
    ("Why sensors?\n\nIn the video Brian Eno on Apollo starting at 2:30 they say", A, "dangling_reference_in_question"),
    ("This answer notes that Apollo 13 holds the record.", A, "dangling_reference_in_question"),
    ("Why slowdown?\n\nLook at this graph of velocity.", A, "dangling_reference_in_question"),
    ("Why not level?\n\nLooking at an image of the orbiter on the ground, the nose gear is higher.", A, None),
    ("What is a pulsar?\n\nI read about them in a book.", A, None),
]
bad = 0
for q, a, want in cases:
    got = b9.se_text_issue(q, a)
    k = got.split(":")[0] if got else None
    bad += k != want
    print("ok  " if k == want else "FAIL", want, "|", got)

# Cevapta insan sesi (Eda kararı 10.11.2026): kişisel deneyim, kişisel görüş, forum dili, sohbet kısaltması, zamana bağlı
voice = [
    ("A pulsar is a rotating neutron star; its beams sweep past Earth.", None),
    ("I remember watching the launch from Florida.", "personal_experience"),
    ("When I measured it with my telescope, the period was 2 s.", "personal_experience"),
    ("I think the answer is that tidal forces dominate.", "personal_opinion"),
    ("As the OP noted, the orbit is elliptical.", "forum_language"),
    ("Great question! The orbit is elliptical.", "forum_language"),
    ("Hope this helps.", "forum_language"),
    ("TL;DR: it is gravity.", "chat_abbreviation"),
    ("IIRC the mission launched in 1977.", "chat_abbreviation"),
    ("The probe is currently 160 AU from the Sun.", "time_dependent"),
    ("As of 2019 there were 4000 known exoplanets.", "time_dependent"),
    ("Thanks to tidal locking, the same face always points to Earth.", None),   # "thanks to" sorun değil
    ("The OPERA experiment measured neutrino speeds.", None),                  # "OPERA" -> OP değil
    ("Optical depth (tau) measures opacity; the Sun's photosphere is where tau is about 2/3.", None),
]
for a, want in voice:
    got = b9.se_voice_issue(a)
    k = got.split(":")[0] if got else None
    bad += k != want
    print("ok  " if k == want else "FAIL", "ses:", want, "|", got)

# Lisans sürümü cevap tarihine göre
for d, want in (("2010-05-01T10:00:00Z", "CC BY-SA 2.5"), ("2013-07-17T08:00:00Z", "CC BY-SA 3.0"),
                ("2018-05-01T23:59:59Z", "CC BY-SA 3.0"), ("2018-05-02T00:00:00Z", "CC BY-SA 4.0"),
                ("2024-03-20T12:00:00Z", "CC BY-SA 4.0"), (None, "CC BY-SA (version unknown)")):
    got = b9.se_license(d)
    bad += got != want
    print("ok  " if got == want else "FAIL", "lisans:", d, want, "|", got)
print("hata:", bad)
sys.exit(1 if bad else 0)
