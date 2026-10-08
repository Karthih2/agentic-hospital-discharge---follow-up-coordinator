'use client';

import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from 'motion/react';
import React, { useRef } from 'react';

interface ScrollRevealProps {
  children: string;
  baseOpacity?: number;
  className?: string;
  textClassName?: string;
}

function Word({ word, progress, range, base }: { word: string; progress: MotionValue<number>; range: [number, number]; base: number }) {
  const opacity = useTransform(progress, range, [base, 1]);
  const blur = useTransform(progress, range, ['blur(4px)', 'blur(0px)']);
  return <motion.span className="mr-[0.25em] inline-block" style={{ opacity, filter: blur }}>{word}</motion.span>;
}

/** React Bits ScrollReveal, rewritten on `motion`: each word fades and unblurs as the block scrolls into view.
 * It takes exactly the height of its text (no tall scrub container, so no empty gap underneath).
 * Under reduced motion the whole sentence is shown at once. */
const ScrollReveal: React.FC<ScrollRevealProps> = ({ children, baseOpacity = 0.15, className = '', textClassName = '' }) => {
  const ref = useRef<HTMLParagraphElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 90%', 'start 45%'] });
  const words = children.split(/\s+/).filter(Boolean);
  if (reduce) return <p className={`${className} ${textClassName}`}>{children}</p>;
  return (
    <p ref={ref} className={`${className} ${textClassName}`}>
      {words.map((w, i) => {
        const a = i / words.length, b = Math.min(1, (i + 1.5) / words.length);
        return <Word key={i} word={w} progress={scrollYProgress} range={[a, b]} base={baseOpacity} />;
      })}
    </p>
  );
};

export default ScrollReveal;
