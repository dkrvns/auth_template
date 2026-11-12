export interface User {
  id: string;
  email: string;
}

export interface Credentials {
  email: string;
  password: string;
}

interface Session {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number = 0) {
    super(message);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function parseUser(value: unknown): User {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.email !== 'string') {
    throw new ApiError('Не удалось получить данные аккаунта. Попробуйте ещё раз.');
  }
  return { id: value.id, email: value.email };
}

function parseSession(value: unknown): Session {
  if (
    !isRecord(value) || typeof value.access_token !== 'string' || !value.access_token ||
    typeof value.refresh_token !== 'string' || !value.refresh_token ||
    typeof value.expires_in !== 'number' || !Number.isFinite(value.expires_in) || value.expires_in <= 0
  ) {
    throw new ApiError('Не удалось получить сессию. Попробуйте войти снова.');
  }
  return {
    accessToken: value.access_token,
    refreshToken: value.refresh_token,
    expiresAt: Date.now() + value.expires_in * 1000,
  };
}

async function request(path: string, method = 'GET', body?: object, token?: string): Promise<unknown> {
  const headers = new Headers();
  if (body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      credentials: 'omit',
      cache: 'no-store',
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    throw new ApiError('Нет связи с сервером. Проверьте соединение и попробуйте ещё раз.');
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: path === '/auth/login'
        ? 'Неверный email или пароль. Проверьте данные и попробуйте снова.'
        : path === '/auth/change-password'
          ? 'Текущий пароль неверен или сессия завершена. Войдите снова.'
          : 'Сессия завершена. Пожалуйста, войдите снова.',
      403: 'Запрос отклонён сервером.',
      409: 'Этот email уже зарегистрирован. Перейдите на вкладку «Войти».',
      422: path === '/auth/change-password'
        ? 'Новый пароль должен отличаться от текущего и содержать 12–128 символов.'
        : 'Укажите корректный email и пароль длиной от 12 до 128 символов.',
      429: 'Слишком много попыток. Подождите минуту и попробуйте снова.',
    };
    throw new ApiError(messages[response.status] ?? 'Сервер временно недоступен. Попробуйте позже.', response.status);
  }
  if (response.status === 204) return null;
  try {
    return await response.json() as unknown;
  } catch {
    throw new ApiError('Сервер вернул неожиданный ответ. Попробуйте ещё раз.');
  }
}

export class AuthClient {
  private session: Session | null = null;
  private refreshRequest: Promise<void> | null = null;

  get isAuthenticated(): boolean { return this.session !== null; }
  get expiresAt(): number | null { return this.session?.expiresAt ?? null; }

  async checkConnection(): Promise<void> {
    await request('/openapi.json');
  }

  async signup(credentials: Credentials): Promise<void> {
    const response = await request('/auth/signup', 'POST', credentials);
    if (!isRecord(response) || typeof response.id !== 'string') {
      throw new ApiError('Не удалось подтвердить регистрацию. Попробуйте войти с указанными данными.');
    }
  }

  async login(credentials: Credentials): Promise<User> {
    this.session = parseSession(await request('/auth/login', 'POST', credentials));
    return this.profile();
  }

  async refresh(): Promise<void> {
    if (this.refreshRequest) return this.refreshRequest;
    const current = this.session;
    if (!current) throw new ApiError('Сначала войдите в аккаунт.', 401);
    // Share one rotation across concurrent actions: replay revokes the server session.
    this.refreshRequest = (async () => {
      try {
        this.session = parseSession(await request('/auth/refresh', 'POST', {
          refresh_token: current.refreshToken,
        }));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) this.session = null;
        throw error;
      }
    })().finally(() => { this.refreshRequest = null; });
    return this.refreshRequest;
  }

  private async authorized(path: string, method = 'GET', body?: object): Promise<unknown> {
    if (!this.session) throw new ApiError('Сначала войдите в аккаунт.', 401);
    if (this.session.expiresAt <= Date.now() + 10_000) await this.refresh();
    const current = this.session;
    if (!current) throw new ApiError('Сессия завершена. Войдите снова.', 401);
    try {
      return await request(path, method, body, current.accessToken);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) this.session = null;
      throw error;
    }
  }

  async profile(): Promise<User> {
    return parseUser(await this.authorized('/users/me'));
  }

  async logout(): Promise<void> {
    try {
      await this.authorized('/auth/logout', 'POST');
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) throw error;
    }
    this.session = null;
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await this.authorized('/auth/change-password', 'POST', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    this.session = null;
  }
}
