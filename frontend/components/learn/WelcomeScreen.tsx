import type { RefObject } from "react";
import { Logo } from "@/components/Logo";
import { ParentMenu } from "./ParentMenu";

interface WelcomeScreenProps {
  childName: string;
  active: boolean;
  anchorRef: RefObject<HTMLDivElement | null>;
  onStart: () => void;
}

export function WelcomeScreen({ childName, active, anchorRef, onStart }: WelcomeScreenProps) {
  return (
    <div
      // Kept mounted while learning (just faded out) so the mascot knows where to return to.
      className={`z-10 flex min-h-dvh flex-col transition-opacity duration-500 ${
        active ? "relative opacity-100" : "pointer-events-none absolute inset-0 opacity-0"
      }`}
      inert={!active}
      aria-hidden={!active}
    >
      <header className="flex items-center justify-between gap-3 border-b border-black/5 px-4 py-3 sm:py-5 md:pl-40 md:pr-12">
        <Logo />
        <ParentMenu childName={childName} />
      </header>

      <main className="flex flex-1 flex-col items-center justify-center gap-4 px-4 py-6 text-center">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl">
            Welcome to <span className="text-accent">Sakhi AI</span>
          </h1>
          <p className="mt-3 text-lg text-muted sm:text-2xl">
            Your child&apos;s personal learning companion
          </p>
          <div className="mx-auto mt-4 h-1 w-16 rounded-full bg-accent" />
        </div>

        <div className="relative">
          <div ref={anchorRef} className="aspect-[660/836] h-[min(44dvh,420px)] min-h-44" />
          <svg
            className="absolute -right-12 top-6 hidden h-14 w-12 sm:block"
            viewBox="0 0 48 56"
            fill="none"
            aria-hidden="true"
          >
            <path d="M6 4l8 18M24 6l-4 22M42 22l-16 8" stroke="#fdb022" strokeWidth="5" strokeLinecap="round" />
          </svg>
        </div>

        <button
          type="button"
          onClick={onStart}
          className="flex h-16 w-full max-w-md items-center justify-center gap-3 rounded-2xl bg-accent px-6 text-xl font-extrabold text-ink shadow-[0_10px_24px_-8px_rgba(253,176,34,0.8)] transition-all hover:bg-accent-hover active:scale-[0.99] sm:h-20 sm:text-2xl"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="#121212" aria-hidden="true">
            <path d="M6 3.500v17l15-8.500-15-8.500Z" />
          </svg>
          Start Learning
          <span aria-hidden="true">→</span>
        </button>
      </main>
    </div>
  );
}
