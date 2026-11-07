"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiAudio, apiUpload, ApiError } from "@/lib/api";
import { startRecording, type Recording } from "@/lib/recorder";
import type { ReportLanguage } from "@/lib/types";

export type Phase = "idle" | "listening" | "transcribing" | "thinking" | "speaking";
export interface Turn {
  role: "user" | "sakhi";
  text: string;
}

interface Transcript {
  text: string;
  language: ReportLanguage | null;
}
/** What the learning board shows (tutor replies only). */
export interface TallyVisual {
  op: "add" | "sub";
  a: number;
  b: number;
  step: "a" | "b" | "sum" | "cross" | "left" | "explain";
}
export interface Board {
  kind: "word" | "sentence" | "letter" | "number" | "math" | "science";
  text: string;
  visual?: TallyVisual; // animated sticks for maths
  highlight?: number; // the letter of the word being sounded out
}
/** One piece of an ordered speech plan (spoken one after another inside a single recording). */
interface Segment {
  text: string;
  language: ReportLanguage;
  pause: number;
}
interface Reply {
  reply: string;
  language: ReportLanguage;
  board?: Board | null;
  state?: unknown; // the tutor's session state; sent back with the next turn
  english_words?: string[]; // spoken by the English voice whatever language Sakhi speaks
  speech?: Segment[] | null; // when present, spoken in exactly this order (sentence teaching)
}

const HISTORY_SENT = 10;

/** The step that failed, so "Try again" can repeat exactly that step. */
type Retry =
  | { type: "transcribe"; wav: Blob }
  | { type: "reply"; message: string; heard: ReportLanguage | null; history: Turn[] }
  | { type: "speak"; text: string; language: ReportLanguage; english: string[]; segments?: Segment[] };

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function microphoneProblem(error: unknown): string {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "The microphone is blocked. Allow microphone access in your browser, then tap the microphone to try again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return "No microphone was found. Plug one in, then tap the microphone to try again.";
  }
  return "The microphone could not start. Please check it and tap the microphone to try again.";
}

function apiProblem(error: unknown, fallback: string): string {
  return error instanceof ApiError && error.status === 0 ? error.message : fallback;
}

/**
 * Hands-free voice conversation: listen -> speech-to-text -> Gemini -> text-to-speech -> play -> listen again.
 * Only one step runs at a time; every step belongs to a "run" and is dropped if the run is cancelled.
 */
export function useVoiceChat(preferredLanguage: ReportLanguage, replyPath = "/voice-chat/reply", sessionId: string | null = null) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [active, setActive] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState("");
  const [canRetry, setCanRetry] = useState(false);
  const [board, setBoard] = useState<Board | null>(null);

  const runRef = useRef(0);
  const activeRef = useRef(false);
  const turnsRef = useRef<Turn[]>([]);
  const tutorStateRef = useRef<unknown>(null);
  const boardRef = useRef<Board | null>(null);
  const languageRef = useRef(preferredLanguage);
  const abortRef = useRef<AbortController | null>(null);
  const recordingRef = useRef<Recording | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const retryRef = useRef<Retry | null>(null);
  const listenRef = useRef<(id: number) => Promise<void>>(async () => {}); // speak() hands back to listen()

  const sessionRef = useRef(sessionId);

  useEffect(() => {
    languageRef.current = preferredLanguage;
    sessionRef.current = sessionId;
  }, [preferredLanguage, sessionId]);

  const cancelEverything = useCallback(() => {
    runRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    recordingRef.current?.cancel();
    recordingRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
  }, []);

  useEffect(() => cancelEverything, [cancelEverything]);

  const addTurn = useCallback((turn: Turn) => {
    turnsRef.current = [...turnsRef.current, turn];
    setTurns(turnsRef.current);
  }, []);

  /** Show an error and remember how to retry the step that failed. */
  const fail = useCallback((message: string, retry?: Retry) => {
    retryRef.current = retry ?? null;
    setCanRetry(Boolean(retry));
    setError(message);
    setPhase("idle");
  }, []);

  const newSignal = useCallback(() => {
    abortRef.current = new AbortController();
    return abortRef.current.signal;
  }, []);

  const speak = useCallback(
    async (id: number, text: string, language: ReportLanguage, english: string[] = [], segments?: Segment[]) => {
      setPhase("speaking");
      let url = "";
      try {
        const sound = await apiAudio("/voice-chat/speak", { text, language, english_words: english, segments: segments ?? [] }, newSignal());
        if (id !== runRef.current) return;
        url = URL.createObjectURL(sound);
        const audio = new Audio(url);
        audioRef.current = audio;
        await new Promise<void>((resolve, reject) => {
          audio.onended = () => resolve();
          audio.onerror = () => reject(new Error("playback"));
          audio.play().catch(reject);
        });
      } catch (caught) {
        if (isAbort(caught) || id !== runRef.current) return;
        const failedPlayback = !(caught instanceof ApiError);
        fail(
          apiProblem(caught, failedPlayback ? "The sound could not be played." : "Sakhi could not speak just now.") +
            " Tap Try again.",
          { type: "speak", text, language, english, segments },
        );
        return;
      } finally {
        if (url) URL.revokeObjectURL(url);
        if (id === runRef.current) audioRef.current = null;
      }
      // Sakhi has finished talking, so it is safe to listen again.
      if (id === runRef.current && activeRef.current) await listenRef.current(id);
    },
    [fail, newSignal],
  );

  const reply = useCallback(
    async (id: number, message: string, heard: ReportLanguage | null, history: Turn[]) => {
      setPhase("thinking");
      try {
        const answer = await api<Reply>(replyPath, {
          method: "POST",
          body: {
            state: tutorStateRef.current,
            message,
            history,
            preferred_language: languageRef.current,
            heard_language: heard,
            session_id: sessionRef.current, // the tutor saves the child's answers to this session
          },
          signal: newSignal(),
        });
        if (id !== runRef.current) return;
        tutorStateRef.current = answer.state ?? null;
        boardRef.current = answer.board ?? null;
        setBoard(answer.board ?? null);
        addTurn({ role: "sakhi", text: answer.reply });
        await speak(id, answer.reply, answer.language, answer.english_words, answer.speech ?? undefined);
      } catch (caught) {
        if (isAbort(caught) || id !== runRef.current) return;
        fail(apiProblem(caught, "Sakhi could not think of an answer just now. Tap Try again."), {
          type: "reply",
          message,
          heard,
          history,
        });
      }
    },
    [addTurn, fail, newSignal, replyPath, speak],
  );

  const transcribe = useCallback(
    async (id: number, wav: Blob) => {
      setPhase("transcribing");
      try {
        // Lessons are in English: an answer to an item on the board is transcribed as English (with the word as a hint).
        const shown = boardRef.current;
        const query = shown ? `?english=true${shown.kind === "word" ? `&keyword=${encodeURIComponent(shown.text)}` : ""}` : "";
        const heard = await apiUpload<Transcript>(`/voice-chat/transcribe${query}`, wav, newSignal());
        if (id !== runRef.current) return;
        if (!heard.text) {
          fail("I couldn't make out what you said. Tap the microphone and try again.");
          return;
        }
        const history = turnsRef.current.slice(-HISTORY_SENT);
        addTurn({ role: "user", text: heard.text });
        await reply(id, heard.text, heard.language, history);
      } catch (caught) {
        if (isAbort(caught) || id !== runRef.current) return;
        fail(apiProblem(caught, "I couldn't understand the audio. Tap Try again."), { type: "transcribe", wav });
      }
    },
    [addTurn, fail, newSignal, reply],
  );

  const listen = useCallback(
    async (id: number) => {
      setError("");
      setCanRetry(false);
      setPhase("listening");
      let recording: Recording;
      try {
        recording = await startRecording();
      } catch (caught) {
        if (id === runRef.current) fail(microphoneProblem(caught));
        return;
      }
      if (id !== runRef.current) {
        recording.cancel();
        return;
      }
      recordingRef.current = recording;
      try {
        const result = await recording.result;
        if (id !== runRef.current) return;
        recordingRef.current = null;
        if (result.kind === "no-speech") {
          fail("I didn't hear anything. Tap the microphone when you are ready to talk.");
          return;
        }
        await transcribe(id, result.wav);
      } catch {
        if (id === runRef.current) fail("The recording could not be processed. Tap the microphone to try again.");
      }
    },
    [fail, transcribe],
  );

  useEffect(() => {
    listenRef.current = listen;
  }, [listen]);

  /** Microphone button: start (a new conversation, or the next turn) or finish speaking now. */
  const tapMicrophone = useCallback(() => {
    if (phase === "listening") {
      recordingRef.current?.stop();
      return;
    }
    if (phase !== "idle") return; // ignore taps while Sakhi is busy: no duplicate submissions
    if (!activeRef.current) {
      turnsRef.current = [];
      tutorStateRef.current = null;
      setTurns([]);
      setBoard(null);
      boardRef.current = null;
      activeRef.current = true;
      setActive(true);
    }
    void listen(++runRef.current);
  }, [phase, listen]);

  const retry = useCallback(() => {
    const step = retryRef.current;
    if (!step) return;
    setError("");
    setCanRetry(false);
    retryRef.current = null;
    const id = ++runRef.current;
    if (step.type === "transcribe") void transcribe(id, step.wav);
    else if (step.type === "reply") void reply(id, step.message, step.heard, step.history);
    else void speak(id, step.text, step.language, step.english, step.segments);
  }, [transcribe, reply, speak]);

  /** Stop everything right now, wherever the conversation is. */
  const end = useCallback(() => {
    cancelEverything();
    activeRef.current = false;
    retryRef.current = null;
    tutorStateRef.current = null;
    boardRef.current = null;
    setBoard(null);
    setActive(false);
    setCanRetry(false);
    setError("");
    setPhase("idle");
  }, [cancelEverything]);

  return { phase, active, turns, board, error, canRetry, tapMicrophone, retry, end };
}
