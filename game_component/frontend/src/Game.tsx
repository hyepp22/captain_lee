import { useEffect, useMemo, useRef, useState } from "react";
import { Streamlit } from "streamlit-component-lib";

import { draw, move, nearest, WIDTH, HEIGHT, type Position } from "./gameEngine";
import { useKeyboard } from "./controls";
import type {
  Direction, Directions, GameData, GameObject, Question, Result
} from "./types";

function savedPosition(sessionId: string): Position {
  try {
    const value = JSON.parse(
      sessionStorage.getItem(`kapitan-position-${sessionId}`) || "null"
    ) as Position | null;
    if (
      value &&
      Number.isFinite(value.x) &&
      Number.isFinite(value.y) &&
      value.x >= 42 && value.x <= WIDTH - 42 &&
      value.y >= 42 && value.y <= HEIGHT - 42
    ) return value;
  } catch {
    // 저장된 좌표가 유효하지 않으면 시작 좌표를 사용한다.
  }
  return { x: 58, y: 64 };
}

export default function Game({ data }: { data: GameData }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const position = useRef<Position>(savedPosition(data.session_id));
  const directions = useRef<Directions>({
    up: false, down: false, left: false, right: false
  });
  const previousResult = useRef<string | undefined>(undefined);

  const [nearbyId, setNearbyId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | string[]>("");
  const [feedback, setFeedback] = useState<Result | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [reflection, setReflection] = useState<string[]>(["", "", ""]);
  const [notice, setNotice] = useState("");

  const questionsByObject = useMemo(() => {
    const grouped: Record<string, Question[]> = {};
    for (const question of data.questions) {
      (grouped[question.object_id] ||= []).push(question);
    }
    for (const group of Object.values(grouped)) {
      group.sort((a, b) => a.question_order - b.question_order);
    }
    return grouped;
  }, [data.questions]);

  const questionIdsByObject = useMemo(
    () => Object.fromEntries(
      Object.entries(questionsByObject).map(
        ([key, value]) => [key, value.map((question) => question.question_id)]
      )
    ),
    [questionsByObject]
  );

  const question = data.questions.find((item) => item.question_id === selectedId);
  const canMove = data.phase === "playing" && !question && !waiting;
  useKeyboard(directions, canMove);

  useEffect(() => {
    if (!data.last_result?.event_id) return;
    if (data.last_result.event_id === previousResult.current) return;
    previousResult.current = data.last_result.event_id;
    setWaiting(false);
    setFeedback(data.last_result);
  }, [data.last_result]);

  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(() => Streamlit.setFrameHeight());
    observer.observe(container.current);
    Streamlit.setFrameHeight();
    return () => observer.disconnect();
  }, [question, data.phase]);

  useEffect(() => {
    let frame = 0;
    let last = performance.now();
    let lastStored = 0;

    const tick = (now: number) => {
      const seconds = (now - last) / 1000;
      last = now;

      if (canMove) {
        position.current = move(
          position.current, directions.current, seconds, data.objects
        );
      }
      const close = nearest(position.current, data.objects);
      setNearbyId((previous) =>
        previous === (close?.object_id || null)
          ? previous
          : (close?.object_id || null)
      );
      if (canvas.current) {
        draw(
          canvas.current, position.current, data.objects, data.quests,
          data.progress.outcomes, questionIdsByObject, close?.object_id || null
        );
      }

      if (now - lastStored > 900) {
        sessionStorage.setItem(
          `kapitan-position-${data.session_id}`,
          JSON.stringify(position.current)
        );
        lastStored = now;
      }
      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [
    canMove, data.objects, data.quests, data.progress.outcomes,
    data.session_id, questionIdsByObject
  ]);

  const send = (type: string, fields: Record<string, unknown>) => {
    setWaiting(true);
    setNotice("");
    Streamlit.setComponentValue({
      type, ...fields, event_id: crypto.randomUUID()
    });
  };

  const openObject = (object: GameObject) => {
    if (Math.hypot(
      object.x - position.current.x, object.y - position.current.y
    ) > 84) {
      setNotice("사물에 조금 더 가까이 다가가세요.");
      return;
    }
    const quest = data.quests.find(
      (item) => item.quest_id === object.quest_id
    );
    if (quest?.state === "locked") {
      setNotice("선행 퀘스트를 완료하면 조사할 수 있습니다.");
      return;
    }
    const next = (questionsByObject[object.object_id] || []).find(
      (item) => !data.progress.outcomes[item.question_id]
    );
    if (!next) {
      setNotice("이 사물의 문항은 모두 완료했습니다.");
      return;
    }
    setSelectedId(next.question_id);
    setFeedback(null);
    setAnswer(next.question_type === "multiple_choice" ? [] : "");
    setNotice(object.interaction_text);
  };

  const touchDirection = (direction: Direction) => ({
    onPointerDown: (event: React.PointerEvent<HTMLButtonElement>) => {
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      directions.current[direction] = true;
    },
    onPointerUp: (event: React.PointerEvent<HTMLButtonElement>) => {
      event.preventDefault();
      directions.current[direction] = false;
    },
    onPointerCancel: () => { directions.current[direction] = false; },
    onLostPointerCapture: () => { directions.current[direction] = false; }
  });

  const submit = () => {
    if (!question || waiting) return;
    const attempt = (data.progress.attempts[question.question_id] || 0) + 1;
    send("answer_submit", {
      question_id: question.question_id,
      attempt_no: attempt,
      answer
    });
  };

  const closeQuestion = () => {
    setSelectedId(null);
    setFeedback(null);
    setNotice("");
    for (const direction of Object.keys(directions.current) as Direction[]) {
      directions.current[direction] = false;
    }
  };

  const allDone = data.quests.every((quest) => quest.state === "done");
  const currentQuest = data.quests.find(
    (quest) => quest.state === "available"
  );
  const nearbyObject = data.objects.find(
    (object) => object.object_id === nearbyId
  );

  return (
    <div className="game" ref={container}>
      <header className="status">
        <strong>문학 탐험 기록관</strong>
        <span>점수 {data.progress.score} · 객관식 정답 {data.progress.correct}</span>
        <span>현재 퀘스트: {currentQuest?.title || "모든 퀘스트 완료"}</span>
      </header>

      {data.progress.pending_writes > 0 &&
        <p className="warning">시트 저장 미확인 기록이 있습니다. 아래의 재시도 버튼을 확인하세요.</p>
      }

      {data.phase === "playing" && <>
        <div className="map-wrap">
          <canvas
            ref={canvas}
            width={WIDTH}
            height={HEIGHT}
            aria-label="문학 탐험 지도"
            {(event) => {
              const bounds = event.currentTarget.getBoundingClientRect();
              const x = (event.clientX - bounds.left) * WIDTH / bounds.width;
              const y = (event.clientY - bounds.top) * HEIGHT / bounds.height;
              const object = data.objects.find(
                (item) => Math.hypot(item.x - x, item.y - y) < 30
              );
              if (object) openObject(object);
            }}
          />
        </div>

        <div className="controls">
          <div className="pad" aria-label="방향 패드">
            <button className="up" {...touchDirection("up")}>▲</button>
            <button className="left" {...touchDirection("left")}>◀</button>
            <button className="down" {...touchDirection("down")}>▼</button>
            <button className="right" {...touchDirection("right")}>▶</button>
          </div>
          <div className="actions">
            <strong>{nearbyObject
              ? `${nearbyObject.object_name} · 조사 가능`
              : "사물 가까이 이동하세요"}</strong>
            <button
              disabled={!nearbyObject || Boolean(question) || waiting}
              {() => nearbyObject && openObject(nearbyObject)}
            >
              조사하기
            </button>
          </div>
        </div>

        {notice && <p role="status" className="notice">{notice}</p>}
        <p>단서: {data.progress.clues.join(" · ") || "아직 없음"}</p>
        <p>
          진행: {data.quests.map((quest) =>
            `${quest.title}(${quest.state === "done" ? "완료" :
              quest.state === "locked" ? "잠김" : "진행 중"})`
          ).join(" · ")}
        </p>

        {allDone && !question &&
          <button
            className="finish"
            disabled={waiting}
            {() => send("game_complete", {})}
          >
            탐험 마치고 성찰하기
          </button>
        }
      </>}

      {data.phase === "ready" &&
        <section className="reflection">
          <h2>탐험 성찰</h2>
          {data.reflection_prompts.map((prompt, index) =>
            <label key={index}>
              <strong>{prompt}</strong>
              <textarea
                value={reflection[index]}
                maxLength={1500}
                {(event) => setReflection((previous) => {
                  const next = [...previous];
                  next[index] = event.target.value;
                  return next;
                })}
              />
            </label>
          )}
          <button
            disabled={waiting || reflection.some(
              (value) => !value.trim()
            )}
            {() => send("reflection_submit", { answers: reflection })}
          >
            성찰 저장하고 결과 보기
          </button>
        </section>
      }

      {question && data.phase === "playing" &&
        <div className="modal-backdrop">
          <section className="question-modal" role="dialog" aria-modal="true">
            <h2>자료 조사: {question.question_id}</h2>
            <p>{question.question_text}</p>
            <p>
              배점 {question.points}점 · 시도 {
                data.progress.attempts[question.question_id] || 0
              } / {question.max_attempts}
            </p>

            {!data.progress.outcomes[question.question_id] &&
              <>
                {question.question_type === "short_answer"
                  ? <textarea
                      aria-label="답안"
                      maxLength={1200}
                      value={typeof answer === "string" ? answer : ""}
                      {(event) => setAnswer(event.target.value)}
                    />
                  : Object.entries(question.options).map(([letter, text]) =>
                      <label className="option" key={letter}>
                        <input
                          type={question.question_type === "multiple_choice"
                            ? "checkbox" : "radio"}
                          name={`answer-${question.question_id}`}
                          checked={Array.isArray(answer)
                            ? answer.includes(letter)
                            : answer === letter}
                          {() => {
                            if (question.question_type === "multiple_choice") {
                              const previous = Array.isArray(answer) ? answer : [];
                              setAnswer(previous.includes(letter)
                                ? previous.filter((item) => item !== letter)
                                : [...previous, letter]);
                            } else {
                              setAnswer(letter);
                            }
                          }}
                        />
                        {letter}. {text}
                      </label>
                    )
                }
                <div className="modal-actions">
                  <button
                    disabled={waiting}
                    {() => send("request_hint", {
                      question_id: question.question_id
                    })}
                  >
                    힌트
                  </button>
                  <button
                    disabled={
                      waiting ||
                      (Array.isArray(answer) ? answer.length === 0 : !answer.trim())
                    }
                    {submit}
                  >
                    답안 제출
                  </button>
                </div>
              </>
            }

            {feedback && (!feedback.question_id ||
              feedback.question_id === question.question_id) &&
              <div className="feedback" role="status">
                <strong>{feedback.message}</strong>
                {feedback.hint && <p>힌트: {feedback.hint}</p>}
                {feedback.explanation && <p>해설: {feedback.explanation}</p>}
                {feedback.save_status === "pending" &&
                  <p className="warning">시트 저장을 확인하지 못했습니다.</p>}
              </div>
            }
            <button {closeQuestion}>지도로 돌아가기</button>
          </section>
        </div>
      }
    </div>
  );
}
