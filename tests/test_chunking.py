from creatorops.ingestion.chunking import (
    find_sections,
    fixed_chunks,
    guess_clause_type,
    structure_chunks,
)

DOC = """# Branded Content Policy

Intro text about the policy that is long enough to be a chunk.

## Disclosure

Creators must use the paid partnership label for all branded content posts.

## Prohibited content

Branded content must not promote alcohol to minors or show unsafe supplements.
"""

CONTRACT = """AGREEMENT between Brand and Creator, signed today by both parties.

1. Term
This agreement lasts twelve months from the effective date written above.

4. Exclusivity
The Creator will not work with competitors in the beauty category for 3 months.
"""


def test_sections_follow_markdown_headings():
    paths = [p for p, _, _ in find_sections(DOC)]
    assert paths == [
        "Branded Content Policy",
        "Branded Content Policy > Disclosure",
        "Branded Content Policy > Prohibited content",
    ]


def test_numbered_clauses_are_sections():
    paths = [c.section_path for c in structure_chunks(CONTRACT)]
    assert "1. Term" in paths
    assert "4. Exclusivity" in paths


def test_offsets_point_to_the_chunk_text():
    for chunk in structure_chunks(DOC):
        assert chunk.text in DOC[chunk.char_start : chunk.char_end]


def test_long_section_is_split_with_size_limit():
    text = "## Big section\n\n" + "\n\n".join(f"Paragraph {i} " + "word " * 60 for i in range(20))
    chunks = structure_chunks(text, max_chars=500, overlap=50)
    assert len(chunks) > 5
    assert all(len(c.text) <= 500 for c in chunks)
    assert all(c.section_path == "Big section" for c in chunks)


def test_fixed_chunks_cover_the_text():
    text = "abcdefghij" * 100
    chunks = fixed_chunks(text, size=300, overlap=50)
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(text)


def test_guess_clause_type():
    assert guess_clause_type("4. Exclusivity") == "exclusivity"
    assert guess_clause_type("Agreement > 9. Governing Law") == "governing_law"
    assert guess_clause_type("2. Deliverables") is None
