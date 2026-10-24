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
        return None
    n = _nz(ins)
    if any(len(_nz(str(q.get("soru", "")))) >= 25 and _nz(str(q.get("soru", ""))) in n for q in qs):
        return "soru_talimatta"
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
    resp = '{"sorular": [{"soru": "Antennae Gökadaları ilk olarak kim tarafından keşfedilmiştir?"}]}'
    got = mcq_in_instruction("Metin... Antennae Gökadaları ilk olarak kim tarafından keşfedilmiştir?", resp)
    bad += got != "soru_talimatta"
    print("tamam" if got == "soru_talimatta" else "HATA", "cevaptaki soru talimatta ->", got)
    print("hata:", bad)
