from __future__ import annotations

import re

import streamlit as st

from services.sheets_service import optional_settings, worksheet_rows

DEFAULT_REFLECTIONS = [
    "이인국의 행동에서 가장 인상 깊었던 점은 무엇이며, 그 이유는 무엇인가?",
    "작품을 이해하는 데 가장 도움이 된 단서는 무엇인가?",
    "작품이 비판하는 대상이나 태도에 대해 새롭게 생각한 점은 무엇인가?",
]


def _active(value: str, context: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("true", "1", "yes", "y"):
        return True
    if normalized in ("false", "0", "no", "n"):
        return False
    raise ValueError(f"{context}: is_active에는 TRUE 또는 FALSE를 입력하세요.")


def _number(value: str, context: str, low: int, high: int) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(f"{context}: 정수를 입력하세요.") from exc
    if not low <= result <= high:
        raise ValueError(f"{context}: {low}~{high} 범위여야 합니다.")
    return result


def _unique(rows: list[dict], column: str, tab: str) -> None:
    seen = set()
    for row in rows:
        identifier = row[column].strip()
        if not identifier or identifier in seen:
            raise ValueError(f"{tab} 탭의 {column}이 비어 있거나 중복되었습니다: {identifier}")
        seen.add(identifier)


@st.cache_data(ttl=300, show_spinner=False)
def load_content() -> dict:
    """새 게임 세션용 데이터. 진행 중 세션은 반환된 사본을 계속 사용한다."""
    questions = worksheet_rows("Questions")
    quests = worksheet_rows("Quests")
    objects = worksheet_rows("Objects")
    settings = optional_settings()

    for tab, rows, column in (
        ("Questions", questions, "question_id"),
        ("Quests", quests, "quest_id"),
        ("Objects", objects, "object_id"),
    ):
        _unique(rows, column, tab)

    active_quests = {}
    for row in quests:
        identifier = row["quest_id"].strip()
        if not _active(row["is_active"], f"Quests/{identifier}"):
            continue
        row["quest_order"] = _number(
            row["quest_order"], f"Quests/{identifier}/quest_order", 1, 1000
        )
        if not row["title"].strip() or not row["map_id"].strip():
            raise ValueError(f"Quests/{identifier}: title과 map_id가 필요합니다.")
        active_quests[identifier] = row

    active_objects = {}
    for row in objects:
        identifier = row["object_id"].strip()
        if not _active(row["is_active"], f"Objects/{identifier}"):
            continue
        quest = active_quests.get(row["quest_id"].strip())
        if not quest or row["map_id"] != quest["map_id"]:
            raise ValueError(f"Objects/{identifier}: 활성 quest_id/map_id를 확인하세요.")
        try:
            x, y = float(row["x"]), float(row["y"])
        except ValueError as exc:
            raise ValueError(f"Objects/{identifier}: x와 y는 숫자여야 합니다.") from exc
        if not (32 <= x <= 928 and 32 <= y <= 568):
            raise ValueError(f"Objects/{identifier}: x=32~928, y=32~568로 설정하세요.")
        row["x"], row["y"] = x, y
        active_objects[identifier] = row

    active_questions = {}
    for row in questions:
        identifier = row["question_id"].strip()
        if not _active(row["is_active"], f"Questions/{identifier}"):
            continue

        quest = active_quests.get(row["quest_id"].strip())
        obj = active_objects.get(row["object_id"].strip())
        if not quest or not obj or obj["quest_id"] != row["quest_id"]:
            raise ValueError(
                f"Questions/{identifier}: 활성 quest_id와 object_id 연결을 확인하세요."
            )
        if not row["question_text"].strip():
            raise ValueError(f"Questions/{identifier}: question_text가 비었습니다.")

        row["question_order"] = _number(
            row["question_order"], f"Questions/{identifier}/question_order", 1, 1000
        )
        row["points"] = _number(row["points"], f"Questions/{identifier}/points", 0, 1000)
        row["max_attempts"] = _number(
            row["max_attempts"], f"Questions/{identifier}/max_attempts", 1, 5
        )

        kind = row["question_type"].strip()
        mode = row["grading_mode"].strip()
        if kind not in ("single_choice", "multiple_choice", "short_answer"):
            raise ValueError(f"Questions/{identifier}: question_type 값이 잘못되었습니다.")
        if mode not in ("auto", "teacher_review"):
            raise ValueError(f"Questions/{identifier}: grading_mode 값이 잘못되었습니다.")
        if kind != "short_answer" and mode != "auto":
            raise ValueError(f"Questions/{identifier}: 객관식은 grading_mode=auto로 설정하세요.")

        if kind in ("single_choice", "multiple_choice"):
            available = {
                letter
                for letter in "ABCD"
                if row[f"option_{letter.lower()}"].strip()
            }
            answers = [item.strip().upper() for item in row["correct_answer"].split(",")]
            if (
                not answers
                or any(answer not in available for answer in answers)
                or len(set(answers)) != len(answers)
                or (kind == "single_choice" and len(answers) != 1)
            ):
                raise ValueError(
                    f"Questions/{identifier}: 선택지와 정답을 확인하세요. "
                    "복수 정답 형식은 A,C입니다."
                )
        elif mode == "auto":
            rule = row["correct_answer"]
            if not rule.startswith("exact:") or not all(
                part.strip() for part in rule[6:].split("|")
            ):
                raise ValueError(
                    f"Questions/{identifier}: 자동 단답형 규칙은 "
                    "exact:표현1|표현2 형식이어야 합니다."
                )

        active_questions[identifier] = row

    if not active_questions or not active_quests or not active_objects:
        raise ValueError("Questions, Quests, Objects에 연결된 활성 데이터를 입력하세요.")

    for identifier, quest in active_quests.items():
        prerequisite = quest["prerequisite_quest_id"].strip()
        if prerequisite and (
            prerequisite not in active_quests or prerequisite == identifier
        ):
            raise ValueError(f"Quests/{identifier}: 선행 퀘스트 ID가 잘못되었습니다.")
        if not any(q["quest_id"] == identifier for q in active_questions.values()):
            raise ValueError(f"Quests/{identifier}: 연결된 활성 문항이 없습니다.")

    for identifier, obj in active_objects.items():
        linked = [q for q in active_questions.values() if q["object_id"] == identifier]
        if not linked:
            raise ValueError(f"Objects/{identifier}: 연결된 활성 문항이 없습니다.")
        specified = obj["question_id"].strip()
        if specified and specified not in {q["question_id"] for q in linked}:
            raise ValueError(f"Objects/{identifier}: question_id 연결이 잘못되었습니다.")

    for identifier in active_quests:
        visited = set()
        current = identifier
        while current:
            if current in visited:
                raise ValueError(f"Quests/{identifier}: 선행 퀘스트에 순환이 있습니다.")
            visited.add(current)
            current = active_quests[current]["prerequisite_quest_id"].strip()

    prompts = [
        settings.get(f"reflection_{index}", default).strip()
        for index, default in enumerate(DEFAULT_REFLECTIONS, 1)
    ]
    if any(not prompt or len(prompt) > 300 for prompt in prompts):
        raise ValueError("Settings의 reflection_1~3은 1~300자로 설정하세요.")

    return {
        "questions": active_questions,
        "quests": active_quests,
        "objects": active_objects,
        "reflection_prompts": prompts,
    }


def public_content(snapshot: dict, state: dict, summary: dict) -> dict:
    """정답·채점 규칙·비공개 해설을 제거한 게임 전달 데이터."""
    questions = []
    for row in snapshot["questions"].values():
        questions.append({
            "question_id": row["question_id"],
            "quest_id": row["quest_id"],
            "object_id": row["object_id"],
            "question_order": row["question_order"],
            "question_type": row["question_type"],
            "question_text": row["question_text"],
            "options": {
                letter: row[f"option_{letter.lower()}"]
                for letter in "ABCD"
                if row[f"option_{letter.lower()}"].strip()
            },
            "points": row["points"],
            "max_attempts": row["max_attempts"],
        })

    quests = []
    for row in sorted(
        snapshot["quests"].values(), key=lambda value: value["quest_order"]
    ):
        quests.append({
            "quest_id": row["quest_id"],
            "quest_order": row["quest_order"],
            "title": row["title"],
            "description": row["description"],
            "map_id": row["map_id"],
            "prerequisite_quest_id": row["prerequisite_quest_id"],
            "state": summary["quest_states"][row["quest_id"]],
        })

    return {
        "session_id": state["session_id"],
        "phase": state["phase"],
        "questions": questions,
        "quests": quests,
        "objects": [
            {
                key: row[key]
                for key in (
                    "object_id", "map_id", "object_name", "object_type",
                    "x", "y", "interaction_text", "quest_id",
                    "appearance_note",
                )
            }
            for row in snapshot["objects"].values()
        ],
        "progress": {
            "attempts": state["attempts"],
            "outcomes": state["outcomes"],
            "score": summary["total_score"],
            "correct": summary["correct_answers"],
            "clues": summary["clues"],
            "pending_writes": len(state["pending_responses"])
            + int(bool(state.get("result_row") and not state["result_saved"])),
        },
        "reflection_prompts": snapshot["reflection_prompts"],
        "last_result": state.get("last_result"),
    }
