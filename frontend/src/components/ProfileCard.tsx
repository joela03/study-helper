import Link from "next/link";
import { Profile } from "@/types";

interface Props {
  profile: Profile;
}

export default function ProfileCard({ profile }: Props) {
  return (
    <Link href={`/profiles/${profile.id}`}>
      <div className="bg-gray-800 rounded-lg p-6 hover:bg-gray-750 transition-colors cursor-pointer border border-gray-700 hover:border-gray-600">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white">{profile.name}</h3>
            {profile.module_code && (
              <p className="text-sm text-gray-400">{profile.module_code}</p>
            )}
          </div>
          {profile.due_card_count > 0 && (
            <span className="bg-blue-600 text-white text-xs font-medium px-2.5 py-1 rounded-full">
              {profile.due_card_count} due
            </span>
          )}
        </div>

        <div className="flex gap-4 text-sm text-gray-400">
          <span>{profile.transcript_count} transcripts</span>
          <span>{profile.card_count} cards</span>
        </div>
      </div>
    </Link>
  );
}
