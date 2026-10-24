"""Alan (domain) ve alt konu tespiti için elle hazırlanmış terim sözlükleri (İngilizce + Türkçe).

- DOMAIN_TERMS: bir metnin astronomi/uzay alanına ait olup olmadığını ölçmek için (04_filter.py)
- SUBTOPIC_KEYWORDS: Tasarım raporundaki kapsam başlıklarına göre alt konu etiketi (05_deduplicate.py)
- OFF_TOPIC: kapsam dışı (astroloji vb.) işaretleri
Terimler kök/önek olarak eşleşir (\\b + terim), büyük-küçük harf duyarsızdır.
"""
import re

DOMAIN_TERMS = [
    # en
    "astronom", "astrophys", "planet", r"stars?\b", "stellar", "galax", "nebula", "cosmolog", "universe", "cosmic",
    "solar system", r"suns?\b", "solar", r"moons?\b", "lunar", "orbit", "comet", "asteroid", r"meteor(?!olo)", "exoplanet",
    "telescope", "observator", "spacecraft", "probe", "mission", "nasa", "esa", "hubble", "webb", "light-year",
    "light year", "parsec", "redshift", "black hole", "neutron star", "white dwarf", "supernova", "pulsar",
    "quasar", "dark matter", "dark energy", "big bang", "spectrum", "spectra", "spectroscop", "luminosity",
    "magnitude", "eclipse", "jupiter", "saturn", r"mars\b", "venus", "mercury", "neptune", "uranus", "pluto",
    "earth", "kuiper", "oort", "gravit", "accretion", "interstellar", "milky way", "constellation", "satellite",
    "astronaut", "rover", "lander", "space", "celestial", "dwarf planet", "brown dwarf", "magnetosphere",
    "heliosphere", "photosphere", "corona", "infrared", "ultraviolet", "x-ray", "radio", "wavelength",
    "kepler", "tess", "cassini", "voyager", "juno", "apod", "crater", "atmosphere",
    # tr
    "astronomi", "astrofizik", "gezegen", "yıldız", "gökada", "galaksi", "bulutsu", "kozmoloji", "evren",
    "güneş sistemi", "güneş", "ay'", "ayın", "uydu", "yörünge", "kuyruklu yıldız", "asteroit", "göktaşı",
    "ötegezegen", "teleskop", "gözlemevi", "uzay", "kara delik", "nötron yıldızı", "beyaz cüce", "süpernova",
    "atarca", "kuasar", "karanlık madde", "karanlık enerji", "büyük patlama", "tayf", "parlaklık", "kadir",
    "tutulma", "jüpiter", "satürn", "mars", "venüs", "merkür", "neptün", "uranüs", "plüton", "dünya",
    "kütleçekim", "çekim", "yıldızlararası", "samanyolu", "takımyıldız", "gök", "ışık yılı", "kırmızıya kayma",
    "cüce gezegen", "kahverengi cüce", "sonda", "kızılötesi", "morötesi", "dalga boyu", "krater", "atmosfer",
]

SUBTOPIC_KEYWORDS = {
    "exoplanets": ["exoplanet", "extrasolar", "habitable zone", r"transit(s|ing)?\b", "hot jupiter", "super-earth",
                   "ötegezegen", "yaşanabilir bölge", "trappist", "kepler-", "toi-", "planetary system"],
    "cosmology": ["cosmolog", "big bang", "cosmic microwave", "dark energy", "dark matter", "inflation",
                  "hubble constant", "expansion of the universe", "kozmoloji", "büyük patlama",
                  "karanlık enerji", "karanlık madde", "kozmik mikrodalga", "evrenin genişlemesi"],
    "galaxies": ["galax", "milky way", "quasar", "active galactic", "spiral arm", "galaxy cluster",
                 "gökada", "galaksi", "samanyolu", "kuasar", "andromeda"],
    "stars_stellar_evolution": [r"stars?\b", "stellar", "supernova", "white dwarf", "neutron star", "pulsar",
                                "red giant", "main sequence", "nebula", "black hole", "binary star",
                                "yıldız", "süpernova", "beyaz cüce", "nötron yıldızı", "atarca", "kırmızı dev",
                                "anakol", "bulutsu", "kara delik"],
    "planets_moons": ["jupiter", "saturn", r"mars\b", "venus", "mercury", "neptune", "uranus", "pluto", "moon",
                      r"europa\b", r"titan\b", "enceladus", "ganymede", r"rings?\b", "dwarf planet", "jüpiter",
                      "satürn", "venüs", "merkür", "neptün", "uranüs", "plüton", "uydu", "halka",
                      "cüce gezegen"],
    "solar_system": ["solar system", r"suns?\b", "solar wind", "comet", "asteroid", r"meteor(?!olo)", "kuiper", "oort",
                     "eclipse", "güneş sistemi", "güneş", "kuyruklu yıldız", "asteroit", "göktaşı", "tutulma"],
    "missions_spacecraft": ["mission", "spacecraft", "probe", "rover", "lander", "launch", "orbiter", "flyby",
                            "astronaut", "voyager", "cassini", "juno", "perseverance", "artemis", "europa clipper",
                            "görev", "uzay aracı", "sonda", "fırlatma", "astronot", "keşif aracı"],
    "observatories_telescopes": ["telescope", "observator", "hubble", "webb", "chandra", "spitzer", "roman space",
                                 "instrument", "detector", "mirror", "interferomet", "teleskop", "gözlemevi",
                                 "dedektör", "ayna"],
}

OFF_TOPIC = ["horoscope", "zodiac sign", "astrolog", "burç yorum", "burcu", "tarot", "falı"]

# ---------------------------------------------------------------- Wikipedia kategori kontrolü
# Kategori gezintisi alt kategorilere indiği için kurgu (dizi, roman, oyun), bayrak, genel spektroskopi ve
# jeomorfoloji maddeleri de seçilebiliyordu (23.10.2026). Bir madde, kendi kategorilerinden en az biri
# astronomi/uzay konulu ise tutulur; kurgu/kültür/eser kategorileri bu kontrolde sayılmaz.
# Not: re.IGNORECASE Türkçe "ı" ile "i"yi eşit sayıyor ("takımyıldızı" ~ "dizi"); bu yüzden metin önce
# küçük harfe çevrilip büyük-küçük harf duyarlı eşleştirme yapılır.
WIKI_ASTRO_CATEGORY = re.compile(
    r"astro|planet|supercluster|galaxy group|galaxy cluster|abell|refractor|reflector|astronomical coordinate|"
    r"astrodynamic|superbubble|photometric|moving group|impact event|çarpma olay|"
    r"\bstars?\b|stellar|galax|galactic|nebula|cosmolog|solar|\bsun\b|\bmoons?\b|"
    r"lunar|orbit|comet|asteroid|meteor(?!olo)|exoplanet|telescope|observator|spacecraft|space|satellite|universe|"
    r"black hole|neutron|white dwarf|supernova|pulsar|quasar|dark matter|dark energy|big bang|constellation|"
    r"celestial|eclipse|crater|jupiter|saturn|\bmars\b|venus|mercury|neptune|uranus|pluto|kuiper|oort|nasa|"
    r"\besa\b|gravit|relativ|interstellar|milky way|cosmic|astronaut|\brovers?\b|\blanders?\b|heliophys|magnetosphere|"
    r"aurora|gamma-ray|x-ray|astrometr|trans-neptunian|centaur|minor planet|variable|binary|molecular cloud|"
    r"h ii|nucleosynthesis|light pollution|copernic|galileo|"
    r"gezegen|yıldız|gökada|galaksi|galaktik|bulutsu|kozmolo|evren|güneş|uydu|yörünge|kuyruklu|"
    r"asteroit|göktaş|ötegezegen|teleskop|gözlemev|uzay|kara delik|nötron|beyaz cüce|süpernova|atarca|kuasar|"
    r"karanlık madde|karanlık enerji|büyük patlama|takımyıldız|gök|tutulma|jüpiter|satürn|\bmars|venüs|"
    r"merkür|neptün|uranüs|plüton|krater|samanyolu|kütleçekim|görelilik|kozmik|astronot|kuiper|ay bilimi|"
    r"değişen|ikililer|nükleosentez|moleküler bulut|[ıi]şık kirliliği|kopernik|galileo|sharpless|ngc |messier")
WIKI_NON_DOMAIN_CATEGORY = re.compile(
    r"fiction|popular culture|in culture|in art\b|video game|\bgames\b|\bfilms?\b|novels?\b|television|"
    r"tv series|comics|anime|manga|music|songs|albums|\bflags?\b|mytholog|toys|characters|franchise|episodes|"
    r"seasons|\bbooks\b|space opera|science fantasy|paintings|poems|astrolog|esoteric|religious cosmolog|"
    r"creation myth|conspiracy|komplo|coats of arms|\bseals?\b|heraldr|observances|armalar|"
    r"kurgu|filmler|filmleri|romanlar|televizyon|dizileri|oyunları|bayrak|mitoloji|popüler kültür|çizgi|"
    r"şarkı|albüm|kitaplar|astroloji|ezoterik|dinî kozmoloji|dini kozmoloji|yaratılış|resimler|şiirler")


def _lower_tr(s: str) -> str:
    # "İ".lower() birleşik nokta (i̇) üretir; önce düz "i" yapılır. "I" -> "i" (İngilizce kategoriler).
    return s.replace("İ", "i").lower()


# Bu kategorilerden birindeki madde doğrudan alan dışıdır (sözde bilim ve dinî kozmoloji astronomi eğitimi
# içeriği değildir). Astroloji kategorileri burada YOK: Wikipedia ekliptik, tutulma, Ay evresi, Tycho Brahe gibi
# temel astronomi maddelerini de "Technical factors of astrology" / "Astroloji tarihi" altına koyuyor; bu
# kategoriler yalnızca astronomi kategorisi olarak SAYILMAZ (WIKI_NON_DOMAIN_CATEGORY).
WIKI_HARD_EXCLUDE_CATEGORY = re.compile(
    r"pseudoscience|religious cosmolog|esoteric|sözdebilim|dinî kozmoloji|dini kozmoloji|hristiyanlıkta kozmoloji|"
    r"ezoterik|mitolojik evren|deities|goddesses|\bgods\b|tanrıları|tanrıçaları")
# Hiç astronomi kategorisi olmayan maddede giriş paragrafı yedek kuralı, bu kategorilerden biri varsa UYGULANMAZ
# (kurgu/kültür ya da yer bilimi maddesi gezegenlerden söz etse de konusu astronomi değildir).
WIKI_FALLBACK_BLOCK = re.compile(r"geolog|jeoloji|jeomorfoloji|yer bilimleri|earth sciences|geodesy|climat|iklim|"
                                 r"ölçü aletleri|navigation|aerodynamic")
LEAD_ASTRO_SELF = re.compile(r"astronom|astrophys|astrofizik|gökbilim")

# Giriş paragrafı kontrolü için yalnız astronomiye özgü terimler ("space", "earth", "radio" gibi genel
# kelimeler yok).
LEAD_TERMS = re.compile(
    r"astronom|astrophys|astropartic|planet|\bstars?\b|stellar|galax|nebula|cosmolog|solar system|\bsun\b|solar|"
    r"\bmoons?\b|lunar|orbit|comet|asteroid|meteor(?!olo)|exoplanet|telescope|observator|spacecraft|space probe|light-year|"
    r"parsec|redshift|black hole|neutron star|white dwarf|supernova|pulsar|quasar|dark matter|dark energy|"
    r"big bang|constellation|celestial|dwarf planet|interstellar|milky way|universe|gravitational|"
    r"\bmars\b|jupiter|saturn|venus|neptune|uranus|\bpluto\b|eclipse|"
    r"astronomi|astrofizik|gezegen|yıldız|gökada|galaksi|bulutsu|kozmoloji|evren|güneş sistemi|uydu|yörünge|"
    r"kuyruklu yıldız|asteroit|göktaşı|ötegezegen|teleskop|gözlemevi|kara delik|süpernova|takımyıldız|"
    r"gökbilim|ışık yılı|cüce gezegen|samanyolu|kütleçekim|uzay aracı|uzay sonda|jüpiter|satürn|venüs|"
    r"merkür|neptün|uranüs|plüton|tutulma")


def wiki_category_on_topic(categories: list[str], text: str = "") -> list[str]:
    """Maddenin astronomi/uzay konulu kategorilerini döndürür (boş liste = alan dışı).

    Tek bir astronomi kategorisi, 10'dan fazla kategori arasında yalnız kalıyorsa giriş paragrafına
    da bakılır (en az 1 astronomi terimi): ör. 'Hanford Site' 22 kategoriden yalnız 'Gravitational-wave
    astronomy' (LIGO orada) ile eşleşiyor ama girişi bir nükleer tesisi anlatıyor."""
    lcs = [_lower_tr(c) for c in categories]
    if any(WIKI_HARD_EXCLUDE_CATEGORY.search(lc) for lc in lcs):
        return []
    out = [c for c, lc in zip(categories, lcs)
           if WIKI_ASTRO_CATEGORY.search(lc) and not WIKI_NON_DOMAIN_CATEGORY.search(lc)]
    lead = text.split("\n## ")[0][:1500].lower()
    lead_hits = len(LEAD_TERMS.findall(lead))
    if len(out) == 1 and len(categories) > 10 and lead_hits == 0:
        return []
    # Az kategorili madde (ör. tek kategorisi "Viking programı" ya da "Superbubbles"): kategori adı kendine
    # özgü olduğu için kalıba uymuyor; karar giriş paragrafına göre verilir: en az 4 astronomi terimi ya da
    # kendini astronomi olarak tanımlayan bir giriş ("In astronomy, ...") + en az 2 terim.
    if not out and len(categories) <= 3 \
            and not any(WIKI_NON_DOMAIN_CATEGORY.search(lc) or WIKI_FALLBACK_BLOCK.search(lc) for lc in lcs) \
            and (lead_hits >= 4 or (lead_hits >= 2 and LEAD_ASTRO_SELF.search(lead))):
        return ["(giriş paragrafı)"]
    return out

_rx_cache: dict[str, re.Pattern] = {}


def _rx(terms: list[str]) -> re.Pattern:
    key = "|".join(terms)
    if key not in _rx_cache:
        _rx_cache[key] = re.compile(r"\b(" + "|".join(terms) + r")", re.I)  # terimler regex parçasıdır
    return _rx_cache[key]


def domain_score(text: str) -> float:
    """1000 kelime başına alan terimi sayısı."""
    words = max(len(text.split()), 1)
    return 1000 * len(_rx(DOMAIN_TERMS).findall(text)) / words


def off_topic_hits(text: str) -> int:
    return len(_rx(OFF_TOPIC).findall(text))


def subtopic_scores(text: str) -> dict[str, int]:
    return {k: len(_rx(v).findall(text)) for k, v in SUBTOPIC_KEYWORDS.items()}
