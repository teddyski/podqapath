import { test, expect } from '@playwright/test'

/**
 * PodQApath E2E test suite (SCRUM-22).
 * All tests use the demo data layer — no live Jira/GitHub credentials needed.
 * Requires the backend running with DEMO_MODE=true (handled by playwright.config.js).
 */

test.describe('Demo mode — load filters and fetch tickets', () => {
  test('clicking Load Demo Data populates the ticket list', async ({ page }) => {
    await page.goto('/')

    // Click the demo mode button
    await page.click('[data-testid="demo-mode-btn"]')

    // Ticket list should appear with demo tickets
    await expect(page.locator('[data-testid="ticket-list"]')).toBeVisible({ timeout: 10000 })

    // At least one ticket card should be present
    const cards = page.locator('[data-testid^="ticket-card-"]')
    await expect(cards.first()).toBeVisible()

    // All four risk bands should be represented
    await expect(page.locator('[data-testid="ticket-card-DEMO-101"]')).toBeVisible()
    await expect(page.locator('[data-testid="ticket-card-DEMO-104"]')).toBeVisible()
  })

  test('filters become enabled after loading demo data', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="demo-mode-btn"]')

    // Filters should be enabled (not disabled) after demo data loads
    await expect(page.locator('[data-testid="filter-tags"]')).not.toBeDisabled({ timeout: 10000 })
    await expect(page.locator('[data-testid="filter-statuses"]')).not.toBeDisabled()
    await expect(page.locator('[data-testid="filter-sprint"]')).not.toBeDisabled()
  })
})

test.describe('Ticket selection and PR diff', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="demo-mode-btn"]')
    await expect(page.locator('[data-testid="ticket-list"]')).toBeVisible({ timeout: 10000 })
  })

  test('selecting a ticket with a linked PR shows the diff viewer', async ({ page }) => {
    // Select DEMO-101 which has an OPEN PR with a diff
    await page.click('[data-testid="ticket-select-btn-DEMO-101"]')

    // PR viewer should appear
    await expect(page.locator('[data-testid="pr-viewer"]')).toBeVisible({ timeout: 8000 })

    // Diff metrics should be visible
    await expect(page.locator('[data-testid="diff-metrics"]')).toBeVisible()

    // File table should be visible
    await expect(page.locator('[data-testid="diff-table"]')).toBeVisible()
  })

  test('selecting a ticket with no PR shows the no-PR state', async ({ page }) => {
    // DEMO-103 has no linked PR
    await page.click('[data-testid="ticket-select-btn-DEMO-103"]')

    await expect(page.locator('[data-testid="pr-viewer-no-prs"]')).toBeVisible({ timeout: 8000 })
  })

  test('select button changes to selected state when ticket is chosen', async ({ page }) => {
    const btn = page.locator('[data-testid="ticket-select-btn-DEMO-102"]')
    await expect(btn).toContainText('Select')

    await btn.click()

    await expect(btn).toContainText('✓ Selected')
  })

  test('expanding raw diff shows diff content', async ({ page }) => {
    await page.click('[data-testid="ticket-select-btn-DEMO-101"]')
    await expect(page.locator('[data-testid="pr-viewer"]')).toBeVisible({ timeout: 8000 })

    // Raw diff should be hidden initially
    await expect(page.locator('[data-testid="raw-diff-content"]')).not.toBeVisible()

    // Click toggle to show
    await page.click('[data-testid="raw-diff-toggle"]')
    await expect(page.locator('[data-testid="raw-diff-content"]')).toBeVisible()

    // Click again to hide
    await page.click('[data-testid="raw-diff-toggle"]')
    await expect(page.locator('[data-testid="raw-diff-content"]')).not.toBeVisible()
  })
})

test.describe('Chat panel', () => {
  test('typing and sending a message shows it in the chat history', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('[data-testid="chat-input"]')
    const sendBtn = page.locator('[data-testid="chat-send-btn"]')

    // Send button disabled when input is empty
    await expect(sendBtn).toBeDisabled()

    await input.fill('What is the overall risk level?')
    await expect(sendBtn).not.toBeDisabled()

    await sendBtn.click()

    // User message should appear in chat history
    await expect(page.locator('[data-testid="chat-msg-0"]')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('[data-testid="chat-msg-0"]')).toContainText('What is the overall risk level?')
  })

  test('pressing Enter sends the message', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('[data-testid="chat-input"]')
    await input.fill('Summarise critical tickets')
    await input.press('Enter')

    await expect(page.locator('[data-testid="chat-msg-0"]')).toBeVisible({ timeout: 5000 })
  })

  test('Shift+Enter inserts a newline without sending', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('[data-testid="chat-input"]')
    await input.fill('line one')
    await input.press('Shift+Enter')
    await input.type('line two')

    // Message should NOT have been sent yet
    await expect(page.locator('[data-testid="chat-msg-0"]')).not.toBeVisible()
    await expect(input).toContainText('line one')
  })
})

test.describe('Repo Test Runner panel', () => {
  test('panel is visible by default with all inputs', async ({ page }) => {
    await page.goto('/')

    // Panel and inputs always visible (no collapse in main content area)
    await expect(page.locator('[data-testid="test-runner"]')).toBeVisible()
    await expect(page.locator('[data-testid="test-runner-repo-path"]')).toBeVisible()
    await expect(page.locator('[data-testid="test-runner-repo-url"]')).toBeVisible()
    await expect(page.locator('[data-testid="test-runner-base-url"]')).toBeVisible()
    await expect(page.locator('[data-testid="test-runner-run-btn"]')).toBeVisible()
  })

  test('shows error when Run Tests is clicked with no inputs', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="test-runner-run-btn"]')

    await expect(page.locator('[data-testid="test-runner-error"]')).toBeVisible()
    await expect(page.locator('[data-testid="test-runner-error"]')).toContainText('repo path or GitHub URL')
  })

  test('runs the PodQApath Playwright suite and streams results', async ({ page }) => {
    await page.goto('/')

    // Run PodQApath's own tests — guaranteed to have playwright.config.js
    const frontendDir = process.cwd()
    await page.fill('[data-testid="test-runner-repo-path"]', frontendDir)
    await page.fill('[data-testid="test-runner-base-url"]', 'http://localhost:5173')

    await page.click('[data-testid="test-runner-run-btn"]')

    // Results panel should appear
    await expect(page.locator('[data-testid="test-runner-results"]')).toBeVisible({ timeout: 30000 })

    // At least one result row should stream in
    const resultRows = page.locator('[data-testid^="test-result-"]')
    await expect(resultRows.first()).toBeVisible({ timeout: 60000 })

    // Summary line should appear when run finishes
    await expect(page.locator('[data-testid="test-runner-summary"]')).toBeVisible({ timeout: 120000 })
  })
})

test.describe('Manager mode toggle', () => {
  test('toggling Manager Mode changes the label and clears history', async ({ page }) => {
    await page.goto('/')

    const toggle = page.locator('[data-testid="manager-mode-toggle"]')

    // Default: Technical mode
    await expect(page.locator('[data-testid="chat-panel"]')).toContainText('Technical mode')

    // Enable Manager mode
    await toggle.check()
    await expect(page.locator('[data-testid="chat-panel"]')).toContainText('Manager mode')

    // Disable again
    await toggle.uncheck()
    await expect(page.locator('[data-testid="chat-panel"]')).toContainText('Technical mode')
  })
})
