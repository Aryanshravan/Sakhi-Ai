import { Logo } from "@/components/Logo";

interface LearningHeaderProps {
  /** Shown once a lesson has started. */
  lesson?: { subject: string; grade: number; step: number; total: number };
  onExit: () => void;
}

export function LearningHeader({ lesson, onExit }: LearningHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 border-b border-black/5 px-4 py-3 sm:py-4 md:pl-36 md:pr-10">
      <Logo />

      {lesson && (
        <div className="hidden items-center gap-2 text-lg font-semibold md:flex">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M3 5.500c3-1 6-.5 9 1.500v12c-3-2-6-2.500-9-1.500v-12Z" fill="#fdb022" stroke="#121212" strokeWidth="1.600" strokeLinejoin="round" />
            <path d="M21 5.500c-3-1-6-.5-9 1.500v12c3-2 6-2.500 9-1.500v-12Z" fill="#ffd36b" stroke="#121212" strokeWidth="1.600" strokeLinejoin="round" />
          </svg>
          {lesson.subject} <span aria-hidden="true">•</span> Grade {lesson.grade}
        </div>
      )}

      <div className="flex items-center gap-3 sm:gap-5">
        {lesson && (
          <div className="rounded-2xl border border-cream-line bg-cream px-4 py-2 shadow-sm">
            <p className="text-xs font-semibold sm:text-sm" id="lesson-progress-label">
              Lesson Progress
            </p>
            <div className="mt-1 flex items-center gap-3">
              <div
                role="progressbar"
                aria-labelledby="lesson-progress-label"
                aria-valuemin={1}
                aria-valuemax={lesson.total}
                aria-valuenow={lesson.step}
                className="h-2 w-24 overflow-hidden rounded-full bg-black/10 sm:w-36"
              >
                <div
                  className="h-full rounded-full bg-accent transition-[width] duration-500"
                  style={{ width: `${(lesson.step / lesson.total) * 100}%` }}
                />
              </div>
              <span className="text-sm font-semibold text-muted">
                {lesson.step} / {lesson.total}
              </span>
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={onExit}
          className="flex h-11 items-center gap-2 rounded-2xl border border-cream-line bg-cream px-4 text-base font-semibold shadow-sm transition-colors hover:border-accent"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M10 4H5v16h5M15 8l4 4-4 4M19 12H9" stroke="#121212" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Exit
        </button>
      </div>
    </header>
  );
}
