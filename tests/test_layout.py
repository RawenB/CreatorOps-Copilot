"""Guards the package layout described in docs/architecture.md."""

import importlib

import pytest

SUBPACKAGES = [
    "ingestion",
    "indexing",
    "retrieval",
    "agent",
    "tools",
    "llm",
    "api",
    "mcp_server",
]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_is_importable_and_documented(name: str) -> None:
    module = importlib.import_module(f"creatorops.{name}")
    assert module.__doc__, f"creatorops.{name} needs a module docstring"
