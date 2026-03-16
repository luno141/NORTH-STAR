import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        base: "#03060B",
        ink: "#EEF3FB",
        accent: "#E5EBF4",
        warm: "#AAB2C0",
        panel: "#080D14"
      }
    }
  },
  plugins: []
};

export default config;
