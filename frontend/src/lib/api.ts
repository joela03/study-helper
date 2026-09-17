import { Profile, Transcript, Card, GeneratedCard, SearchResult } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
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
  await fetch(`${API_BASE}/api/profiles/${id}`, { method: "DELETE" });
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

export async function uploadTranscript(
  profileId: number,
  title: string,
  document?: File,
  audio?: File
): Promise<Transcript> {
  const formData = new FormData();
  formData.append("profile_id", profileId.toString());
  formData.append("title", title);
  if (document) formData.append("document", document);
  if (audio) formData.append("audio", audio);

  const res = await fetch(`${API_BASE}/api/transcripts/`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
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

export async function reviewCard(
  cardId: number,
  quality: number
): Promise<Card> {
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
