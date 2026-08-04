import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["tests/e2e/**"],
    setupFiles: ["./src/test/setup.ts"],
    environmentOptions: {
      jsdom: { url: "http://localhost" },
    },
  },
});
