def test_repeated_excerpt_does_not_rewrite_prior_provenance(store):
    first = store.archive.append_provenance("memory", "same excerpt", source="first-agent")
    before = first.read_bytes()
    second = store.archive.append_provenance("memory", "same excerpt", source="second-agent")
    assert second != first
    assert first.read_bytes() == before
    assert "first-agent" in first.read_text()
    assert "second-agent" in second.read_text()
    assert len(store.archive.provenance_of("memory")) == 2
