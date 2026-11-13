import './style.css';
import { ApiError, AuthClient } from './api';
import type { Credentials, User } from './api';
import { accountView, authView, icons } from './views';

const root = document.querySelector<HTMLDivElement>('#app');
if (!root) throw new Error('Application root is missing');
root.innerHTML = `<div class="site-shell"><header class="site-header"><a href="/" class="brand" aria-label="Auth — главная"><span class="brand-mark">${icons.lock}</span><span>auth<span class="brand-period">.</span></span><span class="brand-tag">ЛИЧНЫЙ КАБИНЕТ</span></a><span id="connection" class="connection"><span class="status-dot"></span><span>Проверяем соединение</span></span></header><main id="main"></main><footer class="site-footer"><span>Ваш аккаунт. Ваш контроль.</span><span>Просто и безопасно <span class="footer-dot">·</span> Auth template</span></footer></div>`;

function element<T extends HTMLElement>(selector: string): T {
  const result = document.querySelector<T>(selector);
  if (!result) throw new Error(`Missing interface element: ${selector}`);
  return result;
}

const api = new AuthClient();
const main = element<HTMLElement>('#main');
let user: User | null = null;
let mode: 'login' | 'signup' = 'login';
let section: 'profile' | 'security' = 'profile';
let email = '';
let busy = false;
let codeEmail = '';

function notify(message: string, kind: 'error' | 'success' = 'success'): void {
  const box = element<HTMLDivElement>('#message');
  box.textContent = message;
  box.dataset.kind = kind;
  box.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  box.hidden = false;
}

function setBusy(value: boolean): void {
  busy = value;
  main.setAttribute('aria-busy', String(value));
  main.querySelectorAll<HTMLButtonElement>('button').forEach(button => { button.disabled = value; });
  main.querySelectorAll<HTMLFieldSetElement>('fieldset').forEach(fieldset => { fieldset.disabled = value; });
  updateCodeCountdown();
}

function updateCodeCountdown(): void {
  const resend = document.querySelector<HTMLButtonElement>('#resend-code');
  const initialSend = !user && mode === 'signup' && !document.querySelector('#registration-code')
    ? document.querySelector<HTMLButtonElement>('#credentials-form button[type="submit"]') : null;
  const button = resend ?? initialSend;
  if (!button) return;
  const seconds = api.registrationCodeWaitSeconds;
  const label = resend ? 'Отправить код ещё раз' : 'Получить код';
  button.disabled = busy || seconds > 0;
  const text = initialSend ? button.querySelector('span') : button;
  if (text) text.textContent = seconds > 0 ? `${label} (${seconds} с)` : label;
}

async function perform(action: () => Promise<void>): Promise<void> {
  if (busy) return;
  const box = element<HTMLDivElement>('#message');
  box.hidden = true;
  setBusy(true);
  try {
    await action();
  } catch (error) {
    if (user && !api.isAuthenticated) {
      user = null;
      mode = 'login';
      render();
    }
    notify(error instanceof ApiError ? error.message : 'Не удалось выполнить действие. Попробуйте ещё раз.', 'error');
  } finally {
    setBusy(false);
  }
}

function updateCountdown(): void {
  const countdown = document.querySelector<HTMLElement>('#session-countdown');
  if (!countdown || api.expiresAt === null) return;
  const seconds = Math.max(0, Math.ceil((api.expiresAt - Date.now()) / 1000));
  countdown.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

function attachPasswordToggles(): void {
  main.querySelectorAll<HTMLButtonElement>('[data-password-target]').forEach(button => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.passwordTarget ?? '');
      if (!(input instanceof HTMLInputElement)) return;
      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      button.textContent = visible ? 'Скрыть' : 'Показать';
      button.setAttribute('aria-label', visible ? 'Скрыть пароль' : 'Показать пароль');
    });
  });
}

function renderAuth(): void {
  main.innerHTML = authView(mode, codeEmail === email && email !== '');
  element<HTMLInputElement>('#email').value = email;
  const emailInput = element<HTMLInputElement>('#email');
  const codeInput = document.querySelector<HTMLInputElement>('#registration-code');
  emailInput.addEventListener('input', () => {
    if (codeInput) {
      codeInput.value = '';
      codeInput.setCustomValidity(emailInput.value.trim() === codeEmail
        ? '' : 'Email изменён. Запросите новый код кнопкой ниже.');
    }
  });
  document.querySelector<HTMLButtonElement>('#resend-code')?.addEventListener('click', () => {
    const currentEmail = emailInput.value.trim();
    if (!emailInput.reportValidity()) return;
    void perform(async () => {
      await api.sendRegistrationCode(currentEmail);
      codeEmail = currentEmail;
      email = currentEmail;
      if (codeInput) {
        codeInput.value = '';
        codeInput.setCustomValidity('');
        codeInput.focus();
      }
      notify('Новый код отправлен. Повторная отправка доступна через 45 секунд.');
    });
  });
  main.querySelectorAll<HTMLButtonElement>('[data-mode]').forEach(button => {
    button.addEventListener('click', () => {
      email = element<HTMLInputElement>('#email').value;
      mode = button.dataset.mode === 'signup' ? 'signup' : 'login';
      render();
    });
  });
  element<HTMLFormElement>('#credentials-form').addEventListener('submit', event => {
    event.preventDefault();
    const credentials: Credentials = {
      email: element<HTMLInputElement>('#email').value.trim(),
      password: element<HTMLInputElement>('#password').value,
    };
    email = credentials.email;
    void perform(async () => {
      const signup = mode === 'signup';
      if (signup) {
        const code = document.querySelector<HTMLInputElement>('#registration-code');
        if (!code || codeEmail !== credentials.email) {
          await api.sendRegistrationCode(credentials.email);
          codeEmail = credentials.email;
          // Preserve the password only in the current form while entering the code.
          render();
          element<HTMLInputElement>('#password').value = credentials.password;
          element<HTMLInputElement>('#registration-code').focus();
          notify('Код отправлен на указанный email. Введите 6 цифр из письма.');
          return;
        }
        await api.signup(credentials, code.value);
        codeEmail = '';
      }
      try {
        user = await api.login(credentials);
      } catch (error) {
        if (signup) {
          mode = 'login';
          render();
          notify('Аккаунт создан. Не удалось выполнить вход — попробуйте войти ещё раз.', 'error');
          return;
        }
        throw error;
      }
      section = 'profile';
      render();
      notify(signup ? 'Аккаунт создан. Добро пожаловать!' : 'Вы успешно вошли в аккаунт.');
    });
  });
}

function renderAccount(): void {
  main.innerHTML = accountView(section);
  main.querySelectorAll<HTMLButtonElement>('[data-section]').forEach(button => {
    button.addEventListener('click', () => {
      section = button.dataset.section === 'security' ? 'security' : 'profile';
      render();
    });
  });
  element<HTMLButtonElement>('#logout').addEventListener('click', () => {
    void perform(async () => {
      await api.logout();
      user = null;
      mode = 'login';
      render();
      notify('Вы вышли из аккаунта. Сессия завершена.');
    });
  });
  if (section === 'profile' && user) {
    element<HTMLElement>('#profile-email').textContent = user.email;
    element<HTMLElement>('#profile-id').textContent = user.id;
    updateCountdown();
    element<HTMLButtonElement>('#load-profile').addEventListener('click', () => {
      void perform(async () => {
        user = await api.profile();
        render();
        notify('Данные профиля обновлены.');
      });
    });
    element<HTMLButtonElement>('#refresh-session').addEventListener('click', () => {
      void perform(async () => {
        await api.refresh();
        render();
        notify('Сессия обновлена. Можно продолжать работу.');
      });
    });
  }
  if (section === 'security') {
    const confirmation = element<HTMLInputElement>('#confirm-password');
    confirmation.addEventListener('input', () => { confirmation.setCustomValidity(''); });
    element<HTMLFormElement>('#password-form').addEventListener('submit', event => {
      event.preventDefault();
      const currentPassword = element<HTMLInputElement>('#current-password').value;
      const newPassword = element<HTMLInputElement>('#new-password').value;
      if (newPassword !== confirmation.value) {
        confirmation.setCustomValidity('Пароли не совпадают.');
        confirmation.reportValidity();
        return;
      }
      void perform(async () => {
        await api.changePassword(currentPassword, newPassword);
        user = null;
        mode = 'login';
        render();
        notify('Пароль изменён. Все сессии завершены. Войдите с новым паролем.');
      });
    });
  }
}

function render(): void {
  if (user) renderAccount();
  else renderAuth();
  attachPasswordToggles();
  updateCodeCountdown();
}

render();
window.setInterval(() => {
  updateCountdown();
  updateCodeCountdown();
}, 1000);
void api.checkConnection().then(() => {
  const connection = element<HTMLSpanElement>('#connection');
  connection.classList.add('online');
  connection.lastElementChild!.textContent = 'Сервис доступен';
}).catch(() => {
  const connection = element<HTMLSpanElement>('#connection');
  connection.classList.add('offline');
  connection.lastElementChild!.textContent = 'Нет связи с сервером';
});
