import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E configuration (SCRUM-22).
 *
 * Setup:
 *   1. npm install          (installs @playwright/test)
 *   2. npx playwright install chromium
 *   3. In a separate terminal: DEMO_MODE=true uvicorn main:app --port 8000
 *   4. npm run test:e2e
 *
 * The tests use the backend's demo data layer (DEMO_MODE=true) so no live
 * Jira or GitHub credentials are required.
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: 'html',

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: [
    {
      // FastAPI backend — must be started with DEMO_MODE=true
      command: 'DEMO_MODE=true uvicorn main:app --port 8000',
      url: 'http://localhost:8000/api/health',
      cwd: '../',
      reuseExistingServer: true,
      timeout: 15000,
    },
    {
      // Vite dev server — proxies /api to :8000
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 15000,
    },
  ],
})
