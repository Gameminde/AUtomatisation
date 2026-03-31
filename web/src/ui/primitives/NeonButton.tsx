import { ReactNode, ButtonHTMLAttributes } from "react";
import { motion, MotionProps } from "framer-motion";

type MotionButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & MotionProps;

interface NeonButtonProps extends MotionButtonProps {
  children: ReactNode;
  variant?: "primary" | "ghost";
  busy?: boolean;
  glow?: boolean;
}

export function NeonButton({ children, variant = "primary", busy = false, glow = false, className = "", disabled, ...props }: NeonButtonProps) {
  const baseClass = variant === "ghost" ? "cf-btn-ghost" : "cf-btn";
  const glowClass = glow && !busy ? "cf-btn-generate" : "";
  const busyClass = busy ? "cf-neon-btn-busy cf-btn-generate is-busy" : "";

  return (
    <motion.button
      className={`${baseClass} ${glowClass} ${busyClass} ${className}`}
      disabled={disabled || busy}
      whileHover={disabled || busy ? {} : { scale: 1.02 }}
      whileTap={disabled || busy ? {} : { scale: 0.98 }}
      transition={{ duration: 0.15 }}
      {...props}
    >
      {children}
    </motion.button>
  );
}
