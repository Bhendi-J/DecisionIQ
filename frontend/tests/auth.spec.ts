import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const password = 'Browser-only-passphrase-2026';
async function register(page: Page, email: string, company: string) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Create an account', exact: true }).click();
  await page.getByLabel('Your name', { exact: true }).fill('Browser owner');
  await page.getByLabel('Email address', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Company name', { exact: true }).fill(company);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Overview.', exact: true })).toBeVisible();
  await expect(page.locator('.workspace-button')).toContainText(company);
}
async function signIn(page: Page, email: string) {
  await page.getByLabel('Email address', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Overview.', exact: true })).toBeVisible();
}

test('registration creates a private company; login, reload, and logout use the backend', async ({
  page,
}) => {
  const email = `browser-owner-${Date.now()}@example.test`;
  await register(page, email, 'Private browser company');
  const account = await (await page.request.get('/api/auth/me')).json();
  expect(account.user.is_admin).toBe(false);
  expect(account.companies).toHaveLength(1);
  await expect(page.getByRole('link', { name: 'Model Lab', exact: true })).toHaveCount(0);
  expect(
    (
      await page.request.post('/api/auth/workspace', {
        headers: { 'X-CSRF-Token': account.csrf_token },
        data: { company_id: 'aster' },
      })
    ).status(),
  ).toBe(403);
  await page.reload();
  await expect(page.locator('.workspace-button')).toContainText('Private browser company');
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  expect((await page.request.get('/api/dashboard')).status()).toBe(401);
  await page.getByLabel('Email address', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill('Incorrect-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('Email or password is incorrect.');
  await signIn(page, email);
  await expect(page.locator('.workspace-button')).toContainText('Private browser company');
  await page.context().clearCookies();
  await page.getByRole('button', { name: 'Refresh workspace', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
});

test('company owners grant and remove team access; members cannot manage company credentials', async ({
  page,
  browser,
}) => {
  const stamp = Date.now();
  const peerContext = await browser.newContext({
    baseURL,
    reducedMotion: 'reduce',
  });
  const peer = await peerContext.newPage();
  try {
    await register(peer, `peer-${stamp}@example.test`, 'Peer company');
    await register(page, `owner-${stamp}@example.test`, 'Shared company');
    await page.getByRole('button', { name: 'Manage team', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Teammate email', { exact: true }).fill(`peer-${stamp}@example.test`);
    await dialog.getByRole('button', { name: 'Grant access', exact: true }).click();
    await expect(dialog.getByText(`peer-${stamp}@example.test`, { exact: true })).toBeVisible();
    await peer.reload();
    await peer.getByTitle('Open company switcher', { exact: true }).click();
    await peer
      .locator('.workspace-menu')
      .getByRole('button', { name: /Shared company/ })
      .click();
    await expect(peer.locator('.workspace-button')).toContainText('Shared company');
    await expect(peer.getByRole('button', { name: 'Manage team', exact: true })).toHaveCount(0);
    const account = await (await peer.request.get('/api/auth/me')).json();
    expect(
      (
        await peer.request.post('/api/settings/api-key', {
          headers: { 'X-CSRF-Token': account.csrf_token },
        })
      ).status(),
    ).toBe(403);
    await page
      .getByRole('button', { name: `Remove access for peer-${stamp}@example.test`, exact: true })
      .click();
    await expect(dialog.getByText(`peer-${stamp}@example.test`, { exact: true })).toHaveCount(0);
    expect((await peer.request.get('/api/dashboard')).status()).toBe(403);
  } finally {
    await peerContext.close();
  }
});

test('sign-in and registration layouts are accessible on desktop and mobile', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  await page.screenshot({ path: '/private/tmp/foresight-sign-in.png', fullPage: true });
  for (const size of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    for (const registerMode of [false, true]) {
      if (registerMode)
        await page.getByRole('button', { name: 'Create an account', exact: true }).click();
      const audit = await new AxeBuilder({ page }).analyze();
      expect(
        audit.violations
          .filter((item) => ['critical', 'serious'].includes(item.impact || ''))
          .map((item) => ({ id: item.id, targets: item.nodes.map((node) => node.target) })),
      ).toEqual([]);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      ).toBeTruthy();
      if (registerMode)
        await page.getByRole('button', { name: 'Sign in instead', exact: true }).click();
    }
  }
  await page.screenshot({ path: '/private/tmp/foresight-sign-in-mobile.png', fullPage: true });
});
