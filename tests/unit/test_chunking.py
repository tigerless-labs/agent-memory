"""A `#` line inside a fenced block is shell syntax, not a heading.

The outline is what an agent sees for `mem read --level outline`, and the chunk anchors are
what a recall citation points at, so a shell comment promoted to a heading both invents a
section and cuts the real one in two.
"""

from agent_memory.core.chunking import chunks, outline
from agent_memory.core.config import Config
from agent_memory.core.record import MemoryRecord

FENCED = """## 部署步骤

先装依赖，然后跑迁移。这一段要写得足够长，才能让正文进入分段逻辑，而不是被当成一个整块。

```bash
# install dependencies
pip install -r requirements.txt
alembic upgrade head
```

## 回滚

删掉新版本即可。这一段也写长一点，保证正文总长度超过 chunk_min_chars 的门槛，否则整篇会被当成一个整块。
"""

TILDE_FENCED = """## Deploy

Install the dependencies first, then run the migration. This paragraph is long enough to keep
the body above the chunking threshold so the section split actually happens.

~~~bash
# install dependencies
pip install -r requirements.txt
~~~

## Roll back

Delete the new release. This paragraph exists only to push the body over the threshold.
"""


def record(body: str) -> MemoryRecord:
    return MemoryRecord(
        name="deploy",
        abstract="部署与回滚",
        type="note",
        author="dream",
        created="2026-10-31T00:00:00Z",
        updated="2026-10-31T00:00:00Z",
        body=body,
    )


def body_chunks(body: str) -> list:
    return [chunk for chunk in chunks(record(body), Config()) if chunk.kind == "body"]


def test_a_shell_comment_inside_a_fence_is_not_an_outline_entry():
    assert [entry.title for entry in outline(FENCED, Config())] == ["部署步骤", "回滚"]


def test_a_shell_comment_inside_a_fence_does_not_split_the_body():
    assert [chunk.heading for chunk in body_chunks(FENCED)] == ["部署步骤", "回滚"]


def test_no_chunk_anchor_is_named_after_a_shell_comment():
    assert all("install" not in chunk.anchor for chunk in body_chunks(FENCED))


def test_a_tilde_fence_is_honoured_too():
    assert [entry.title for entry in outline(TILDE_FENCED, Config())] == ["Deploy", "Roll back"]


def test_a_shorter_run_does_not_close_a_longer_fence():
    body = "## A\n\n````\n```\n# nope\n```\n````\n\n## B\n"

    assert [entry.title for entry in outline(body, Config())] == ["A", "B"]


def test_a_fence_line_with_an_info_string_does_not_close_a_block():
    body = "## A\n\n```\n# nope\n```bash\n# still nope\n```\n\n## B\n"

    assert [entry.title for entry in outline(body, Config())] == ["A", "B"]


def test_an_unclosed_fence_runs_to_the_end():
    assert [entry.title for entry in outline("## A\n\n```\n# nope\n## B\n", Config())] == ["A"]


def test_a_hash_line_outside_a_fence_is_still_a_heading():
    body = "## One\n\n" + "text " * 60 + "\n## Two\n\n" + "text " * 60 + "\n"

    assert [entry.title for entry in outline(body, Config())] == ["One", "Two"]
