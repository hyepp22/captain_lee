from __future__ import annotations

import html
import io
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
)

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "NotoSansKR-Regular.ttf"


def _json_list(value: object) -> list:
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


def _lines(result: dict, responses: list[dict], save_notice: str) -> list[str]:
    lines = [
        "꺼삐딴 리: 문학 탐험 기록관",
        f'학생: {result["grade"]}학년 {result["class"]}반 '
        f'{result["number"]}번 {result["student_name"]}',
        f'시작: {result["started_at"]} / 종료: {result["ended_at"]}',
        f'점수: {result["total_score"]} / {result["total_possible"]}',
        f'객관식 정답: {result["correct_answers"]} / {result["objective_answers"]}',
        f'완료 퀘스트: {", ".join(_json_list(result["completed_quests"])) or "없음"}',
        f'수집 단서: {", ".join(_json_list(result["collected_clues"])) or "없음"}',
        f'완료 상태: {result["completion_status"]}',
    ]
    if save_notice:
        lines.append(save_notice)

    lines.append("문항별 제출 기록")
    for row in responses:
        verdict = (
            "정답" if row["is_correct"] == "TRUE"
            else "교사 검토 필요" if row["grading_status"] == "pending_review"
            else "오답"
        )
        lines.append(
            f'{row["question_id"]} · {row["attempt_no"]}회차 · '
            f'답안: {row["answer"]} · {verdict} · '
            f'획득 점수: {row["earned_points"]}'
        )

    lines.append("학생 성찰")
    for reflection in _json_list(result["reflection"]):
        if isinstance(reflection, dict):
            lines.append(str(reflection.get("question", "")))
            lines.append(str(reflection.get("answer", "")))
    return lines


def printable_html(result: dict, responses: list[dict], save_notice: str = "") -> bytes:
    content = "\n".join(
        f"<p>{html.escape(line)}</p>"
        for line in _lines(result, responses, save_notice)
    )
    page = (
        '<!doctype html><html lang="ko"><meta charset="utf-8">'
        "<title>문학 탐험 보고서</title>"
        '<style>body{max-width:820px;margin:32px auto;padding:16px;'
        'font:16px/1.65 sans-serif}p{overflow-wrap:anywhere}'
        '@media print{body{margin:8mm}}</style>'
        f"<body>{content}</body></html>"
    )
    return page.encode("utf-8")


def pdf_report(result: dict, responses: list[dict], save_notice: str = "") -> bytes:
    if not FONT_PATH.is_file():
        raise FileNotFoundError(
            "assets/NotoSansKR-Regular.ttf가 없습니다. 인쇄용 HTML을 이용하세요."
        )

    pdfmetrics.registerFont(TTFont("ReportKorean", str(FONT_PATH)))
    style = ParagraphStyle(
        "ReportKoreanStyle",
        fontName="ReportKorean",
        fontSize=10,
        leading=17,
        textColor=colors.HexColor("#20332f"),
        wordWrap="CJK",
    )
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=38, rightMargin=38,
        topMargin=38, bottomMargin=38,
    )
    story = []
    for line in _lines(result, responses, save_notice):
        story.append(Paragraph(html.escape(line), style))
        story.append(Spacer(1, 8))
    document.build(story)
    return buffer.getvalue()
