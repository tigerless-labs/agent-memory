"""P1 — the interop matrix itself, exercised against stub hosts."""

from agent_memory.core.store import Store
from agent_memory.harness import interop
from agent_memory.harness.hosts import Host, HostResult, HostSpec

FACT = interop.Fact(
    subject="the drain window",
    sentence="The queue drain window must exceed the worker lease TTL by 90 seconds.",
    token="90 seconds",
)


class StubHost(Host):
    """Writes what it is told, and reads back whatever the shared store returns."""

    def __init__(self, name, can_write=True, can_read=True):
        super().__init__(HostSpec(name=name, binary=name, attempts=1))
        self.can_write = can_write
        self.can_read = can_read

    def run(self, prompt, store_root=None, tools_enabled=False, system_prompt="",
            max_turns=8, workdir=None):
        if "Record this" in prompt:
            if not self.can_write:
                return HostResult("", False, 0.1, "cannot write")
            Store(store_root, agent=self.name).record(
                abstract=FACT.sentence, type="fact", domain="user", name="drain-window-rule"
            )
            return HostResult("drain-window-rule", True, 0.2)
        if not self.can_read:
            return HostResult("", False, 0.1, "cannot read")
        from agent_memory.core.recall import Recall

        hits = Recall(Store(store_root, agent=self.name)).recall(FACT.subject)
        return HostResult(hits[0].abstract if hits else "nothing found", True, 0.2)


def test_a_memory_written_by_one_host_is_read_by_another(tmp_path):
    result = interop.check(StubHost("alpha"), StubHost("beta"), FACT, tmp_path)
    assert result.passed
    assert result.memories == 1
    assert FACT.token in result.answer


def test_the_matrix_covers_every_ordered_pair(tmp_path):
    hosts = [StubHost("alpha"), StubHost("beta"), StubHost("gamma")]
    results = interop.matrix(hosts, FACT, tmp_path)
    assert len(results) == len(hosts) ** 2
    assert all(result.passed for result in results)
    assert {(r.writer, r.reader) for r in results} == {
        (a.name, b.name) for a in hosts for b in hosts
    }


def test_each_pair_gets_its_own_store_so_a_pass_cannot_borrow_another_pair_s_write(tmp_path):
    hosts = [StubHost("alpha"), StubHost("beta", can_write=False)]
    results = interop.matrix(hosts, FACT, tmp_path)
    beta_writes = [r for r in results if r.writer == "beta"]
    assert beta_writes and not any(r.passed for r in beta_writes)
    assert all(r.passed for r in results if r.writer == "alpha")


def test_a_reader_that_finds_nothing_fails_rather_than_passing_quietly(tmp_path):
    result = interop.check(StubHost("alpha"), StubHost("beta", can_read=False), FACT, tmp_path)
    assert not result.passed
    assert result.wrote
    assert result.error


def test_the_rendered_matrix_names_the_failures(tmp_path):
    hosts = [StubHost("alpha"), StubHost("beta", can_read=False)]
    text = interop.render(interop.matrix(hosts, FACT, tmp_path))
    assert "FAIL" in text
    assert "interoperate" in text
    assert "alpha" in text and "beta" in text
