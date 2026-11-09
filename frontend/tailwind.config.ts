import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // ARIA control-room accent — safety amber on warm graphite.
        brand: {
          50: "#fdf4e3",
          100: "#f8e5c2",
          200: "#efcf95",
          300: "#e3b265",
          400: "#d3953f",
          500: "#b97b2d",
          600: "#9a6122",
          700: "#7a4a1c",
          800: "#593617",
          900: "#3d2511",
          950: "#24160a",
        },
        ink: {
          50: "#f6f4ef",
          100: "#ece8df",
          200: "#d8d2c6",
          300: "#bcb4a5",
          400: "#a69e8e",
          500: "#8f8676",
          600: "#6f685b",
          700: "#514b41",
          800: "#39352e",
          900: "#25221d",
          950: "#0e0f0c",
        },
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
