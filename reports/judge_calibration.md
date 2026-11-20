# Toplu yargıç kalibrasyonu

Rapor: 2026-11-20T12:30:36+00:00 · seçim: 2026-11-13T20:06:11+00:00 · üretici: `scripts/judge_calibration.py`

Soru: Bir yargıç çağrısında 3 iş değerlendirmek, her işi ayrı çağrıda değerlendirmekle aynı kararları veriyor mu? Her iş iki kez, **aynı yargıç modeliyle** değerlendirildi: tek başına ve üçlüsüyle birlikte.

## Önceden belirlenen ölçüt (11.11.2026, sonuçlardan önce)
1. Karar uyumu ≥ %90
2. Tekli yargıcın elediği örneklerin ≥ %90'ı toplu yargıçta da elenir (tekli yargıç 5'ten az örnek elediyse değerlendirilemez = sağlanmadı)
3. Uyuşmayan örneklerde kaynak karıştırma yok (elle inceleme)

## Sonuç
| Ölçü | Değer |
|---|---|
| Karşılaştırılan örnek | 171 / 180 |
| Karar uyumu | %94.7 |
| Tekli yargıcın elediği | 15 |
| Toplu yargıcın elediği | 6 |
| İkisinin de elediği | 6 (yakalama %40.0) |
| Yalnız tekli eledi (toplu daha gevşek) | 9 |
| Yalnız toplu eledi (toplu daha sıkı) | 0 |
| SE seviye uyumu | %72.2 (18 örnek) |

- Ölçüt 1 (uyum): **sağlandı**
- Ölçüt 2 (yakalama): **SAĞLANMADI**
- Ölçüt 3 (kaynak karıştırma): uyuşmayan örneklerin elle incelenmesi gerekir (aşağıdaki tablo)

## Türe göre
| Tür | Örnek | Uyum | Tekli eledi | Toplu eledi |
|---|---|---|---|---|
| DOC | 109 | %97.2 | 5 | 2 |
| REF | 44 | %100.0 | 0 | 0 |
| SE | 18 | %66.7 | 10 | 4 |

## Ölçüt bazında farklı karar sayısı
| Ölçüt | Farklı |
|---|---|
| supported | 7 |
| correct | 7 |
| follows_instruction | 6 |
| instruction_clear | 2 |
| fluent_english | 4 |

## Üçlüler
| # | İşler | Yargıç modeli |
|---|---|---|
| 0 | JOB_DOC_DOC_010762, JOB_DOC_DOC_011444, JOB_DOC_DOC_011517 | gemini-3.7-flash |
| 1 | JOB_DOC_DOC_000701, JOB_DOC_DOC_002037, JOB_DOC_DOC_013587 | gemini-3.7-flash |
| 2 | JOB_DOC_DOC_003599, JOB_DOC_DOC_009184, JOB_DOC_DOC_011547 | gemini-3.8-flash |
| 3 | JOB_DOC_DOC_000273, JOB_DOC_DOC_011450, JOB_DOC_DOC_013345 | gemini-3.7-flash |
| 4 | JOB_REF_007, JOB_REF_009, JOB_REF_010 | gemini-3.8-flash |
| 5 | JOB_SE_0006, JOB_SE_0017, JOB_SE_0048 | gemini-3.7-flash |

## Uyuşmayan örnekler (9)
| Örnek | Görev | Tekli | Toplu | Talimat |
|---|---|---|---|---|
| JOB_DOC_DOC_010762_05 | comparison | FAIL ['supported', 'correct'] The response incorrectly claims that eucrites contain oxygen isotope signatures that match the spectral signatures observed directly on Vesta, conflating distinct isotopic and spectroscopic  | pass [] none | Compare the oxygen isotopes found in eucrite meteorites with those found in rocks from Earth and the Moon. |
| JOB_DOC_DOC_010762_06 | definition_explanation | FAIL ['supported', 'correct'] The claim that Dawn aims to shed light on the 'early history of the universe' is unsupported by the text and factually inaccurate (Dawn explores planetary bodies from the early solar system, | pass [] none | What is the Dawn spacecraft and what is its mission in the asteroid belt? |
| JOB_DOC_DOC_013345_09 | classification | FAIL ['instruction_clear'] The instruction asks the user to classify items 'based on the text', but no reference passage is included in the instruction. | pass []  | Classify the following four items into either Astronomical Telescopes/Instruments or Young Stellar Objects: TIFR 100-cm balloon-born telescope, HH 1042, HAWK-I, |
| JOB_SE_0006_03 | question_answering | FAIL ['supported', 'correct', 'follows_instruction'] The response makes a factual and logical slip stating there was no 'Chinese reluctance to be part of the CNSA' (intending to say ISS), and fails to address the questio | pass []  | Why is China still not invited to the ISS? (Or, why do certain countries not get invited/rejected to work on the ISS?)  I understand that U.S. Congress passed a |
| JOB_SE_0006_07 | question_answering | FAIL ['supported', 'follows_instruction'] The response fails to address the second question in the instruction asking whether NASA has plans for an even bigger reusable spacecraft. | pass []  | What made NASA shut down the Shuttle program?  Recently NASA shut down its Space Shuttle program. Between the first launch on April 12, 1981, and the final land |
| JOB_SE_0006_08 | question_answering | FAIL ['supported', 'correct'] The explanation is physically incorrect, attributing galaxy collisions to randomly distributed kinetic energy and random directions of motion like particles bumping into each other, rather t | pass []  | Why do galaxies collide?  If the universe is expanding outward, what is the processes for one galaxy to get off track enough to collide with another?  Say, the  |
| JOB_SE_0017_00 | question_answering | FAIL ['supported', 'correct', 'fluent_english'] The response is not fluent due to a garbled sentence ('Finding faint, moving extremely faint objects in a series of pictures...'). It also fails to adequately explain why d | pass []  | Undiscovered dwarf planets  Scientists think there may be dozens of undiscovered dwarf planets in the Solar system. What I find intriguing is that, we have been |
| JOB_SE_0017_05 | question_answering | FAIL ['supported', 'correct'] The response contains a factual error claiming gravitomagnetism is tied to the finite speed of gravity (in general relativity, it arises from mass currents/momentum density, not retardation) | pass []  | How do we know that black holes are spinning?  How is it possible to know if a black hole is spinning or not?  If a planet is spinning, you can see it clearly b |
| JOB_SE_0017_06 | question_answering | FAIL ['fluent_english'] The response contains multiple grammatical errors and typos, including 'an intense electric fields', 'have convective zone', 'certainity', and 'ligthnings'. | pass []  | Can lightning occur in stars like the Sun?  In the Wikipedia article about lightining, the following explanation is given about the electrification process in c |

Karşılaştırılamayan örnek: 9 (bir modda değerlendirilemedi)

Karar: 18.11.2026 ara sonuçla Eda toplu yargıcı seçti (`jobs_per_call: 3`, tam kapsam); ayrıntı experiments.md.
