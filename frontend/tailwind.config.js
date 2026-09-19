/** @type {import('tailwindcss').Config} */
// HELIOS COMMAND theme: a clean, dark "control center" palette.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        helios: {
          bg: "#0b1120",
          panel: "#111a2e",
          border: "#1e2a44",
          accent: "#f5a524", // sun/HELIOS amber
          text: "#e6edf7",
          muted: "#8ba0c0",
          ok: "#3fb950",
          warn: "#f0a020",
          danger: "#f85149",
        },
      },
    },
  },
  plugins: [],
};
