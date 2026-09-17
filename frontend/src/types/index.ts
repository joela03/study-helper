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
