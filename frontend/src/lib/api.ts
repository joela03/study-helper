import {
  Profile,
  Transcript,
  Card,
  GeneratedCard,
  SearchResult,
  Concept,
  ConceptJob,
  CourseMaterial,
  MaterialKind,
} from "@/types";

import { clearToken, getToken } from "@/lib/auth-store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Bearer header when signed in; omitted otherwise so login still works. */
function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * A 401 means the token is gone or expired. Clear it and announce it, rather
 * than navigating from here — this module isn't a component, so it has no
 * router, and a hard location change would throw away React state.
 * AuthProvider listens for this and signs out through the router.
 */
export const AUTH_EXPIRED_EVENT = "study-helper:auth-expired";

function handleUnauthorised(status: number): void {
  if (status !== 401) return;
  clearToken();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
}

async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    handleUnauthorised(res.status);
    const error = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }

  return res.json();
}

// Profiles
export async function getProfiles(): Promise<{ profiles: Profile[]; total: number }> {
  return fetchAPI("/api/profiles/");
}

export async function getProfile(id: number): Promise<Profile> {
  return fetchAPI(`/api/profiles/${id}`);
}

export async function createProfile(data: {
  name: string;
  module_code?: string;
  module_spec?: string;
}): Promise<Profile> {
  return fetchAPI("/api/profiles/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteProfile(id: number): Promise<void> {
  await fetch(`${API_BASE}/api/profiles/${id}`, { method: "DELETE", headers: authHeaders() });
}

// Transcripts
export async function getTranscripts(
  profileId?: number
): Promise<{ transcripts: Transcript[]; total: number }> {
  const params = profileId ? `?profile_id=${profileId}` : "";
  return fetchAPI(`/api/transcripts/${params}`);
}

export async function getTranscript(id: number): Promise<Transcript> {
  return fetchAPI(`/api/transcripts/${id}`);
}

export interface TranscriptUpload {
  profileId: number;
  title: string;
  document?: File;
  audio?: File;
  /** An already-made transcript, e.g. pasted from Panopto. Skips Whisper. */
  transcriptText?: string;
  /** A .txt/.md/.docx export of the same. Also skips Whisper. */
  transcriptFile?: File;
}

export async function uploadTranscript({
  profileId,
  title,
  document,
  audio,
  transcriptText,
  transcriptFile,
}: TranscriptUpload): Promise<Transcript> {
  const formData = new FormData();
  formData.append("profile_id", profileId.toString());
  formData.append("title", title);
  if (document) formData.append("document", document);
  if (audio) formData.append("audio", audio);
  if (transcriptText) formData.append("transcript_text", transcriptText);
  if (transcriptFile) formData.append("transcript_file", transcriptFile);

  const res = await fetch(`${API_BASE}/api/transcripts/`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (!res.ok) {
    handleUnauthorised(res.status);
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return res.json();
}

// Cards
export async function getCards(
  profileId?: number
): Promise<{ cards: Card[]; total: number }> {
  const params = profileId ? `?profile_id=${profileId}` : "";
  return fetchAPI(`/api/cards/${params}`);
}

export async function getDueCards(
  profileId?: number
): Promise<{ cards: Card[]; total_due: number }> {
  const params = profileId ? `?profile_id=${profileId}` : "";
  return fetchAPI(`/api/cards/due${params}`);
}

export interface ReviewResponse {
  card: Card;
  failed: boolean;
  requeued: boolean;
}

export async function reviewCard(
  cardId: number,
  quality: number
): Promise<ReviewResponse> {
  return fetchAPI(`/api/cards/${cardId}/review`, {
    method: "POST",
    body: JSON.stringify({ quality }),
  });
}

// Generation
export async function generateFromText(data: {
  profile_id: number;
  content: string;
  num_cards?: number;
  save?: boolean;
}): Promise<{ cards: GeneratedCard[]; source: string; provider: string }> {
  return fetchAPI("/api/generate/from-text", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function generateFromTranscript(data: {
  transcript_id: number;
  num_cards?: number;
  save?: boolean;
}): Promise<{ cards: GeneratedCard[]; source: string; provider: string }> {
  return fetchAPI("/api/generate/from-transcript", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function generateFromSearch(data: {
  profile_id: number;
  query: string;
  num_cards?: number;
  num_chunks?: number;
  save?: boolean;
}): Promise<{ cards: GeneratedCard[]; source: string; provider: string }> {
  return fetchAPI("/api/generate/from-search", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Search
export async function search(
  query: string,
  profileId?: number
): Promise<{ query: string; results: SearchResult[]; total: number }> {
  const params = new URLSearchParams({ q: query });
  if (profileId) params.append("profile_id", profileId.toString());
  return fetchAPI(`/api/search/?${params}`);
}

// Concepts
export async function getConcepts(
  params: { transcriptId?: number; profileId?: number } = {}
): Promise<{ concepts: Concept[]; total: number }> {
  const query = new URLSearchParams();
  if (params.transcriptId) query.set("transcript_id", String(params.transcriptId));
  if (params.profileId) query.set("profile_id", String(params.profileId));
  return fetchAPI(`/api/concepts/?${query}`);
}

/** Queues the work and returns straight away; poll getConceptJob. */
export async function generateConcepts(
  transcriptId: number
): Promise<{ task_id: string; transcript_id: number; passes: number }> {
  return fetchAPI("/api/concepts/from-transcript", {
    method: "POST",
    body: JSON.stringify({ transcript_id: transcriptId }),
  });
}

export async function getConceptJob(taskId: string): Promise<ConceptJob> {
  return fetchAPI(`/api/concepts/jobs/${taskId}`);
}

// Course materials
export async function getMaterials(
  profileId: number
): Promise<{ materials: CourseMaterial[]; total: number }> {
  return fetchAPI(`/api/materials/?profile_id=${profileId}`);
}

export async function createMaterial(data: {
  profileId: number;
  title: string;
  kind: MaterialKind;
  content?: string;
  file?: File;
}): Promise<CourseMaterial> {
  const formData = new FormData();
  formData.append("profile_id", String(data.profileId));
  formData.append("title", data.title);
  formData.append("kind", data.kind);
  if (data.content) formData.append("content", data.content);
  if (data.file) formData.append("file", data.file);

  const res = await fetch(`${API_BASE}/api/materials/`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (!res.ok) {
    handleUnauthorised(res.status);
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return res.json();
}

/** Partial edit — retitle, reclassify, or correct the text. */
export async function updateMaterial(
  id: number,
  changes: { title?: string; kind?: MaterialKind; content?: string }
): Promise<CourseMaterial> {
  return fetchAPI(`/api/materials/${id}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export async function deleteMaterial(id: number): Promise<void> {
  await fetch(`${API_BASE}/api/materials/${id}`, { method: "DELETE", headers: authHeaders() });
}

// Auth
export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
  created_at: string;
}

export async function login(
  email: string,
  password: string
): Promise<{ access_token: string; user: AuthUser }> {
  return fetchAPI("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(data: {
  email: string;
  display_name: string;
  password: string;
  invite_code?: string;
}): Promise<{ access_token: string; user: AuthUser }> {
  return fetchAPI("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getMe(): Promise<AuthUser> {
  return fetchAPI("/api/auth/me");
}
