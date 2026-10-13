import type { Transition, Variants } from "framer-motion";

/**
 * Standardized easing curves for enterprise/premium motion design.
 */
export const EASE_OUT = [0.23, 1, 0.32, 1] as const;
export const EASE_IN_OUT = [0.4, 0, 0.2, 1] as const;
export const EASE_SMOOTH = [0.25, 0.1, 0.25, 1] as const;

/**
 * Standardized transition durations (in seconds).
 */
export const DURATION = {
  micro: 0.18,
  button: 0.22,
  cardHover: 0.3,
  cardEntrance: 0.55,
  sectionEntrance: 0.7,
  pageTransition: 0.3,
} as const;

/**
 * Spring configurations for physical interactive responses.
 */
export const SPRING = {
  snappy: { type: "spring", stiffness: 420, damping: 32 } as Transition,
  subtle: { type: "spring", stiffness: 320, damping: 28 } as Transition,
  tabIndicator: { type: "spring", stiffness: 380, damping: 30 } as Transition,
  tiltReturn: { stiffness: 280, damping: 22, mass: 0.5 },
};

/**
 * Controlled page entrance sequence variants for Hero.
 * Assembles background -> kicker -> heading -> supporting text -> verify card -> footnote.
 */
export const heroContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.09,
      delayChildren: 0.04,
    },
  },
};

export const heroKickerVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: EASE_OUT },
  },
};

export const heroHeadingVariants: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: EASE_OUT },
  },
};

export const heroSubVariants: Variants = {
  hidden: { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: EASE_OUT },
  },
};

export const heroCardVariants: Variants = {
  hidden: { opacity: 0, y: 22, scale: 0.985 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.65, ease: EASE_OUT },
  },
};

export const heroFootnoteVariants: Variants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: EASE_OUT },
  },
};

/**
 * Staggered container for card grids (evidence cards, process steps, fact checks, sources).
 */
export const staggerContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.05,
    },
  },
};

/**
 * Controlled card reveal: opacity + upward motion + subtle scale.
 */
export const cardRevealVariants: Variants = {
  hidden: { opacity: 0, y: 20, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: DURATION.cardEntrance,
      ease: EASE_OUT,
    },
  },
};

/**
 * Section scroll reveal variants for whileInView.
 */
export const sectionRevealVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: DURATION.sectionEntrance,
      ease: EASE_OUT,
    },
  },
};

/**
 * Interactive button and micro-control transitions.
 */
export const buttonMotion = {
  whileHover: { scale: 1.015, y: -1 },
  whileTap: { scale: 0.98, y: 0 },
  transition: { duration: DURATION.button, ease: EASE_OUT },
};

export const chipMotion = {
  whileHover: { scale: 1.015, y: -2 },
  whileTap: { scale: 0.97 },
  transition: SPRING.snappy,
};
