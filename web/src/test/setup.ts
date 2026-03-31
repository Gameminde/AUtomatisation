import { cleanup } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { afterEach, expect, vi } from "vitest";

expect.extend(matchers);

const MOTION_PROP_KEYS = new Set([
  "animate",
  "exit",
  "initial",
  "layout",
  "layoutId",
  "transition",
  "variants",
  "whileFocus",
  "whileHover",
  "whileInView",
  "whileTap",
  "viewport",
]);

vi.mock("framer-motion", async () => {
  const React = await import("react");
  type MockMotionProps = Record<string, unknown> & { children?: React.ReactNode };

  function stripMotionProps(props: Record<string, unknown>) {
    const next = { ...props };
    for (const key of MOTION_PROP_KEYS) {
      delete next[key];
    }
    return next;
  }

  const cache = new Map<PropertyKey, React.ComponentType<Record<string, unknown>>>();
  const motion = new Proxy({}, {
    get(_target, tag: string | symbol) {
      if (!cache.has(tag)) {
        const MotionTag = React.forwardRef<HTMLElement, MockMotionProps>(({ children, ...props }, ref) =>
          React.createElement(String(tag), { ...stripMotionProps(props), ref }, children as React.ReactNode),
        );
        MotionTag.displayName = `MockMotion(${String(tag)})`;
        cache.set(tag, MotionTag as unknown as React.ComponentType<Record<string, unknown>>);
      }
      return cache.get(tag);
    },
  });

  return {
    AnimatePresence: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    motion,
  };
});

afterEach(() => {
  cleanup();
});
