"""Split documents into chunks.

Two strategies:
- structure_chunks: first split by sections (markdown headings, numbered clauses like
  "4. Exclusivity" or "Section 2.1", ARTICLE headings), then cut long sections into
  smaller pieces on paragraph boundaries. Each chunk remembers its section path.
- fixed_chunks: plain fixed-size windows (used as a baseline in the ablation).

Every chunk keeps char_start / char_end so we can highlight the exact passage in the UI.
"""

import re
from dataclasses import dataclass

MAX_CHARS = 1200
OVERLAP = 150

MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
# "1. Term", "4.2 Exclusivity", "Section 5. Payment", "ARTICLE III - TERM", "SECTION 2"
NUMBERED_HEADING = re.compile(
    r"^((ARTICLE|Article|SECTION|Section)\s+[\dIVXLC]+[.:]?\s*.{0,80}|\d{1,2}\.\s+[A-Z][^.]{2,80})$"
)


@dataclass
class Chunk:
    text: str
    section_path: str
    char_start: int
    char_end: int


def find_sections(text: str) -> list[tuple[str, int, int]]:
    """Return (section_path, start, end) for every section of the text."""
    headings = []  # (level, title, start offset of the line)
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        md = MARKDOWN_HEADING.match(stripped)
        if md:
            headings.append((len(md.group(1)), md.group(2).strip(), offset))
        elif len(stripped) < 100 and NUMBERED_HEADING.match(stripped):
            headings.append((3, stripped, offset))  # treat clause headings as level 3
        offset += len(line)

    if not headings:
        return [("", 0, len(text))]

    sections = []
    if headings[0][2] > 0:  # text before the first heading
        sections.append(("", 0, headings[0][2]))

    stack = []  # current path of (level, title)
    for i, (level, title, start) in enumerate(headings):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        end = headings[i + 1][2] if i + 1 < len(headings) else len(text)
        path = " > ".join(t for _, t in stack)
        sections.append((path, start, end))
    return sections


def split_long(text: str, start: int, max_chars: int, overlap: int) -> list[tuple[int, int]]:
    """Cut text[start:...] into windows of at most max_chars, preferring paragraph breaks."""
    pieces = []
    pos = 0
    while pos < len(text):
        end = min(pos + max_chars, len(text))
        if end < len(text):
            # try to stop at a paragraph break, then a sentence end
            cut = text.rfind("\n\n", pos + max_chars // 2, end)
            if cut == -1:
                cut = text.rfind(". ", pos + max_chars // 2, end)
                if cut != -1:
                    cut += 1
            if cut != -1:
                end = cut
        pieces.append((start + pos, start + end))
        if end >= len(text):
            break
        pos = max(end - overlap, pos + 1)
    return pieces


def structure_chunks(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[Chunk]:
    chunks = []
    for path, start, end in find_sections(text):
        section = text[start:end]
        for s, e in split_long(section, start, max_chars, overlap):
            piece = text[s:e].strip()
            # skip empty pieces and pieces that are only a heading
            if len(piece) < 30:
                continue
            chunks.append(Chunk(piece, path, s, e))
    return chunks


def fixed_chunks(text: str, size: int = MAX_CHARS, overlap: int = OVERLAP) -> list[Chunk]:
    chunks = []
    pos = 0
    while pos < len(text):
        piece = text[pos : pos + size]
        if piece.strip():
            chunks.append(Chunk(piece.strip(), "", pos, min(pos + size, len(text))))
        pos += size - overlap
    return chunks


CLAUSE_KEYWORDS = {
    "exclusivity": ["exclusiv"],
    "non_compete": ["non-compet", "noncompet", "competitor", "non-solicit"],
    "term_renewal": ["term", "renewal", "duration"],
    "termination": ["terminat"],
    "ip_license": ["license", "licence", "usage right", "intellectual property", "ownership"],
    "payment": ["payment", "compensation", "fee", "price", "royalt"],
    "governing_law": ["governing law", "jurisdiction", "applicable law"],
    "confidentiality": ["confidential"],
}


def guess_clause_type(section_path: str) -> str | None:
    """Guess the clause type of a contract chunk from its section heading (simple keywords)."""
    heading = section_path.split(" > ")[-1].lower()
    for clause_type, words in CLAUSE_KEYWORDS.items():
        if any(w in heading for w in words):
            return clause_type
    return None
