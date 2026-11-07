// Prototype lesson content for the UI. The real curriculum comes later.

export interface AdditionStep {
  a: number;
  b: number;
  /** What Sakhi says (and shows in her speech bubble) on this step. */
  sakhi: string;
}

export const LESSON = {
  subject: "Mathematics",
  title: "Addition of Two-Digit Numbers",
  intro: "Let’s learn how to add two-digit numbers with an example!",
  steps: [
    { a: 23, b: 14, sakhi: "See? We added the tens and ones separately!" },
    { a: 31, b: 25, sakhi: "Here is another one. Tens first, then ones!" },
    { a: 42, b: 17, sakhi: "You are getting it! Add the tens, then the ones." },
    { a: 54, b: 23, sakhi: "Nice work! Same trick again." },
    { a: 62, b: 36, sakhi: "Last one! Tens, ones, then combine." },
  ] satisfies AdditionStep[],
};

export interface Breakdown {
  tens: [number, number, number];
  ones: [number, number, number];
  total: number;
}

/** Split an addition (without carrying) into its tens and ones parts. */
export function breakDown({ a, b }: AdditionStep): Breakdown {
  const tensA = Math.floor(a / 10) * 10;
  const tensB = Math.floor(b / 10) * 10;
  const onesA = a % 10;
  const onesB = b % 10;
  return {
    tens: [tensA, tensB, tensA + tensB],
    ones: [onesA, onesB, onesA + onesB],
    total: a + b,
  };
}
