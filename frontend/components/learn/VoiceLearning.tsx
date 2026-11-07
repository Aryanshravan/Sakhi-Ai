"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LanguageSelector } from "@/components/auth/LanguageSelector";
import type { ReportLanguage } from "@/lib/types";
import { useVoiceChat, type Board, type Phase } from "@/lib/useVoiceChat";
import { LearningHeader } from "./LearningHeader";
import { TallyMarks } from "./TallyMarks";
import { dogHeight } from "./useDogRect";

interface VoiceLearningProps {
  initialLanguage: ReportLanguage;
  dogWidth: number;
  onExit: () => void;
}

// The board shows only the item being learned, sized for the kind of item.
const BOARD_TEXT: Record<Board["kind"], string> = {
  letter: "text-[9rem] sm:text-[14rem]",
  number: "text-[8rem] sm:text-[13rem]",
  word: "text-7xl sm:text-9xl",
  math: "text-6xl sm:text-9xl",
  sentence: "text-4xl sm:text-7xl",
  science: "text-3xl sm:text-6xl",
};

// Audio-only: the conversation is never shown as text, only a small hint of what is happening.
const HINT: Record<Phase, string> = {
  idle: "",
  listening: "Listening…",
  transcribing: "Thinking…",
  thinking: "Thinking…",
  speaking: "Sakhi is talking…",
};

interface ReportStatus {
  status: string;
  message: string;
  in_progress: boolean;
}

const POLL_MS = 3000;
const POLL_LIMIT = 40; // about two minutes

export function VoiceLearning({ initialLanguage, dogWidth, onExit }: VoiceLearningProps) {
  const [language, setLanguage] = useState(initialLanguage);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState("");
  const [ending, setEnding] = useState(false);
  const [report, setReport] = useState<ReportStatus | null>(null);
  const [endError, setEndError] = useState("");
  const chat = useVoiceChat(language, "/tutor/turn", sessionId);
  const listening = chat.phase === "listening";
  const working = chat.phase === "transcribing" || chat.phase === "thinking";
  const canTap = (chat.phase === "idle" || listening) && sessionId !== null && !ending && !report;

  // The lesson session the child's answers are saved to (an unfinished one is resumed).
  const requestSession = useCallback(() => {
    api<{ id: string }>("/learning/sessions", { method: "POST", body: { lesson_id: "voice-learning" } })
      .then((started) => setSessionId(started.id))
      .catch(() => setSessionError("Could not start the lesson session."));
  }, []);
  useEffect(requestSession, [requestSession]);

  // End the session: the backend saves it, writes the report, makes the voice note and sends it to Telegram.
  async function endSession() {
    if (!sessionId || ending) return;
    setEnding(true);
    setEndError("");
    chat.end();
    try {
      let result = await api<ReportStatus>(`/reports/${sessionId}/finalize`, { method: "POST" });
      for (let i = 0; result.in_progress && i < POLL_LIMIT; i++) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        result = await api<ReportStatus>(`/reports/${sessionId}`);
      }
      setReport(result);
    } catch {
      setEndError("Could not finish the session just now. Your answers are saved. Please try again.");
    } finally {
      setEnding(false);
    }
  }
  const retryable = report !== null && !["sent", "telegram_not_connected"].includes(report.status);
  const hint = HINT[chat.phase] || (chat.error ? "" : chat.active ? "Tap the microphone to continue." : "Tap the microphone to talk.");

  return (
    <div className="relative z-10 flex min-h-dvh animate-fade-up flex-col">
      <LearningHeader onExit={onExit} />

      {/* The learning board: empty until an activity puts one item on it. */}
      <div
        role="region"
        aria-label="Learning board"
        className="mx-4 mt-4 flex min-h-48 flex-1 items-center justify-center rounded-[28px] border border-cream-line bg-cream p-6 text-center sm:mx-8"
      >
        {(ending || report) && (
          <div className="max-w-xl space-y-4" role="status" aria-live="polite">
            {ending ? (
              <>
                <span className="mx-auto block size-10 animate-spin rounded-full border-4 border-accent-soft border-t-accent" aria-hidden="true" />
                <p className="text-2xl font-extrabold">Preparing parent report...</p>
                <p className="text-muted">Please keep this page open.</p>
              </>
            ) : (
              report && (
                <>
                  <p className="text-3xl font-extrabold">Session ended</p>
                  <p className="text-lg font-medium">{report.message}</p>
                  <div className="flex flex-wrap justify-center gap-3">
                    {retryable && (
                      <button type="button" onClick={endSession} className="rounded-full bg-accent px-6 py-3 font-bold hover:bg-accent-hover">
                        Try again
                      </button>
                    )}
                    <button type="button" onClick={onExit} className="rounded-full border-2 border-ink bg-white px-6 py-3 font-bold hover:bg-accent-soft">
                      Back to start
                    </button>
                  </div>
                </>
              )
            )}
          </div>
        )}
        {!ending && !report && chat.board && (
          <div key={chat.board.text} className="flex flex-col items-center gap-6">
            <p className={`animate-fade-up font-extrabold leading-tight tracking-tight ${chat.board.visual ? "text-5xl sm:text-7xl" : BOARD_TEXT[chat.board.kind]}`}>
              {chat.board.highlight === undefined
                ? chat.board.text
                : [...chat.board.text].map((letter, i) => (
                    <span key={i} className={i === chat.board?.highlight ? "rounded-2xl bg-accent px-1" : undefined}>
                      {letter}
                    </span>
                  ))}
            </p>
            {chat.board.visual && (
              <TallyMarks key={`${chat.board.text}-${chat.board.visual.step}`} visual={chat.board.visual} />
            )}
          </div>
        )}
      </div>

      {/* Bottom strip: the mascot is fixed at the left of it; the controls sit beside her. */}
      <div
        className="flex flex-wrap items-center gap-x-5 gap-y-2 py-3 pr-4 sm:pr-8"
        style={{ minHeight: dogHeight(dogWidth) + 16, paddingLeft: dogWidth + 24 }}
      >
        <button
          type="button"
          onClick={chat.tapMicrophone}
          disabled={!canTap}
          aria-label={listening ? "Stop talking and send" : "Start talking"}
          className={`relative grid size-16 shrink-0 place-items-center rounded-full bg-accent shadow-[0_8px_20px_-8px_rgba(253,176,34,0.95)] transition-transform hover:bg-accent-hover disabled:opacity-70 sm:size-20 ${
            listening ? "scale-110" : ""
          }`}
        >
          {(listening || chat.phase === "speaking") && (
            <span className="absolute inset-0 animate-ping rounded-full bg-accent/40" aria-hidden="true" />
          )}
          {working ? (
            <span className="size-6 animate-spin rounded-full border-2 border-ink/30 border-t-ink" aria-hidden="true" />
          ) : (
            <svg className="relative size-7 sm:size-9" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              {listening ? (
                <rect x="6" y="6" width="12" height="12" rx="2" fill="#121212" />
              ) : (
                <>
                  <rect x="9" y="3" width="6" height="11" rx="3" fill="#121212" />
                  <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" stroke="#121212" strokeWidth="2" strokeLinecap="round" />
                </>
              )}
            </svg>
          )}
        </button>

        <div className="space-y-1.5">
          <LanguageSelector value={language} onChange={setLanguage} label="Language" compact />
          <p className="min-h-5 text-sm font-medium text-muted" role="status" aria-live="polite">
            {hint}
          </p>
        </div>

        <button
          type="button"
          onClick={endSession}
          disabled={!sessionId || ending || report !== null}
          className="ml-auto rounded-full border-2 border-ink bg-white px-6 py-3 text-base font-bold transition-colors hover:bg-accent-soft disabled:opacity-60 sm:px-8 sm:py-4 sm:text-lg"
        >
          {ending ? "Preparing parent report..." : "End Session"}
        </button>

        {((!sessionId && sessionError) || endError) && (
          <div role="alert" className="basis-full rounded-xl bg-danger-soft px-3 py-2 text-sm font-medium text-danger">
            {endError || sessionError}
            <button
              type="button"
              onClick={() => (endError ? endSession() : (setSessionError(""), requestSession()))}
              className="ml-3 rounded-lg bg-white px-3 py-1 text-sm font-semibold text-ink transition-colors hover:bg-accent-soft"
            >
              Try again
            </button>
          </div>
        )}

        {chat.error && (
          <div role="alert" className="basis-full rounded-xl bg-danger-soft px-3 py-2 text-sm font-medium text-danger">
            {chat.error}
            {chat.canRetry && (
              <button
                type="button"
                onClick={chat.retry}
                className="ml-3 rounded-lg bg-white px-3 py-1 text-sm font-semibold text-ink transition-colors hover:bg-accent-soft"
              >
                Try again
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
