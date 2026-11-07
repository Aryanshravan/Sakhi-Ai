import { dogHeight, type DogRect } from "./useDogRect";

// One mascot element for the whole experience. Changing `rect` animates it from
// the welcome screen to the bottom-left corner (and back) instead of swapping images.
export function Husky({ rect }: { rect: DogRect | null }) {
  if (!rect) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- animated fixed element; sizes come from layout
    <img
      src="/sakhi-husky.png"
      alt="Sakhi, your learning companion"
      width={rect.width}
      height={dogHeight(rect.width)}
      draggable={false}
      className="pointer-events-none fixed z-20 select-none transition-[left,top,width,height] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
      style={{ left: rect.left, top: rect.top, width: rect.width, height: dogHeight(rect.width) }}
    />
  );
}
