import type { ReportLanguage } from "@/lib/types";

const LANGUAGES: { value: ReportLanguage; label: string }[] = [
  { value: "en", label: "English" },
  { value: "te", label: "తెలుగు" },
  { value: "hi", label: "हिन्दी" },
];

interface LanguageSelectorProps {
  value: ReportLanguage;
  onChange: (value: ReportLanguage) => void;
  disabled?: boolean;
  label?: string;
  compact?: boolean;
}

export function LanguageSelector({
  value,
  onChange,
  disabled,
  label = "Preferred Report Language",
  compact = false,
}: LanguageSelectorProps) {
  return (
    <fieldset className="space-y-1.5" disabled={disabled}>
      <legend className={compact ? "sr-only" : "text-sm font-semibold"}>{label}</legend>
      <div className={`grid grid-cols-3 overflow-hidden rounded-lg border border-line ${compact ? "w-56" : ""}`}>
        {LANGUAGES.map((language) => (
          <label
            key={language.value}
            className={`flex ${compact ? "h-9 text-sm" : "h-12 text-base"} cursor-pointer items-center justify-center border-l border-line font-medium transition-colors first:border-l-0 hover:bg-accent-soft/60 has-checked:bg-accent-soft has-checked:font-semibold has-focus-visible:outline-2 has-focus-visible:-outline-offset-2 has-focus-visible:outline-ink`}
          >
            <input
              type="radio"
              name="report-language"
              value={language.value}
              checked={value === language.value}
              onChange={() => onChange(language.value)}
              className="sr-only"
            />
            {language.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
