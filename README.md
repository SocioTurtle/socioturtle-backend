# Socioturtle MVP

A resource-bookmarking app: sign up with captcha, search a database of links.
The backend is a JSON API that serves the React web app today and a mobile app later.

```
backend/    FastAPI + SQLAlchemy (SQLite in dev, Postgres in prod)
frontend/   React + TypeScript + Vite — the app, plus the admin console
widget/     Vanilla-JS registration widget embedded in socioturtle.com
```

## The three pieces and how they fit

socioturtle.com is a **static GitHub Pages site**, so it cannot run Python. The
widget is plain JavaScript that lives in the site repo and calls the API
cross-origin; the API and the React app are deployed separately.

```
socioturtle.com (GitHub Pages, static)
   └── socioturtle-register.js  ──POST /api/leads──┐
                                                   ▼
                                    api.socioturtle.com (FastAPI, Render)
                                                   ▲
   app.socioturtle.com (React) ─────────────────────┘
     ├── invite links land here (?invite=…)
     └── admin console: leads, invites, newsletter
```

## Lead lifecycle

```
visitor registers on socioturtle.com
        │  captcha verified, row written to `leads`
        ▼
      NEW ──── admin clicks "Invite" ───▶ INVITED
                  one-time link emailed        │
                                               │ invitee clicks link,
                                               │ chooses their own password
                                               ▼
                                          ACTIVATED  (a real `users` row exists)
```

**No password is ever emailed.** The invite carries a single-use token (stored
hashed, 7-day expiry) and the recipient sets their own password on arrival. A
lead who never activates never has a live account.

## Backend

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
./.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into SECRET_KEY
./.venv/bin/python seed.py            # demo data + demo/demo-password-1
./.venv/bin/python -m uvicorn app.main:app --reload
```

Interactive API docs: http://127.0.0.1:8000/docs

```bash
./.venv/bin/python -m pytest      # 13 unit/integration tests
./.venv/bin/python smoke_test.py  # end-to-end against a running server
```

## Frontend

Requires Node.js 18+.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
```

## API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/health` | – | Liveness probe |
| GET | `/api/auth/captcha` | – | Issue a captcha challenge |
| POST | `/api/auth/signup` | – | Register (captcha + `role` required) |
| POST | `/api/auth/login` | – | Sign in (captcha required) |
| POST | `/api/auth/refresh` | – | Exchange refresh for access token |
| GET | `/api/auth/me` | Bearer | Current user |
| GET | `/api/resources/search` | – | Search resources |
| POST | `/api/resources` | Bearer | Add a resource |
| POST | `/api/leads` | – | Register interest (captcha required) — used by the widget |
| GET | `/api/leads` | Admin | List / filter registrations |
| GET | `/api/leads/export.csv` | Admin | Download all registrations |
| POST | `/api/leads/invite` | Admin | Email one-time invite links |
| GET | `/api/invites/{token}` | – | Check an invite before showing the form |
| POST | `/api/invites/activate` | – | Redeem an invite, create the account |
| POST | `/api/newsletter/send` | Admin | Send an issue (or a test) |
| GET/POST | `/api/newsletter/unsubscribe` | – | One-click unsubscribe |

Search accepts `q` (matches title, description, tags, URL), `tag`, `limit`, `offset`.

## Running the whole flow locally

```bash
# 1. API — emails print to the log, no credentials needed
cd backend && ./.venv/bin/python -m uvicorn app.main:app --reload

# 2. App + admin console
cd frontend && npm run dev

# 3. The marketing-site widget
cd widget && python3 -m http.server 8080   # then open demo.html
```

Make yourself an admin so the Admin tab appears:

```bash
cd backend && ./.venv/bin/python manage.py make-admin mentor
```

With `EMAIL_BACKEND=console` every email is written to `logs/app.log` instead of
being sent. To pull an invite link out of the log:

```bash
grep '"message": "email_console"' logs/app.log | tail -1
```

## Operations CLI

```bash
python manage.py make-admin <username|email>
python manage.py list-admins
python manage.py leads [--role student] [--status new]
python manage.py send-newsletter "Subject" issue.md [--audience all]
```

## Sending real email

Set these in `backend/.env` (or the Render dashboard):

```
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.zoho.in          # or smtp.gmail.com
SMTP_PORT=587
SMTP_USER=admin@socioturtle.com
SMTP_PASSWORD=<app password>
```

**Gmail needs an App Password**, not your account password, and requires 2FA to be
on. Gmail also caps sending at roughly 500/day — fine while the list is small,
but move to a dedicated sender (Resend, SES, Postmark) before the newsletter
outgrows that, or deliverability will suffer.

Always use **Send test** before **Send to subscribers**. There is no unsend.

## Architecture

### System overview

```mermaid
flowchart TB
    WEB["React Web · Vite :5173<br/>screens/ · components/"]
    RN["React Native app · future<br/>native screens"]

    subgraph CORE["frontend/src/core — shared, zero DOM imports"]
        HOOKS["hooks/<br/>useAuth · useSearch · useCaptcha"]
        VAL["validation.ts · types.ts"]
        EP["api/endpoints.ts<br/>typed API surface"]
        CLIENT["api/client.ts<br/>ApiClient · auto token refresh"]
        STORE["storage.ts<br/>TokenStorage interface"]
    end

    LSTOR[("localStorage")]
    NSTOR[("AsyncStorage /<br/>SecureStore")]

    subgraph API["FastAPI backend :8000"]
        MW["CORSMiddleware<br/>RequestLoggingMiddleware · X-Request-ID"]
        AUTH["routers/auth.py<br/>captcha · signup · login<br/>refresh · me"]
        RES["routers/resources.py<br/>search public<br/>create Bearer"]
        DEP["dependencies.py<br/>get_current_user"]
        CAP["core/captcha.py<br/>CaptchaProvider<br/>LocalSVG / hCaptcha"]
        SEC["core/security.py<br/>bcrypt · JWT"]
        DBL["database.py<br/>SQLAlchemy session"]
    end

    SQLITE[("SQLite<br/>DATABASE_URL to Postgres")]
    LOGS[/"stdout JSON +<br/>logs/app.log rotating"/]

    WEB --> HOOKS
    RN --> HOOKS
    WEB -.-> VAL
    RN -.-> VAL
    HOOKS --> EP
    EP --> CLIENT
    CLIENT --> STORE
    STORE --> LSTOR
    STORE --> NSTOR

    CLIENT -->|"JSON · Bearer JWT"| MW

    MW --> AUTH
    MW --> RES
    MW --> LOGS
    AUTH --> CAP
    AUTH --> SEC
    RES --> DEP
    DEP --> SEC
    AUTH --> DBL
    RES --> DBL
    CAP --> DBL
    DBL --> SQLITE
```

The `core` layer is the reuse boundary: everything above it is platform-specific,
everything inside it runs unchanged on web and native.

### Data model

```mermaid
erDiagram
    USERS ||--o{ RESOURCES : owns
    USERS {
        int id PK
        string email UK
        string username UK
        string password_hash
        string role "student or mentor, indexed"
        bool is_active
        datetime created_at
    }
    RESOURCES {
        int id PK
        int owner_id FK "nullable"
        string title "indexed"
        string url
        string description
        string tags "comma separated, indexed"
        datetime created_at
    }
    LEADS {
        int id PK
        string name
        string email UK
        string role "student or mentor"
        string phone
        string organisation
        string source "campaign attribution"
        bool newsletter_opt_in
        string status "new, invited, activated"
        string invite_token_hash "sha256, nullable"
        datetime invite_expires_at
        string unsubscribe_token UK
        int user_id FK "set on activation"
        datetime created_at
    }
    CAPTCHA_CHALLENGES {
        string id PK "uuid"
        string answer_hash "sha256"
        datetime expires_at
        bool consumed
    }
```

`LEADS` is deliberately separate from `USERS`: a lead is interest, a user is an
account. `user_id` stays null until the invite is redeemed.

`tags` is denormalised into a comma-separated column so a single `LIKE` scan covers
title, description, tags, and URL without a join.

### Captcha-protected login

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant C as core/ApiClient
    participant A as routers/auth.py
    participant P as CaptchaProvider
    participant D as Database

    U->>C: mount LoginScreen
    C->>A: GET /api/auth/captcha
    A->>P: issue()
    P->>D: INSERT challenge (answer_hash, expires_at)
    P-->>A: challenge_id + SVG data URI
    A-->>C: 200
    C-->>U: render captcha image

    U->>C: submit identifier + password + answer
    C->>A: POST /api/auth/login
    A->>P: verify(challenge_id, answer)
    P->>D: mark consumed (on every attempt)
    alt wrong, expired, or replayed
        P-->>A: CaptchaError
        A-->>C: 400
        C-->>U: show error, fetch fresh challenge
    else valid
        P-->>A: ok
        A->>D: lookup user by email or username
        A->>A: bcrypt.checkpw
        A->>A: sign access + refresh JWT
        A-->>C: 200 tokens + user
        C->>C: saveTokens()
        C-->>U: render SearchScreen
    end
```

Marking the challenge consumed on *every* attempt is what stops a wrong answer from
being retried against the same image.

### Token refresh

```mermaid
flowchart TB
    R["request with auth: true"] --> S{"401?"}
    S -->|no| OK["return response"]
    S -->|yes| RF["refreshAccessToken()<br/>concurrent 401s collapse<br/>into one in-flight promise"]
    RF --> P["POST /api/auth/refresh"]
    P --> Q{"refresh token valid?"}
    Q -->|yes| SV["saveTokens()"]
    SV --> RT["retry original request"]
    Q -->|no| CL["clearTokens()"]
    CL --> AE["onAuthExpired · logged out"]
```

This lives entirely in `core/api/client.ts` and uses only `fetch`, so a native app
inherits session handling for free.

## Design notes

**Auth.** Stateless JWT access + refresh tokens rather than cookie sessions, because
a mobile client cannot rely on browser cookie handling. Passwords are bcrypt-hashed.

**Roles.** Every account is either a `student` or a `mentor`, chosen once at signup and
stored on the user row. The login form deliberately has *no* role selector: if the client
could send a role at login, anyone could sign in to a student account claiming to be a
mentor. The role always comes back from the database in the `user` object, so the UI
renders a badge from server state rather than from anything the user typed.

**Captcha.** `CAPTCHA_PROVIDER=local` generates an SVG challenge server-side, so the
MVP runs with no third-party account. Challenges are single-use and TTL-bound —
verifying burns the challenge, so a wrong answer cannot be retried against the same
image. Switch to `CAPTCHA_PROVIDER=hcaptcha` with `HCAPTCHA_SECRET` for production;
the routers are unchanged because both implement the same `CaptchaProvider` interface.

**Logging.** Structured JSON to stdout plus a rotating file (`logs/app.log`). Every
request gets an `X-Request-ID` (honoured from the inbound header if present) that is
attached to every log line emitted during that request, so a single request can be
traced across auth, search, and error logs.

**Database.** SQLite via SQLAlchemy ORM. Point `DATABASE_URL` at Postgres to switch —
no code changes. There are no migrations yet; tables are created at startup.

## Sharing code with a mobile app

`frontend/src/core/` contains no DOM or web-specific imports and is meant to be
lifted into a React Native app as-is:

- `api/client.ts` — `fetch`-based client with automatic token refresh
- `api/endpoints.ts` — typed API surface
- `hooks/` — `useAuth`, `useSearch`, `useCaptcha` hold all the screen logic
- `types.ts`, `validation.ts` — shared contracts and form rules

Platform differences are isolated behind the `TokenStorage` interface in
`core/storage.ts`: web uses `localStorage`, native supplies AsyncStorage or
SecureStore. `components/` and `screens/` are the only web-only layers — a native
app rewrites those and reuses everything else.

**Invites, not passwords.** Emailed passwords sit in inboxes indefinitely, get
forwarded, and surface in breaches. The invite instead carries a single-use token
— stored as a SHA-256 hash, expiring in 7 days, cleared the moment it is redeemed
or a send fails. If the mail fails to go out the token is rolled back, so a failed
send never leaves a live link behind.

**Consent and unsubscribe.** The newsletter checkbox is opt-in and unticked by
default, and the flag is only ever set to true by an explicit tick. Every issue
carries an unsubscribe link plus the RFC 8058 `List-Unsubscribe` headers that let
Gmail and Outlook show their own one-click button — which materially helps you
stay out of spam folders. Unsubscribing with an unknown token renders the same
page as a valid one, so the endpoint cannot be used to test whether an address is
on the list.

## Known limitations (MVP)

- Search uses `LIKE` scans. Move to SQLite FTS5 or Postgres full-text at scale.
- No rate limiting on login; failures are logged but not throttled.
- No email verification or password reset.
- Refresh tokens are not revocable — logout clears the client only.
- No schema migrations (add Alembic before the first production deploy).
- Web navigation is local state, not URL routing; add React Router if deep links matter.
- **The public lead endpoint is captcha-protected but not rate-limited.** Worth
  adding a per-IP limit before the widget goes live on a public page.
- **Newsletter sends run inside the HTTP request.** Fine for a few hundred
  subscribers; beyond that the request will time out and it needs a task queue.
- No bounce or complaint handling — repeatedly mailing dead addresses will hurt
  your sender reputation.
- Emails are not DKIM/SPF-signed by this code; configure that on the sending
  domain or invites will land in spam.
