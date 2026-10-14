from __future__ import annotations

import hmac
import re
import uuid
from datetime import datetime, timezone

import streamlit as st

from game_component import game_component
from services.answer_service import evaluate, hint
from services.question_service import load_content, public_content
from services.report_service import pdf_report, printable_html
from services.result_service import make_result_row, summarize
from services.sheets_service import append_unique, worksheet_rows

st.set_page_config(
    page_title="꺼삐딴 리: 문학 탐험 기록관",
    page_icon="📚",
    layout="wide",
)

EVENT_ID = re.compile(r"^[a-zA-Z0-9_-]{8,80}$")


def secret(name: str) -> str:
    try:
        return str(st.secrets["app"].get(name, "")).strip()
    except (KeyError, FileNotFoundError):
        return ""


def sync_writes(state: dict) -> None:
    """실패한 행은 세션에 남긴다. 결과는 모든 응답의 저장 확인 뒤 기록한다."""
    for identifier, row in list(state["pending_responses"].items()):
        try:
            append_unique("Responses", row)
        except Exception:
            state["write_error"] = (
                "일부 답안을 Google Sheets에 저장하지 못했습니다. "
                "인터넷 연결을 확인하고 '미저장 기록 재시도'를 누르세요."
            )
            continue
        del state["pending_responses"][identifier]

    if (
        state.get("result_row")
        and not state["pending_responses"]
        and not state["result_saved"]
    ):
        try:
            append_unique("GameResults", state["result_row"])
        except Exception:
            state["write_error"] = (
                "최종 결과 저장을 확인하지 못했습니다. "
                "'미저장 기록 재시도'를 누르세요."
            )
        else:
            state["result_saved"] = True

    if not state["pending_responses"] and (
        not state.get("result_row") or state["result_saved"]
    ):
        state["write_error"] = ""


def process_event(state: dict, event: object) -> None:
    if not isinstance(event, dict):
        return

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not EVENT_ID.fullmatch(event_id):
        state["last_result"] = {"message": "이벤트 ID가 올바르지 않습니다."}
        return

    if event_id in state["events"]:
        state["last_result"] = state["events"][event_id]
        return

    snapshot = state["snapshot"]
    kind = event.get("type")
    try:
        if kind == "answer_submit":
            row, change = evaluate(snapshot, state, event)

            # 결과와 미저장 행을 먼저 세션에 보관한다.
            question_id = row["question_id"]
            state["attempts"][question_id] = change["attempt"]
            if change["outcome"]:
                state["outcomes"][question_id] = change["outcome"]
            state["response_rows"].append(row)
            state["pending_responses"][row["response_id"]] = row

            result = change["result"]
            sync_writes(state)
            result["save_status"] = (
                "saved" if row["response_id"] not in state["pending_responses"]
                else "pending"
            )
            if result["save_status"] == "pending":
                result["message"] += " 답안의 시트 저장은 아직 확인되지 않았습니다."

        elif kind == "request_hint":
            result = hint(snapshot, state, event)

        elif kind == "game_complete":
            summary = summarize(snapshot, state)
            if state["phase"] != "playing" or len(
                summary["completed_quests"]
            ) != len(snapshot["quests"]):
                raise ValueError("서버에서 필수 퀘스트 완료를 확인할 수 없습니다.")
            state["phase"] = "ready"
            result = {
                "event_id": event_id,
                "kind": "game_complete",
                "message": "탐험을 마쳤습니다. 성찰을 작성하세요.",
            }

        elif kind == "reflection_submit":
            if state["phase"] != "ready":
                raise ValueError("성찰을 제출할 수 있는 단계가 아닙니다.")
            answers = event.get("answers")
            if (
                not isinstance(answers, list)
                or len(answers) != len(snapshot["reflection_prompts"])
                or any(
                    not isinstance(answer, str)
                    or not 1 <= len(answer.strip()) <= 1500
                    for answer in answers
                )
            ):
                raise ValueError("성찰 문항마다 1~1500자로 답하세요.")

            state["result_row"] = make_result_row(
                snapshot, state, [answer.strip() for answer in answers]
            )
            state["phase"] = "finished"
            sync_writes(state)
            result = {
                "event_id": event_id,
                "kind": "reflection",
                "message": (
                    "결과가 저장되었습니다."
                    if state["result_saved"]
                    else "결과 화면이 열렸지만 시트 저장은 아직 확인되지 않았습니다."
                ),
            }
        else:
            raise ValueError("지원하지 않는 게임 이벤트입니다.")

    except ValueError as exc:
        result = {
            "event_id": event_id,
            "kind": "error",
            "message": str(exc),
        }

    state["events"][event_id] = result
    state["last_result"] = result


def start_game(student: dict) -> None:
    snapshot = load_content()
    st.session_state.game = {
        "session_id": uuid.uuid4().hex,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "student": student,
        "snapshot": snapshot,
        "attempts": {},
        "outcomes": {},
        "events": {},
        "response_rows": [],
        "pending_responses": {},
        "result_row": None,
        "result_saved": False,
        "write_error": "",
        "last_result": None,
        "phase": "playing",
    }


def report_buttons(result: dict, responses: list[dict], suffix: str, notice: str = ""):
    if not result:
        return
    html_data = printable_html(result, responses, notice)
    st.download_button(
        "인쇄용 HTML 보고서",
        html_data,
        file_name=f"kapitan-ri-{suffix}.html",
        mime="text/html",
        key=f"html_{suffix}",
    )
    try:
        pdf_data = pdf_report(result, responses, notice)
    except (FileNotFoundError, ValueError) as exc:
        st.info(f"PDF를 제공할 수 없습니다: {exc} HTML 파일을 브라우저에서 인쇄하세요.")
    else:
        st.download_button(
            "PDF 보고서 다운로드",
            pdf_data,
            file_name=f"kapitan-ri-{suffix}.pdf",
            mime="application/pdf",
            key=f"pdf_{suffix}",
        )


def student_page():
    st.title("꺼삐딴 리: 문학 탐험 기록관")
    state = st.session_state.get("game")

    if state is None:
        st.write(
            "가상의 문학 탐험 공간에서 자료를 조사하고 문항을 풀어 "
            "인물, 시대, 풍자와 주제를 해석합니다. 방향 패드 또는 방향키·WASD로 "
            "이동하고, 사물 가까이에서 조사 버튼을 누르세요. "
            "지도와 사물은 학습용 구성으로, 소설의 실제 장소를 재현한 것이 아닙니다."
        )
        with st.form("student_start"):
            grade = st.text_input("학년", max_chars=2)
            klass = st.text_input("반", max_chars=2)
            number = st.text_input("번호", max_chars=2)
            name = st.text_input("이름", max_chars=30)
            access = (
                st.text_input("학급 접속 코드", type="password")
                if secret("class_access_code") else ""
            )
            submitted = st.form_submit_button("탐험 시작", use_container_width=True)

        if submitted:
            if not (
                grade.isdigit() and 1 <= int(grade) <= 6
                and klass.isdigit() and 1 <= int(klass) <= 99
                and number.isdigit() and 1 <= int(number) <= 99
                and re.fullmatch(r"[가-힣A-Za-z .-]{2,30}", name.strip())
            ):
                st.error("학년·반·번호는 허용 범위의 숫자로, 이름은 2~30자로 입력하세요.")
            elif secret("class_access_code") and not hmac.compare_digest(
                access, secret("class_access_code")
            ):
                st.error("학급 접속 코드가 맞지 않습니다.")
            else:
                try:
                    start_game({
                        "grade": grade,
                        "class": klass,
                        "number": number,
                        "student_name": name.strip(),
                    })
                except ValueError as exc:
                    st.error(f"문항 설정 오류: {exc}")
                except Exception:
                    st.error(
                        "Google Sheets 연결에 실패했습니다. "
                        "Secrets, 시트 공유 권한과 필수 탭을 확인하세요."
                    )
                else:
                    st.rerun()
        return

    if state["phase"] != "finished":
        snapshot = state["snapshot"]
        summary = summarize(snapshot, state)
        try:
            event = game_component(public_content(snapshot, state, summary))
        except RuntimeError as exc:
            st.error(str(exc))
            return
        if isinstance(event, dict) and event.get("event_id") not in state["events"]:
            process_event(state, event)
            st.rerun()
    else:
        st.success("탐험과 성찰을 마쳤습니다.")
        summary = summarize(state["snapshot"], state)
        st.metric("획득 점수", f'{summary["total_score"]} / {summary["total_possible"]}')
        st.write(
            f'객관식 정답 {summary["correct_answers"]} / '
            f'{summary["objective_answers"]}'
        )
        st.write("완료 퀘스트:", ", ".join(summary["completed_quests"]))
        st.write("수집 단서:", ", ".join(summary["clues"]) or "없음")
        st.write(
            "교사 검토가 필요한 문항:",
            summary["pending_review"],
        )
        for question_id in state["snapshot"]["questions"]:
            outcome = state["outcomes"].get(question_id, "미완료")
            st.write(f"- {question_id}: {outcome}")

        st.subheader("성찰")
        for item in __import__("json").loads(state["result_row"]["reflection"]):
            st.write(f'**{item["question"]}**')
            st.write(item["answer"])

        notice = ""
        if state["pending_responses"] or not state["result_saved"]:
            notice = (
                f'시트 저장 미확인: 응답 {len(state["pending_responses"])}건; '
                f'최종 결과 {"저장됨" if state["result_saved"] else "미확인"}'
            )
        report_buttons(
            state["result_row"], state["response_rows"],
            state["session_id"], notice,
        )
        st.caption("PDF를 내려받아 필요한 경우 클래스룸 과제에 직접 첨부하세요.")

    if state["write_error"]:
        st.warning(state["write_error"])
    if state["pending_responses"] or (
        state.get("result_row") and not state["result_saved"]
    ):
        if st.button("미저장 기록 재시도", use_container_width=True):
            sync_writes(state)
            st.rerun()

    st.caption(
        "진행 정보와 미저장 기록은 현재 서버 세션에 보관됩니다. "
        "저장 미확인 상태에서 탭을 닫거나 서버가 재시작되면 복구할 수 없습니다."
    )


def teacher_page():
    st.title("교사용 확인 화면")
    configured = secret("teacher_access_code")
    if not configured or configured == "CHANGE_ME":
        st.error("Secrets의 app.teacher_access_code를 실제 코드로 설정하세요.")
        return

    if not st.session_state.get("teacher_authenticated", False):
        with st.form("teacher_login"):
            entered = st.text_input("교사 접근 코드", type="password")
            submitted = st.form_submit_button("확인")
        if submitted:
            if hmac.compare_digest(entered, configured):
                st.session_state.teacher_authenticated = True
                st.rerun()
            else:
                st.error("접근 코드가 맞지 않습니다.")
        return

    st.caption(
        "교사 접근 코드는 간편한 화면 제한 수단이며 완전한 신원 인증이 아닙니다."
    )
    if st.button("문항 데이터 새로고침"):
        load_content.clear()
        st.success("문항 캐시를 지웠습니다. 진행 중인 학생의 기준은 유지됩니다.")

    try:
        snapshot = load_content()
        st.success(
            f'연결 확인: Questions {len(snapshot["questions"])}건 / '
            f'Quests {len(snapshot["quests"])}건 / '
            f'Objects {len(snapshot["objects"])}건'
        )
    except ValueError as exc:
        st.error(f"데이터 설정 오류: {exc}")
    except Exception:
        st.error("시트 연결을 확인하지 못했습니다. 권한과 Secrets를 점검하세요.")

    if not st.button("학생 결과·응답 조회"):
        return

    try:
        results = worksheet_rows("GameResults")
        responses = worksheet_rows("Responses")
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("학생 기록 조회에 실패했습니다. 시트 권한과 연결을 확인하세요.")
        return

    st.write("교사 검토 필요 응답:", sum(
        row["grading_status"] == "pending_review" for row in responses
    ))
    st.dataframe([
        {
            "session_id": row["session_id"],
            "학년": row["grade"],
            "반": row["class"],
            "번호": row["number"],
            "이름": row["student_name"],
            "점수": row["total_score"],
            "전체 배점": row["total_possible"],
            "완료 상태": row["completion_status"],
        }
        for row in results
    ], use_container_width=True)

    objective_groups = {}
    for row in responses:
        if row["question_type"] not in ("single_choice", "multiple_choice"):
            continue
        key = (row["session_id"], row["question_id"])
        objective_groups[key] = (
            objective_groups.get(key, False) or row["is_correct"] == "TRUE"
        )
    by_question = {}
    for (_, question_id), correct in objective_groups.items():
        total, hits = by_question.get(question_id, (0, 0))
        by_question[question_id] = (total + 1, hits + int(correct))
    st.subheader("문항별 정답률")
    st.dataframe([
        {
            "문항 ID": identifier,
            "응시 세션": total,
            "정답 세션": hits,
            "정답률(%)": round(100 * hits / total, 1),
        }
        for identifier, (total, hits) in sorted(by_question.items())
    ], use_container_width=True)

    if results:
        selected = st.selectbox(
            "개인 보고서 조회",
            results,
            format_func=lambda row: (
                f'{row["grade"]}학년 {row["class"]}반 '
                f'{row["number"]}번 {row["student_name"]} · '
                f'{row["session_id"][:8]}'
            ),
        )
        individual = [
            row for row in responses
            if row["session_id"] == selected["session_id"]
        ]
        report_buttons(selected, individual, f'teacher-{selected["session_id"]}')


page = st.radio("화면", ("학생용", "교사용"), horizontal=True)
if page == "학생용":
    student_page()
else:
    teacher_page()
