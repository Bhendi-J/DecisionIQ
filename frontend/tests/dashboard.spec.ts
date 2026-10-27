import { test, expect } from '@playwright/test';

async function navigate(page: import('@playwright/test').Page, label: string) {
  const toggle = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await toggle.isVisible()) await toggle.click();
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: label, exact: true })
    .click();
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  await page
    .getByLabel('Email address', { exact: true })
    .fill(process.env.FORESIGHT_TEST_ADMIN_EMAIL!);
  await page
    .getByLabel('Password', { exact: true })
    .fill(process.env.FORESIGHT_TEST_ADMIN_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Overview.', exact: true })).toBeVisible();
  await expect(page.locator('.metric').first()).toBeVisible();
});

test('premium dashboard has local fonts, working navigation, and distinct company data', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(16, 17, 18)');
  expect(await page.evaluate(() => document.fonts.check('13px "Manrope Variable"'))).toBeTruthy();
  const firstSales = await page.locator('.metric strong').first().innerText();
  await page.getByTitle('Open admin company switcher', { exact: true }).click();
  await page
    .locator('.workspace-menu')
    .getByRole('button', { name: /Maison Supply/ })
    .click();
  await expect(page.getByTitle('Open admin company switcher', { exact: true })).toContainText(
    'Maison Supply',
  );
  await expect(page.locator('.metric strong').first()).not.toHaveText(firstSales);
  for (const [label, heading] of [
    ['Sales Outlook', 'Sales Outlook.'],
    ['Data Hub', 'Data Hub.'],
    ['Security', 'Security.'],
    ['Insights', 'Insights.'],
    ['Activity', 'Activity.'],
  ]) {
    await navigate(page, label);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
  }
  await expect(page.getByText('Every 24 hours while overdue')).toBeVisible();
  expect(errors).toEqual([]);
});

test('upload reviews a mapping and processes a company-specific history', async ({ page }) => {
  await page.getByRole('button', { name: 'Add data', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Workspace name', { exact: true }).fill('Browser upload ' + Date.now());
  const records = ['record_id,date,product_id,product,units,sales,currency'];
  for (let i = 0; i < 120; i++) {
    const date = new Date(Date.UTC(2026, 5, 1 + i)).toISOString().slice(0, 10);
    records.push(
      `browser-${i},${date},NOTEBOOK,Notebook,${3 + (i % 7)},${100 + i * 2 + (i % 7) * 15},GBP`,
    );
  }
  await page.getByLabel('Choose sales file').setInputFiles({
    name: 'browser-sales.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(records.join('\n')),
  });
  await dialog.getByRole('button', { name: 'Review columns' }).click();
  await expect(dialog.getByRole('heading', { name: 'Match your columns' })).toBeVisible();
  await expect(dialog.getByLabel('Transaction date')).toHaveValue('date');
  await dialog.getByRole('button', { name: 'Validate mapping' }).click();
  await expect(dialog.getByText('Mapping validated. Your data is ready to process.')).toBeVisible();
  await dialog.getByRole('button', { name: 'Process data', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Data Hub.', exact: true })).toBeVisible();
  await expect(page.locator('tbody').getByText('processed', { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await expect(page.getByText('120 new · 0 duplicates')).toBeVisible();
  await navigate(page, 'Sales Outlook');
  await expect(page.locator('.metric strong').first()).not.toHaveText('£175,269');
  await expect(page.getByText(/notebook/i).first()).toBeVisible();
  await page.getByRole('button', { name: 'Model evaluation', exact: true }).click();
  await expect(page.getByText('Make the model earn its place')).toBeVisible();
  await expect(page.locator('.evaluation-grid')).toBeVisible({ timeout: 30000 });
});

test('sales assumptions change a conditional estimate and can be reset', async ({ page }) => {
  await navigate(page, 'Sales Outlook');
  const original = await page.locator('.scenario-result strong').innerText();
  await page.getByRole('slider', { name: 'Volume assumption' }).fill('20');
  await expect(page.locator('.scenario-result strong')).not.toHaveText(original);
  await page.getByRole('button', { name: 'Reset', exact: true }).click();
  await expect(page.locator('.scenario-result strong')).toHaveText(original);
});

test('security analysis calls real models and exposes missing artifacts', async ({ page }) => {
  await navigate(page, 'Security');
  await page.getByRole('button', { name: 'Analyze login', exact: true }).click();
  await expect(page.locator('.analysis-result')).toBeVisible();
  await expect(page.locator('.analysis-result')).toContainText('calibrated probability');
  await page.getByRole('button', { name: 'Email analysis', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Message-level evidence', exact: true }),
  ).toBeVisible();
  const dashboard = await (await page.request.get('/api/dashboard')).json();
  if (process.env.FORESIGHT_REQUIRE_PHISHING === '1')
    expect(dashboard.phishing_status).toBe('ready');
  if (dashboard.phishing_status === 'ready') {
    await page
      .getByLabel('Email content', { exact: true })
      .fill('Team meeting tomorrow at 10 AM. Please review the agenda before joining.');
    await page.getByRole('button', { name: 'Analyze email', exact: true }).click();
    await expect(page.locator('.analysis-result')).toContainText(
      'Model score for this message only.',
    );
    await expect(page.locator('main')).toContainText('Manual analysis');
  } else {
    await expect(page.getByText('Trained model required', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Analyze email', exact: true })).toBeDisabled();
  }
});

test('search and export are usable controls', async ({ page }) => {
  await page.getByRole('button', { name: 'Find anything' }).click();
  const search = page.getByRole('dialog');
  await search.getByRole('textbox', { name: 'Search workspace' }).fill('security');
  await search.getByRole('button', { name: 'Security', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Security.', exact: true })).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export data — sales observations', exact: true }).click(),
  ]);
  expect(download.suggestedFilename()).toContain('sales.csv');
});

test('mobile layout has accessible navigation and no page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await navigate(page, 'Data Hub');
  await expect(page.getByRole('heading', { name: 'Data Hub.', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Add data', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.getByRole('button', { name: 'Close dialog', exact: true }).click();
  await navigate(page, 'Overview');
  await page.screenshot({ path: '/private/tmp/decisioniq-mobile-verified.png', fullPage: true });
});

test('integration controls generate a scoped key and pause real API intake', async ({ page }) => {
  await page.getByTitle('Open admin company switcher', { exact: true }).click();
  await page.getByRole('button', { name: 'New upload workspace' }).click();
  const modal = page.getByRole('dialog');
  await modal.getByLabel('Workspace name', { exact: true }).fill('Browser API ' + Date.now());
  await modal.getByRole('button', { name: 'Create workspace', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Data Hub.', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Configure integration', exact: true }).click();
  await page.getByRole('button', { name: 'Generate credential', exact: true }).click();
  await expect(page.locator('.key-reveal code')).toBeVisible();
  const key = (await page.locator('.key-reveal code').innerText()).trim();
  expect(key.startsWith('diq_')).toBeTruthy();
  await page.getByRole('button', { name: 'Activate', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  const request = {
    currency: 'GBP',
    records: [
      { record_id: 'ui-api-001', date: '2026-01-01', sales: 375, product: 'Browser product' },
    ],
  };
  const accepted = await page.request.post('/api/intake/sales', {
    headers: { 'X-API-Key': key },
    data: request,
  });
  expect(accepted.status()).toBe(202);
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await expect(page.getByText('1 new · 0 duplicates')).toBeVisible({ timeout: 30000 });
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Activate', exact: true })).toBeVisible();
  expect(
    (
      await page.request.post('/api/intake/sales', { headers: { 'X-API-Key': key }, data: request })
    ).status(),
  ).toBe(409);
});

test('reporting schedule and snooze are persistent interface actions', async ({ page }) => {
  await page.getByTitle('Open admin company switcher', { exact: true }).click();
  await page.getByRole('button', { name: 'New upload workspace' }).click();
  const created = page.getByRole('dialog');
  await created
    .getByLabel('Workspace name', { exact: true })
    .fill('Browser reminders ' + Date.now());
  await created.getByRole('button', { name: 'Create workspace', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Data Hub.', exact: true })).toBeVisible();
  await navigate(page, 'Activity');
  await page.getByRole('button', { name: 'Edit reporting schedule' }).click();
  const modal = page.getByRole('dialog');
  await modal.getByLabel('Next update due (UTC)').fill('2026-10-24T12:00');
  await modal.getByLabel('Required data coverage through').fill('2026-10-24');
  await modal.getByLabel('Repeat overdue reminders').selectOption('12');
  await modal.getByRole('button', { name: 'Save schedule' }).click();
  await expect(page.getByText('Every 12 hours while overdue')).toBeVisible();
  await page.getByRole('button', { name: 'Snooze 24h' }).click();
  await expect(page.getByText('A little breathing room.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('A little breathing room.')).toBeVisible();
  await page.getByRole('button', { name: 'Resume reminders', exact: true }).click();
  await expect(page.getByText('Your next data update is due', { exact: true })).toBeVisible();
});

test('desktop and mobile interfaces have no serious accessibility violations', async ({ page }) => {
  const { default: AxeBuilder } = await import('@axe-core/playwright');
  for (const label of [
    'Overview',
    'Data Hub',
    'Sales Outlook',
    'Security',
    'Insights',
    'Activity',
  ]) {
    await navigate(page, label);
    const results = await new AxeBuilder({ page }).analyze();
    const violations = results.violations.filter((item) =>
      ['critical', 'serious'].includes(item.impact || ''),
    );
    expect(
      violations.map((item) => ({
        id: item.id,
        description: item.description,
        targets: item.nodes.map((node) => node.target),
      })),
      label,
    ).toEqual([]);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await navigate(page, 'Overview');
  const mobile = await new AxeBuilder({ page }).analyze();
  expect(
    mobile.violations
      .filter((item) => ['critical', 'serious'].includes(item.impact || ''))
      .map((item) => ({ id: item.id, targets: item.nodes.map((node) => node.target) })),
  ).toEqual([]);
});
