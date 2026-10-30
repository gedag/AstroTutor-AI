"""NASA basın bülteni künyesi ve kişisel iletişim bilgisi temizliği (06b adım 1b).

24.10.2026 corpus incelemesi: NASA Science metinlerinde 348 e-posta adresi ve 183 telefon numarası (basın iletişim
blokları: "Media Contact: ⏎ Jane Roe ⏎ NASA's Goddard Space Flight Center, Greenbelt, Md. ⏎ 301-555-0100"),
ayrıca kredi satırları ("Image Credit: ..."), yalnız bağlantıdan oluşan satırlar ve "For more information ... visit"
çağrıları vardı. Bunlar alan bilgisi taşımaz; e-posta/telefon kişisel veridir.

Kurallar satır düzeyindedir; düzyazı paragraflarına dokunulmaz (uzun satırlar korunur).
"""
from __future__ import annotations

import re

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.(?:[\w-]+\.)*[a-z]{2,}\b", re.I)
# Telefon: "(617) 954-3214", "321-867-2525", "818.354.7581", "808 555 0199". Sondan sonra cümle noktası gelebilir
# (30.10.2026: ilk sürüm "(?![\d.])" yüzünden cümle sonundaki 5 numarayı kaçırmıştı); ondalık devamı ("752.3142")
# telefon sayılmaz. Alan kodundan sonraki ayraç ile ikinci ayraç aynı olmalıdır (parantezli alan kodunda serbest);
# bu yüzden "6 356 752.3142" gibi sayısal veriler eşleşmez, "+01 303 447 2020" ise eşleşir.
PHONE = re.compile(r"(?<![\d.])(?:\+?1[ .-]?)?(?:\(\d{3}\)\s?|\d{3}([ .-]))\d{3}(?(1)\1|[ .-])\d{4}(?!\d|\.\d)")
CONTACT_HEAD = re.compile(r"^(Media|News Media|Press|Public Affairs)?\s*Contacts?\s*(Information)?\s*:?\s*$|"
                          r"^(Media|News Media|Press) Contacts?\s*:|"
                          # "For more information about the DART mission:" ardından ad satırları gelir
                          r"^For more information( about [^:]{0,80})?:\s*$|"
                          r"^Reporters with questions about [^:]{0,60}(should )?contact:?\s*$", re.I)
CREDIT = re.compile(r"^(Text|Image|Video|Illustration|Animation|Photo|Banner image|Header image|Graphic)s?\s+"
                    r"[Cc]redits?\s*[:-]", re.I)
MORE_INFO = re.compile(r"^(For more (information|info|details)|To (learn|get|find|see) (more|even more)|Learn more|"
                       r"Find out more|More information).{0,160}(visit|see|go to|check out|at|available)\b", re.I)
LINK_ONLY = re.compile(r"^(For the full text.{0,60}link to:?|.{0,40}\blink to:)\s*$|^(https?://|www\.|/resources/)\S+\s*$",
                       re.I)
SEPARATOR = re.compile(r"^(#{3}|-{3,}|\*{3,})\s*$")
# Tek başına duran merkez künyesi: "NASA's Goddard Space Flight Center, Greenbelt, Md.", "NASA Headquarters, Washington"
CENTER_LINE = re.compile(r"^(NASA.s |NASA )?([A-Z][\w.'’ -]{0,40} )?(Space Flight Center|Research Center|Space Center|"
                         r"Propulsion Laboratory|Headquarters|Flight Research Center)(,\s*[A-Z][\w. ]{1,25}){0,2}\.?\s*$")
TAIL_LINK = re.compile(r"\s*(For the full text( and image)?|For more (information|details)),? (link|go) to:?\s*$", re.I)
CONTACT_FIELD = re.compile(r"^(E-?mail|Phone|Tel|Fax|Web ?Site|Website)\s*:", re.I)
MAX_BOILER = 200  # bu uzunluktan uzun satırlar düzyazı sayılır, dokunulmaz


def clean_press(text: str) -> tuple[str, dict]:
    out, n = [], {"contact_block": 0, "pii_line": 0, "credit": 0, "more_info": 0, "link_only": 0, "separator": 0,
                  "center_line": 0}
    in_block, block_left = False, 0
    for ln in text.splitlines():
        s = ln.strip()
        short = len(s) <= MAX_BOILER
        if in_block:
            # İletişim bloğu: en fazla 6 satır ve her satır en fazla 8 kelime (ad, kurum, şehir, telefon).
            # Satırları ~70 karakterde kırılmış eski bültenlerde düzyazı satırları 10+ kelimedir; ilk sürüm burada
            # boş satır bulamayıp bütün metni siliyordu (DOC_009307, 24.10.2026).
            if s and block_left > 0 and len(s.split()) <= 8 and not s.startswith("#"):
                n["contact_block"] += 1
                block_left -= 1
                continue
            in_block = False
        if s and short and CONTACT_HEAD.match(s):
            in_block, block_left = True, 6
            n["contact_block"] += 1
            continue
        # e-posta/telefon içeren KISA satır (iletişim satırı) silinir; uzun (düzyazı) satırda yalnız bilgi
        # maskelenir (scrub_inline_pii), cümle yarım kalmasın
        if s and (EMAIL.search(s) or PHONE.search(s)) and (len(s.split()) <= 8 or CONTACT_FIELD.match(s)):
            n["pii_line"] += 1
            continue
        if s and short and CONTACT_FIELD.match(s):
            n["pii_line"] += 1
            continue
        if s and short and CREDIT.match(s):
            n["credit"] += 1
            continue
        if s and short and MORE_INFO.match(s):
            n["more_info"] += 1
            continue
        if s and short and LINK_ONLY.match(s):
            n["link_only"] += 1
            continue
        if s and SEPARATOR.match(s):
            n["separator"] += 1
            continue
        if s and len(s.split()) <= 10 and CENTER_LINE.match(s):
            n["center_line"] += 1
            continue
        if s and TAIL_LINK.search(s):  # paragrafın sonuna yapışmış "For the full text and image link to:"
            n["link_only"] += 1
            ln = TAIL_LINK.sub("", ln)
        out.append(ln)
    return "\n".join(out).strip(), n


def scrub_inline_pii(text: str) -> tuple[str, int]:
    """Uzun satırların içinde kalan e-posta/telefonlar (satır silinmez, yalnız bilgi çıkarılır)."""
    k = len(EMAIL.findall(text)) + len(PHONE.findall(text))
    return PHONE.sub("[telefon]", EMAIL.sub("[e-posta]", text)), k


if __name__ == "__main__":
    t = ("NASA's Webb telescope found water in the disk around the young star.\n"
         "For more information on NASA's Lucy mission, visit:\nhttps://www.nasa.gov/lucy\n"
         "Image Credit: NASA, ESA, and the Hubble Heritage Team\n"
         "Media Contacts:\nJane Roe\nNASA's Goddard Space Flight Center, Greenbelt, Md.\n301-555-0100\n\n"
         "The Hubble Space Telescope is a project of international cooperation between NASA and ESA. NASA's Goddard "
         "Space Flight Center in Greenbelt, Maryland, manages the telescope.\n"
         "Contacts:\nphone 808 555 0199; email: jroe@example.edu\n###\n"
         "John Roe 818-555-0123\n"
         "The comet's nucleus is 1.5 km across and rotates every 12.4 hours, according to the team.")
    out, n = clean_press(t)
    print(out)
    print(n)
    must_keep = ["water in the disk", "project of international cooperation", "1.5 km across"]
    must_drop = ["For more information", "https://", "Image Credit", "Jane Roe", "301-555", "jroe@", "John Roe", "###"]
    bad = [x for x in must_keep if x not in out] + [x for x in must_drop if x in out]
    print("HATA:" if bad else "tamam", bad)
    print(scrub_inline_pii("Results show R@P0.99 of 0.903 and contact jane.roe@example.org or 301-555-0100 today."))
    # satırları kırılmış eski bülten: iletişim bloğu düzyazıyı YUTMAMALI
    old = ("Two Spacecraft See New Plume Activity on Jovian Moon Io\nMarch 29, 2001\nContact:\nJohn Roe\n"
           "Jet Propulsion Laboratory, Pasadena, Calif.\n(818) 555-0123\n"
           "The new plume originates from a volcanic feature named Tvashtar Catena\n"
           "near Io's north pole. Scientists were astounded to discover so large a\n"
           "plume so near the pole, because all active plumes previously detected on\n")
    out2, n2 = clean_press(old)
    ok2 = "Tvashtar Catena" in out2 and "astounded" in out2 and "John Roe" not in out2 and "555-0123" not in out2
    print("kırık satırlı bülten:", "tamam" if ok2 else "HATA", n2)
    print(out2)
    t3 = ("The Hubble Space Telescope is operated by NASA's Goddard Space Flight Center in Greenbelt, Maryland.\n"
          "NASA's Goddard Space Flight Center, Greenbelt, Md.\nNASA Headquarters, Washington\n"
          "Titan passed in front of Mimas, as seen from the spacecraft. For the full text and image link to:\n"
          "## Jet Propulsion Laboratory\nJPL built the rover.")
    out3, n3 = clean_press(t3)
    ok3 = ("operated by NASA's Goddard" in out3 and "Greenbelt, Md." not in out3 and "Headquarters, Washington" not in out3
           and out3.count("as seen from the spacecraft.") == 1 and "link to" not in out3 and "## Jet Propulsion" in out3)
    print("künye satırı / yapışık bağlantı:", "tamam" if ok3 else "HATA", n3)
    print(out3)
    t4 = ("Langley Research Center in Hampton, Virginia supported the mission.\n"
          "For more information about the DART mission:\nAnn Roe / Mary Roe\nHeadquarters, Washington\n")
    out4, n4 = clean_press(t4)
    ok4 = "Langley Research Center in Hampton" in out4 and "Ann Roe" not in out4 and "Headquarters" not in out4
    print("DART kalıbı:", "tamam" if ok4 else "HATA", n4, "|", out4)
    # cümle sonundaki numaralar maskelenir; sayısal veriler korunur (30.10.2026)
    s5 = ("To arrange interviews call the GSA Newsroom in Boston, Massachusetts at any time during the meeting: "
          "(617) 954-3214. Updates are available by calling 321-867-2525. Or 818.354.7581. "
          "Earth's polar radius is 6 356 752.3142 m and the value 6416 247.4627 comes from the table; R@P0.99 of 0.903.")
    o5, k5 = scrub_inline_pii(s5)
    ok5 = (k5 == 3 and "954-3214" not in o5 and "867-2525" not in o5 and "354.7581" not in o5
           and "6 356 752.3142" in o5 and "6416 247.4627" in o5 and "R@P0.99" in o5)
    print("cümle sonu numara / sayısal veri:", "tamam" if ok5 else "HATA", k5, "|", o5)
    out6, n6 = clean_press("The observatory hosted the workshop.\n+01 303 447 2020 ext. 1156\nThe meeting ended.")
    ok6 = "447 2020" not in out6 and "hosted the workshop" in out6 and n6["pii_line"] == 1
    print("uluslararası önekli numara satırı:", "tamam" if ok6 else "HATA", "|", out6.replace("\n", " / "))
