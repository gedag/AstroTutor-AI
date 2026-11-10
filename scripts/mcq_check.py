"""Multiple-choice question GENERATION examples (mcq_generation): are the question/options/answer already given in
the instruction? (v2.0, English; the Turkish v1.0 version is in Git tag v1.0.)

Used by: 10_generate_instructions.py (job-level rejection: if >= JOB_REJECT_RATIO of a job's mcq examples leak, the
output is not saved and the job is retried) and 11_verify_instructions.py (example-level removal,
`mcq_answer_in_instruction`).

Lessons from v1.0 (24-25.10.2026 reviews), carried over to English:
- the instruction said "answer the following question: ... A) ... B) ..." -> the response only copies the instruction,
  so the example does not teach GENERATING questions (106 of 446 examples; 29 also had the correct answer);
- a labelled stem ("Question: ...") or a content question ("... who discovered it?") inside the instruction;
- an instruction asking to answer a question that is not there ("answer the related question");
- no teaching passage at all ("Based on the source text, write a question about ...").
"""
from __future__ import annotations

import json
import re

JOB_REJECT_RATIO = 0.3

MCQ_KEY_IN_INS = re.compile(r'"answer"\s*:\s*"[ABCD]"|\bcorrect\s+(?:answer|option|choice)\w*\s*(?:is|:|=)\s*\(?[A-D]\b',
                            re.I)
MCQ_OPT_LINE = re.compile(r"(?m)^\s*\(?[A-D][).:]\s+\S")
MCQ_OPT_INLINE = re.compile(r"\bA\)\s.{3,300}?\bB\)\s.{3,300}?\bC\)\s.{3,300}?\bD\)\s", re.S)
MCQ_STEM_LABEL = re.compile(r"(?:^|\s)Question\s*\d*\s*:\s*\S")
# "answer the following question" / "answer the questions below" (the task is to WRITE questions, not answer them).
# "generate two questions and give the answer key in JSON" does not match: "answer" must be followed by "question(s)".
MCQ_ANSWER_FRAME = re.compile(r"\b(?:answer|solve|respond to)\s+(?:the|this|these|each|all|both|following|"
                              r"related|given|\s)*\s*(?:multiple[- ]choice\s+|four[- ]option\s+)?questions?\b", re.I)

_TEMPLATE = re.compile(r"\{.*\}", re.S)
_SEG = re.compile(r"(?<=[.!?:])\s+|(?<=[.!?:][\"'”’])\s+|\n+|[\"“”]")
# Request sentences: imperative generation verbs and task words. Declarative passage sentences ("Pulsars emit ...")
# do not match.
_REQUEST = re.compile(r"\b(write|create|generate|produce|prepare|make|draft|compose|give|provide|design|turn|use|"
                      r"format|return|output)\b|json|multiple[- ]choice|four[- ]option|\bquestions?\b|"
                      r"\b(could|can|would|will) you\b|\bplease\b", re.I)
PASSAGE_MIN_CHARS = 100


def _segments(ins: str) -> list[str]:
    return [s.strip() for s in _SEG.split(_TEMPLATE.sub(" ", ins)) if s and s.strip()]


def mcq_passage_chars(ins: str) -> int:
    """Characters of teaching passage in the instruction (everything except request sentences and the JSON template)."""
    return sum(len(s) for s in _segments(ins) if not _REQUEST.search(s))


def content_question_in_instruction(ins: str) -> str | None:
    """Does the instruction contain the content question itself ("... who discovered it?")? Request sentences
    ("Could you write a question?") do not count."""
    for s in _segments(ins):
        if s.endswith("?") and not _REQUEST.search(s):
            return s[-80:]
    return None


def _nz(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def mcq_in_instruction(ins: str, resp: str) -> str | None:
    """Is the question itself / its options / its correct answer already given in a question-generation instruction?"""
    if MCQ_KEY_IN_INS.search(ins):
        return "answer_in_instruction"
    if len(MCQ_OPT_LINE.findall(ins)) >= 3 or MCQ_OPT_INLINE.search(ins):
        return "options_in_instruction"
    if MCQ_STEM_LABEL.search(ins):
        return "question_in_instruction"
    if MCQ_ANSWER_FRAME.search(ins):
        return "answering_instruction"
    try:
        qs = json.loads(re.search(r"\{.*\}", resp, re.S).group(0))["questions"]
    except Exception:
        qs = []
    n = _nz(ins)
    if any(len(_nz(str(q.get("question", "")))) >= 25 and _nz(str(q.get("question", ""))) in n for q in qs):
        return "question_in_instruction"
    if content_question_in_instruction(ins):
        return "content_question_in_instruction"
    return None


def job_mcq_leak_ratio(rows: list[dict]) -> float:
    m = [r for r in rows if r.get("task_type") == "mcq_generation"]
    if not m:
        return 0.0
    return sum(1 for r in m if mcq_in_instruction(r.get("instruction", ""), r.get("response", ""))) / len(m)


if __name__ == "__main__":
    P = ("Pulsars are rapidly rotating neutron stars that emit beams of radio waves. As the star spins, the beams sweep "
         "across Earth like a lighthouse, so we detect regular pulses.")
    cases = {
        # must NOT be flagged
        f"Use the passage below to write one multiple-choice question and return it as JSON. Passage: {P}": None,
        f"Read this text and create two four-option questions in JSON format: {P}": None,
        f"{P} Based on this information, could you prepare a multiple-choice question?": None,
        f"Generate 2 questions from the passage and give the answer key in JSON. {P}": None,
        "Kepler (A) and Brahe (B) observations were combined. C) none": None,
        'passage "answer": "A|B|C|D"': None,
        # must be flagged
        f"Read the passage and answer the following question: {P}": "answering_instruction",
        f"{P} Answer the multiple-choice questions below in JSON.": "answering_instruction",
        f"{P} Question: What do pulsars emit?": "question_in_instruction",
        f"{P} A) radio waves B) sound waves C) gravity waves D) water waves": "options_in_instruction",
        f"{P}\nA) one\nB) two\nC) three\nD) four": "options_in_instruction",
        f'{P} "answer": "B"': "answer_in_instruction",
        f"{P} The correct answer is B.": "answer_in_instruction",
    }
    bad = 0
    for ins, want in cases.items():
        got = mcq_in_instruction(ins, '{"questions": []}')
        bad += got != want
        print("ok  " if got == want else "FAIL", want, got, "|", ins[:70].replace("\n", " "))
    q_cases = {
        f"{P} According to this passage, who first detected a pulsar?": True,
        f"Generate a question from the passage below: 'What causes the regular pulses of a pulsar? Pulsars spin...'": True,
        f"Could you read the text and prepare a multiple-choice question? Text: {P}": False,
        "Can you create a four-option question from this passage?": False,
        f"{P} Using this information, write one question.": False,
    }
    for ins, want in q_cases.items():
        got = content_question_in_instruction(ins) is not None
        bad += got != want
        print("ok  " if got == want else "FAIL", "content question", want, got, "|", ins[:70])
    p_cases = {
        "Based on the source text, write a four-option question about which oxygen line the Te method uses. "
        'Give a short introduction of about 100 words in the instruction and return JSON: {"questions": []}': False,
        f"{P} Using this information, write one question.": True,
    }
    for ins, want in p_cases.items():
        got = mcq_passage_chars(ins) >= PASSAGE_MIN_CHARS
        bad += got != want
        print("ok  " if got == want else "FAIL", "has teaching passage", want, got, mcq_passage_chars(ins))
    resp = '{"questions": [{"question": "Who first discovered the Antennae Galaxies?"}]}'
    got = mcq_in_instruction(f"{P} Who first discovered the Antennae Galaxies?", resp)
    bad += got != "question_in_instruction"
    print("ok  " if got == "question_in_instruction" else "FAIL", "question from response in instruction ->", got)
    print("errors:", bad)
