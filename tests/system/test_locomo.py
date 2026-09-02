"""A second benchmark has to arrive in the shape the driver already replays, or it is a fork."""

import json

from agent_memory.harness import dataset, locomo
from agent_memory.harness.main import main as exp_main

SAMPLE = {
    "sample_id": "conv-26",
    "conversation": {
        "speaker_a": "Caroline",
        "speaker_b": "Melanie",
        "session_1_date_time": "1:56 pm on 8 May, 2023",
        "session_1": [
            {"speaker": "Caroline", "dia_id": "D1:1", "text": "I adopted a greyhound."},
            {"speaker": "Melanie", "dia_id": "D1:2", "text": "What did you name her?"},
        ],
        "session_2_date_time": "10:00 am on 20 May, 2023",
        "session_2": [
            {"speaker": "Caroline", "dia_id": "D2:1", "text": "Her name is Comet."},
        ],
    },
    "qa": [
        {
            "question": "What pet did Caroline adopt?",
            "answer": "a greyhound",
            "category": 4,
            "evidence": ["D1:1"],
        },
        {
            "question": "Where does Melanie work?",
            "adversarial_answer": "Not mentioned in the conversation",
            "category": 5,
        },
    ],
}


def _written(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "locomo.json"
    source.write_text(json.dumps([SAMPLE]), encoding="utf-8")
    target = tmp_path / "suite.json"
    assert exp_main(["convert-locomo", "--source", str(source), "--target", str(target)]) == 0
    return target


def test_every_question_becomes_an_episode_the_driver_can_replay(tmp_path):
    episodes = dataset.load(_written(tmp_path))
    assert len(episodes) == len(SAMPLE["qa"])
    assert {episode.question for episode in episodes} == {
        entry["question"] for entry in SAMPLE["qa"]
    }


def test_the_conversation_becomes_sessions_in_order_with_their_dates(tmp_path):
    episode = dataset.load(_written(tmp_path))[0]
    assert [session.id for session in episode.sessions] == ["session_1", "session_2"]
    assert all(session.date for session in episode.sessions)
    assert episode.sessions[0].turns[0].content.endswith("I adopted a greyhound.")


def test_a_speaker_is_carried_into_the_turn_because_two_people_are_talking(tmp_path):
    episode = dataset.load(_written(tmp_path))[0]
    assert "Caroline" in episode.sessions[0].turns[0].content
    assert "Melanie" in episode.sessions[0].turns[1].content


def test_an_unanswerable_question_is_marked_as_one(tmp_path):
    episodes = dataset.load(_written(tmp_path))
    unanswerable = [episode for episode in episodes if episode.is_abstention()]
    assert [episode.question for episode in unanswerable] == ["Where does Melanie work?"]
    assert unanswerable[0].answer


def test_evidence_points_at_the_session_that_holds_it(tmp_path):
    episode = dataset.load(_written(tmp_path))[0]
    assert episode.evidence_session_ids == ("session_1",)


def test_question_types_are_names_rather_than_the_numbers_on_disk(tmp_path):
    episodes = dataset.load(_written(tmp_path))
    assert set(locomo.CATEGORIES.values()) >= {episode.question_type for episode in episodes}
    assert not any(episode.question_type.isdigit() for episode in episodes)


def test_episode_identifiers_are_stable_across_two_conversions(tmp_path):
    first = dataset.load(_written(tmp_path))
    second = dataset.load(_written(tmp_path / "again"))
    assert [episode.id for episode in first] == [episode.id for episode in second]
