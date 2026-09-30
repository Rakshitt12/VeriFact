import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { motion, useMotionValue, useSpring, useTransform, type HTMLMotionProps } from "framer-motion";
import { SPRING } from "@/lib/motion";

interface TiltCardProps extends HTMLMotionProps<"div"> {
  children: ReactNode;
  className?: string;
  maxTilt?: number; // max tilt degrees, default 3.0deg
  perspective?: number; // default 1000px
  disabled?: boolean;
}

export function TiltCard({
  children,
  className = "",
  maxTilt = 3.0,
  perspective = 1000,
  disabled = false,
  ...rest
}: TiltCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [isTouchDevice, setIsTouchDevice] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const touchQuery = window.matchMedia("(pointer: coarse)");
      const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

      setIsTouchDevice(touchQuery.matches);
      setPrefersReducedMotion(motionQuery.matches);

      const handleTouchChange = (e: MediaQueryListEvent) => setIsTouchDevice(e.matches);
      const handleMotionChange = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);

      touchQuery.addEventListener("change", handleTouchChange);
      motionQuery.addEventListener("change", handleMotionChange);

      return () => {
        touchQuery.removeEventListener("change", handleTouchChange);
        motionQuery.removeEventListener("change", handleMotionChange);
      };
    }
  }, []);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Smooth springs for rotation
  const rotateXSpring = useSpring(mouseY, SPRING.tiltReturn);
  const rotateYSpring = useSpring(mouseX, SPRING.tiltReturn);

  // Transform normalized [-0.5, 0.5] coordinates to degrees
  const rotateX = useTransform(rotateXSpring, [-0.5, 0.5], [maxTilt, -maxTilt]);
  const rotateY = useTransform(rotateYSpring, [-0.5, 0.5], [-maxTilt, maxTilt]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (disabled || isTouchDevice || prefersReducedMotion || !cardRef.current) return;

      const rect = cardRef.current.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;

      // Mouse position from center: -0.5 (left/top) to +0.5 (right/bottom)
      const xPct = (e.clientX - rect.left) / width - 0.5;
      const yPct = (e.clientY - rect.top) / height - 0.5;

      mouseX.set(xPct);
      mouseY.set(yPct);
    },
    [disabled, isTouchDevice, prefersReducedMotion, mouseX, mouseY],
  );

  const handleMouseLeave = useCallback(() => {
    mouseX.set(0);
    mouseY.set(0);
  }, [mouseX, mouseY]);

  const shouldApplyTilt = !disabled && !isTouchDevice && !prefersReducedMotion;

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={className}
      style={{
        transformStyle: "preserve-3d",
        perspective: `${perspective}px`,
        rotateX: shouldApplyTilt ? rotateX : 0,
        rotateY: shouldApplyTilt ? rotateY : 0,
        ...rest.style,
      }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
