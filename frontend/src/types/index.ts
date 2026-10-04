export interface Profile {
  id: number;
  name: string;
  module_code: string | null;
  module_spec: string | null;
  created_at: string;
  updated_at: string;
  transcript_count: number;
  card_count: number;
  due_card_count: number;
}

export interface Transcript {
  id: number;
  profile_id: number;
  title: string;
  status: "pending" | "processing" | "completed" | "failed";
  document_path: string | null;
  audio_path: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  chunk_count: number;
}

export interface Card {
  id: number;
  profile_id: number;
  transcript_id: number | null;
  concept_id: number | null;
  card_type: "flashcard" | "practice_question";
  question: string;
  answer: string;
  ease_factor: number;
  interval: number;
  repetitions: number;
  next_review: string;
  created_at: string;
  updated_at: string;
}

export interface GeneratedCard {
  question: string;
  answer: string;
  saved: boolean;
  card_id: number | null;
}

export interface SearchResult {
  chunk_id: number;
  transcript_id: number;
  content: string;
  similarity: number;
}

/** A question attached to a concept. A explains an idea, B is a scenario. */
export interface ConceptQuestion {
  text: string;
  type: "A" | "B";
  answer: string;
}

/** One lecture idea, condensed: what it is, why, how, and where it breaks. */
export interface Concept {
  id: number;
  profile_id: number;
  transcript_id: number;
  order_index: number;
  title: string;
  headline: string | null;
  definition: string | null;
  intuition: string | null;
  mechanism: string | null;
  limitation: string | null;
  relevance: string | null;
  questions: ConceptQuestion[];
  followups: string[];
  card_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConceptJob {
  task_id: string;
  state: "PENDING" | "PROGRESS" | "SUCCESS" | "FAILURE";
  stage: string | null;
  current: number;
  total: number;
  concepts: number;
  cards_created: number | null;
  covered_chunks: number;
  total_chunks: number;
  error: string | null;
}

export type MaterialKind =
  | "outline"
  | "past_paper"
  | "problem_sheet"
  | "notes"
  | "other";

/** Standing context for a subject: outline, past papers, problem sheets. */
export interface CourseMaterial {
  id: number;
  profile_id: number;
  kind: MaterialKind;
  title: string;
  file_path: string | null;
  content: string | null;
  content_chars: number;
  created_at: string;
  updated_at: string;
}
