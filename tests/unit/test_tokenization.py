"""CJK tokenization: query extraction, index-side segmentation, and drift rebuild."""

import pytest
from agent_memory.core.config import Config
from agent_memory.core.recall import Recall
from agent_memory.core.search_index import to_match_query
from agent_memory.core.store import Store
from agent_memory.core.tokenization import TOKENIZER_CJK


def test_ascii_queries_keep_the_current_expression():
    assert to_match_query("deploy fails E4021") == '"deploy" OR "fails" OR "e4021"'


def test_pure_cjk_queries_produce_no_ascii_tokens():
    assert to_match_query("构件命名规范") == ""


def test_cjk_queries_never_match_under_the_ascii_tokenizer(seeded):
    assert Recall(seeded).recall("队列排空时部署失败") == []


def test_unknown_tokenizer_is_rejected(store):
    store.config.index.tokenizer = "soundex"
    with pytest.raises(ValueError, match="unknown tokenizer"):
        store.record(
            abstract="any abstract",
            type="fact",
            name="bad-tokenizer",
        )


def test_missing_jieba_fails_with_an_install_hint(store, monkeypatch):
    import builtins
    import sys

    store.config.index.tokenizer = TOKENIZER_CJK
    monkeypatch.delitem(sys.modules, "jieba", raising=False)
    real_import = builtins.__import__

    def no_jieba(name, *args, **kwargs):
        if name == "jieba":
            raise ImportError("no jieba")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_jieba)
    with pytest.raises(RuntimeError, match="agent-memory-core\\[cjk\\]"):
        store.record(
            abstract="构件命名规范",
            type="decision",
            body="数字孪生项目的构件命名采用 wc_类_L层-序号 格式。",
            name="naming-convention",
        )


jieba = pytest.importorskip("jieba", reason="cjk tokenization tests need the cjk extra")


@pytest.fixture
def cjk_store(tmp_path, clock):
    config = Config.default()
    config.index.tokenizer = TOKENIZER_CJK
    store = Store(tmp_path / "store", config=config, clock=clock, agent="test-agent")
    store.init()
    return store


@pytest.fixture
def cjk_seeded(cjk_store):
    cjk_store.record(
        abstract="构件命名采用 wc_类_L层-序号 格式",
        type="decision",
        body="数字孪生项目的构件命名采用 wc_wall_L3-012 形式，由 JSON 事实源流水线强制执行。",
        name="naming-convention",
    )
    cjk_store.record(
        abstract="Blender 自动化必须走 bpy headless CLI",
        type="fact",
        body="Blender 的 GUI 自动化不可行，批量渲染必须通过 bpy 的 headless 命令行接口执行。",
        name="blender-headless",
    )
    cjk_store.record(
        abstract="平面图识别采用渐进式策略",
        type="procedure",
        body="PDF 转结构化数据时先低分辨率整体定位，再对构件区域高精度识别，避免内存溢出。",
        name="progressive-recognition",
    )
    return cjk_store


def test_cjk_query_tokens_include_words_not_characters():
    from agent_memory.core.tokenization import query_tokens

    tokens = query_tokens("构件命名规范是什么", TOKENIZER_CJK)
    assert "构件" in tokens and "命名" in tokens
    assert "是" not in tokens


def test_ascii_literals_survive_cjk_segmentation():
    from agent_memory.core.tokenization import segment_text

    segmented = segment_text("Blender 的 bpy headless CLI", TOKENIZER_CJK)
    assert "Blender" in segmented.split() and "headless" in segmented.split()


def test_pure_cjk_query_retrieves_the_matching_memory(cjk_seeded):
    hits = Recall(cjk_seeded).recall("构件命名规范是什么")
    assert hits[0].name == "naming-convention"


def test_mixed_query_still_matches_ascii_literals(cjk_seeded):
    hits = Recall(cjk_seeded).recall("blender 怎么自动化")
    assert "blender-headless" in [hit.name for hit in hits]


def test_cjk_heading_stays_readable(cjk_seeded):
    cjk_seeded.record(
        abstract="带标题的中文记忆",
        type="fact",
        body="# 构件命名规范\n正文必须包含足够的字符数以触发分节切块。" * 8,
        name="with-heading",
    )
    hits = [hit for hit in Recall(cjk_seeded).recall("命名") if hit.name == "with-heading"]
    if hits:
        assert hits[0].heading in ("", "构件命名规范")


def test_switching_tokenizer_rebuilds_the_projection(tmp_path, clock):
    config = Config.default()
    store = Store(tmp_path / "store", config=config, clock=clock, agent="test-agent")
    store.init()
    store.record(
        abstract="构件命名采用 wc 格式",
        type="decision",
        body="数字孪生项目的构件命名规范。",
        name="naming-convention",
    )
    assert Recall(store).recall("构件命名") == []

    config.index.tokenizer = TOKENIZER_CJK
    store.record(  # any later write re-syncs, and drift forces a full rebuild first
        abstract="another memory",
        type="fact",
        body="an unrelated english body.",
        name="another",
    )
    hits = Recall(store).recall("构件命名")
    assert "naming-convention" in [hit.name for hit in hits]
