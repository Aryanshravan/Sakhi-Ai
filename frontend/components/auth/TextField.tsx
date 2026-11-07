import type { InputHTMLAttributes, ReactNode } from "react";

export const inputClass =
  "h-12 w-full rounded-lg border bg-white px-4 text-base text-ink placeholder:text-muted/70 transition-colors focus:border-ink focus:outline-none focus-visible:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60";

interface FieldProps {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}

export function Field({ id, label, error, hint, children }: FieldProps) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-semibold">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : hint ? (
        <p className="text-sm text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  id: string;
  label: string;
  error?: string;
  hint?: string;
}

export function TextField({ id, label, error, hint, className, ...input }: TextFieldProps) {
  return (
    <Field id={id} label={label} error={error} hint={hint}>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`${inputClass} ${error ? "border-danger" : "border-line"} ${className ?? ""}`}
        {...input}
      />
    </Field>
  );
}
