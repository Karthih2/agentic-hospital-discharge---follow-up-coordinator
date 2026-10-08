import { motion, useReducedMotion } from 'motion/react';
import type { ReactNode } from 'react';

/** Section bodies rise a little and fade in once, when they scroll into view. Visible at once if motion is off. */
export default function Reveal({ children, delay = 0, className = '', as = 'div', soft = false }: {
  children: ReactNode; delay?: number; className?: string; as?: 'div' | 'li' | 'section'; soft?: boolean;
}) {
  const reduce = useReducedMotion();
  const M = motion[as];
  return (
    <M className={className} initial={reduce ? false : { opacity: 0, y: soft ? 0 : 18 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-8% 0px' }} transition={{ duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] }}>
      {children}
    </M>
  );
}
