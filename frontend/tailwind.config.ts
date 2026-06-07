import type { Config } from "tailwindcss";

export default {
  darkMode: ["class", ".dark"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0A0A0A",
          secondary: "#111111",
          tertiary: "#1a1a1a",
        },
        border: {
          subtle: "rgba(255, 255, 255, 0.06)",
          muted: "rgba(255, 255, 255, 0.1)",
        },
        accent: {
          DEFAULT: "#3B82F6",
          cyan: "#06B6D4",
          glow: "rgba(59, 130, 246, 0.3)",
        },
        surface: {
          glass: "rgba(255, 255, 255, 0.03)",
          elevated: "rgba(255, 255, 255, 0.06)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "Menlo", "monospace"],
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "fade-in": "fade-in 0.4s ease-out",
        "slide-up": "slide-up 0.3s ease-out",
        "slide-in-right": "slide-in-right 0.3s ease-out",
        "node-activate": "node-activate 0.6s ease-out",
        "edge-flow": "edge-flow 1.5s linear infinite",
        "spin-slow": "spin 3s linear infinite",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "0.4", transform: "scale(0.98)" },
          "50%": { opacity: "1", transform: "scale(1.02)" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "node-activate": {
          "0%": { boxShadow: "0 0 0 0 rgba(59, 130, 246, 0.6)" },
          "70%": { boxShadow: "0 0 0 12px rgba(59, 130, 246, 0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(59, 130, 246, 0)" },
        },
        "edge-flow": {
          "0%": { backgroundPosition: "0% 50%" },
          "100%": { backgroundPosition: "200% 50%" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
} satisfies Config;