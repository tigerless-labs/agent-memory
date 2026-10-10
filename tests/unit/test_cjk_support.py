"""CJK recall: segmentation, similarity, group keys, slugs — with and without jieba."""

from agent_memory.core import tokenizer
from agent_memory.core.manage import _group_key, _similarity
from agent_memory.core.recall import Recall


def test_ascii_queries_tokenize_exactly_as_before():
    assert tokenizer.query_tokens("Deploy fails with E4021!") == [
        "deploy",
        "fails",
        "with",
        "e4021",
    ]


def test_cjk_query_yields_tokens_even_without_jieba(monkeypatch):
    monkeypatch.setattr(tokenizer, "_jieba", None)
    tokens = tokenizer.query_tokens("扫码枪触发")
    assert tokens
    assert all(tokenizer.has_cjk(token) for token in tokens)


def test_bigram_fallback_lines_up_between_query_and_stored_text(monkeypatch):
    monkeypatch.setattr(tokenizer, "_jieba", None)
    stored = tokenizer.segment("扫码枪(串口)触发条件")
    tokens = tokenizer.query_tokens("扫码枪")
    assert tokens
    assert all(token in stored for token in tokens)


def test_ascii_text_is_untouched_by_segmentation():
    assert tokenizer.segment("plain English body, no CJK here") == "plain English body, no CJK here"


def test_a_chinese_query_reaches_a_chinese_memory(store):
    store.record(
        abstract="扫码枪与在位检测双条件触发",
        type="decision",
        body="状态机 WAIT_BOARD→RUNNING；NG 锁线。",
        name="station-trigger-cn",
    )
    hits = Recall(store).recall("扫码枪")
    assert hits and hits[0].name == "station-trigger-cn"


def test_chinese_abstracts_are_comparable_for_merge_proposals(store):
    store.record(abstract="扫码枪触发条件与状态机流转说明", type="decision", name="cn-a")
    store.record(abstract="扫码枪触发条件补充与状态机流转", type="decision", name="cn-b")
    left = store.find("cn-a")
    right = store.find("cn-b")
    assert left is not None and right is not None
    assert _similarity(left, right) > 0.0


def test_group_keys_keep_chinese_names_distinct():
    assert _group_key("扫码枪") != ""
    assert _group_key("扫码枪") != _group_key("状态机")
    assert _group_key("Sessions") == "session"
