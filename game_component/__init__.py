from pathlib import Path

import streamlit.components.v1 as components

_BUILD = Path(__file__).resolve().parent / "frontend" / "build"
_component = None


def game_component(data: dict):
    global _component
    if not (_BUILD / "index.html").is_file():
        raise RuntimeError(
            "게임 컴포넌트가 빌드되지 않았습니다. "
            "game_component/frontend에서 npm install && npm run build를 실행하세요."
        )
    if _component is None:
        _component = components.declare_component(
            "kapitan_ri_canvas", path=str(_BUILD)
        )
    return _component(data=data, key="student_canvas", default=None)
