import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      colors: {
        bg: "hsl(var(--bg) / <alpha-value>)",
        surface: "hsl(var(--surface) / <alpha-value>)",
        border: "hsl(var(--border) / <alpha-value>)",
        fg: "hsl(var(--fg) / <alpha-value>)",
        muted: "hsl(var(--muted) / <alpha-value>)",
        brand: "hsl(var(--brand) / <alpha-value>)",
        "brand-fg": "hsl(var(--brand-fg) / <alpha-value>)",
        danger: "hsl(var(--danger) / <alpha-value>)",
        success: "hsl(var(--success) / <alpha-value>)",
      },
    },
  },
  plugins: [],
} satisfies Config;
