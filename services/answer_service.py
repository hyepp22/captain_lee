from __future__ import annotations

import re
from datetime import datetime, timezone

from services.result_service import summarize


def _normalized_answer(question: dict, raw: object) -> tuple[str, bool | None]:
    kind = question["question_type"]

    if kind == "single_choice":
        if not isinstance(raw, str):
            raise ValueError("선택지 하나를 고르세요.")
        answer = raw.strip().upper()
        if answer not in {
            letter for letter in "ABCD" if question[f"option_{letter.lower()}"].strip()
        }:
            raise ValueError("유효한 선택지를 고르세요.")
        return answer, answer == question["correct_answer"].strip().upper()

    if kind == "multiple_choice":
        if not isinstance(raw, list) or not raw:
            raise ValueError("선택지를 한 개 이상 고르세요.")
        available = {
            letter for letter in "ABCD" if question[f"option_{letter.lower()}"].strip()
        }
        if (
            any(not isinstance(item, str) for item in raw)
            or len(raw) != len(set(raw))
            or any(item not in available for item in raw)
        ):
            raise ValueError("복수 선택 답안을 확인하세요.")
        answer = ",".join(sorted(raw))
        expected = ",".join(sorted(question["correct_answer"].split(",")))
        return answer, answer == expected

    if not isinstance(raw, str):
        raise ValueError("답안을 입력하세요.")
    answer = re.sub(r"\s+", " ", raw).strip()
    if not answer or len(answer) > 1200:
        raise ValueError("서술형 답안은 1~1200자로 입력하세요.")
    if question["grading_mode"] == "teacher_review":
        return answer, None

    # exact: 규칙은 폐쇄형 단답의 명시적 일치 표현에만 적용한다.
    # 일치하지 않는 답을 곧바로 오답 처리하지 않고 교사 검토로 보낸다.
    choices = [
        re.sub(r"\s+", " ", value).strip().casefold()
        for value in question["correct_answer"][6:].split("|")
    ]
    return answer, True if answer.casefold() in choices else None


def evaluate(snapshot: dict, state: dict, event: dict) -> tuple[dict, dict]:
    if state["phase"] != "playing":
        raise ValueError("현재 답안을 제출할 수 없습니다.")

    question_id = str(event.get("question_id", ""))
    question = snapshot["questions"].get(question_id)
    if not question:
        raise ValueError("등록되지 않은 문항 ID입니다.")
    if question_id in state["outcomes"]:
        raise ValueError("이미 완료한 문항입니다.")

    summary = summarize(snapshot, state)
    if summary["quest_states"][question["quest_id"]] != "available":
        raise ValueError("선행 퀘스트를 먼저 완료하세요.")

    attempt = state["attempts"].get(question_id, 0) + 1
    if attempt > question["max_attempts"]:
        raise ValueError("최대 시도 횟수를 초과했습니다.")
    if event.get("attempt_no") != attempt:
        raise ValueError("시도 횟수가 일치하지 않습니다. 화면을 확인한 뒤 다시 제출하세요.")

    answer, is_correct = _normalized_answer(question, event.get("answer"))
    completed = is_correct is True or is_correct is None or attempt == question["max_attempts"]
    outcome = (
        "correct" if is_correct is True
        else "pending" if is_correct is None
        else "exhausted" if completed
        else ""
    )
    points = question["points"] if is_correct is True else 0

    submitted = datetime.now(timezone.utc)
    started = datetime.fromisoformat(state["started_at"])
    row = {
        "response_id": f'{state["session_id"]}-{event["event_id"]}',
        "session_id": state["session_id"],
        "submitted_at": submitted.isoformat(timespec="seconds"),
        "grade": state["student"]["grade"],
        "class": state["student"]["class"],
        "number": state["student"]["number"],
        "student_name": state["student"]["student_name"],
        "quest_id": question["quest_id"],
        "question_id": question_id,
        "question_type": question["question_type"],
        "answer": answer,
        "attempt_no": attempt,
        "is_correct": (
            "TRUE" if is_correct is True else "FALSE" if is_correct is False else ""
        ),
        "earned_points": points,
        "grading_status": "pending_review" if is_correct is None else "graded",
        "elapsed_seconds": max(0, int((submitted - started).total_seconds())),
    }

    if is_correct is True:
        message = f"정답입니다. {points}점을 획득했습니다."
    elif is_correct is None:
        message = "답안을 기록했습니다. 정답 여부는 교사가 검토합니다."
    elif completed:
        message = "시도 기회를 모두 사용했습니다. 해설을 확인하세요."
    else:
        message = "다시 생각해 보세요. 정답은 아직 공개되지 않습니다."

    result = {
        "event_id": event["event_id"],
        "kind": "answer",
        "question_id": question_id,
        "message": message,
        "is_correct": is_correct,
        "completed": completed,
        "attempt_no": attempt,
        "earned_points": points,
        "explanation": question["explanation"] if completed and is_correct is not None else "",
        "save_status": "pending",
    }
    return row, {"attempt": attempt, "outcome": outcome, "result": result}


def hint(snapshot: dict, state: dict, event: dict) -> dict:
    question_id = str(event.get("question_id", ""))
    question = snapshot["questions"].get(question_id)
    if not question or question_id in state["outcomes"]:
        raise ValueError("힌트를 요청할 수 없는 문항입니다.")
    if summarize(snapshot, state)["quest_states"][question["quest_id"]] != "available":
        raise ValueError("아직 열리지 않은 퀘스트입니다.")
    return {
        "event_id": event["event_id"],
        "kind": "hint",
        "question_id": question_id,
        "message": "힌트를 확인하세요.",
        "hint": question["hint"] or "이 문항에는 등록된 힌트가 없습니다.",
    }
