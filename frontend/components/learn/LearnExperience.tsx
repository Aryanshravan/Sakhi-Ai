"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { CornerShapes } from "./CornerShapes";
import { Husky } from "./Husky";
import { useDogRect } from "./useDogRect";
import { VoiceLearning } from "./VoiceLearning";
import { WelcomeScreen } from "./WelcomeScreen";

// Welcome screen -> voice-learning screen (empty board, small husky, language selector, microphone).
export function LearnExperience() {
  const router = useRouter();
  const anchorRef = useRef<HTMLDivElement>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [learning, setLearning] = useState(false);

  const dog = useDogRect(!learning, anchorRef, profile !== null);

  useEffect(() => {
    api<Profile | null>("/auth/me")
      .then((me) => (me ? setProfile(me) : router.replace("/")))
      .catch(() => router.replace("/"));
  }, [router]);

  if (!profile) {
    return (
      <main className="flex min-h-dvh items-center justify-center" role="status" aria-label="Loading">
        <span className="size-6 animate-spin rounded-full border-2 border-line border-t-ink" />
      </main>
    );
  }

  return (
    <div className="relative min-h-dvh overflow-x-hidden">
      <CornerShapes />

      <WelcomeScreen
        childName={profile.child_name}
        active={!learning}
        anchorRef={anchorRef}
        onStart={() => setLearning(true)}
      />

      {learning && dog && (
        <VoiceLearning
          initialLanguage={profile.report_language}
          dogWidth={dog.width}
          onExit={() => setLearning(false)}
        />
      )}

      <Husky rect={dog} />
    </div>
  );
}
