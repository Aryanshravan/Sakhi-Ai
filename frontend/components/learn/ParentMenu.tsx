"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";

interface TelegramStatus {
  configured: boolean;
  connected: boolean;
}

const POLL_MS = 3000;
const POLL_LIMIT = 40; // wait about two minutes for the parent to press Start in Telegram

export function ParentMenu({ childName }: { childName: string }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const [telegram, setTelegram] = useState<TelegramStatus | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [telegramError, setTelegramError] = useState("");

  useEffect(() => {
    if (!open) return;
    api<TelegramStatus>("/telegram/status").then(setTelegram).catch(() => setTelegram(null));
  }, [open]);

  async function connectTelegram() {
    setTelegramError("");
    try {
      const { url } = await api<{ url: string }>("/telegram/link", { method: "POST" });
      window.open(url, "_blank", "noopener");
      setWaiting(true);
      for (let i = 0; i < POLL_LIMIT; i++) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        const status = await api<TelegramStatus>("/telegram/status");
        setTelegram(status);
        if (status.connected) break;
      }
    } catch (caught) {
      setTelegramError(caught instanceof ApiError ? caught.message : "Could not connect Telegram.");
    } finally {
      setWaiting(false);
    }
  }

  async function disconnectTelegram() {
    await api("/telegram/disconnect", { method: "POST" });
    setTelegram((current) => (current ? { ...current, connected: false } : current));
  }

  useEffect(() => {
    if (!open) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    // Full page load on purpose: no logged-in client state may survive logout.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/";
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2.5 rounded-full border border-cream-line bg-cream py-1.5 pl-1.5 pr-4 text-sm font-semibold transition-colors hover:border-accent sm:text-base"
      >
        <span className="grid size-9 place-items-center rounded-full bg-accent-soft">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="8" r="4" stroke="#121212" strokeWidth="2" />
            <path d="M4 21c0-4.200 3.600-7 8-7s8 2.800 8 7" stroke="#121212" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </span>
        <span>Hi, {childName}&apos;s Parent</span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
          className={`transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path d="m4 6 4 4 4-4" stroke="#121212" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-2 w-full min-w-40 rounded-xl border border-line bg-white p-1 shadow-md">
          {telegram?.connected ? (
            <div className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm font-semibold">
              <span>Telegram connected</span>
              <button type="button" onClick={disconnectTelegram} className="text-muted underline">
                Disconnect
              </button>
            </div>
          ) : (
            <button
              type="button"
              role="menuitem"
              onClick={connectTelegram}
              disabled={waiting}
              className="w-full rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition-colors hover:bg-accent-soft disabled:opacity-60"
            >
              {waiting ? "Press Start in Telegram…" : "Connect Telegram"}
            </button>
          )}
          {telegramError && <p className="px-3 pb-2 text-xs font-medium text-danger">{telegramError}</p>}
          <button
            type="button"
            role="menuitem"
            onClick={logout}
            className="w-full rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition-colors hover:bg-accent-soft"
          >
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
