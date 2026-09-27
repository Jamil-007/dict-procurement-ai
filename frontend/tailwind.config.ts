import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        // The AI Analyst palette. Named literally so markup reads the same as
        // the design reference in html-proto/ai-analyst.html.
        navy: "#123B6D",
        brand: "#1E5AA8",
        sky: "#EAF3FB",
        page: "#F5F9FD",
        ink: "#172B4D",
        subtle: "#64748B",
        line: "#D9E5F0",
        critical: "#B42318",
        warning: "#B54708",
        compliant: "#067647",
        // Finding severity. One value per level, used at full strength for the
        // card's left bar and legend dot and at /10 and /20 for chip fills and
        // borders, so the accent stays the same hue wherever a level appears.
        // Every value clears 4.5:1 on white, which is why medium is a deep
        // yellow rather than a bright one.
        sev: {
          critical: "#B42318",
          medium: "#A16207",
          low: "#1E5AA8",
          info: "#64748B",
          compliant: "#067647",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        // Inter everywhere (this branch's design). The stack after it is what
        // renders while the webfont loads, and on the rare client that blocks it.
        sans: [
          "var(--font-inter)",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        // Accent only — signature and attestation lines in report
        // endorsements. Georgia is the fallback because it ships everywhere
        // and is the closest formal serif to Playfair at text sizes.
        serif: ["var(--font-playfair)", "Georgia", "serif"],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
