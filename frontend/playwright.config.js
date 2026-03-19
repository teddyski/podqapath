import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E configuration (SCRUM-22).
 *
 * Setup:
 *   1. npm install          (installs @playwright/test)
 *   2. npx playwright install chromium
 *   3. In a separate terminal: cd backend && DEMO_MODE=true mix phx.server
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
      // Phoenix backend — must be started with DEMO_MODE=true
      command: 'DEMO_MODE=true mix phx.server',
      url: 'http://localhost:4000/api/health',
      cwd: '../backend',
      reuseExistingServer: true,
      timeout: 20000,
    },
    {
      // Vite dev server — proxies /api to :4000
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 15000,
    },
  ],
})
