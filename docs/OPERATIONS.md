# Local operation and deployment notes

Preserve the existing root .env. Never copy credentials into tracked files or chat. PostgreSQL is required; no SQLite fallback exists.

## Verify and migrate

From the repository root in PowerShell:

```powershell
$env:RUN_DATABASE_TESTS = 'true'
backend/.venv/Scripts/python.exe backend/manage.py test tests --settings=config.settings.test --noinput
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
backend/.venv/Scripts/python.exe -m ruff check backend
backend/.venv/Scripts/python.exe -m ruff format --check backend
```

Tests create/drop only the dedicated growthsathi_class_test database. Keep it disposable. Development uses growthsathi_class_dev. On a new machine install the hash-pinned backend requirements and run npm ci in frontend first; see README prerequisites.

## Run the demo

```powershell
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,platform.localhost,testserver'
$env:PLATFORM_HOSTS = 'platform.localhost'
backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000
```

In another terminal:

```powershell
cd frontend
npm.cmd run dev
```

Demo URLs: Success Academy at http://localhost:3000; Bright Classes at http://127.0.0.1:3000; platform at http://platform.localhost:3000. These hostname mappings are created by seed_demo. Some systems may require a local platform.localhost DNS/hosts entry.

Synthetic account access is stored in backend/.local/demo-access.json, which is ignored. Open it locally; never publish it. For a fresh demo only, run manage.py seed_demo, then manage.py seed_demo_activity with the virtual-environment interpreter. The identity seed refuses to overwrite existing demo identities/access files. Do not rerun seeds against important data.

Local recovery emails are written under backend/.local/emails and contain sensitive recovery links. They are not sent externally.

## Frontend checks

In frontend run npm.cmd run lint, npm.cmd run typecheck, npm.cmd test and npm.cmd run build. With both local servers running, backend/scripts/proxy_smoke.py checks role API access through the frontend using the ignored demo credentials without printing them.

## Before deployment

Set DJANGO_SETTINGS_MODULE=config.settings.production explicitly, with strong secrets and explicit hosts. Configure Secure cookies over HTTPS and trusted CSRF origins. API_BACKEND_URL is a server-only Next setting (default http://127.0.0.1:8000).

The Next proxy supplies the tenant hostname in X-Forwarded-Host; Django trusts that header. Keep the Django origin private and ensure the ingress strips/replaces client forwarding headers. Configure HTTPS forwarding with the actual trusted deployment topology and verify redirect/cookie behavior before release.

Configure EMAIL_BACKEND for SMTP plus EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD and EMAIL_USE_TLS via private environment settings. Verify actual activation/reset delivery. Persist private media outside ephemeral application storage and authorize every download through Django.

Prepare PostgreSQL and private-media backups, exercise restoration, use a least-privilege production database role without CREATEDB, and schedule expired-token/session/attempt cleanup. Production hosting, delivery, backup and restore verification remain outstanding; do not infer deployment readiness from local tests.
