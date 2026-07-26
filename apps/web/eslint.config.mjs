import eslint from "@eslint/js";
import nextVitals from "eslint-config-next/core-web-vitals";

const config = [
  eslint.configs.recommended,
  ...nextVitals,
  {
    ignores: [".next/**", "node_modules/**"],
  },
];

export default config;
