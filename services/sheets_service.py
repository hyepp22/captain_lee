from __future__ import annotations

import random
import threading
import time
from typing import Callable, TypeVar

import gspread
import requests
import streamlit as st
from gspread.exceptions import APIError, WorksheetNotFound

T = TypeVar("T")
_WRITE_LOCK = threading.Lock()

HEADERS = {
    "Questions": [
        "question_id", "is_active", "quest_id", "object_id",
        "question_order", "question_type", "question_text",
        "option_a", "option_b", "option_c", "option_d",
        "correct_answer", "grading_mode", "points", "max_attempts",
        "hint", "explanation", "learning_goal", "source_note",
    ],
    "Quests": [
        "quest_id", "is_active", "quest_order", "title",
        "description", "map_id", "prerequisite_quest_id",
        "reward_clue", "completion_message",
    ],
    "Objects": [
        "object_id", "is_active", "map_id", "object_name",
        "object_type", "x", "y", "interaction_text", "quest_id",
        "question_id", "appearance_note",
    ],
    "Responses": [
        "response_id", "session_id", "submitted_at", "grade",
        "class", "number", "student_name", "quest_id",
        "question_id", "question_type", "answer", "attempt_no",
        "is_correct", "earned_points", "grading_status",
        "elapsed_seconds",
    ],
    "GameResults": [
        "session_id", "started_at", "ended_at", "grade",
        "class", "number", "student_name", "total_score",
        "total_possible", "correct_answers", "objective_answers",
        "accuracy", "completed_quests", "collected_clues",
        "completion_status", "reflection",
    ],
    "Settings": ["key", "value"],
}


@st.cache_resource
def spreadsheet():
    try:
        app = st.secrets["app"]
        account = dict(st.secrets["gcp_service_account"])
        sheet_id = str(app["spreadsheet_id"]).strip()
        if not sheet_id or sheet_id == "GOOGLE_SHEET_ID":
            raise ValueError("Secrets의 app.spreadsheet_id를 설정하세요.")
        if not str(account.get("private_key", "")).startswith(
            "-----BEGIN PRIVATE KEY-----"
        ):
            raise ValueError("Secrets의 gcp_service_account.private_key를 확인하세요.")
        return gspread.service_account_from_dict(account).open_by_key(sheet_id)
    except KeyError as exc:
        raise ValueError("Secrets의 app 및 gcp_service_account 설정을 확인하세요.") from exc


def _retry(action: Callable[[], T]) -> T:
    for attempt in range(3):
        try:
            return action()
        except APIError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == 2:
                raise
        time.sleep(0.4 * (2**attempt) + random.uniform(0, 0.2))
    raise RuntimeError("Google Sheets 요청 재시도에 실패했습니다.")


def worksheet_rows(name: str) -> list[dict[str, str]]:
    if name not in HEADERS:
        raise ValueError("허용되지 않은 시트 이름입니다.")

    try:
        values = _retry(lambda: spreadsheet().worksheet(name).get_all_values())
    except WorksheetNotFound as exc:
        raise ValueError(f"{name} 탭을 생성하고 README의 헤더를 입력하세요.") from exc

    if not values:
        raise ValueError(f"{name} 탭의 첫 행에 헤더를 입력하세요.")

    header = [cell.strip() for cell in values[0]]
    duplicates = sorted({cell for cell in header if cell and header.count(cell) > 1})
    missing = [cell for cell in HEADERS[name] if cell not in header]

    if duplicates or missing:
        raise ValueError(
            f"{name} 탭의 헤더 오류. 누락: {missing or '없음'}; "
            f"중복: {duplicates or '없음'}"
        )

    return [
        dict(zip(header, row + [""] * (len(header) - len(row))))
        for row in values[1:]
        if any(cell.strip() for cell in row)
    ]


def optional_settings() -> dict[str, str]:
    try:
        rows = worksheet_rows("Settings")
    except ValueError as exc:
        if "Settings 탭을 생성" in str(exc):
            return {}
        raise

    settings = {}
    for row in rows:
        key = row["key"].strip()
        if not key or key in settings:
            raise ValueError("Settings 탭의 key는 비어 있거나 중복될 수 없습니다.")
        settings[key] = row["value"].strip()
    return settings


def append_unique(name: str, row: dict[str, object]) -> None:
    """한 서버 프로세스 안에서 조회와 추가를 직렬화하고, 재시도마다 ID를 확인한다."""
    if name not in ("Responses", "GameResults"):
        raise ValueError("쓰기가 허용되지 않은 시트입니다.")

    columns = HEADERS[name]
    identifier = str(row[columns[0]])
    if not identifier:
        raise ValueError("저장할 행의 고유 ID가 없습니다.")

    with _WRITE_LOCK:
        worksheet = spreadsheet().worksheet(name)

        def operation() -> None:
            if identifier in worksheet.col_values(1)[1:]:
                return

            worksheet.append_row(
                [str(row.get(column, "")) for column in columns],
                value_input_option="RAW",
            )

        _retry(operation)
