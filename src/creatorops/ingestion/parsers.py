"""Turn raw files (HTML, eCFR XML, plain text, markdown) into clean markdown text.

We keep markdown headings (#, ##) because the chunker uses them to split documents by section.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import trafilatura


def html_to_markdown(html: str) -> str:
    """Extract the main text of a web page, keeping headings and lists."""
    text = trafilatura.extract(
        html,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_comments=False,
        favor_recall=True,
    )
    return clean_text(text or "")


def ecfr_xml_to_markdown(xml: str) -> str:
    """Convert an eCFR part (XML from the eCFR API) to markdown, one heading per section."""
    root = ET.fromstring(xml)
    lines = []
    for section in root.iter("DIV8"):  # DIV8 = a section like "§ 255.0"
        head = section.find("HEAD")
        lines.append(f"## {head_text(head)}" if head is not None else "## Section")
        for p in section.iter("P"):
            lines.append("".join(p.itertext()).strip())
        lines.append("")
    return clean_text("\n\n".join(lines))


def head_text(element) -> str:
    return " ".join("".join(element.itertext()).split())


def clean_text(text: str) -> str:
    """Normalize whitespace and remove leftover noise."""
    text = text.replace(" ", " ").replace("​", "").replace("‌", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def parse_file(path: Path) -> str:
    """Parse any supported file into markdown text."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix in (".html", ".htm"):
        return html_to_markdown(raw)
    if path.suffix == ".xml":
        return ecfr_xml_to_markdown(raw)
    return clean_text(raw)  # .md and .txt
