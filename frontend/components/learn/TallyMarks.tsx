import type { CSSProperties } from "react";
import type { TallyVisual } from "@/lib/useVoiceChat";

// Traditional tally marks: four upright sticks crossed by a diagonal makes five.
const SPACING = 20;
const HEIGHT = 100;
const GROUP_STEP = 3 * SPACING + 38; // distance between two groups of five
const CLUSTER_GAP = 60; // empty space between the two numbers being added
const STEP = 0.45; // seconds between two sticks being drawn
const INK = "#121212";
const ACCENT = "#fdb022";
const DANGER = "#b42318";

interface Mark {
  diagonal: boolean;
  x1: number;
  x2: number;
}

/** Positions of `count` tally marks whose first group starts at x0. */
function cluster(count: number, x0: number): Mark[] {
  return Array.from({ length: count }, (_, i) => {
    const groupX = x0 + Math.floor(i / 5) * GROUP_STEP;
    const position = i % 5;
    if (position === 4) return { diagonal: true, x1: groupX - 10, x2: groupX + 3 * SPACING + 10 };
    const x = groupX + position * SPACING;
    return { diagonal: false, x1: x, x2: x };
  });
}

function width(marks: Mark[]) {
  return marks.reduce((far, mark) => Math.max(far, mark.x1, mark.x2), 0) + 12;
}

interface Drawn extends Mark {
  color: string;
  animation: string;
  removed?: boolean;
  dx?: number;
}

const draw = (delay: number) => `tally-draw 0.4s ease-out ${delay}s both`;
const appear = (delay: number) => `tally-appear 0.5s ease-out ${delay}s both`;
const cross = (delay: number) => `tally-cross 0.6s ease-out ${delay}s both`;

function build({ op, a, b, step }: TallyVisual): { marks: Drawn[]; label: string | null; labelDelay: number; span: number } {
  const total = op === "add" ? a + b : a - b;
  const explain = step === "explain";
  const first = cluster(a, 0);

  if (op === "add") {
    const second = cluster(b, width(first) + CLUSTER_GAP);
    const separate = (animateFirst: boolean, animateSecond: boolean): Drawn[] => [
      ...first.map((m, i) => ({ ...m, color: INK, animation: animateFirst ? draw(i * STEP) : "" })),
      ...second.map((m, i) => ({
        ...m,
        color: ACCENT,
        animation: animateSecond ? draw((animateFirst ? a * STEP + 0.3 : 0) + i * STEP) : "",
      })),
    ];
    if (step === "a") return { marks: separate(true, false).slice(0, a), label: null, labelDelay: 0, span: width(second) };
    if (step === "b") return { marks: separate(false, true), label: null, labelDelay: 0, span: width(second) };
    if (step === "explain") {
      const delay = (a + b) * STEP + 0.6;
      return { marks: separate(true, true), label: `${a} + ${b} = ${total}`, labelDelay: delay, span: width(second) };
    }
    // "sum": the two groups slide together into one tally of the total.
    const apart = [...first, ...second];
    const merged = cluster(total, 0);
    const marks = merged.map((m, i): Drawn => {
      const old = apart[i];
      const same = old && old.diagonal === m.diagonal;
      return {
        ...m,
        color: i < a ? INK : ACCENT,
        animation: same ? "tally-slide 1s ease-in-out both" : appear(0.9),
        dx: same ? old.x1 - m.x1 : 0,
      };
    });
    return { marks, label: `= ${total}`, labelDelay: 1.2, span: width(second) };
  }

  // subtraction: the last b sticks are crossed out
  const marks: Drawn[] = first.map((m, i) => {
    const removed = i >= a - b;
    if (step === "a") return { ...m, color: INK, animation: draw(i * STEP) };
    if (step === "cross") return { ...m, color: INK, removed, animation: removed ? cross((i - (a - b)) * 0.5) : "" };
    if (step === "left") return { ...m, color: removed ? DANGER : ACCENT, removed, animation: "" };
    return {
      ...m,
      color: INK,
      removed,
      animation: removed ? `${draw(i * STEP)}, ${cross(a * STEP + 0.4 + (i - (a - b)) * 0.5)}` : draw(i * STEP),
    };
  });
  const label = step === "left" ? `= ${total}` : explain ? `${a} - ${b} = ${total}` : null;
  return { marks, label, labelDelay: explain ? a * STEP + b * 0.5 + 1 : 0.3, span: width(first) };
}

export function TallyMarks({ visual }: { visual: TallyVisual }) {
  const { marks, label, labelDelay, span } = build(visual);
  const left = visual.step === "left";
  return (
    <div className="flex flex-col items-center gap-3" role="img" aria-label={`Sticks for ${visual.a} ${visual.op === "add" ? "plus" : "minus"} ${visual.b}`}>
      <svg viewBox={`0 0 ${Math.max(span, 60)} ${HEIGHT}`} className="h-24 w-auto max-w-full sm:h-36" fill="none">
        {marks.map((mark, i) => {
          const style = {
            animation: mark.animation || undefined,
            opacity: left && mark.removed ? 0.3 : undefined,
            "--dx": `${mark.dx ?? 0}px`,
          } as CSSProperties;
          return mark.diagonal ? (
            <line key={i} x1={mark.x1} y1={HEIGHT - 8} x2={mark.x2} y2={8} stroke={mark.color} strokeWidth={8} strokeLinecap="round" pathLength={1} strokeDasharray={1} style={style} />
          ) : (
            <line key={i} x1={mark.x1} y1={8} x2={mark.x2} y2={HEIGHT - 8} stroke={mark.color} strokeWidth={8} strokeLinecap="round" pathLength={1} strokeDasharray={1} style={style} />
          );
        })}
      </svg>
      {label && (
        <p className="text-4xl font-extrabold tracking-tight sm:text-6xl" style={{ animation: appear(labelDelay) }}>
          {label}
        </p>
      )}
    </div>
  );
}
