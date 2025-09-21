const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: false
  });
  const context = await browser.newContext();
  const page = await context.newPage();

await page.goto('https://www.amazon.in');

await page.getByRole('searchbox', { name: 'Search Amazon.in' }).fill('iphone 16');
await page.getByRole('searchbox', { name: 'Search Amazon.in' }).press('Enter');

await page.goto('https://www.amazon.in');

await page.getByRole('searchbox', { name: 'Search Amazon.in' }).fill('iphone 16');
await page.getByRole('searchbox', { name: 'Search Amazon.in' }).press('Enter');

await page.goto('https://www.amazon.in');

await page.getByRole('searchbox', { name: 'Search Amazon.in' }).fill('iphone 16');
await page.getByRole('searchbox', { name: 'Search Amazon.in' }).press('Enter');
    await context.close();
    await browser.close();
})();
