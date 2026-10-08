import Lenis from 'lenis';
import { useReducedMotion } from 'motion/react';
import { useEffect, type ReactNode } from 'react';

/** Smooth scrolling. Anchor jumps stop 5rem (the sticky header) below the top. Off under reduced motion. */
export default function SmoothScroll({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) return;
    const lenis = new Lenis({ anchors: { offset: -80 }, duration: 1.1 });
    let id = requestAnimationFrame(function raf(t) { lenis.raf(t); id = requestAnimationFrame(raf); });
    return () => { cancelAnimationFrame(id); lenis.destroy(); };
  }, [reduce]);
  return <>{children}</>;
}
