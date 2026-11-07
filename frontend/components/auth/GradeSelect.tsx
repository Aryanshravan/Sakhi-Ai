import { Field, inputClass } from "./TextField";

const GRADES = [1, 2, 3, 4, 5];

interface GradeSelectProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
}

export function GradeSelect({ value, onChange, error, disabled }: GradeSelectProps) {
  return (
    <Field id="grade" label="Child's Grade" error={error}>
      <div className="relative">
        <select
          id="grade"
          value={value}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "grade-error" : undefined}
          onChange={(event) => onChange(event.target.value)}
          className={`${inputClass} appearance-none pr-11 ${value ? "" : "text-muted/70"} ${error ? "border-danger" : "border-line"}`}
        >
          <option value="" disabled>
            Select grade
          </option>
          {GRADES.map((grade) => (
            <option key={grade} value={grade} className="text-ink">
              Grade {grade}
            </option>
          ))}
        </select>
        <svg
          className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2"
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <path d="m4 6 4 4 4-4" stroke="#121212" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </Field>
  );
}
