"""Check the citations of an answer and decide if the agent should abstain."""

import re

CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

ABSTAIN_PHRASES = [
    "i don't know", "i do not know", "not enough information", "couldn't find", "could not find",
    "no information", "not mentioned in", "don't have information", "do not have information",
    "unable to find", "cannot answer", "can't answer",
]  # fmt: skip

# routes where an answer without sources is not acceptable
NEEDS_EVIDENCE = {"policy", "contract", "sql", "hybrid"}


def cited_numbers(answer: str) -> list[int]:
    numbers = []
    for group in CITATION.findall(answer):
        for n in group.split(","):
            if int(n) not in numbers:
                numbers.append(int(n))
    return numbers


def remove_invalid_citations(answer: str, valid: set[int]) -> str:
    def fix(match):
        kept = [n.strip() for n in match.group(1).split(",") if int(n) in valid]
        return f"[{', '.join(kept)}]" if kept else ""

    return CITATION.sub(fix, answer)


def looks_like_abstention(answer: str) -> bool:
    a = answer.lower()
    return any(p in a for p in ABSTAIN_PHRASES)


def verify(answer: str, sources: list[dict], route: str) -> dict:
    """Returns {"answer", "citations", "invalid_citations", "abstained", "unverified"}.

    - citations that point to no source are removed (and reported)
    - abstained: the answer says it does not know, or an evidence route found no usable source
    - unverified: sources were found but the answer cites none of them (shown with a warning)
    """
    # an empty SQL result cannot support any claim, so citing it does not count
    known = {s["n"] for s in sources if not (s.get("kind") == "sql" and not s.get("rows"))}
    numbers = cited_numbers(answer)
    valid = [n for n in numbers if n in known]
    invalid = [n for n in numbers if n not in known]
    clean = remove_invalid_citations(answer, known) if invalid else answer
    abstained = looks_like_abstention(answer) or (route in NEEDS_EVIDENCE and not known)
    unverified = route in NEEDS_EVIDENCE and not abstained and not valid
    return {
        "answer": clean,
        "citations": valid,
        "invalid_citations": invalid,
        "abstained": abstained,
        "unverified": unverified,
    }
