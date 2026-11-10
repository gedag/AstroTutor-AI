"""11_verify_instructions.py İngilizce kural testleri (API çağrısı yok).

    python scripts/tests/test_verify_rules.py
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
v11 = importlib.import_module("11_verify_instructions")
bad = 0


def check(name, got, want):
    global bad
    ok = got == want
    bad += not ok
    print("ok  " if ok else "FAIL", name, "| beklenen:", want, "| bulunan:", got)


# 1) Görülmeyen metne atıf (talimat veya cevapta)
unseen = {
    "According to the text, how old is the Sun?": True,
    "What does the passage say about pulsars?": False,          # "the passage say" kalıbı yok -> yakalanmaz
    "Based on the provided information, explain redshift.": True,
    "As mentioned in the document, Mars has two moons.": True,
    "The source states that Jupiter is the largest planet.": False,
    "The text says that Jupiter is the largest planet.": True,
    "What is the source of the Sun's energy?": False,
    "Explain how light from distant galaxies is redshifted.": False,
    "Describe the objects listed in the article.": True,
    "In the passage above, the author compares two stars.": True,
    "What is a light-year?": False,
}
for s, want in unseen.items():
    check(f"UNSEEN: {s[:50]}", bool(v11.UNSEEN.search(s)), want)

# 2) Sınıflandırmada atıf silme (öğeler sayılmışken)
strip = {
    "Classify the objects mentioned in the text: Mercury, Venus, Jupiter and Neptune as terrestrial or giant planets.":
        "Classify the objects: Mercury, Venus, Jupiter and Neptune as terrestrial or giant planets.",
    "According to the text, classify Ceres, Pluto, Eris and Vesta as dwarf planets or asteroids.":
        "Classify Ceres, Pluto, Eris and Vesta as dwarf planets or asteroids.",
    "Sort the missions from the passage (Voyager 1, Cassini, Juno, New Horizons) into flybys and orbiters.":
        "Sort the missions (Voyager 1, Cassini, Juno, New Horizons) into flybys and orbiters.",
}
for s, want in strip.items():
    got = v11.strip_unseen_ref(s)
    check(f"strip: {s[:50]}", got, want)
    check("  silme sonrası atıf kalmadı", bool(v11.UNSEEN.search(got)), False)

# 3) Çoktan seçmeli JSON
good = {"questions": [{"question": "What do pulsars emit?", "options": {"A": "radio beams", "B": "sound",
        "C": "neutrinos only", "D": "nothing"}, "answer": "A", "explanation": "..."}]}
check("mcq geçerli", v11.check_mcq(json.dumps(good)), None)
check("mcq türkçe anahtar", v11.check_mcq('{"sorular": []}'), "question_count")
b = json.loads(json.dumps(good)); b["questions"][0]["answer"] = "E"
check("mcq geçersiz cevap", v11.check_mcq(json.dumps(b)), "answer")
b = json.loads(json.dumps(good)); b["questions"][0]["options"]["D"] = "radio beams"
check("mcq tekrar eden seçenek", v11.check_mcq(json.dumps(b)), "duplicate_option")
check("mcq bozuk json", v11.check_mcq("questions: none"), "json_parse")
check("mcq json etrafında metin", v11.check_mcq("Here it is: " + json.dumps(good)), None)

# 4) Üretici türü
check("tier flash", v11.tier("gemini-3.6-flash"), "flash")
check("tier lite", v11.tier("gemini-3.5-flash-lite"), "lite")
check("tier SE", v11.tier(None), "none")

# 5) Kanıt kontrolü
src = ("Pulsars are rapidly rotating neutron stars. As the star spins, beams of radio waves sweep across Earth like a "
       "lighthouse, so astronomers detect regular pulses of radiation.")
check("kanıt bulundu", v11.evidence_ok("beams of radio waves sweep across Earth like a lighthouse, so astronomers detect", src)[0], True)
check("kanıt uydurma", v11.evidence_ok("pulsars are white dwarfs that rotate slowly and emit visible light pulses", src)[0], False)

# 6) Dil tespiti: kısa İngilizce talimatlar İngilizce sayılmalı (yanlış eleme olmasın)
from lingua import Language, LanguageDetectorBuilder  # noqa: E402

det = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.TURKISH, Language.GERMAN, Language.FRENCH,
                                             Language.SPANISH).build()
RESP = ("A pulsar is a rapidly rotating neutron star. Its beams of radio waves sweep across Earth, so we detect "
        "regular pulses, much like the light of a lighthouse.")
en = ["What is a pulsar?", "Explain redshift to a beginner.", "Compare Mars and Venus.", "Why is the sky dark at night?",
      "Summarize the following text in three sentences for high school students",
      "Classify Ceres, Pluto, Eris and Vesta as dwarf planets or asteroids.",
      "How far is Proxima Centauri?", "Define albedo.", "Nebulae: what are they made of?",
      "Could you explain to an advanced student how astronomers measure the mass of a black hole?",
      "Prepare a short lesson for beginners about why Venus is hotter than Mercury.",
      "Write two multiple-choice questions from the passage below and return them as JSON.",
      "Compare the Hubble Space Telescope and the James Webb Space Telescope in terms of wavelength."]
for s in en:
    check(f"is_english: {s[:45]}", v11.is_english(det, RESP, s), True)
mcq = '{"questions": [{"question": "What do pulsars emit?", "options": {"A": "radio beams", "B": "sound"}, "answer": "A"}]}'
check("is_english: mcq json cevap", v11.is_english(det, mcq, "Write one question from this passage."), True)
check("is_english: Türkçe cevap", v11.is_english(det, "Pulsar, hızla dönen bir nötron yıldızıdır ve düzenli radyo "
                                                      "atımları yayar.", "What is a pulsar?"), False)
check("is_english: Türkçe uzun talimat", v11.is_english(det, RESP, "Başlangıç seviyesindeki bir öğrenciye pulsarların "
                                                             "nasıl oluştuğunu kısa bir dersle anlat."), False)
print("hata:", bad)
sys.exit(1 if bad else 0)
