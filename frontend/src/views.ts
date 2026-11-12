export const icons = {
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 6.3A8 8 0 0 1 20 12M4 12a8 8 0 0 0 13.9 5.7"/></svg>',
};

function passwordField(id: string, label: string, autocomplete: string): string {
  return `<div class="field"><label for="${id}">${label}</label>
    <span class="password-wrap"><input id="${id}" name="${id}" type="password" required minlength="12" maxlength="128" autocomplete="${autocomplete}" placeholder="Не менее 12 символов" />
    <button type="button" class="password-toggle" data-password-target="${id}" aria-controls="${id}" aria-label="Показать пароль">Показать</button></span></div>`;
}

export function authView(mode: 'login' | 'signup'): string {
  const signup = mode === 'signup';
  return `<section class="auth-layout">
    <div class="intro">
      <span class="eyebrow"><span class="tiny-line"></span> ВАШЕ ЛИЧНОЕ ПРОСТРАНСТВО</span>
      <h1>Один аккаунт.<br /><span>Всё под контролем.</span></h1>
      <p class="intro-description">Войдите в свой профиль или создайте новый.<br class="desktop-break" /> Дальше — только нужные настройки.</p>
      <div class="intro-note"><span class="note-icon">${icons.lock}</span><div><strong>Доступ только у вас</strong><p>Пароль защищён. Вы управляете своей сессией.</p></div></div>
      <div class="decorative-card" aria-hidden="true"><span class="decorative-orbit"></span><span class="decorative-lock">${icons.lock}</span><div class="decorative-caption"><span class="status-dot"></span> ВАШ АККАУНТ ЗАЩИЩЁН</div></div>
    </div>
    <div class="auth-panel">
      <div class="tabs" role="tablist" aria-label="Вход или регистрация">
        <button id="login-tab" type="button" role="tab" aria-selected="${!signup}" class="tab ${signup ? '' : 'active'}" data-mode="login">Войти</button>
        <button id="signup-tab" type="button" role="tab" aria-selected="${signup}" class="tab ${signup ? 'active' : ''}" data-mode="signup">Создать аккаунт</button>
      </div>
      <div class="panel-body" role="tabpanel" aria-labelledby="${signup ? 'signup' : 'login'}-tab">
        <span class="panel-icon">${signup ? icons.user : icons.lock}</span>
        <h2>${signup ? 'Начнём знакомство' : 'С возвращением'}</h2>
        <p class="muted">${signup ? 'Пара полей — и ваш аккаунт готов.' : 'Введите данные, чтобы открыть свой профиль.'}</p>
        <form id="credentials-form">
          <fieldset><label class="field" for="email"><span>Email</span><input id="email" name="email" type="email" required maxlength="254" autocomplete="email" placeholder="you@example.com" /></label>
          ${passwordField('password', 'Пароль', signup ? 'new-password' : 'current-password')}
          <p class="field-hint">От 12 до 128 символов. Можно использовать пробелы.</p>
          <button class="button primary" type="submit"><span>${signup ? 'Создать аккаунт' : 'Войти в аккаунт'}</span>${icons.arrow}</button></fieldset>
        </form>
        <div id="message" class="message" role="status" aria-live="polite" hidden></div>
        <p class="session-note">${icons.lock}<span>При обновлении страницы потребуется войти снова.</span></p>
      </div>
    </div>
  </section>`;
}

export function accountView(section: 'profile' | 'security'): string {
  return `<section class="account-layout">
    <div class="account-heading"><div><span class="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h1>Ваш аккаунт<span class="blue-dot">.</span></h1><p class="muted">Профиль, безопасность и управление доступом.</p></div><button id="logout" class="button ghost" type="button">Выйти ${icons.arrow}</button></div>
    <nav class="account-tabs" aria-label="Разделы аккаунта"><button data-section="profile" class="${section === 'profile' ? 'active' : ''}" type="button">${icons.user}Профиль</button><button data-section="security" class="${section === 'security' ? 'active' : ''}" type="button">${icons.lock}Безопасность</button></nav>
    <div id="message" class="message account-message" role="status" aria-live="polite" hidden></div>
    ${section === 'profile' ? `<div class="profile-grid">
      <article class="surface profile-card"><div class="card-heading"><span class="panel-icon">${icons.user}</span><span class="pill">Вы вошли в аккаунт</span></div><h2>Личный профиль</h2><p class="muted">Данные вашего аккаунта.</p><dl class="profile-details"><div><dt>Email</dt><dd id="profile-email"></dd></div><div><dt>ID аккаунта</dt><dd id="profile-id" class="mono"></dd></div></dl><button id="load-profile" class="button secondary" type="button">${icons.refresh}Обновить данные</button></article>
      <article class="surface session-card"><div class="card-heading"><span class="panel-icon">${icons.lock}</span><span class="live-label"><span class="status-dot"></span> АКТИВНА</span></div><h2>Текущая сессия</h2><p class="muted">Продолжайте работу без повторного входа.</p><div class="countdown-label">До обновления доступа</div><div id="session-countdown" class="countdown">—</div><button id="refresh-session" class="button secondary" type="button">${icons.refresh}Обновить сессию</button><p class="card-footnote">Выход завершает эту сессию на сервере.</p></article>
    </div>` : `<div class="security-layout"><article class="surface security-card"><span class="panel-icon">${icons.lock}</span><h2>Изменить пароль</h2><p class="muted">После смены пароля потребуется войти заново на всех устройствах.</p><form id="password-form"><fieldset>${passwordField('current-password', 'Текущий пароль', 'current-password')}${passwordField('new-password', 'Новый пароль', 'new-password')}${passwordField('confirm-password', 'Повторите новый пароль', 'new-password')}<p class="field-hint">12–128 символов. Новый пароль должен отличаться от текущего.</p><button class="button primary" type="submit">Сохранить пароль ${icons.arrow}</button></fieldset></form></article><aside class="security-note"><span class="eyebrow">ПОЛЕЗНО ЗНАТЬ</span><h3>Один шаг для<br />безопасного доступа.</h3><p>Выбирайте длинный уникальный пароль, который не используете в других сервисах.</p><div class="note-divider"></div><p>Смена пароля завершит все текущие сессии. Это поможет, если доступ к аккаунту мог получить кто-то ещё.</p></aside></div>`}
  </section>`;
}
