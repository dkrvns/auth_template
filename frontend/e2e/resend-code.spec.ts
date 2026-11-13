import { expect, test } from '@playwright/test';

test('resend stays disabled for 45 seconds, survives errors and restarts after sending', async ({ page }) => {
  await page.clock.install();
  await page.clock.pauseAt(new Date(Date.now() + 1000));
  let sends = 0;
  await page.route('**/api/auth/signup/code', route => {
    sends += 1;
    return route.fulfill({ status: 204 });
  });
  await page.route('**/api/auth/signup', route => route.fulfill({
    status: 400, json: { detail: 'Invalid or expired registration code' },
  }));
  await page.goto('/');
  await page.getByRole('tab', { name: 'Создать аккаунт' }).click();
  await page.getByLabel('Email', { exact: true }).fill('cooldown@example.com');
  await page.getByLabel('Пароль', { exact: true }).fill('Timer-test-password-123!');
  await page.getByRole('button', { name: 'Получить код', exact: true }).click();

  const resend = page.locator('#resend-code');
  await expect(resend).toHaveText('Отправить код ещё раз (45 с)');
  await expect(resend).toBeDisabled();
  await page.getByLabel('Код из письма').fill('111111');
  await page.getByRole('button', { name: 'Подтвердить и создать аккаунт' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(resend).toBeDisabled();

  await page.getByRole('tab', { name: 'Войти', exact: true }).click();
  await page.getByRole('tab', { name: 'Создать аккаунт' }).click();
  await expect(resend).toBeDisabled();
  await page.clock.fastForward(44_000);
  await expect(resend).toHaveText('Отправить код ещё раз (1 с)');
  await expect(resend).toBeDisabled();
  await resend.evaluate((button: HTMLButtonElement) => button.click());
  expect(sends).toBe(1);

  await page.clock.fastForward(1000);
  await expect(resend).toBeEnabled();
  await expect(resend).toHaveText('Отправить код ещё раз');
  await resend.click();
  await expect(resend).toHaveText('Отправить код ещё раз (45 с)');
  await expect(resend).toBeDisabled();
  expect(sends).toBe(2);
});

test('server Retry-After keeps the send button disabled after a rejected request', async ({ page }) => {
  await page.clock.install();
  await page.clock.pauseAt(new Date(Date.now() + 1000));
  await page.route('**/api/auth/signup/code', route => route.fulfill({
    status: 429, headers: { 'Retry-After': '60' }, json: { detail: 'Too many requests' },
  }));
  await page.goto('/');
  await page.getByRole('tab', { name: 'Создать аккаунт' }).click();
  await page.getByLabel('Email', { exact: true }).fill('rate-limit@example.com');
  await page.getByLabel('Пароль', { exact: true }).fill('Timer-test-password-123!');
  await page.getByRole('button', { name: 'Получить код', exact: true }).click();

  const send = page.locator('#credentials-form button[type="submit"]');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(send).toBeDisabled();
  await page.clock.fastForward(45_000);
  await expect(send).toHaveText('Получить код (15 с)');
  await expect(send).toBeDisabled();
  await page.clock.fastForward(15_000);
  await expect(send).toBeEnabled();
});
