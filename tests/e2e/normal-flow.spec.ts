// Note: Enable/Disable parallelism in playwright.config.ts as needed

import { test, expect } from '@playwright/test';

test('normal flow - analyze competitor', async ({ page }) => {

  //
  // 1. Navigate to the app
  //
  await page.goto('http://localhost:5000/');

  //
  // 2. Enter competitor name into the textbox
  //
  const competitorInput = page.getByRole('textbox', { name: /competitor name/i });
  await expect(competitorInput).toBeVisible();
  await competitorInput.fill('algonquin college');

  //
  // 3. Click the "Analyze Now" button to trigger backend processing
  //
  const analyzeButton = page.getByRole('button', { name: /analyze now/i });
  await expect(analyzeButton).toBeVisible();
  await analyzeButton.click();

  //
  // 4. Wait for "Job ID" label to appear (confirm job started)
  //    - No clicking, this is just checking visibility.
  //
  const jobIdLabel = page.getByText(/job id/i);
  await expect(jobIdLabel).toBeVisible();

  //
  // 5. Wait for company name to appear (e.g., "algonquin college")
  //    - Ensures the job response populated UI.
  //
  const companyName = page.getByText(/algonquin college/i);
  await companyName.waitFor({ state: 'visible' });

  //
  // 6. Wait for the "Processing ads data..." text
  //    - Confirms backend processing is underway
  //
  const processingText = page.getByText(/processing ads data/i);
  await expect(processingText).toBeVisible();

  //
  // 7. Wait for the loading spinner to fully disappear
  //    - Indicates backend completed processing
  //
  const spinner = page.locator('.loading-spinner');
  await spinner.waitFor({ state: 'hidden' });

  //
  // 8. Navigate through all report tabs (Text Report → Ads → Analysis)
  //
  const tabs = ['Text Report', 'Analyzed Ads', 'Analysis Results'];
  for (const tabName of tabs) {
    const tab = page.getByText(new RegExp(tabName, 'i'));
    await expect(tab).toBeVisible();
    await tab.click();
  }

  //
  // 9. Verify final output appears
  //    - Looks for generic confirmation text
  //
  const resultText = page.getByText(/ads analyzed and processed/i);
  await expect(resultText).toBeVisible();
});
