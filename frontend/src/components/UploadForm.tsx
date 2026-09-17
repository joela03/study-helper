"use client";

import { useState } from "react";
import { uploadTranscript } from "@/lib/api";
import { Transcript } from "@/types";

interface Props {
  profileId: number;
  onUploaded: (transcript: Transcript) => void;
}

export default function UploadForm({ profileId, onUploaded }: Props) {
  const [title, setTitle] = useState("");
  const [document, setDocument] = useState<File | null>(null);
  const [audio, setAudio] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    if (!document && !audio) {
      setError("At least one file (document or audio) is required");
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const transcript = await uploadTranscript(
        profileId,
        title,
        document || undefined,
        audio || undefined
      );
      onUploaded(transcript);
      setTitle("");
      setDocument(null);
      setAudio(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-gray-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-white mb-4">
        Upload New Transcript
      </h3>

      {error && (
        <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Lecture 1 - Introduction"
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Document (PDF, PPTX, TXT)
          </label>
          <input
            type="file"
            accept=".pdf,.pptx,.ppt,.txt"
            onChange={(e) => setDocument(e.target.files?.[0] || null)}
            className="w-full text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-gray-700 file:text-white hover:file:bg-gray-600"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Audio (MP3, WAV, M4A)
          </label>
          <input
            type="file"
            accept=".mp3,.wav,.m4a,.ogg,.flac"
            onChange={(e) => setAudio(e.target.files?.[0] || null)}
            className="w-full text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-gray-700 file:text-white hover:file:bg-gray-600"
          />
        </div>

        <button
          type="submit"
          disabled={isUploading}
          className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg font-medium"
        >
          {isUploading ? "Uploading..." : "Upload"}
        </button>
      </div>
    </form>
  );
}
