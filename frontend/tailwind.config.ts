import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        navy: "#1a365d",
        "navy-light": "#2b6cb0",
        accent: "#4299e1",
      },
    },
  },
  plugins: [],
};

export default config;
