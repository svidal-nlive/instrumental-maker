import { test, expect } from '@playwright/test';

const viewports = [
  { name: 'mobile-small', width: 375, height: 667 },
  { name: 'mobile-large', width: 414, height: 896 },
  { name: 'phablet', width: 540, height: 960 },
  { name: 'small-tablet', width: 600, height: 800 },
  { name: 'medium-tablet', width: 700, height: 900 },
  { name: 'tablet-portrait', width: 768, height: 1024 },
  { name: 'tablet-wide', width: 900, height: 600 },
  { name: 'tablet-landscape', width: 1024, height: 768 },
  { name: 'laptop-small', width: 1200, height: 800 },
  { name: 'laptop', width: 1366, height: 768 },
  { name: 'desktop', width: 1920, height: 1080 },
];

test.describe('Library Page Responsive Screenshots', () => {
  // Run only on chromium for faster testing
  test.describe.configure({ mode: 'serial' });
  
  for (const viewport of viewports) {
    test(`Screenshot at ${viewport.name} (${viewport.width}x${viewport.height})`, async ({ page }) => {
      // Set viewport size
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      
      // Navigate to the webui
      await page.goto('http://localhost:5000');
      
      // Wait for page to load
      await page.waitForLoadState('networkidle');
      
      // On mobile viewports, need to open sidebar first
      if (viewport.width < 768) {
        // Look for mobile menu button (hamburger) - use first() to handle multiple matches
        const menuBtn = page.locator('#menu-toggle');
        if (await menuBtn.isVisible()) {
          await menuBtn.click();
          await page.waitForTimeout(300);
        }
      }
      
      // Click on Library nav link using JavaScript to bypass viewport issues
      await page.evaluate(() => {
        const link = document.querySelector('a[data-page="library"]') as HTMLElement;
        if (link) link.click();
      });
      
      // Wait for library content to load
      await page.waitForTimeout(1500);
      
      // Take screenshot of the full page
      await page.screenshot({
        path: `./e2e/screenshots/library-${viewport.name}-${viewport.width}x${viewport.height}.png`,
        fullPage: true
      });
      
      // Also take a screenshot of just the library grid area if visible
      const librarySection = page.locator('#page-library');
      if (await librarySection.isVisible()) {
        await librarySection.screenshot({
          path: `./e2e/screenshots/library-grid-${viewport.name}-${viewport.width}x${viewport.height}.png`
        });
      }
      
      console.log(`✓ Captured ${viewport.name}`);
    });
  }
});
