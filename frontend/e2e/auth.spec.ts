import { expect, test } from '@playwright/test';

test('registration, profile, refresh, password change and logout', async ({ page, request }) => {
  const email = `frontend-e2e-${crypto.randomUUID()}@example.com`;
  const password = 'Browser-test-password-123!';
  const newPassword = 'Updated-browser-password-456!';

  await page.goto('/');
  await expect(page.getByText('Сервис доступен')).toBeVisible();
  await page.screenshot({ path: '/tmp/frontend-desktop.png', fullPage: true });
  await page.getByRole('tab', { name: 'Создать аккаунт' }).click();
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Пароль', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Получить код', exact: true }).click();
  await expect(page.getByLabel('Код из письма')).toBeVisible();
  const mailbox = process.env.MAILPIT_BASE_URL ?? 'http://mailpit:8025';
  const search = await request.get(`${mailbox}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`);
  expect(search.ok()).toBe(true);
  const messages = await search.json();
  expect(messages.messages).toHaveLength(1);
  const message = await request.get(`${mailbox}/api/v1/message/${messages.messages[0].ID}`);
  expect(message.ok()).toBe(true);
  const body = await message.json();
  const code = body.Text.match(/\b[0-9]{6}\b/)?.[0];
  expect(Boolean(code)).toBe(true);
  await page.getByLabel('Код из письма').fill(code);
  await page.getByRole('button', { name: 'Подтвердить и создать аккаунт' }).click();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await expect(page.getByText('Аккаунт создан. Добро пожаловать!')).toBeVisible();

  await page.getByRole('button', { name: 'Обновить сессию' }).click();
  await expect(page.getByText('Сессия обновлена. Можно продолжать работу.')).toBeVisible();
  await page.getByRole('button', { name: 'Обновить данные' }).click();
  await expect(page.getByText('Данные профиля обновлены.')).toBeVisible();
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);

  await page.getByRole('button', { name: 'Безопасность', exact: true }).click();
  await page.getByLabel('Текущий пароль', { exact: true }).fill(password);
  await page.getByLabel('Новый пароль', { exact: true }).fill(newPassword);
  await page.getByLabel('Повторите новый пароль', { exact: true }).fill(newPassword);
  await page.getByRole('button', { name: 'Сохранить пароль' }).click();
  await expect(page.getByText('Пароль изменён. Все сессии завершены. Войдите с новым паролем.')).toBeVisible();

  await page.getByLabel('Пароль', { exact: true }).fill(newPassword);
  await page.getByRole('button', { name: 'Войти в аккаунт' }).click();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(page.getByText('Вы вышли из аккаунта. Сессия завершена.')).toBeVisible();
});

test('login rejects invalid credentials with a readable message', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill(`unknown-${crypto.randomUUID()}@example.com`);
  await page.getByLabel('Пароль', { exact: true }).fill('Wrong-password-123!');
  await page.getByRole('button', { name: 'Войти в аккаунт' }).click();
  await expect(page.getByRole('alert')).toHaveText('Неверный email или пароль. Проверьте данные и попробуйте снова.');
});

test('mobile form fits the screen and prevents short passwords', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.screenshot({ path: '/tmp/frontend-mobile.png', fullPage: true });
  await page.getByLabel('Email', { exact: true }).fill('mobile@example.com');
  await page.getByLabel('Пароль', { exact: true }).fill('short');
  await page.getByRole('button', { name: 'Войти в аккаунт' }).click();
  expect(await page.getByLabel('Пароль', { exact: true }).evaluate((input: HTMLInputElement) => input.validity.tooShort)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByRole('heading', { name: 'С возвращением' })).toBeVisible();
});
