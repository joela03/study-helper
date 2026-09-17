"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Profile, Card } from "@/types";
import { getProfiles, getDueCards } from "@/lib/api";
import ProfileCard from "@/components/ProfileCard";

export default function Dashboard() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [dueCards, setDueCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [profilesRes, dueRes] = await Promise.all([
          getProfiles(),
          getDueCards(),
        ]);
        setProfiles(profilesRes.profiles);
        setDueCards(dueRes.cards);
      } catch (error) {
        console.error("Failed to fetch data:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const totalDue = profiles.reduce((sum, p) => sum + p.due_card_count, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-gray-400 text-sm font-medium">Total Profiles</h3>
          <p className="text-3xl font-bold mt-2">{profiles.length}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-gray-400 text-sm font-medium">Cards Due Today</h3>
          <p className="text-3xl font-bold mt-2 text-blue-400">{totalDue}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-gray-400 text-sm font-medium">Total Cards</h3>
          <p className="text-3xl font-bold mt-2">
            {profiles.reduce((sum, p) => sum + p.card_count, 0)}
          </p>
        </div>
      </div>

      {/* Quick actions */}
      {totalDue > 0 && (
        <div className="mb-8">
          <Link
            href="/review"
            className="inline-flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium"
          >
            Start Review ({totalDue} cards due)
          </Link>
        </div>
      )}

      {/* Recent profiles */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Your Profiles</h2>
          <Link
            href="/profiles"
            className="text-blue-400 hover:text-blue-300 text-sm"
          >
            View all →
          </Link>
        </div>

        {profiles.length === 0 ? (
          <div className="bg-gray-800 rounded-lg p-8 text-center">
            <p className="text-gray-400 mb-4">No profiles yet</p>
            <Link
              href="/profiles"
              className="text-blue-400 hover:text-blue-300"
            >
              Create your first profile →
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {profiles.slice(0, 6).map((profile) => (
              <ProfileCard key={profile.id} profile={profile} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
