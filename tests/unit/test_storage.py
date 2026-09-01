"""M1 — truth store and the file-boundary rules."""

import pytest
from agent_memory.core import frontmatter
from agent_memory.core import record as record_module
from agent_memory.core.archive import Archive
from agent_memory.core.errors import ValidationError
from agent_memory.core.record import STATUS_RETIRED, MemoryRecord
from agent_memory.core.slug import is_valid_slug, slugify

DESTRUCTIVE_NAMES = ("delete", "remove", "purge", "unlink", "drop", "erase")


def test_init_creates_every_domain_and_archive_bucket(store):
    for domain in store.config.storage.domains:
        assert store.layout.domain_dir(domain).is_dir()
    for bucket in (store.layout.provenance, store.layout.retired, store.layout.sessions):
        assert bucket.is_dir()
    assert store.layout.memory_index.exists()


def test_recorded_file_round_trips_through_frontmatter(store):
    written = store.record(
        abstract="Deploys run from the release branch only",
        type="procedure",
        domain="project",
        body="# Steps\nCut a tag, then run the pipeline.\n",
        name="release-branch-only",
        links=["file-truth-invariant"],
    )
    text = written.path.read_text(encoding="utf-8")
    fields, body = frontmatter.parse(text)
    assert fields["name"] == written.name
    assert fields["abstract"] == written.abstract
    assert fields["links"] == ["file-truth-invariant"]
    assert "Cut a tag" in body


@pytest.mark.parametrize(
    ("field", "value", "expected_field"),
    [
        ("abstract", "", "abstract"),
        ("type", "reference", "type"),
        ("name", "Not A Slug", "name"),
    ],
)
def test_invalid_frontmatter_is_rejected_with_a_structured_error(
    store, field, value, expected_field
):
    kwargs = {
        "abstract": "A perfectly ordinary preference",
        "type": "preference",
        "domain": "user",
        "name": "ordinary-preference",
    }
    kwargs[field] = value
    with pytest.raises(ValidationError) as raised:
        store.record(**kwargs)
    assert expected_field in {error.field for error in raised.value.errors}


def test_bad_date_is_rejected(store, config):
    bad = MemoryRecord(
        name="bad-date",
        abstract="has an unparseable date",
        type="fact",
        author="test",
        created="not-a-date",
        updated="2026-01-15",
        domain="user",
    )
    with pytest.raises(ValidationError) as raised:
        record_module.validate(bad, config)
    assert "created" in {error.field for error in raised.value.errors}


def test_rewriting_the_same_name_is_an_update_not_a_second_file(store):
    first = store.record(
        abstract="Queue timeout is 30 seconds", type="fact", domain="project", name="queue-timeout"
    )
    second = store.record(
        abstract="Queue timeout is 60 seconds", type="fact", domain="project", name="queue-timeout"
    )
    assert first.path == second.path
    assert len([path for path in store.layout.truth_files() if path.stem == "queue-timeout"]) == 1
    assert second.created == first.created
    assert "60 seconds" in second.path.read_text(encoding="utf-8")


def test_superseded_record_leaves_the_active_set_but_stays_on_disk(seeded):
    seeded.record(
        abstract="The staging deploy no longer drains the queue at all",
        type="experience",
        domain="experience",
        name="staging-deploy-no-drain",
    )
    old = seeded.correct("staging-deploy-e4021", supersede_with="staging-deploy-no-drain")
    assert old.path.exists()
    active = {record.name for record in seeded.records() if record.is_active()}
    assert "staging-deploy-e4021" not in active
    assert "staging-deploy-no-drain" in active


def test_archive_module_exposes_no_destructive_interface():
    public = [name for name in dir(Archive) if not name.startswith("_")]
    assert not [name for name in public if any(word in name for word in DESTRUCTIVE_NAMES)]


def test_provenance_excerpt_is_stored_and_retrievable_by_name(store):
    excerpt = "user said: the drain window must exceed the lease TTL"
    written = store.record(
        abstract="Drain window must exceed lease TTL",
        type="fact",
        domain="project",
        name="drain-window-rule",
        provenance=[excerpt],
    )
    stored = store.archive.provenance_of("drain-window-rule")
    assert stored
    assert excerpt in stored[0].read_text(encoding="utf-8")
    assert written.provenance


def test_retire_moves_the_file_into_archive_without_losing_it(seeded):
    retired = seeded.retire("file-truth-invariant")
    assert retired.status == STATUS_RETIRED
    assert retired.path.exists()
    assert seeded.layout.retired in retired.path.parents
    assert "file-truth-invariant" not in {record.name for record in seeded.records()}
    assert "file-truth-invariant" in {
        record.name for record in seeded.records(include_archived=True)
    }


def test_slug_is_stable_and_links_survive_a_move_across_directories(seeded):
    seeded.record(
        abstract="Link target for the move test",
        type="fact",
        domain="project",
        name="link-target",
    )
    seeded.record(
        abstract="Holds a link to the target",
        type="fact",
        domain="project",
        name="link-holder",
        links=["link-target"],
    )
    moved = seeded.record(
        abstract="Link target for the move test",
        type="fact",
        domain="project",
        name="link-target",
        topic="deploys",
    )
    assert moved.path.parent.name == "deploys"
    assert moved.name == "link-target"
    report = seeded.sync_index()
    assert report.dangling_links == ()


def test_depth_below_a_domain_is_capped(store):
    with pytest.raises(ValidationError):
        store.record(
            abstract="Too deep to be found by address",
            type="fact",
            domain="project",
            name="too-deep",
            topic="a/b",
        )


def test_slugify_is_idempotent_and_produces_valid_slugs(config):
    for text in ("Deploy fails: error E4021!", "  Mixed   Case __ names  ", "重构 pipeline v2"):
        once = slugify(text, config.storage.slug_max_length)
        if once:
            assert is_valid_slug(once)
            assert slugify(once, config.storage.slug_max_length) == once
