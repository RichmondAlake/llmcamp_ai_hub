"""Swap 7 · tool selection (notebook 07): top-k by similarity vs "which one, if any?"."""
from __future__ import annotations

import harness
import numpy as np
from harness import demo_tools
from harness import questions as Q

from backend.core.swaps import common

META = {
    "id": "tools", "today_short": "top 3 by similarity", "n": 7, "title": "Tool selection", "stage": "Reuse", "notebook": "07_tool_selection",
    "subtitle": 'Top-k by similarity vs "which one, if any?"',
    "when": "Every turn, on the hot path. Decision 19.",
    "today": "Embed the request and the tool descriptions; the top 3 by similarity go into the prompt and the LLM picks.",
    "model": 'Keep the embedding top 5 for recall, then one Choice: "which of these tools does this request need, if any?". Only that tool, or none, reaches the prompt.',
    "judge": "75 labelled turns over eleven tools: the right tool first, wrong tool calls by the LLM, and prompt tokens per turn.",
    "input": "turn",
    "notes": [{"title": "Who does what: this app, MemoRizz and the decision model", "columns": ["Step", "Done by", "The call"], "rows": [
        ["Store each tool: its name, its docstring as the description, and a JSON schema from its signature", "MemoRizz", "Toolbox.register_tool"],
        ["Embed one line per tool, “name: docstring Arguments: …”, at the first search", "MemoRizz (the file store)", "inside get_most_similar_tools"],
        ["Today: embed the request and return the k closest tools", "MemoRizz", "get_most_similar_tools"],
        ["Decision model: one Choice over the top 5 tools’ docstrings, plus none", "the decision model", "system_one (d1) or HTTP"]],
        "text": ["For send_email the embedded line is “send_email: Send an email to a person or address, with a subject and a message, and optionally a file. Use it when the user asks to email, mail or forward something to someone. Arguments: body, subject, to.” The similarity search compares the request with lines like that, which is why a request about a report finds the report tool first."]}],
    "takeaways": [
        "Similarity ranks tools by topic. The request's action, and its \"don't\", decide the right tool.",
        "Keep the embedding top k for recall, and let a Choice with a none option pick from it.",
        "A none is a safe answer: when the decision model is unsure, the agent calls nothing.",
        "Fewer tool schemas in the prompt means fewer tokens on every turn.",
    ],
}

TURNS = harness.labels("tools")["turns"]
LABELS = {t["turn"]: t["tool"] for t in TURNS}
EXAMPLES = [{"label": t, "input": t} for t in (
    "Send the Q3 report to Sarah.", "Don't email it, just post it in Slack.",
    "Don't post anything in Slack; email Sarah the numbers instead.", "Thanks, that's all for now.")]


def toolbox(session):
    """The session's MemoRizz Toolbox with the eleven demo tools, built once."""
    with session.lock:
        if "toolbox" not in session.cache:
            from memorizz import Toolbox

            provider = session.provider()
            demo_tools.bind(provider)
            box = Toolbox(memory_provider=provider)
            for tool in demo_tools.TOOLS:
                box.register_tool(tool)
            session.cache["toolbox"] = box
            session.note("write", f"registered {len(demo_tools.TOOLS)} tools in the session Toolbox")
        return session.cache["toolbox"]


def top_k(session, turn: str, k: int) -> list[str]:
    return [row["name"] for row in toolbox(session).get_most_similar_tools(turn, limit=k)]


def try_(session, turn: str, backends: list[str]) -> dict:
    needed = LABELS.get(turn)
    methods = []

    def today():
        names = top_k(session, turn, 3)
        lines = [{"text": f"#{i + 1} {n}", "ok": (n == needed) if needed else None} for i, n in enumerate(names)]
        return {"answer": names[0], "right": (names[0] == needed) if needed else None, "lines": lines,
                "usd": common.embed_usd([turn])}

    if common.openai_ready():
        methods.append(common.today("Top 3 by similarity", today))
    names = top_k(session, turn, 5)
    question = {"tool": Q.tool_question(names)}
    for name, rec in common.ask_each(backends, turn, question).items():
        answer = (rec.get("answers") or {}).get("tool", {})
        choice = answer.get("choice")
        lines = [{"text": f"{k}: {v:.2f}", "ok": (k == needed) if needed else None}
                 for k, v in sorted((answer.get("probabilities") or {}).items(), key=lambda kv: -kv[1])[:3]]
        methods.append(common.model_record(name, rec, str(choice), (choice == needed) if needed else None, lines))
    common.log(session, "tools", methods, turn)
    return {"input": turn, "methods": methods, "shown": names,
            "truth": f"Needs: {needed}" if needed else None}


def labelled_items(session):
    return [(t["turn"], {"tool": Q.tool_question(top_k(session, t["turn"], 5))}) for t in TURNS]


def score(answers: list) -> dict:
    picks = [a["tool"]["choice"] if a else None for a in answers]
    right = [p == t["tool"] for p, t in zip(picks, TURNS)]
    none_right = [p == "none" for p, t in zip(picks, TURNS) if t["tool"] == "none"]
    return {"measure": "right tool first", "score": float(np.mean(right)),
            "detail": f"{sum(right)} of {len(right)} turns right, none on {sum(none_right)} of {len(none_right)} no-tool turns"}
