from creatorops.ingestion.versioning import Registry, content_hash


def make_chunk(doc_id, version):
    return {
        "chunk_id": f"{doc_id}:v{version}:0",
        "doc_id": doc_id,
        "version": version,
        "is_latest": True,
        "valid_to": None,
        "text": f"text of version {version}",
    }


def test_first_ingestion_creates_version_1(tmp_path):
    reg = Registry(tmp_path / "r.sqlite")
    status, version, previous = reg.add_version("doc", content_hash("a"), "2024-06-01")
    assert (status, version, previous) == ("new", 1, None)


def test_same_content_is_unchanged(tmp_path):
    reg = Registry(tmp_path / "r.sqlite")
    reg.add_version("doc", content_hash("a"), "2024-06-01")
    status, version, _ = reg.add_version("doc", content_hash("a"), "2025-01-01")
    assert status == "unchanged"
    assert version == 1
    assert len(reg.versions("doc")) == 1


def test_changed_content_creates_new_version_and_keeps_history(tmp_path):
    reg = Registry(tmp_path / "r.sqlite")
    reg.add_version("doc", content_hash("a"), "2024-06-01")
    reg.save_chunks([make_chunk("doc", 1)])

    status, version, previous = reg.add_version("doc", content_hash("b"), "2025-03-01")
    reg.save_chunks([make_chunk("doc", 2)])

    assert (status, version, previous) == ("updated", 2, 1)
    assert reg.versions("doc") == [(1, "2024-06-01", "2025-03-01", 0), (2, "2025-03-01", None, 1)]

    chunks = {c["version"]: c for c in reg.all_chunks()}
    assert chunks[1]["is_latest"] is False
    assert chunks[1]["valid_to"] == "2025-03-01"
    assert chunks[2]["is_latest"] is True
    assert [c["version"] for c in reg.all_chunks(latest_only=True)] == [2]
