"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { type FC, useCallback, useLayoutEffect, useRef, useState } from "react";

export const ThemeToggle: FC = () => {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [rotating, setRotating] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Avoid hydration mismatch — runs synchronously before paint
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useLayoutEffect(() => setMounted(true), []);

  const toggle = useCallback(() => {
    if (rotating || !mounted) return;
    const next = resolvedTheme === "light" ? "dark" : "light";
    setRotating(true);
    setTheme(next);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setRotating(false), 300);
  }, [mounted, resolvedTheme, rotating, setTheme]);

  const handleKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggle();
      }
    },
    [toggle],
  );

  if (!mounted) {
    return <div className="h-9 w-9 rounded-full" aria-hidden="true" />;
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggle}
      onKeyDown={handleKey}
      className="group relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border bg-surface transition-all duration-200 hover:border-foreground/20 hover:bg-muted active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/40"
    >
      <span
        className="relative flex h-4 w-4 items-center justify-center overflow-hidden"
        style={{ animation: rotating ? "theme-icon-rotate 0.3s ease-in-out" : "none" }}
      >
        <Sun
          className="absolute h-4 w-4 text-foreground transition-all duration-300"
          style={{
            opacity: isDark ? 0 : 1,
            transform: isDark ? "rotate(-90deg) scale(0.5)" : "rotate(0deg) scale(1)",
          }}
        />
        <Moon
          className="absolute h-4 w-4 text-foreground transition-all duration-300"
          style={{
            opacity: isDark ? 1 : 0,
            transform: isDark ? "rotate(0deg) scale(1)" : "rotate(90deg) scale(0.5)",
          }}
        />
      </span>
    </button>
  );
};