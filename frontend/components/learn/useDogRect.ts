"use client";

import { useLayoutEffect, useState, type RefObject } from "react";

export const DOG_RATIO = 836 / 660; // height / width of the mascot image
const CORNER_GAP = 8;

export interface DogRect {
  left: number;
  top: number;
  width: number;
}

export function dogHeight(width: number) {
  return width * DOG_RATIO;
}

function cornerWidth(viewportWidth: number) {
  return Math.round(Math.min(170, Math.max(96, viewportWidth * 0.11)));
}

/**
 * Where the mascot should be: on top of the welcome screen's placeholder, or in
 * the bottom-left corner while learning. Moving between the two is what the
 * CSS transition on the mascot animates.
 */
export function useDogRect(
  atWelcome: boolean,
  anchorRef: RefObject<HTMLElement | null>,
  ready: boolean,
): DogRect | null {
  const [rect, setRect] = useState<DogRect | null>(null);

  useLayoutEffect(() => {
    if (!ready) return;
    function update() {
      if (atWelcome) {
        const anchor = anchorRef.current?.getBoundingClientRect();
        if (anchor) setRect({ left: anchor.left, top: anchor.top, width: anchor.width });
      } else {
        const width = cornerWidth(window.innerWidth);
        setRect({ left: CORNER_GAP, top: window.innerHeight - dogHeight(width) - CORNER_GAP, width });
      }
    }
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, { passive: true });
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update);
    };
  }, [atWelcome, anchorRef, ready]);

  return rect;
}
