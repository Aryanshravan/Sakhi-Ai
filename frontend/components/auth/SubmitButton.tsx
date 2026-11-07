interface SubmitButtonProps {
  label: string;
  loadingLabel: string;
  loading: boolean;
}

export function SubmitButton({ label, loadingLabel, loading }: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="flex h-13 w-full items-center justify-center gap-2 rounded-lg bg-accent px-5 text-base font-bold text-ink transition-colors hover:bg-accent-hover active:scale-[0.99] disabled:cursor-wait disabled:opacity-80"
    >
      {loading ? (
        <>
          <span className="size-4 animate-spin rounded-full border-2 border-ink/30 border-t-ink" aria-hidden="true" />
          {loadingLabel}
        </>
      ) : (
        <>
          {label}
          <span aria-hidden="true">→</span>
        </>
      )}
    </button>
  );
}

export function FormError({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-lg bg-danger-soft px-4 py-3 text-sm font-medium text-danger">
      {message}
    </p>
  );
}
