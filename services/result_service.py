from __future__ import annotations

import json
from datetime import datetime, timezone


def summarize(snapshot: dict, state: dict) -> dict:
    questions = snapshot["questions"]
    quests = snapshot["quests"]
    outcomes = state["outcomes"]

    completed = set()
    while True:
        new = {
            quest_id
            for quest_id, quest in quests.items()
            if quest_id not in completed
            and all(
                question_id in outcomes
                for question_id, question in questions.items()
                if question["quest_id"] == quest_id
            )
            and (
                not quest["prerequisite_quest_id"]
                or quest["prerequisite_quest_id"] in completed
            )
        }
        if not new:
            break
        completed.update(new)

    quest_states = {}
    for quest_id, quest in quests.items():
        prerequisite = quest["prerequisite_quest_id"]
        quest_states[quest_id] = (
            "done" if quest_id in completed
            else "locked" if prerequisite and prerequisite not in completed
            else "available"
        )

    ordered = sorted(quests.values(), key=lambda quest: quest["quest_order"])
    clues = [
        quest["reward_clue"]
        for quest in ordered
        if quest["quest_id"] in completed and quest["reward_clue"].strip()
    ]
    objective = [
        question_id
        for question_id, question in questions.items()
        if question["question_type"] != "short_answer"
    ]
    correct_objective = sum(
        outcomes.get(question_id) == "correct" for question_id in objective
    )

    return {
        "quest_states": quest_states,
        "completed_quests": [
            quest["quest_id"] for quest in ordered if quest["quest_id"] in completed
        ],
        "clues": clues,
        "total_score": sum(
            question["points"]
            for question_id, question in questions.items()
            if outcomes.get(question_id) == "correct"
        ),
        "total_possible": sum(question["points"] for question in questions.values()),
        "correct_answers": correct_objective,
        "objective_answers": len(objective),
        "accuracy": round(
            100 * correct_objective / len(objective), 1
        ) if objective else 0.0,
        "pending_review": sum(value == "pending" for value in outcomes.values()),
    }


def make_result_row(snapshot: dict, state: dict, reflection: list[str]) -> dict:
    summary = summarize(snapshot, state)
    if len(summary["completed_quests"]) != len(snapshot["quests"]):
        raise ValueError("필수 퀘스트가 아직 완료되지 않았습니다.")

    student = state["student"]
    return {
        "session_id": state["session_id"],
        "started_at": state["started_at"],
        "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "grade": student["grade"],
        "class": student["class"],
        "number": student["number"],
        "student_name": student["student_name"],
        "total_score": summary["total_score"],
        "total_possible": summary["total_possible"],
        "correct_answers": summary["correct_answers"],
        "objective_answers": summary["objective_answers"],
        "accuracy": summary["accuracy"],
        "completed_quests": json.dumps(summary["completed_quests"], ensure_ascii=False),
        "collected_clues": json.dumps(summary["clues"], ensure_ascii=False),
        "completion_status": (
            "completed_pending_review"
            if summary["pending_review"] else "completed"
        ),
        "reflection": json.dumps(
            [
                {"question": prompt, "answer": answer}
                for prompt, answer in zip(snapshot["reflection_prompts"], reflection)
            ],
            ensure_ascii=False,
        ),
    }
