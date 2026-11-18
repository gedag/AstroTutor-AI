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
    # 10.11.2026 canlı üretimde bulunan kalıp
    "Classify the following moons: Nereid, Triton, Mimas and Phoebe based on their descriptions in the provided text "
    "as either regular or irregular satellites.":
        "Classify the following moons: Nereid, Triton, Mimas and Phoebe based on their descriptions as either regular "
        "or irregular satellites.",
    "Classify Phobos, Deimos, Mars and Earth into planets or moons based on the provided document.":
        "Classify Phobos, Deimos, Mars and Earth into planets or moons.",
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
# 7) SFT uzunluğu (Final Rehberi: 1024 token; Qwen3 chat template, düşünme kapalı, sistem mesajı dahil)
short = v11.train_tokens("What is a pulsar?", "A rotating neutron star.")
check("kısa örnek kısa ölçülüyor", 20 < short < 80, True)
long_resp = " ".join(["Pulsars are rapidly rotating neutron stars."] * 200)
check("uzun örnek sınırı aşıyor", v11.train_tokens("Explain pulsars.", long_resp) > 1024, True)

# 8) 18.11.2026 kural denetimi: canlı veride kaçan kalıplar ve yeni güvenlik kuralları
unseen2 = {
    # kaçanlar (gerçek örneklerden)
    "Classify the four items into telescopes or young stellar objects based on the text: TIFR, HH 1042, HAWK-I.": True,
    "Compare the two black holes based on characteristics described in the study.": True,
    "Here is a comparison based on the study:": True,
    "Classify the observatories by wavelength range as described in the survey context: JWST, ALMA, VLA.": True,
    "According to the authors, the planet is tidally locked.": True,
    "Classify the missions by status described in the source: Kepler, Spitzer, TESS.": True,
    # doğal İngilizce: tetiklenmemeli
    "Helioseismology is the study of solar surface oscillations.": False,
    "What was its effect on the study of planetoid motions?": False,
    "Why can interstellar dust be ruled out as the source of the dark matter?": False,
    "The waves compress if the source moves closer to the observer.": False,
    "It is discussed in the context of solar time series.": False,
    "Explain this in the context of stellar evolution.": False,
}
for s, want in unseen2.items():
    check(f"UNSEEN+: {s[:50]}", bool(v11.UNSEEN.search(s)), want)
strip2 = {
    "Classify the following space missions based on Dr. Stapelfeldt's involvement as described in the text into two "
    "categories: WFPC2, Spitzer, TPF, and WFIRST.":
        "Classify the following space missions based on Dr. Stapelfeldt's involvement into two categories: WFPC2, "
        "Spitzer, TPF, and WFIRST.",
    "Classify the observatories by wavelength range as described in the survey context: JWST, ALMA, VLA, Chandra.":
        "Classify the observatories by wavelength range: JWST, ALMA, VLA, Chandra.",
    "Classify the items into telescopes or young stellar objects based on the text: TIFR, HH 1042, HAWK-I, and Chandra.":
        "Classify the items into telescopes or young stellar objects: TIFR, HH 1042, HAWK-I, and Chandra.",
}
for s, want in strip2.items():
    got = v11.strip_unseen_ref(s)
    check(f"strip+: {s[:50]}", got, want)
    check("  silme sonrası atıf kalmadı", bool(v11.UNSEEN.search(got)), False)
long_list = ("Classify the following space observatories as either Space Observatories (Infrared / Multi-wavelength) or "
             "Radio Ground-Based Telescopes based on their primary operating platform and wavelength range: James Webb "
             "Space Telescope, Atacama Large Millimeter/submillimeter Array, Jansky Very Large Array, Chandra.")
check("has_passage: uzun tek satır öğe listesi metin DEĞİL", v11.has_passage(long_list), False)
with_text = ("Classify the objects described in the passage below into planets and moons.\n\nPassage:\n" +
             "Titan is the largest moon of Saturn and has a thick nitrogen atmosphere. Mars is a terrestrial planet "
             "with two small moons, Phobos and Deimos, which may be captured asteroids. Europa orbits Jupiter and hides "
             "a global ocean beneath its icy crust.")
check("has_passage: ayrı satırda metin var", v11.has_passage(with_text), True)

media = {
    "In the figure below, the arrows show CMB photons.": "figure below",
    "They used the training vehicle, as pictured below.": "pictured below",
    "Consider the below picture:": "below picture",
    "Image source: NASA": "Image source",
    "Below is a plot of initial mass versus remnant mass.": "Below is a plot",
    "The Moon keeps the same face, as seen in the figure on the left.": "as seen in the figure",
    # tetiklenmemeli
    "A flaw in any of the surfaces will distort the image.": None,
    "The distance between the lens and the image formed at the focus is the focal length.": None,
    "The following table compares them:\n\n| Planet | Moons |\n|---|---|\n| Mars | 2 |": None,
}
for s, want in media.items():
    check(f"media_ref: {s[:45]}", v11.media_ref(s), want)
trunc = {"Have a look at this NASA simulation of the collision:": True,
         "Only near the equator could the moon be completely horizontal,": True,
         "The spacecraft then returned the sample to Earth.": False,
         "* **Mass:** about 5 to 30 solar masses": False,
         "Galactic archaeology studies the Milky Way (using stellar ages)": False,
         "Temperatures reach 6000 K": False}
for s, want in trunc.items():
    check(f"truncated: {s[:45]}", bool(v11.TRUNCATED.search(s.rstrip("*_` \n"))), want)
check("encoding: mojibake", bool(v11.ENCODING_ART.search("The Sunâ€™s core is hot.")), True)
check("encoding: replacement char", bool(v11.ENCODING_ART.search("The Sun�s core")), True)
check("encoding: temiz (−, °, ’)", bool(v11.ENCODING_ART.search("It is −15 °C at the Sun’s pole.")), False)
check("placeholder: [insert]", bool(v11.PLACEHOLDER.search("The mass is [insert value] kg.")), True)
check("placeholder: TODO", bool(v11.PLACEHOLDER_CS.search("TODO: add the distance")), True)
check("placeholder: normal köşeli parantez", bool(v11.PLACEHOLDER.search("Iron [Fe] is common.") or
                                                 v11.PLACEHOLDER_CS.search("Iron [Fe] is common.")), False)
check("ai_disclaimer", bool(v11.AI_DISCLAIMER.search("As an AI language model, I think pulsars spin.")), True)
check("ai_disclaimer: normal metin", bool(v11.AI_DISCLAIMER.search("Astronomers model the galaxy with AI tools.")), False)
rep = "Pulsars are rotating neutron stars that emit beams. They are very dense.\nPulsars are rotating neutron stars that emit beams."
check("repeated_sentence", bool(v11.repeated_sentence(rep)), True)
check("repeated_sentence: yok", v11.repeated_sentence("Pulsars spin fast. They emit radio beams that sweep Earth."), None)

# 8b) talimata uyum: soru sayısı ve hedef kitle-seviye
q2 = json.dumps({"questions": [good["questions"][0]] * 2}) if isinstance(good, dict) and "questions" in good else None
q3 = json.dumps({"questions": [good["questions"][0]] * 3}) if q2 else None
check("mcq sayı: iki istendi, iki var", v11.mcq_count_mismatch("Generate two multiple-choice questions.\n\nPassage: x", q2),
      None)
check("mcq sayı: iki istendi, üç var", v11.mcq_count_mismatch("Generate two multiple-choice questions.", q3),
      "asked=2 got=3")
check("mcq sayı: 'four-option' sayı sayılmaz", v11.mcq_count_mismatch(
    "Write four-option multiple-choice questions about the passage.", q3), None)
check("mcq sayı: 'two four-option questions'", v11.mcq_count_mismatch(
    "Write two four-option multiple-choice questions.", q2), None)
aud = {"Explain TRAPPIST-1 to a high school science student.": "beginner",
       "Summarize the text in 2 sentences for a general audience:": "intermediate",
       "Summarize the passage for an undergraduate astronomy student:": "advanced",
       "Explain fusion to a pre-university student.": "intermediate",
       "Why did researchers combine Webb data with ground-based telescopes?": None,
       "What is a pulsar?": None}
for s, want in aud.items():
    check(f"audience_level: {s[:45]}", v11.audience_level(s), want)

# 9) rule_checks uçtan uca: yeni kurallar doğru nedenle eler, iyi örnek kalır
from common import RemovalLog  # noqa: E402
from lingua import LanguageDetectorBuilder, Language  # noqa: E402

det2 = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.TURKISH, Language.SPANISH,
                                              Language.FRENCH, Language.GERMAN).build()
GOOD = ("A pulsar is a rapidly rotating neutron star that emits beams of radio waves from its magnetic poles. "
        "As it spins, the beams sweep across Earth like a lighthouse, so astronomers detect regular pulses.")


def row(i, ins, resp, t="definition_explanation", se=False):
    return {"raw_example_id": f"R{i}", "task_type": t, "planned_task_type": t, "level": "unassigned" if se else "beginner",
            "instruction": ins, "response": resp, "source_name": "x", "source_document": f"D{i}",
            "generation_method": v11.SE_METHOD if se else "llm_synthetic_from_source_document"}


cases = [row(0, "What is a pulsar and how is it detected?", GOOD),
         row(1, "Why does the Moon look larger near the horizon?", GOOD + " Consider the below picture:", se=True),
         row(2, "What is a pulsar and how do astronomers find them?", GOOD + " Have a look at this simulation:", se=True),
         row(3, "Explain what a pulsar is to a beginner student.", GOOD + " " + GOOD.split(". ")[0] + "."),
         row(4, "Explain what a pulsar is to an undergraduate astronomy student.", GOOD)]   # etiket beginner
rl = RemovalLog(Path(__file__).parent / "_tmp_removed.csv", "t")
kept = v11.rule_checks(cases, rl, det2, set())
check("rule_checks: iyi örnek kaldı", [r["raw_example_id"] for r in kept], ["R0"])
check("rule_checks: nedenler", sorted((x["id"], x["reason"]) for x in rl.rows),
      [("R1", "missing_media_reference"), ("R2", "truncated_response"), ("R3", "repeated_sentence"),
       ("R4", "level_audience_mismatch")])
print("hata:", bad)
sys.exit(1 if bad else 0)
