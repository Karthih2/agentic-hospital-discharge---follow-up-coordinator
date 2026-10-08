import { motion, useReducedMotion } from 'motion/react';

/** A check mark that draws its own stroke. Shown when a task is marked done. */
export default function DrawCheck({ size = 18, className = '' }: { size?: number; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <motion.path d="M4 12.5l5 5L20 6.5" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round"
        initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.35, ease: 'easeOut' }} />
    </svg>
  );
}
