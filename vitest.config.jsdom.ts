// vitest.config.jsdom.ts
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  resolve: {
    alias: {
      "@shared": path.resolve("./shared"),
      "@": path.resolve("./client/src"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    testTimeout: 30000, // 30 seconds
    include: ["tests/server/integration/**/*.{test,spec}.tsx"],
    coverage: { provider: "v8" },
  },

});
