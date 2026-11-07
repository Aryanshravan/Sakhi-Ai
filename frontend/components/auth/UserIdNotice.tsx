"use client";

import { useState } from "react";

interface UserIdNoticeProps {
  userId: string;
  childName: string;
  onContinue: () => void;
}

export function UserIdNotice({ userId, childName, onContinue }: UserIdNoticeProps) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(userId);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <h2 className="text-2xl font-extrabold tracking-tight">You&apos;re all set</h2>
        <p className="text-muted">{childName}&apos;s profile has been created.</p>
      </div>

      <div className="rounded-lg border border-line p-5 text-center">
        <p className="text-sm font-semibold text-muted">Your User ID</p>
        <p className="mt-1 select-all font-mono text-3xl font-bold tracking-wider" data-testid="user-id">
          {userId}
        </p>
        <button
          type="button"
          onClick={copy}
          className="mt-3 rounded-lg border border-line px-4 py-2 text-sm font-semibold transition-colors hover:border-ink"
        >
          {copied ? "Copied" : "Copy User ID"}
        </button>
      </div>

      <p className="rounded-lg bg-accent-soft px-4 py-3 text-sm font-medium">
        Please save this User ID. You will need it with your PIN to log in again, and it cannot be recovered.
      </p>

      <button
        type="button"
        onClick={onContinue}
        className="flex h-13 w-full items-center justify-center gap-2 rounded-lg bg-accent px-5 text-base font-bold text-ink transition-colors hover:bg-accent-hover active:scale-[0.99]"
      >
        Continue <span aria-hidden="true">→</span>
      </button>
    </div>
  );
}
