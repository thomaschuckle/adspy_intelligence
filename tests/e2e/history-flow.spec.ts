// Note: Enable/Disable parallelism in playwright.config.ts as needed

import { test, expect } from '@playwright/test';

test('history page - load existing job by ID', async ({ page }) => {

  //
  // 1. Navigate to the app
  //
  await page.goto('http://localhost:5000/');

  //
  // 2. Navigate to History page
  //
  const historyLink = page.getByRole('link', { name: 'History' });
  await expect(historyLink).toBeVisible();
  await historyLink.click();

  //
  // 3. Verify history page loaded with job ID input
  //
  const instructionText = page.getByText(/enter your job id to retrieve/i);
  await expect(instructionText).toBeVisible();

  const jobIdInput = page.getByRole('textbox', { name: /enter job id/i });
  await expect(jobIdInput).toBeVisible();

  //
  // 4. Enter a valid job ID
  //    Note: This assumes the job exists. For real tests, create a job first or use a known test job ID
  //
  const testJobId = '96b0df166b882d4aef84b9ea327238a9d13c7f83113f1fe014bc7c499f9b230a';
  await jobIdInput.fill(testJobId);

  //
  // 5. Click "Load History" button
  //
  const loadButton = page.getByRole('button', { name: /load history/i });
  await expect(loadButton).toBeVisible();
  await loadButton.click();

  //
  // 6. Wait for results to load (spinner should disappear or results should appear)
  //
  const spinner = page.locator('.loading-spinner');
  await spinner.waitFor({ state: 'hidden' }).catch(() => {
    // Spinner might not appear if results load instantly
  });

  //
  // 7. Navigate through report tabs to verify data loaded correctly
  //
  const tabs = ['Text Report', 'Analyzed Ads'];
  for (const tabName of tabs) {
    const tab = page.getByText(new RegExp(tabName, 'i'));
    await expect(tab).toBeVisible();
    await tab.click();
  }

  //
  // 8. Verify final output appears
  //
  const resultText = page.getByText(/ads analyzed and processed/i);
  await expect(resultText).toBeVisible();
});