/** Design tokens mirror Blackline Estimating PRO (monochrome, square, Chivo/Inter/JetBrains Mono). */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["Chivo", "sans-serif"],
        body: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        card: "hsl(var(--card))",
        green: { fg: "hsl(var(--green-fg))", bg: "hsl(var(--green-bg))", line: "hsl(var(--green-line))" },
        amber: { fg: "hsl(var(--amber-fg))", bg: "hsl(var(--amber-bg))", line: "hsl(var(--amber-line))" },
        red: { fg: "hsl(var(--red-fg))", bg: "hsl(var(--red-bg))", line: "hsl(var(--red-line))" },
      },
      borderRadius: { DEFAULT: "0", sm: "0", md: "0", lg: "0", full: "9999px" },
      fontSize: { "2xs": ["0.6875rem", { lineHeight: "1rem" }] },
    },
  },
  plugins: [],
};
