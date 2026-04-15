import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  resolve: {
    alias: {
      "@shared": path.resolve(__dirname, "shared"),
      "@": path.resolve(__dirname, "client/src"),
    },
  },
  test: {
    globals: true,
    environment: "node", // Node environment for server/api tests
    include: [
      "tests/server/unit/**/*.{test,spec}.ts"
    ],
    coverage: { provider: "v8" },
  },
});
