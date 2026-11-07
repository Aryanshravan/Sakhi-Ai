import { dogHeight, type DogRect } from "./useDogRect";

// Sakhi's words, shown next to the mascot so the child can read along while she speaks.
export function SpeechBubble({ text, dog }: { text: string; dog: DogRect }) {
  const left = dog.left + dog.width * 0.92;
  return (
    <div
      key={text}
      role="status"
      aria-live="polite"
      className="fixed z-20 animate-fade-up"
      style={{ left, bottom: window.innerHeight - dog.top - dogHeight(dog.width) + dogHeight(dog.width) * 0.42, maxWidth: `min(250px, calc(100vw - ${left + 12}px))` }}
    >
      <div className="relative rounded-3xl border-2 border-accent bg-white px-4 py-3 text-center text-base font-semibold leading-snug shadow-sm">
        {text}
        <span className="absolute -left-2 bottom-3 size-4 rotate-45 border-b-2 border-l-2 border-accent bg-white" aria-hidden="true" />
      </div>
    </div>
  );
}
