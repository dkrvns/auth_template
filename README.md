# FastAPI auth template

Самостоятельный шаблон: Python 3.14, uv, FastAPI, Dishka, PostgreSQL,
SQLAlchemy и Alembic. Готовые auth-фреймворки не используются.
`pwdlib[argon2]` отвечает только за хеширование, PyJWT — за подпись JWT.

Референс: [dkrvns/city_api, ветка auth](https://github.com/dkrvns/city_api/tree/auth),
коммит `33bec43229aec6d94fcd519b08cd8de28a71ce64`. Сохранены сценарии signup,
login, logout, change password, разделение слоёв, порты и Dishka. Код написан
заново: в референсе не указана лицензия на копирование.

## Возможности

- Регистрация по email и паролю, нормализация email без учёта регистра,
  уникальность на уровне PostgreSQL, UUIDv7.
- Argon2id, пароли длиной 12–128 символов, ограничение параллельного хеширования.
  Неизвестный пользователь тоже проходит проверку dummy hash; ошибки входа одинаковы.
- JWT access: HS256, обязательные sub, sid, iat, nbf, exp, iss, aud, type=access.
- Refresh-токен на 384 бита; в БД хранится только SHA-256. Каждый refresh меняет
  токен. Replay отзывает всю соответствующую сессию, включая access-токены.
- Несколько независимых сессий. Logout отзывает текущую, смена пароля — все.
  Сессия и активность пользователя проверяются в БД при каждом защищённом запросе.
- Bearer transport и опциональные HttpOnly cookies с CSRF-защитой.
- Общий для workers лимит auth-запросов в PostgreSQL; тело запроса до 16 KiB;
  безопасные ошибки валидации без исходных паролей и токенов.
- JSON-логи: request ID, статус, время ответа; без credentials и query string.

## Запуск

```bash
cp .env.example .env
docker run --rm python:3.14-slim python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Вставьте сгенерированное значение в `AUTH__SECRET` в `.env`. Затем:

```bash
docker compose up --build -d --wait frontend
```

Интерфейс: http://127.0.0.1:3000. Swagger: http://127.0.0.1:8000/docs.
FRONTEND_PORT меняет порт интерфейса. Host, port и concurrency API задаются через
`HTTP__HOST`, `HTTP__PORT`, `HTTP__CONCURRENCY`. Все настройки — в `.env.example`.
PostgreSQL, миграции и API работают в Docker. Compose сначала дожидается БД,
затем применяет миграции и запускает API. Установки Python на хосте не требуется.
DATABASE__DSN использует имя Compose-сервиса `postgres`, а не localhost.
Пример credentials PostgreSQL предназначен для локальной разработки.
`.env` не попадает в Git или Docker image.

Остановка: `docker compose down`. Данные БД остаются в named volume.

## CI/CD

GitHub Actions запускает проверки при push в любую ветку и при PR в `master`
или `main`. Backend job выполняет Ruff, mypy, pytest с PostgreSQL/SMTP и pip-audit;
frontend job собирает production-образ, проверяет TypeScript и npm audit;
browser job проверяет пользовательские сценарии через настоящий API и Mailpit.
При push в `master`/`main` после всех проверок Docker-образы API и фронтенда
сохраняются в Actions artifact на один день. Автоматический деплой на сервер
не настроен: цель развёртывания и её credentials не заданы.

`compose.ci.yaml` убирает публикацию портов и поддерживает `CI_ENV_FILE` для
одноразовой конфигурации. Требуется Docker Compose 2.24.4+. Проверки используют
отдельный Compose project и удаляют только свои временные volumes.

## Фронтенд

`frontend/` — TypeScript в strict-режиме, Vite и обычные HTML/CSS, без UI-фреймворка.
Интерфейс поддерживает регистрацию с подтверждением email и автоматическим входом, профиль, обновление
сессии, смену пароля и выход. Требуется `AUTH__TRANSPORT=bearer` (по умолчанию).

Браузер обращается к `/api/` на том же origin. Nginx в Docker проксирует запросы
в API; дополнительная настройка CORS не нужна. Токены хранятся только в памяти
страницы, не записываются в localStorage/sessionStorage и не показываются в UI.
После перезагрузки страницы нужно войти снова. Запросы refresh объединяются,
чтобы параллельные действия не вызвали повторное использование refresh-токена.

### Подтверждение email

1. Введите email и пароль на вкладке регистрации и нажмите «Получить код».
2. Откройте локальный почтовый ящик: http://127.0.0.1:8025 (Mailpit в Docker).
3. Вставьте шестизначный код из письма и подтвердите создание аккаунта.

Письма принимает собственный локальный SMTP-сервис. Mailpit не пересылает их
в Gmail/Яндекс: все учебные адреса видны в его web-интерфейсе. SMTP-порт доступен
только контейнерам; web-интерфейс привязан к loopback. Ящик временный, сохраняет
не более 100 писем; перезапуск контейнера может удалить письма.

Отправку выполняет Python `smtplib` в ограниченном пуле потоков. В PostgreSQL
хранятся HMAC-отпечатки кодов, привязанные к email, без открытых кодов и паролей
ожидающих регистрации. Код действует 10 минут, допускает 5 неверных попыток и
используется один раз. Кнопка повторной отправки показывает отсчёт 45 секунд;
сервер также ограничивает отправку одним письмом на email за 45 секунд и заменяет
предыдущий код. Неверные попытки сохраняются при ошибке HTTP. Проверка кода,
его использование и создание пользователя проходят в одной транзакции.

Для настоящей доставки укажите SMTP-сервер в `MAIL__HOST`, `MAIL__PORT`,
`MAIL__SENDER`, `MAIL__SECURITY` (`starttls` или `ssl`), `MAIL__USERNAME` и
`MAIL__PASSWORD` в `.env`. Сертификаты TLS проверяются; SMTP-аутентификация
без TLS запрещена. `plain` предназначен для локального Mailpit без пароля.
При отсутствии почтовой конфигурации отправка возвращает 503, обхода кода нет.
Ошибка SMTP не создаёт аккаунт и делает выданный код недействительным; запрос
автоматически не повторяется. Успешный ответ означает принятие письма SMTP,
а не подтверждённую доставку во внешний ящик.

Исходники: `src/api.ts` — запросы и сессия; `src/views.ts` — разметка;
`src/main.ts` — события и состояние интерфейса; `src/style.css` — стили.

```bash
docker compose --profile test build frontend_checks frontend_e2e
docker compose run --rm --no-deps frontend_checks npm run check
docker compose run --rm --no-deps frontend_checks npm audit
docker compose run --rm frontend_e2e
```

Браузерные тесты запускаются в Chromium внутри Docker и используют текущий API.
Они создают отдельный учебный аккаунт с префиксом `frontend-e2e-`, меняют пароль
только ему и завершают его сессию. Запускайте их только в локальном учебном окружении.

## API

| Метод | Путь | Вход | Результат |
|---|---|---|---|
| POST | `/auth/signup/code` | email | 204, письмо принято SMTP |
| POST | `/auth/signup` | email, password, code | 201, id |
| POST | `/auth/login` | email, password | 200, пара токенов |
| POST | `/auth/refresh` | refresh_token | 200, новая пара токенов |
| POST | `/auth/logout` | авторизация | 204, отзыв текущей сессии |
| POST | `/auth/change-password` | авторизация, current_password, new_password | 204, отзыв всех сессий |
| GET | `/users/me` | авторизация | 200, id и email |

В Bearer-режиме передавайте `Authorization: Bearer <access_token>`.
В Swagger используйте Authorize и вставьте access-токен после login.
Login принимает JSON: это собственный API, а не OAuth2 token endpoint.
Signup и login требуют валидный email и пароль длиной 12–128 символов.
Signup дополнительно требует действующий код из письма; старые аккаунты
продолжают входить без повторного подтверждения.
Swagger содержит корректный демонстрационный пример:

```json
{"email": "learner@example.com", "password": "Example-password-123!"}
```

Замените пример своим email и паролем. При `422 Invalid request` проверьте
формат email, длину пароля и отсутствие лишних полей в JSON. При повторной
регистрации того же email вернётся 409; для существующего аккаунта используйте login.

Refresh принимает JSON: `{"refresh_token": "..."}`.
Смена пароля определяет пользователя по авторизации, без email или чужого user_id.

Ошибки: 401 — credentials/токен/отозванная сессия; 409 — занятый email;
422 — некорректный ввод или совпадение паролей; 403 — CSRF; 413 — размер тела;
429 — лимит запросов; 503 — недоступность БД. Ответы не кешируются.

## Cookies

```dotenv
AUTH__TRANSPORT=cookie
AUTH__COOKIE_SECURE=true
AUTH__ALLOWED_ORIGINS=["https://app.example.com"]
```

Login/refresh устанавливают access_token (Path=/) и refresh_token
(Path=/auth/refresh), оба HttpOnly, Secure, SameSite=Strict. В ответе токены
равны null. Logout и смена пароля удаляют обе cookies.

Каждый POST к `/auth/*`, включая signup/login, требует разрешённого `Origin`
и `X-CSRF-Token: 1`. Значение `1` — маркер нестандартного заголовка, не секрет:
защита основана на проверке Origin и ограничении CORS. Браузер отправляет
`fetch(..., {credentials: 'include', headers: {'X-CSRF-Token': '1'}})`.
CORS разрешает только перечисленные origins, без wildcard.

SameSite=Strict предполагает frontend/API на одном site, например
app.example.com и api.example.com. Для разных sites этот режим не подходит.
Для HTTP localhost явно установите `AUTH__COOKIE_SECURE=false`.
Режим выбирается один для приложения: Bearer не обходит cookie-политику,
а в Bearer-режиме cookies не используются для авторизации.

## Архитектура и встраивание

```text
src/auth_template/
  application/       DTO, ошибки, Protocol-порты
    dto/
      user/          user.py, credentials.py, change_password.py
      session/       auth_session.py
      security/      refresh_token.py, token_pair.py
      principal.py
      auth_policy.py
    ports/
      user/          reader.py, saver.py, updater.py
      session/       reader.py, saver.py, updater.py
      security/      password_hasher.py, access_token_codec.py, refresh_token_generator.py
      clock.py
      committer.py
      id_generator.py
      rate_limiter.py
  infrastructure/    ORM, gateways, Argon2/JWT adapters, rate limiter
    gateways/
      user.py
      session.py
    db/
      models.py
      committer.py
      rate_limiter.py
    security/
      password_hasher.py
      access_token_codec.py
      refresh_token_generator.py
    clock.py
    auth/
      handlers/
        registration/sign_up.py
        session/     log_in.py, refresh.py, log_out.py
        user/change_password.py
      interactors/user/get_current_user.py
      tokens/issuer.py
  presentation/      schemas, маршруты, зависимости, cookies/CSRF, ASGI boundary
  config.py          настройки окружения
  ioc.py             связывание портов с адаптерами
  main.py            create_app(), lifespan, обработчики ошибок
```

Auth — generic subdomain. По требованию проекта используется собственная
реализация с handlers и портами, без избыточной доменной модели.
Signup, login, refresh, logout и смена пароля реализованы отдельными handlers
в инфраструктуре. Проверка текущего пользователя — отдельный auth interactor.
TokenIssuer находится в инфраструктуре: он собирает технические credentials,
подписывает access через порт и генерирует refresh с техническими TTL.
Application-контракты не импортируют FastAPI, SQLAlchemy или Pydantic.
Порты и DTO импортируются из конкретных модулей в исходниках и тестах.
`__init__.py` этих пакетов пустые, без совместимых реэкспортов.
UserGateway и SessionGateway напрямую наследуют узкие application-порты
Reader, Saver и Updater своей сущности. DI регистрирует один экземпляр
реализации для всех её ролей. Auth handlers зависят от нужных им узких портов.
При отсутствии записи одиночные чтения gateway возвращают пустой экземпляр
существующего DTO: `User()`, `AuthSession()` или `RefreshToken()`. ID и даты
в нём равны None, строки пустые. Handlers проверяют обязательные поля результата,
а не сам объект; пустая сессия не может использоваться для выдачи токенов.
Будущие бизнес-команды размещаются в `application/commands/<область>/`,
атомарные действия — в `application/interactors/<область>/`.
Текущие auth-операции не классифицируются как бизнес-команды.
Handlers, auth interactor и TokenIssuer импортируются напрямую из инфраструктуры.
Application не импортирует инфраструктуру, в том числе через совместимые экспорты.

Новые защищённые маршруты принимают `CurrentUser` из `presentation.dependencies`.
Он предоставляет `(User, Principal)`. Используйте User.id при фильтрации ресурсов
владельца; дополнительные права на объекты проверяйте в соответствующей
application-команде или interactor.
Для своей БД замените gateways, сохранив контракты application.ports,
и зарегистрируйте их в ioc.py. ORM-модели не передаются в application.

Пароль обновляется и сессии отзываются в одной транзакции. Login, refresh и
смена пароля согласованно блокируют пользователя до сессии. История использованных
refresh сохраняется до истечения сессии. Срок сессии абсолютный: refresh его
не продлевает. Клиент должен выполнять refresh последовательно: два параллельных
запроса считаются replay и отзывают сессию.

## Проверки

Compose-профиль test использует отдельную PostgreSQL БД с суффиксом `_test`.
TEST_DATABASE_DSN передаётся в тестовый контейнер через environment.
Тесты создают и удаляют таблицы только в этой БД; рабочая БД не используется.

```bash
docker compose --profile test build tests
docker compose run --rm tests uv run ruff format --check .
docker compose run --rm tests uv run ruff check .
docker compose run --rm tests uv run mypy src
docker compose run --rm tests uv run pytest
docker compose run --rm tests uv run pip-audit --progress-spinner off
```

Покрыты HTTP, cookie/CSRF, поддельные/просроченные JWT и чужой sub,
отзыв сессий, replay, гонки на независимых соединениях, общий rate limit,
Alembic upgrade/downgrade/model consistency. Обычные DB-тесты используют внешнюю
транзакцию и savepoints, конкурентные — настоящие commit и очистку данных.
CI выполняет те же проверки через Docker Compose.

## Эксплуатация

- Используйте HTTPS reverse proxy с ограничением соединений, времени чтения тела
  и размера заголовков. Приложение ограничивает размер тела и Argon2 workers.
- По умолчанию forwarded headers не принимаются. При запуске через отдельный
  uvicorn доверяйте только известным proxy IP, иначе IP rate limit можно обойти.
  Лимит AUTH__REQUESTS_PER_MINUTE применяется ко всем auth POST на IP за фиксированную
  минуту. При публичном развёртывании добавьте распределённую защиту на edge.
- В учебном проекте истёкшие сессии и их refresh history автоматически не удаляются.
  При длительной эксплуатации записи будут накапливаться; очистку можно настроить
  на стороне PostgreSQL, например через pg_cron. Историю refresh-токенов активных
  сессий нужно сохранять для обнаружения повторного использования.
- Смена JWT-секрета инвалидирует access. Для полного принудительного выхода
  также отзовите сессии в БД. Плавная ротация нескольких JWT-ключей не реализована.
- Docker: `docker build -t auth-template .`. Передайте окружение с доступной БД
  и HTTP__HOST=0.0.0.0. Миграции применяйте отдельным шагом до старта API.
  Контейнер работает без root. Обновляемые base image tags перед production
  проверяйте и фиксируйте по digest в своей системе сборки.
- JSON-логи status/duration_ms/request_id позволяют считать error rate и p95/p99.
  Пароли, токены, тела запросов и SQL-параметры логировать нельзя.

Email verification, восстановление пароля с письмами, MFA, OAuth/OIDC и RBAC
не включены: для них нужны отдельные требования и интеграции.
