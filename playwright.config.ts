import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // --------------- General Test Settings ---------------
  testDir: 'tests/e2e',
  timeout: 600_000, // 10 minutes for long API jobs
  fullyParallel: true,
  retries: 0,

  // Test report
  reporter: 'html',

  // --------------- Shared Browser Context Settings ---------------
  use: {
    baseURL: 'http://localhost:5000',
    viewport: { width: 1280, height: 800 },

    // Artifacts
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },

  // --------------- Browser Projects ---------------
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        headless: true,
      },
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        headless: true,
      },
    },
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        headless: true,    // Safari is unstable in headless mode
      },
    },
  ],
});
