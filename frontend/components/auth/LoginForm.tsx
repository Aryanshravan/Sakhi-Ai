"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { validateLogin, type FieldErrors } from "@/lib/validation";
import { PinField } from "./PinField";
import { FormError, SubmitButton } from "./SubmitButton";
import { TextField } from "./TextField";

export function LoginForm() {
  const router = useRouter();
  const [userId, setUserId] = useState("");
  const [pin, setPin] = useState("");
  const [errors, setErrors] = useState<FieldErrors<"userId" | "pin">>({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateLogin(userId, pin);
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length > 0) return;

    setLoading(true);
    try {
      await api<Profile>("/auth/login", { method: "POST", body: { user_id: userId, pin } });
      setUserId("");
      setPin("");
      setLoading(false);
      router.replace("/learn");
    } catch (error) {
      setPin("");
      setFormError(error instanceof ApiError ? error.message : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <TextField
        id="user-id"
        label="User ID"
        placeholder="SAKHI-XXXX"
        autoComplete="username"
        autoCapitalize="characters"
        spellCheck={false}
        maxLength={20}
        value={userId}
        onChange={(event) => {
          setUserId(event.target.value.toUpperCase());
          setErrors((current) => ({ ...current, userId: undefined }));
        }}
        error={errors.userId}
        disabled={loading}
      />
      <PinField
        id="login-pin"
        label="PIN"
        autoComplete="current-password"
        value={pin}
        onChange={(value) => {
          setPin(value);
          setErrors((current) => ({ ...current, pin: undefined }));
        }}
        error={errors.pin}
        disabled={loading}
      />
      {formError && <FormError message={formError} />}
      <SubmitButton label="Login" loadingLabel="Logging in…" loading={loading} />
    </form>
  );
}
