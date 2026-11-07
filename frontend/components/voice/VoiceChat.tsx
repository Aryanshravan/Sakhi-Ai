"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LanguageSelector } from "@/components/auth/LanguageSelector";
import { Logo } from "@/components/Logo";
import { CornerShapes } from "@/components/learn/CornerShapes";
import { api } from "@/lib/api";
import type { Profile, ReportLanguage } from "@/lib/types";
import { useVoiceChat, type Phase } from "@/lib/useVoiceChat";

export function VoiceChat() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);

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
  return <VoiceChatScreen initialLanguage={profile.report_language} />;
}

const STATUS: Record<Phase, string> = {
  idle: "",
  listening: "Listening… tap the button when you are done.",
  transcribing: "Listening to what you said…",
  thinking: "Sakhi is thinking…",
  speaking: "Sakhi is speaking…",
};

function VoiceChatScreen({ initialLanguage }: { initialLanguage: ReportLanguage }) {
  const [language, setLanguage] = useState(initialLanguage);
  const chat = useVoiceChat(language);
  const listening = chat.phase === "listening";
  const canTap = chat.phase === "idle" || listening;
  const idleHint = chat.active
    ? "Tap the microphone to keep talking."
    : "Tap the microphone and start talking to Sakhi.";

  return (
    <div className="relative min-h-dvh overflow-hidden">
      <CornerShapes />
      <div className="relative z-10 flex min-h-dvh flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-black/5 px-4 py-3 sm:py-5 md:pl-40 md:pr-12">
          <Logo />
          <Link
            href="/learn"
            className="flex h-11 items-center rounded-2xl border border-cream-line bg-cream px-4 text-base font-semibold shadow-sm transition-colors hover:border-accent"
          >
            Back
          </Link>
        </header>

        <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center px-4 py-8 text-center">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl">Voice Chat</h1>
          <p className="mt-2 text-lg text-muted">Talk to Sakhi in English, Hindi or Telugu.</p>

          <div className="mt-6 w-full text-left">
            <LanguageSelector value={language} onChange={setLanguage} label="Preferred language" />
          </div>

          <button
            type="button"
            onClick={chat.tapMicrophone}
            disabled={!canTap}
            aria-label={listening ? "Stop talking and send" : "Start talking"}
            className={`relative mt-8 grid size-28 place-items-center rounded-full bg-accent shadow-[0_12px_28px_-10px_rgba(253,176,34,0.95)] transition-transform hover:bg-accent-hover disabled:opacity-60 ${
              listening ? "scale-110" : ""
            }`}
          >
            {listening && <span className="absolute inset-0 animate-ping rounded-full bg-accent/50" aria-hidden="true" />}
            <svg className="relative" width="44" height="44" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              {listening ? (
                <rect x="6" y="6" width="12" height="12" rx="2" fill="#121212" />
              ) : (
                <>
                  <rect x="9" y="3" width="6" height="11" rx="3" fill="#121212" />
                  <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" stroke="#121212" strokeWidth="2" strokeLinecap="round" />
                </>
              )}
            </svg>
          </button>

          <p className="mt-4 min-h-7 text-lg font-semibold" role="status" aria-live="polite">
            {STATUS[chat.phase] || (chat.error ? "" : idleHint)}
          </p>

          {chat.error && (
            <div role="alert" className="mt-2 w-full rounded-xl bg-danger-soft px-4 py-3 text-base font-medium text-danger">
              <p>{chat.error}</p>
              {chat.canRetry && (
                <button
                  type="button"
                  onClick={chat.retry}
                  className="mt-2 rounded-lg bg-white px-4 py-1.5 text-sm font-semibold text-ink transition-colors hover:bg-accent-soft"
                >
                  Try again
                </button>
              )}
            </div>
          )}

          {chat.active && (
            <button
              type="button"
              onClick={chat.end}
              className="mt-4 h-11 rounded-2xl border border-line bg-white px-5 text-base font-semibold transition-colors hover:border-ink"
            >
              End conversation
            </button>
          )}

          {chat.turns.length > 0 && (
            <ul aria-label="Conversation" className="mt-8 w-full space-y-3 text-left">
              {chat.turns.map((turn, index) => (
                <li
                  key={index}
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-lg ${
                    turn.role === "user" ? "ml-auto bg-accent-soft" : "mr-auto border border-line bg-white"
                  }`}
                >
                  <span className="block text-xs font-semibold text-muted">{turn.role === "user" ? "You" : "Sakhi"}</span>
                  {turn.text}
                </li>
              ))}
            </ul>
          )}
        </main>
      </div>
    </div>
  );
}
