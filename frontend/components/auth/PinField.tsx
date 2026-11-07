"use client";

import { useState } from "react";
import { Field, inputClass } from "./TextField";

interface PinFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: string;
  autoComplete: "new-password" | "current-password";
  disabled?: boolean;
}

export function PinField({ id, label, value, onChange, error, hint, autoComplete, disabled }: PinFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <Field id={id} label={label} error={error} hint={hint}>
      <div className="relative">
        <input
          id={id}
          type={visible ? "text" : "password"}
          inputMode="numeric"
          autoComplete={autoComplete}
          maxLength={6}
          value={value}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))}
          className={`${inputClass} pr-16 ${error ? "border-danger" : "border-line"}`}
        />
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex items-center rounded-r-lg px-4 text-sm font-semibold text-muted transition-colors hover:text-ink"
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
    </Field>
  );
}
