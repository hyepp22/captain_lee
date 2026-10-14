import React from "react";
import { createRoot } from "react-dom/client";
import { Streamlit, type RenderData } from "streamlit-component-lib";

import Game from "./Game";
import type { GameData } from "./types";
import "./styles.css";

const element = document.getElementById("root");
if (!element) throw new Error("컴포넌트 루트가 없습니다.");
const root = createRoot(element);

function onRender(event: Event): void {
  const detail = (event as CustomEvent<RenderData>).detail;
  root.render(
    <React.StrictMode>
      <Game data={detail.args.data as GameData} />
    </React.StrictMode>
  );
  Streamlit.setFrameHeight();
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, (event) => onRender(event as unknown as Event));
Streamlit.setComponentReady();
