import { motion } from "framer-motion";

const ribbons = [
  {
    className: "cf-cinematic-ribbon is-primary",
    animate: {
      x: ["-4%", "3%", "-2%"],
      y: ["-3%", "4%", "-2%"],
      rotate: [-10, -4, -12],
      scale: [1, 1.08, 0.98],
    },
    transition: { duration: 24, repeat: Infinity, repeatType: "mirror" as const, ease: [0.45, 0, 0.55, 1] as const },
  },
  {
    className: "cf-cinematic-ribbon is-secondary",
    animate: {
      x: ["4%", "-2%", "2%"],
      y: ["2%", "-3%", "3%"],
      rotate: [8, 14, 10],
      scale: [1.02, 0.96, 1.04],
    },
    transition: { duration: 28, repeat: Infinity, repeatType: "mirror" as const, ease: [0.45, 0, 0.55, 1] as const },
  },
  {
    className: "cf-cinematic-ribbon is-tertiary",
    animate: {
      x: ["-1%", "2%", "-3%"],
      y: ["5%", "1%", "6%"],
      rotate: [-3, 4, -1],
      scale: [0.94, 1.02, 0.97],
    },
    transition: { duration: 32, repeat: Infinity, repeatType: "mirror" as const, ease: [0.45, 0, 0.55, 1] as const },
  },
];

const glows = [
  {
    className: "cf-cinematic-orb is-left",
    animate: { x: ["-2%", "3%", "-1%"], y: ["0%", "4%", "1%"], scale: [1, 1.05, 0.98] },
    transition: { duration: 22, repeat: Infinity, repeatType: "mirror" as const, ease: [0.45, 0, 0.55, 1] as const },
  },
  {
    className: "cf-cinematic-orb is-right",
    animate: { x: ["2%", "-3%", "1%"], y: ["3%", "-1%", "4%"], scale: [1.03, 0.97, 1.02] },
    transition: { duration: 26, repeat: Infinity, repeatType: "mirror" as const, ease: [0.45, 0, 0.55, 1] as const },
  },
];

export function CinematicBackground({ fixed = true }: { fixed?: boolean }) {
  return (
    <div className={`cf-cinematic-bg ${fixed ? "" : "is-contained"}`.trim()} aria-hidden="true">
      <div className="cf-cinematic-bg-gradient" />
      <div className="cf-cinematic-bg-grid" />
      {glows.map((glow) => (
        <motion.div
          key={glow.className}
          className={glow.className}
          animate={glow.animate}
          transition={glow.transition}
        />
      ))}
      {ribbons.map((ribbon) => (
        <motion.div
          key={ribbon.className}
          className={ribbon.className}
          animate={ribbon.animate}
          transition={ribbon.transition}
        />
      ))}
      <div className="cf-cinematic-bg-vignette" />
      <div className="cf-cinematic-bg-noise" />
    </div>
  );
}
