"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { LoginForm } from "./LoginForm";
import { RegisterForm } from "./RegisterForm";
import { UserIdNotice } from "./UserIdNotice";

type Mode = "register" | "login";

const TABS: { mode: Mode; label: string }[] = [
  { mode: "register", label: "Create Account" },
  { mode: "login", label: "Login" },
];

export function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("register");
  const [checking, setChecking] = useState(true);
  const [registered, setRegistered] = useState<Profile | null>(null);

  // A parent who is already logged in goes straight to their child's learning space.
  useEffect(() => {
    api<Profile | null>("/auth/me")
      .then((profile) => (profile ? router.replace("/learn") : setChecking(false)))
      .catch(() => setChecking(false));
  }, [router]);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[520px] flex-col items-center px-4 py-10 sm:py-16">
      <Logo />
      <p className="mt-3 text-center text-lg text-muted">Every child deserves a learning companion.</p>

      <div className="mt-10 w-full rounded-2xl border border-line bg-white p-6 shadow-sm sm:p-8">
        {checking ? (
          <div className="flex h-64 items-center justify-center" role="status" aria-label="Loading">
            <span className="size-6 animate-spin rounded-full border-2 border-line border-t-ink" />
          </div>
        ) : registered ? (
          <UserIdNotice
            userId={registered.user_id}
            childName={registered.child_name}
            onContinue={() => router.replace("/learn")}
          />
        ) : (
          <div className="space-y-6">
            <div role="tablist" aria-label="Account" className="grid grid-cols-2 rounded-lg bg-black/[0.05] p-1">
              {TABS.map((tab) => (
                <button
                  key={tab.mode}
                  type="button"
                  role="tab"
                  aria-selected={mode === tab.mode}
                  onClick={() => setMode(tab.mode)}
                  className={`h-10 rounded-md text-sm font-semibold transition-colors ${
                    mode === tab.mode ? "bg-white shadow-sm" : "text-muted hover:text-ink"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="text-center">
              <h1 className="text-2xl font-extrabold tracking-tight">
                {mode === "register" ? "Let’s Get Started" : "Welcome back"}
              </h1>
              <p className="mt-1 text-muted">
                {mode === "register" ? "Tell us a few details to continue" : "Log in with your User ID and PIN"}
              </p>
            </div>

            {mode === "register" ? <RegisterForm onRegistered={setRegistered} /> : <LoginForm />}
          </div>
        )}
      </div>
    </main>
  );
}
