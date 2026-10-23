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
    "solar system", r"suns?\b", "solar", r"moons?\b", "lunar", "orbit", "comet", "asteroid", "meteor", "exoplanet",
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
    "solar_system": ["solar system", r"suns?\b", "solar wind", "comet", "asteroid", "meteor", "kuiper", "oort",
                     "eclipse", "güneş sistemi", "güneş", "kuyruklu yıldız", "asteroit", "göktaşı", "tutulma"],
    "missions_spacecraft": ["mission", "spacecraft", "probe", "rover", "lander", "launch", "orbiter", "flyby",
                            "astronaut", "voyager", "cassini", "juno", "perseverance", "artemis", "europa clipper",
                            "görev", "uzay aracı", "sonda", "fırlatma", "astronot", "keşif aracı"],
    "observatories_telescopes": ["telescope", "observator", "hubble", "webb", "chandra", "spitzer", "roman space",
                                 "instrument", "detector", "mirror", "interferomet", "teleskop", "gözlemevi",
                                 "dedektör", "ayna"],
}

OFF_TOPIC = ["horoscope", "zodiac sign", "astrolog", "burç yorum", "burcu", "tarot", "falı"]

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
