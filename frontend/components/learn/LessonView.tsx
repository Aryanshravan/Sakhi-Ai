import type { ReactNode } from "react";
import { breakDown, LESSON } from "@/lib/lesson";
import { BaseTenBlocks } from "./BaseTenBlocks";

interface LessonViewProps {
  stepIndex: number;
  onPrevious: () => void;
  onNext: () => void;
}

function Chip({ children }: { children: ReactNode }) {
  return <span className="rounded-full bg-accent-soft px-4 py-1 text-base font-bold">{children}</span>;
}

function Operator({ children }: { children: ReactNode }) {
  return <span className="pb-6 text-3xl font-bold sm:text-4xl">{children}</span>;
}

export function LessonView({ stepIndex, onPrevious, onNext }: LessonViewProps) {
  const step = LESSON.steps[stepIndex];
  const { tens, ones, total } = breakDown(step);
  const isLast = stepIndex === LESSON.steps.length - 1;

  return (
    // On wide screens the left column is kept free for Sakhi and her speech bubble.
    <div className="w-full lg:pl-72" key={stepIndex}>
    <div className="mx-auto w-full max-w-[1080px] px-4 pb-4 pt-5 sm:px-8 sm:pt-8">
      <div className="animate-fade-up">
        <p className="inline-flex items-center gap-2 rounded-full bg-accent-soft px-4 py-1.5 text-base font-bold">
          <span className="size-3 rounded-full bg-accent" aria-hidden="true" />
          Lesson 1
        </p>
        <h1 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-5xl">{LESSON.title}</h1>
        <p className="mt-2 text-lg text-muted sm:text-2xl">{LESSON.intro}</p>

        <section
          aria-label="Worked example"
          className="mt-6 rounded-[28px] border border-cream-line bg-cream p-4 sm:p-8"
        >
          <div className="grid items-center gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
            <div className="space-y-3">
              <span className="inline-block rounded-full bg-[#fdd36a] px-5 py-1.5 text-lg font-bold">Example</span>
              <p className="text-4xl font-extrabold tracking-tight sm:text-5xl">
                {step.a} + {step.b} = ?
              </p>
            </div>

            <div className="flex flex-wrap items-end justify-center gap-x-4 gap-y-4 rounded-2xl bg-white p-4 sm:p-5">
              <div className="flex flex-col items-center gap-3">
                <Chip>{step.a}</Chip>
                <BaseTenBlocks value={step.a} />
              </div>
              <Operator>+</Operator>
              <div className="flex flex-col items-center gap-3">
                <Chip>{step.b}</Chip>
                <BaseTenBlocks value={step.b} />
              </div>
              <Operator>=</Operator>
              <div className="relative pb-3">
                <p className="rounded-2xl border-2 border-accent bg-accent-soft px-5 py-2 text-4xl font-extrabold sm:text-5xl">
                  {total}
                </p>
                <svg className="absolute -right-3 -top-4 h-6 w-7" viewBox="0 0 28 24" fill="none" aria-hidden="true">
                  <path d="M4 22l4-10M14 18l1-14M24 20l-6-8" stroke="#fdb022" strokeWidth="3" strokeLinecap="round" />
                </svg>
              </div>
            </div>
          </div>

          <ol className="mt-6 space-y-3 text-xl sm:text-2xl">
            <ExplanationStep number={1}>
              Add the <strong>tens</strong>: {tens[0]} + {tens[1]} = {tens[2]}
            </ExplanationStep>
            <ExplanationStep number={2}>
              Add the <strong>ones</strong>: {ones[0]} + {ones[1]} = {ones[2]}
            </ExplanationStep>
            <ExplanationStep number={3}>
              <strong>Combine</strong>: {tens[2]} + {ones[2]} = {total}
            </ExplanationStep>
          </ol>
        </section>
      </div>

      <div className="mt-6 flex justify-end gap-3 sm:gap-4">
        <button
          type="button"
          onClick={onPrevious}
          disabled={stepIndex === 0}
          className="flex h-14 items-center gap-2 rounded-full border-2 border-line bg-white px-6 text-lg font-bold transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line sm:px-8"
        >
          <span aria-hidden="true">←</span> Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          className="flex h-14 items-center gap-2 rounded-full bg-accent px-7 text-lg font-bold shadow-[0_8px_20px_-8px_rgba(253,176,34,0.9)] transition-colors hover:bg-accent-hover active:scale-[0.99] sm:px-9"
        >
          {isLast ? "Finish" : "Next"} <span aria-hidden="true">→</span>
        </button>
      </div>
    </div>
    </div>
  );
}

function ExplanationStep({ number, children }: { number: number; children: ReactNode }) {
  return (
    <li className="flex items-center gap-4">
      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent text-lg font-bold" aria-hidden="true">
        {number}
      </span>
      <span>{children}</span>
    </li>
  );
}
