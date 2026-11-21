import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        salt: "#F2F5F3", paper: "#FBFCFB", ink: "#12303F", mute: "#5B7280", line: "#D5DFDB",
        sea: { DEFAULT: "#1D6B80", dark: "#14505F", soft: "#E1EEF1" },
        murex: { DEFAULT: "#6A2C5E", soft: "#F1E6EE" },
        ok: { DEFAULT: "#2F7D5B", soft: "#E3F1EA" },
        warn: { DEFAULT: "#9A6200", soft: "#FBF0D9" },
        bad: { DEFAULT: "#B3261E", soft: "#FBE7E5" },
      },
      fontFamily: { display: ["var(--font-display)", "system-ui", "sans-serif"], body: ["var(--font-body)", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
