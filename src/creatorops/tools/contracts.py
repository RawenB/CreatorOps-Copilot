"""Contract tool: find clauses (exclusivity, payment, termination...) in the contracts."""

import sqlite3

from creatorops.config import settings
from creatorops.tools.common import get_retriever, to_source

# words used to search each clause type when the user gives no query
CLAUSE_QUERIES = {
    "exclusivity": "exclusive exclusivity shall not work with competitors",
    "non_compete": "non-compete shall not compete competitor restriction after termination",
    "term_renewal": "term of the agreement duration renewal automatically renew expiration",
    "termination": "termination terminate notice breach kill fee",
    "ip_license": "license usage rights intellectual property ownership content use",
    "payment": "payment fee compensation invoice net days paid",
    "governing_law": "governing law jurisdiction courts disputes",
    "confidentiality": "confidential information non-disclosure",
}


def contract_doc_id(contract_id: str) -> str:
    """Accept a contract id from contracts_index (C001) or a document id."""
    if contract_id.upper().startswith("C") and contract_id[1:].isdigit():
        conn = sqlite3.connect(f"file:{settings.db_path}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT doc_id FROM contracts_index WHERE contract_id = ?", (contract_id.upper(),)
        ).fetchone()
        conn.close()
        if row:
            return row[0]
    return contract_id


def find_clause(
    clause_type: str,
    contract_id: str | None = None,
    query: str | None = None,
    top_k: int = 5,
) -> dict:
    """Find clauses of a given type in the contracts.

    clause_type: exclusivity, non_compete, term_renewal, termination, ip_license, payment,
    governing_law or confidentiality.
    contract_id: optional, "C001" (contracts_index) or a document id like "cuad_012".
    query: optional extra words, e.g. "competitors in the beauty category".
    """
    if clause_type not in CLAUSE_QUERIES:
        return {"error": f"Unknown clause_type. Use one of: {', '.join(CLAUSE_QUERIES)}"}
    doc_id = contract_doc_id(contract_id) if contract_id else None
    search_text = f"{clause_type.replace('_', ' ')}: {query or CLAUSE_QUERIES[clause_type]}"

    results = get_retriever().search(
        search_text, top_k=top_k * 3, doc_type="contract", doc_id=doc_id
    )
    # chunks whose heading already says the right clause type go first
    results.sort(key=lambda r: r.get("clause_type") != clause_type)
    return {
        "clause_type": clause_type,
        "contract_id": contract_id,
        "doc_id": doc_id,
        "sources": [to_source(r) for r in results[:top_k]],
    }
