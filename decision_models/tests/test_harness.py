"""Fast checks on the harness and the data. None of these call a model."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import harness  # noqa: E402
from harness import measure, spans  # noqa: E402
from harness.decision_points import DECISION_POINTS, R_ORDER, inventory  # noqa: E402


def test_inventory_has_twenty_rows_in_loop_order():
    table = inventory()
    assert len(table) == 20
    assert sorted(table["n"]) == list(range(1, 21))
    assert list(dict.fromkeys(table["r"].astype(str))) == R_ORDER
    assert set(DECISION_POINTS[0]) == {"r", "n", "name", "question", "typical", "d1_primitive", "notebook"}


def test_demo_text_shape():
    text, gold = harness.demo()
    assert 1400 <= len(text.split()) <= 1600
    assert len(gold["gold_boundaries"]) == 8 and gold["gold_boundaries"][0] == 0
    assert gold["gold_boundaries"] == sorted(gold["gold_boundaries"])
    assert text.count(gold["fake_card_number"]) == 1
    starts = spans.sentence_starts(text)
    assert set(gold["gold_boundaries"]) <= set(starts), "every gold boundary starts a sentence"


def test_eval_excerpts_are_exact_and_unique():
    text, _ = harness.demo()
    rows = harness.eval_questions()
    assert len(rows) == 40
    for row in rows:
        for excerpt, (start, end) in zip(row["excerpts"], row["spans"]):
            assert text.count(excerpt) == 1
            assert text[start:end] == excerpt


def test_tool_labels_cover_every_tool_and_none():
    from harness import demo_tools

    data = harness.labels("tools")
    assert len(data["turns"]) == 75 and len(demo_tools.TOOLS) == 11
    assert {turn["tool"] for turn in data["turns"]} == set(data["options"]) == {t.__name__ for t in demo_tools.TOOLS} | {"none"}


def test_swap_label_sets_have_their_documented_shape():
    cache = harness.labels("cache")
    ids = {c["id"] for c in cache["cached"]}
    assert len(cache["cached"]) == 16 and len(cache["queries"]) == 48
    assert all(q["serves"] is None or q["serves"] in ids for q in cache["queries"])
    assert sum(q["kind"] == "paraphrase" for q in cache["queries"]) == 20
    dedup = harness.labels("dedup")
    assert len(dedup["pairs"]) == 50 and set(dedup["actions"]) == set(dedup["relations"])
    assert all(sum(p["relation"] == r for p in dedup["pairs"]) == 10 for r in dedup["relations"])
    extraction = harness.labels("extraction")
    assert len(extraction["turns"]) == 60 and sum(t["durable"] for t in extraction["turns"]) == 36
    assert all((t["type"] in extraction["types"]) == t["durable"] for t in extraction["turns"])
    routing = harness.labels("memory_routing")
    assert len(routing["turns"]) == 58 and sum(len(t["stores"]) == 2 for t in routing["turns"]) == 12
    assert all(set(t["stores"]) <= {"episodic", "semantic", "procedural"} for t in routing["turns"])


def _notebook_strings(name: str) -> list[str]:
    """Every string constant in a notebook's code (adjacent literals already joined by the parser)."""
    import ast

    path = next((ROOT / "notebooks").glob(f"{name}*.ipynb"))
    out = []
    for cell in json.loads(path.read_text())["cells"]:
        if cell["cell_type"] == "code":
            out += [n.value for n in ast.walk(ast.parse("".join(cell["source"]))) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return out


@pytest.mark.parametrize("notebook,question", [
    ("01", "CHUNK_BOUNDARY"), ("03", "CACHE_SERVES"), ("05", "DEDUP"),
    *[("04", f"ROUTES.{k}") for k in ("episodic", "semantic", "procedural")],
    ("06", "EXTRACTION.durable"), ("06", "EXTRACTION.type"),
])
def test_notebooks_ask_exactly_the_shared_questions(notebook, question):
    """Every instruction and criterion in harness.questions appears word for word in its notebook."""
    from harness import questions as Q

    name, _, key = question.partition(".")
    q = getattr(Q, name)[key] if key else getattr(Q, name)
    strings = _notebook_strings(notebook)
    texts = [q["instructions"]] + (list(q["criteria"].values()) if q["type"] == "noul" and q.get("criteria") else [])
    for text in texts:
        assert text in strings, f"notebook {notebook} no longer asks: {text[:60]}"
    assert Q.NO_TOOL in _notebook_strings("07")


def test_retrieval_scores_match_the_span_definitions():
    # 10 gold characters, half covered by one 20-character chunk.
    scores = spans.retrieval_scores([(5, 25)], [(0, 10)])
    assert scores["recall"] == pytest.approx(0.5)
    assert scores["precision"] == pytest.approx(5 / 20)
    assert scores["iou"] == pytest.approx(5 / 25)


def test_overlapping_chunks_count_against_precision_not_recall():
    single = spans.retrieval_scores([(0, 10)], [(0, 10)])
    overlap = spans.retrieval_scores([(0, 10), (0, 10)], [(0, 10)])
    assert single["recall"] == overlap["recall"] == 1.0
    assert overlap["precision"] == pytest.approx(0.5)
    assert overlap["iou"] == pytest.approx(0.5)


def test_boundary_scores_tolerance_and_one_to_one_matching():
    starts = [0, 10, 20, 30, 40, 50]
    # Gold cut at sentence 3. A cut at 2 is within one sentence; so is 4, but gold matches once.
    assert spans.boundary_scores([20, 40], [0, 30], starts)["true_positive"] == 1
    assert spans.boundary_scores([10], [0, 30], starts)["recall"] == 0.0
    assert spans.boundary_scores([0], [0, 30], starts)["cuts"] == 0, "offset 0 is not a cut"


def test_locate_tolerates_rejoined_whitespace():
    text = "One line.\nTwo lines here."
    assert spans.locate(text, "One line. Two lines here.") == (0, len(text))
    with pytest.raises(ValueError):
        spans.locate(text, "Not in the text")


def test_prices_refuse_unknown_models():
    assert measure.price("d1.1", 1_000_000) == pytest.approx(0.02)
    assert measure.price("gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)
    assert measure.price("jev", 1_000_000) == pytest.approx(0.042)
    assert measure.price("gpt-6-luna", 1_000_000, 1_000_000) == pytest.approx(0.10)
    with pytest.raises(KeyError):
        measure.price("no-such-model", 1)


def test_results_rows_append_as_json_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(measure, "RESULTS", tmp_path)
    measure.use_notebook("t")
    with measure.timed("step", count=3):
        pass
    measure.cost("step", 100, 10)
    rows = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert [row["kind"] for row in rows] == ["time", "cost"]
    assert rows[0]["count"] == 3 and rows[1]["input_tokens"] == 100


def test_hosted_backend_needs_a_key_and_posts_the_documented_shape(monkeypatch):
    from harness import d1

    monkeypatch.setenv("D1_BACKEND", "hosted")
    monkeypatch.delenv("LIQUID_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        d1.ask("state", {"q": d1.noul("yes?")})

    sent = {}

    class Reply:
        status_code, ok, text = 200, True, ""

        def json(self):
            return {"answers": {"q": {"type": "noul", "noul": 0.9}}, "usage": {"input_tokens": 7, "output_tokens": 0}}

    def post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return Reply()

    import requests

    monkeypatch.setenv("LIQUID_API_KEY", "liquid_test")
    monkeypatch.setattr(requests, "post", post)
    assert d1.decide("state", {"q": d1.noul("yes?")})["q"]["noul"] == 0.9
    assert sent["url"] == "https://api.liquid.ai/decisions/v1/systemone"
    assert sent["body"]["model"] == "d1.1" and sent["headers"]["Authorization"] == "Bearer liquid_test"


def test_openai_backend_translates_questions_and_answers(monkeypatch):
    from harness import d1

    sent = {}

    class Reply:
        status_code, ok, text = 200, True, ""

        def json(self):
            return {"model": "gpt-6-luna", "usage": {"input_tokens": 11, "output_tokens": 0}, "answers": [
                {"type": "predicate", "name": "yes", "probability": 0.8},
                {"type": "choice", "name": "pick", "choice": "b", "confidence": 0.7,
                 "probabilities": [{"value": "a", "probability": 0.2}, {"value": "b", "probability": 0.8}]},
                {"type": "score", "name": "level", "score": 1.2, "confidence": 0.6,
                 "probabilities": [{"value": 0, "label": "0", "probability": 0.1},
                                   {"value": 1, "label": "1", "probability": 0.6},
                                   {"value": 2, "label": "2", "probability": 0.3}]},
                {"type": "refusal", "name": "no"}]}

    def post(url, headers, json, timeout):
        sent.update(url=url, body=json)
        return Reply()

    import requests

    monkeypatch.setenv("OPENAI_API_KEY", "sk_test")
    monkeypatch.setattr(requests, "post", post)
    questions = {"yes": d1.noul("ok?", true="it is", false="it is not"), "pick": d1.choice("which?", {"a": "A", "b": "B"}),
                 "level": d1.score("how much?", ["low", "mid", "high"]), "no": d1.noul("refused?")}
    with d1.using("openai"):
        answers = d1.decide({"k": "v"}, questions)
    assert sent["url"] == "https://api.openai.com/v1/decisions" and sent["body"]["model"] == "gpt-6-luna"
    assert sent["body"]["input"][0]["content"][0] == {"type": "input_json", "data": {"k": "v"}}
    first, second, third, _ = sent["body"]["questions"]
    assert first["type"] == "predicate" and "True when: it is" in first["instructions"]
    assert second["choices"] == [{"value": "a", "description": "A"}, {"value": "b", "description": "B"}]
    assert third["levels"][2] == {"label": "2", "description": "high"}
    assert answers["yes"] == {"type": "noul", "noul": 0.8}
    assert answers["pick"]["choice"] == "b" and answers["pick"]["probabilities"] == {"a": 0.2, "b": 0.8}
    assert answers["level"]["probabilities"]["1"] == 0.6 and answers["level"]["legend"]["2"] == "high"
    assert answers["no"]["refused"] and answers["no"]["noul"] == 0.5


def test_notebook_text_has_no_session_wording():
    banned = re.compile(r"\b(webinar|workshop|lesson|lecture|slides?|course|deck)\b", re.I)
    for path in sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb")):
        for cell in json.loads(path.read_text())["cells"]:
            if cell["cell_type"] == "markdown":
                assert not banned.search("".join(cell["source"])), path.name
