export type Direction = "up" | "down" | "left" | "right";
export type Directions = Record<Direction, boolean>;

export interface Question {
  question_id: string;
  quest_id: string;
  object_id: string;
  question_order: number;
  question_type: "single_choice" | "multiple_choice" | "short_answer";
  question_text: string;
  options: Record<string, string>;
  points: number;
  max_attempts: number;
}

export interface Quest {
  quest_id: string;
  quest_order: number;
  title: string;
  description: string;
  map_id: string;
  prerequisite_quest_id: string;
  state: "locked" | "available" | "done";
}

export interface GameObject {
  object_id: string;
  object_name: string;
  object_type: string;
  map_id: string;
  x: number;
  y: number;
  interaction_text: string;
  quest_id: string;
  appearance_note: string;
}

export interface Result {
  event_id?: string;
  kind?: string;
  question_id?: string;
  message: string;
  hint?: string;
  completed?: boolean;
  is_correct?: boolean | null;
  explanation?: string;
  earned_points?: number;
  save_status?: string;
}

export interface GameData {
  session_id: string;
  phase: "playing" | "ready" | "finished";
  questions: Question[];
  quests: Quest[];
  objects: GameObject[];
  reflection_prompts: string[];
  progress: {
    attempts: Record<string, number>;
    outcomes: Record<string, string>;
    score: number;
    correct: number;
    clues: string[];
    pending_writes: number;
  };
  last_result: Result | null;
}
