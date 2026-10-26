"""Çoktan seçmeli soru ÜRETİMİ örneklerinde sorunun/şıkların/doğru cevabın talimatta verilip verilmediği.

Kullanım: 10_generate_instructions.py (iş düzeyinde ret: çoktan seçmeli örneklerin >= JOB_REJECT_RATIO'su
sızıntılıysa çıktı kaydedilmez, iş yeniden denenir) ve 11_verify_instructions.py (örnek düzeyinde eleme,
`mcq_answer_in_instruction`).
"""
from __future__ import annotations

import json
import re

JOB_REJECT_RATIO = 0.3

MCQ_KEY_IN_INS = re.compile(r'"dogru_cevap"\s*:\s*"[ABCD]"|doğru (cevap|yanıt|şık|seçenek)\w*\s*[:=]\s*\(?[A-D]\b',
                            re.I)
MCQ_OPT_LINE = re.compile(r"(?m)^\s*\(?[A-D][).:]\s+\S")
MCQ_OPT_INLINE = re.compile(r"\bA\)\s.{3,300}?\bB\)\s.{3,300}?\bC\)\s.{3,300}?\bD\)\s", re.S)
MCQ_STEM_LABEL = re.compile(r"(?:^|\s)Soru\s*\d*\s*:\s*\S")
# "ilgili soruyu yanıtlayınız" (ortada soru yokken): görev soru ÜRETMEK iken talimat soru CEVAPLATIYOR.
# "soru hazırlayıp JSON formatında yanıtlayın" (yalın "soru") ve "bazı soruları yanıtlayamaz" bu kalıba girmez.
MCQ_ANSWER_FRAME = re.compile(r"\b(soruyu|soruları|sorulara|soruya)\s+(\w+\s+){0,3}?(yanıtla|cevapla|cevap ver|yanıt ver)"
                              r"(?!ya?ma|ye?me)\w*", re.I)


# 25.10.2026 (LLM yargıç bulguları): talimat parçaları. Tek tırnak bölmez (Türkçe kesme işareti).
_TEMPLATE = re.compile(r"\{.*\}", re.S)
_SEG = re.compile(r"(?<=[.!?:])\s+|(?<=[.!?:][\"'”’])\s+|\n+|[\"“”]")
# Talimat (istek) parçası: emir kipindeki üretim fiilleri ve görev sözcükleri. "oluşturur", "verir" gibi bildirme
# kipleri metin cümlesidir, eşleşmez.
_REQUEST = re.compile(r"\b(hazırla|hazırlayın|hazırlayınız|oluştur|oluşturun|oluşturunuz|üret|üretin|üretiniz|ver|verin|"
                      r"veriniz|yaz|yazın|yazınız|sun|sunun|kullan|kullanın|irdele)\b|json|format|seçenekli|"
                      r"çoktan seçmeli|\bsoru(yu|su|lar)?\b|m[ıi]s[ıi]n\b|m[ıi]s[ıi]n[ıi]z\b", re.I)
PASSAGE_MIN_CHARS = 100


def _segments(ins: str) -> list[str]:
    return [s.strip() for s in _SEG.split(_TEMPLATE.sub(" ", ins)) if s and s.strip()]


def mcq_passage_chars(ins: str) -> int:
    """Talimattaki öğretim metninin (istek cümleleri ve JSON şablonu dışındaki kısım) karakter sayısı.
    25.10.2026: "Kaynak metne dayanarak ... soru hazırla" gibi metinsiz 4 talimat; ölçüt bütün sette yalnız bunları
    yakaladı (eşik 100; metni olan en kısa talimatta değer 117)."""
    return sum(len(s) for s in _segments(ins) if not _REQUEST.search(s))


def content_question_in_instruction(ins: str) -> str | None:
    """Soru üretimi talimatında öğrenciye sorulacak sorunun kendisi ("... kimdir?") var mı? İstek cümleleri
    ("soru hazırlar mısın?") sayılmaz. 25.10.2026: 7 örnek, 7'si de gerçek kusur."""
    for s in _segments(ins):
        if s.endswith("?") and not _REQUEST.search(s):
            return s[-80:]
    return None


def _nz(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def mcq_in_instruction(ins: str, resp: str) -> str | None:
    """Soru üretimi talimatında sorunun kendisi/şıkları/doğru cevabı zaten verilmiş mi?

    24.10.2026 incelemesi: 446 çoktan seçmeli örneğin 106'sında talimat "aşağıdaki soruyu cevapla: ... A) ... B) ..."
    biçimindeydi, 29'unda doğru cevap da talimattaydı. Cevap talimatın kopyası olunca örnek soru ÜRETMEYİ öğretmez.
    Kalanlardan 20'lik elle kontrolde ayrıca "Soru: ..." etiketli kök ve soru olmadan "ilgili soruyu yanıtlayınız"
    diyen (tutarsız) talimatlar bulundu.
    """
    if MCQ_KEY_IN_INS.search(ins):
        return "cevap_talimatta"
    if len(MCQ_OPT_LINE.findall(ins)) >= 3 or MCQ_OPT_INLINE.search(ins):
        return "secenekler_talimatta"
    if MCQ_STEM_LABEL.search(ins):
        return "soru_talimatta"
    if MCQ_ANSWER_FRAME.search(ins):
        return "cevaplatan_talimat"
    try:
        qs = json.loads(re.search(r"\{.*\}", resp, re.S).group(0))["sorular"]
    except Exception:
        qs = []
    n = _nz(ins)
    if any(len(_nz(str(q.get("soru", "")))) >= 25 and _nz(str(q.get("soru", ""))) in n for q in qs):
        return "soru_talimatta"
    if content_question_in_instruction(ins):
        return "icerik_sorusu_talimatta"
    return None


def job_mcq_leak_ratio(rows: list[dict]) -> float:
    m = [r for r in rows if r.get("task_type") == "coktan_secmeli_soru_uretimi"]
    if not m:
        return 0.0
    return sum(1 for r in m if mcq_in_instruction(r.get("instruction", ""), r.get("response", ""))) / len(m)


if __name__ == "__main__":
    # 24.10.2026 incelemesinde gerçek örneklerden alınan durumlar
    cases = {
        "Aşağıdaki metni kullanarak çoktan seçmeli bir soru oluşturunuz ve yalnızca JSON formatında yanıtlayınız. Metin: X": None,
        "Standart model bazı soruları yanıtlayamaz. Şişme hipotezi...": None,
        "Aşağıdaki metne dayanarak bir çoktan seçmeli soru hazırlayıp JSON formatında yanıtlayın: metin": None,
        "Bu metinden iki soru üret. Soru sayısı: 2": None,
        "Kepler (A) ve Brahe (B) gözlemleri... C) yok": None,
        'metin "dogru_cevap": "A|B|C|D"': None,
        "Aşağıdaki metni okuyarak ilgili soruyu yanıtlayınız: P/2013 R3...": "cevaplatan_talimat",
        "Metin... 2 adet çoktan seçmeli soruyu JSON formatında yanıtla. Metin:": "cevaplatan_talimat",
        "metin. Soru: Keşif tablolarındaki 'o' harfi neyi ifade eder?": "soru_talimatta",
        "metin A) bir şey B) iki şey C) üç şey D) dört şey": "secenekler_talimatta",
        "metin\nA) bir\nB) iki\nC) üç\nD) dört": "secenekler_talimatta",
        'metin "dogru_cevap": "B"': "cevap_talimatta",
    }
    bad = 0
    for ins, want in cases.items():
        got = mcq_in_instruction(ins, '{"sorular": []}')
        bad += got != want
        print("tamam" if got == want else "HATA", want, got, "|", ins[:60].replace("\n", " "))
    # 25.10.2026 yargıç bulguları
    q_cases = {
        "Metin cümlesi burada. Bu metne göre, 1960'lı yıllarda yerçekimi treni fikrini tekrar gündeme getiren kişi kimdir?": True,
        "Aşağıdaki metne dayanarak bir soru üret: 'Güneş tutulması sırasında gamanın pozitif bir değer alması ne anlama gelir? Gamanın işareti...'": True,
        "Aşağıdaki metni okuyup bir çoktan seçmeli soru hazırlar mısın? Metin: Kepler teleskobu...": False,
        "Bu metinden dört seçenekli bir soru oluşturur musun?": False,
        "Kozmik ışınların çoğunu protonlar oluşturur. Bu bilgilere dayanarak bir soru hazırlayınız.": False,
    }
    for ins, want in q_cases.items():
        got = content_question_in_instruction(ins) is not None
        bad += got != want
        print("tamam" if got == want else "HATA", "içerik sorusu", want, got, "|", ins[:60])
    p_cases = {
        "Kaynak metne dayanarak, Te yöntemiyle hangi oksijen çizgisinin kullanıldığını soran dört seçenekli bir soru hazırla. "
        'Talimatta yaklaşık 100 kelimelik bilgilendirici bir giriş yap ve sonucu JSON formatında ver: {"sorular": []}': False,
        "Kozmik ışınların büyük bir çoğunluğunu hidrojen çekirdekleri, yani protonlar oluşturur. Geri kalan kısmın yaklaşık "
        "yüzde 9'unu helyum ve daha ağır çekirdekler oluştururken, küçük bir kısmı da elektronlar ve pozitronlardan meydana "
        "gelir. Bu bilgilere dayanarak bir soru hazırlayınız.": True,
    }
    for ins, want in p_cases.items():
        got = mcq_passage_chars(ins) >= PASSAGE_MIN_CHARS
        bad += got != want
        print("tamam" if got == want else "HATA", "öğretim metni var", want, got, mcq_passage_chars(ins))
    resp = '{"sorular": [{"soru": "Antennae Gökadaları ilk olarak kim tarafından keşfedilmiştir?"}]}'
    got = mcq_in_instruction("Metin... Antennae Gökadaları ilk olarak kim tarafından keşfedilmiştir?", resp)
    bad += got != "soru_talimatta"
    print("tamam" if got == "soru_talimatta" else "HATA", "cevaptaki soru talimatta ->", got)
    print("hata:", bad)
