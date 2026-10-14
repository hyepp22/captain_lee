import { useEffect } from "react";
import type { MutableRefObject } from "react";
import type { Direction, Directions } from "./types";

const keys: Record<string, Direction> = {
  arrowup: "up",
  w: "up",
  arrowdown: "down",
  s: "down",
  arrowleft: "left",
  a: "left",
  arrowright: "right",
  d: "right"
};

export function useKeyboard(
  directions: MutableRefObject<Directions>,
  enabled: boolean
): void {
  useEffect(() => {
    const onKey = (event: KeyboardEvent, pressed: boolean) => {
      if (!enabled) return;
      const target = event.target as HTMLElement | null;
      if (
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "BUTTON"
      ) return;

      const direction = keys[event.key.toLowerCase()];
      if (direction) {
        event.preventDefault();
        directions.current[direction] = pressed;
      }
    };

    const down = (event: KeyboardEvent) => onKey(event, true);
    const up = (event: KeyboardEvent) => onKey(event, false);
    const reset = () => {
      for (const direction of Object.keys(directions.current) as Direction[]) {
        directions.current[direction] = false;
      }
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", reset);
    return () => {
      reset();
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", reset);
    };
  }, [directions, enabled]);
}
