import type { Directions, GameObject, Quest } from "./types";

export const WIDTH = 960;
export const HEIGHT = 600;

export interface Position {
  x: number;
  y: number;
}

interface Wall {
  x: number;
  y: number;
  w: number;
  h: number;
}

const WALLS: Wall[] = [
  { x: 284, y: 95, w: 24, h: 96 },
  { x: 672, y: 88, w: 24, h: 104 },
  { x: 290, y: 412, w: 24, h: 95 },
  { x: 674, y: 393, w: 24, h: 100 }
];

const RADIUS = 13;

function overlapsWall(position: Position, wall: Wall): boolean {
  const nearX = Math.max(wall.x, Math.min(position.x, wall.x + wall.w));
  const nearY = Math.max(wall.y, Math.min(position.y, wall.y + wall.h));
  return (position.x - nearX) ** 2 + (position.y - nearY) ** 2 < RADIUS ** 2;
}

function free(position: Position, objects: GameObject[]): boolean {
  if (
    position.x < 28 + RADIUS ||
    position.x > WIDTH - 28 - RADIUS ||
    position.y < 28 + RADIUS ||
    position.y > HEIGHT - 28 - RADIUS
  ) {
    return false;
  }
  if (WALLS.some((wall) => overlapsWall(position, wall))) return false;
  return !objects.some(
    (object) =>
      (position.x - object.x) ** 2 + (position.y - object.y) ** 2 <
      (RADIUS + 18) ** 2
  );
}

export function move(
  position: Position,
  directions: Directions,
  seconds: number,
  objects: GameObject[]
): Position {
  let dx = Number(directions.right) - Number(directions.left);
  let dy = Number(directions.down) - Number(directions.up);
  if (dx === 0 && dy === 0) return position;

  const scale = Math.hypot(dx, dy);
  dx = (dx / scale) * Math.min(seconds, 0.05) * 215;
  dy = (dy / scale) * Math.min(seconds, 0.05) * 215;

  const next = { ...position };
  if (free({ x: next.x + dx, y: next.y }, objects)) next.x += dx;
  if (free({ x: next.x, y: next.y + dy }, objects)) next.y += dy;
  return next;
}

export function nearest(
  position: Position,
  objects: GameObject[]
): GameObject | null {
  let found: GameObject | null = null;
  let distance = 84;
  for (const object of objects) {
    const current = Math.hypot(position.x - object.x, position.y - object.y);
    if (current < distance) {
      distance = current;
      found = object;
    }
  }
  return found;
}

export function draw(
  canvas: HTMLCanvasElement,
  position: Position,
  objects: GameObject[],
  quests: Quest[],
  outcomes: Record<string, string>,
  questionsByObject: Record<string, string[]>,
  nearbyId: string | null
): void {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const physicalWidth = Math.round(WIDTH * ratio);
  const physicalHeight = Math.round(HEIGHT * ratio);
  if (canvas.width !== physicalWidth || canvas.height !== physicalHeight) {
    canvas.width = physicalWidth;
    canvas.height = physicalHeight;
  }

  const context = canvas.getContext("2d");
  if (!context) return;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, WIDTH, HEIGHT);

  const colors = ["#d9e9dc", "#dce8f0", "#f1e6cc", "#e8dff0"];
  const zones = [
    [28, 28, 452, 272],
    [480, 28, 452, 272],
    [28, 300, 452, 272],
    [480, 300, 452, 272]
  ];

  zones.forEach(([x, y, w, h], index) => {
    context.fillStyle = colors[index];
    context.fillRect(x, y, w, h);
  });

  context.fillStyle = "#efe8d6";
  context.fillRect(446, 28, 68, 544);
  context.fillRect(28, 271, 904, 58);

  quests.slice(0, 4).forEach((quest, index) => {
    const [x, y] = zones[index];
    context.fillStyle = quest.state === "locked" ? "#6e7480" : "#345c56";
    context.font = "bold 20px sans-serif";
    context.fillText(
      `${quest.title}${quest.state === "locked" ? " · 잠김" : quest.state === "done" ? " · 완료" : ""}`,
      x + 28,
      y + 38,
      385
    );
  });

  context.fillStyle = "#526775";
  WALLS.forEach(({ x, y, w, h }) => context.fillRect(x, y, w, h));

  for (const object of objects) {
    const solved = (questionsByObject[object.object_id] || []).every(
      (id) => Boolean(outcomes[id])
    );
    const locked = quests.find(
      (quest) => quest.quest_id === object.quest_id
    )?.state === "locked";

    context.beginPath();
    context.arc(object.x, object.y, 18, 0, Math.PI * 2);
    context.fillStyle = solved ? "#6a9c73" : locked ? "#839095" : "#db9a3e";
    context.fill();
    context.lineWidth = object.object_id === nearbyId ? 5 : 2;
    context.strokeStyle = object.object_id === nearbyId ? "#fff" : "#31433d";
    context.stroke();

    context.fillStyle = "#243932";
    context.font = "bold 16px sans-serif";
    context.textAlign = "center";
    context.fillText(
      `${solved ? "✓ " : ""}${object.object_name}`,
      object.x,
      object.y - 27,
      210
    );
  }

  context.beginPath();
  context.arc(position.x, position.y, RADIUS, 0, Math.PI * 2);
  context.fillStyle = "#315dbe";
  context.fill();
  context.lineWidth = 3;
  context.strokeStyle = "#fff";
  context.stroke();
  context.textAlign = "start";
}
