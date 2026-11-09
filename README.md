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
uv python install 3.14
uv sync
cp .env.example .env
uv run python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Вставьте сгенерированное значение в `AUTH__SECRET` в `.env`. Затем:

```bash
docker compose up -d --wait postgres
uv run alembic upgrade head
uv run python -m auth_template
```

Swagger: http://127.0.0.1:8000/docs. Host, port и concurrency задаются через
`HTTP__HOST`, `HTTP__PORT`, `HTTP__CONCURRENCY`. Все настройки — в `.env.example`.
Пример credentials PostgreSQL предназначен для локальной разработки.
`.env` не попадает в Git или Docker image.

## API

| Метод | Путь | Вход | Результат |
|---|---|---|---|
| POST | `/auth/signup` | email, password | 201, id |
| POST | `/auth/login` | email, password | 200, пара токенов |
| POST | `/auth/refresh` | refresh_token | 200, новая пара токенов |
| POST | `/auth/logout` | авторизация | 204, отзыв текущей сессии |
| POST | `/auth/change-password` | авторизация, current_password, new_password | 204, отзыв всех сессий |
| GET | `/users/me` | авторизация | 200, id и email |

В Bearer-режиме передавайте `Authorization: Bearer <access_token>`.
В Swagger используйте Authorize и вставьте access-токен после login.
Login принимает JSON: это собственный API, а не OAuth2 token endpoint.
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
      security/      password_hasher.py, access_token_codec.py, refresh_token_generator.py
      clock.py
      committer.py
      id_generator.py
      rate_limiter.py
  infrastructure/    ORM, gateways, Argon2/JWT adapters, rate limiter
    interfaces/gateways/
      user.py        UserGatewayInterface
      session.py     SessionGatewayInterface
    gateways/
      user.py
      session.py
    committer.py
    rate_limiter.py
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
UserGateway и SessionGateway явно реализуют интерфейсы из
`infrastructure/interfaces/gateways/`. Интерфейс пользователя объединяет узкие
application-порты UserReader, UserSaver и UserUpdater. DI регистрирует одну
реализацию для общего интерфейса и этих ролей. Auth handlers зависят от интерфейса
сессии и нужных им узких пользовательских портов.
Будущие бизнес-команды размещаются в `application/commands/<область>/`,
атомарные действия — в `application/interactors/<область>/`.
Текущие auth-операции не классифицируются как бизнес-команды.
Handlers, auth interactor и TokenIssuer импортируются напрямую из инфраструктуры.
Application не импортирует инфраструктуру, в том числе через совместимые экспорты.

Новые защищённые маршруты принимают `CurrentUser` из `presentation.dependencies`.
Он предоставляет `(User, Principal)`. Используйте User.id при фильтрации ресурсов
владельца; дополнительные права на объекты проверяйте в соответствующей
application-команде или interactor.
Для своей БД замените gateways, сохранив контракты application.ports и
infrastructure.interfaces.gateways,
и зарегистрируйте их в ioc.py. ORM-модели не передаются в application.

Пароль обновляется и сессии отзываются в одной транзакции. Login, refresh и
смена пароля согласованно блокируют пользователя до сессии. История использованных
refresh сохраняется до истечения сессии. Срок сессии абсолютный: refresh его
не продлевает. Клиент должен выполнять refresh последовательно: два параллельных
запроса считаются replay и отзывают сессию.

## Проверки

Нужна отдельная PostgreSQL БД с суффиксом `_test`. pytest намеренно читает
TEST_DATABASE_DSN только из окружения процесса, не из `.env`.
Тесты создают и удаляют таблицы в этой БД; она должна быть выделена только им.

```bash
docker compose --profile test up -d --wait postgres_test
export TEST_DATABASE_DSN='postgresql+psycopg://auth_test:auth-test-only@127.0.0.1:5433/auth_test'
uv run ruff format .
uv run ruff check --fix .
uv run mypy src
uv run pytest
uv run pip-audit --progress-spinner off
```

Покрыты HTTP, cookie/CSRF, поддельные/просроченные JWT и чужой sub,
отзыв сессий, replay, гонки на независимых соединениях, общий rate limit,
Alembic upgrade/downgrade/model consistency. Обычные DB-тесты используют внешнюю
транзакцию и savepoints, конкурентные — настоящие commit и очистку данных.
CI выполняет те же проверки с PostgreSQL service.

## Эксплуатация

- Используйте HTTPS reverse proxy с ограничением соединений, времени чтения тела
  и размера заголовков. Приложение ограничивает размер тела и Argon2 workers.
- По умолчанию forwarded headers не принимаются. При запуске через отдельный
  uvicorn доверяйте только известным proxy IP, иначе IP rate limit можно обойти.
  Лимит AUTH__REQUESTS_PER_MINUTE применяется ко всем auth POST на IP за фиксированную
  минуту. При публичном развёртывании добавьте распределённую защиту на edge.
- Ежедневно запускайте `uv run python -m auth_template.maintenance` для удаления
  истёкших сессий и их refresh history. Не удаляйте историю активных сессий.
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
