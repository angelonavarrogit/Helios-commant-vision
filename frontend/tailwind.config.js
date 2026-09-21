/** @type {import('tailwindcss').Config} */
// HELIOS COMMAND theme — brand identity of ANGELO NAVARRO / Sistema AN.
// Palette per docs/brand.md: forest green dominates; teal is an accent only.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        helios: {
          bg: "#071612", // verde profundo (fondo)
          panel: "#123C2A", // verde bosque (primario / paneles)
          border: "#1F3D2B", // verde oscuro (secundario / bordes)
          accent: "#00D1A7", // teal (acento — usar con moderación)
          text: "#FFFFFF", // blanco
          muted: "#6B7280", // gris
          ok: "#00D1A7", // estados positivos usan el teal de marca
          warn: "#E0A44A", // ámbar sobrio para advertencias
          danger: "#E5534B", // rojo sobrio para errores
        },
      },
    },
  },
  plugins: [],
};
