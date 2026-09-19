# GrowthSathi Class System

One shared, tenant-isolated coaching-class management codebase. Development continues on **develop**. PostgreSQL authentication, migrations and integration tests are working. Authentication, academic administration, attendance, fees, materials, exams/results, announcements, settings and platform management now have implementations, with shared role-based portal screens.

**V1 remains in progress; PILOT CORE READY has not been declared.** See [current status and remaining acceptance work](docs/V1_PROGRESS.md) and [local operation](docs/OPERATIONS.md).
Read [approved decisions](docs/DEVELOPMENT_DECISIONS.md) alongside the eight unchanged DOCX specifications in docs. Work remains on develop; no commits/pushes are automatic.

## Prerequisites

- Python 3.14 (verified locally: 3.14.5), Node 24 (24.19.0), npm 11 (11.17.0).
- PostgreSQL 18 (local installation 18.6).
- On this Windows machine use npm.cmd if PowerShell blocks npm.ps1.
- Python's WindowsApps alias may fail. Use the real interpreter shown below, or your own working Python 3.14 executable.
- PostgreSQL binaries are at C:\Program Files\PostgreSQL\18\bin; PATH is optional.

## Local environment

From the repository root, copy .env.example to .env if it does not already exist. .env is ignored. Fill credentials locally; never paste them into chat or tracked files.

Generate a Django key directly into the ignored file (only when initially creating it; do not overwrite an existing configured file):

```powershell
& 'C:/Users/Harsh Desai/AppData/Local/Python/pythoncore-3.14-64/python.exe' -c "from pathlib import Path; import secrets; p=Path('.env'); assert not p.exists(), 'Preserve existing .env'; p.write_text(Path('.env.example').read_text().replace('DJANGO_SECRET_KEY=', 'DJANGO_SECRET_KEY='+secrets.token_urlsafe(64)), encoding='utf-8')"
```

Enter the application database password in PGPASSWORD inside .env. Quote values when needed using dotenv syntax. Existing process environment variables take precedence. Do not use the database superuser as the application role.

## Approved local PostgreSQL setup

The product owner approved performing this interactively. Do not rerun CREATE statements if the objects already exist.

```powershell
& 'C:/Program Files/PostgreSQL/18/bin/psql.exe' -h 127.0.0.1 -U postgres -d postgres -W
```

Inside psql:

```sql
CREATE ROLE growthsathi_app_dev LOGIN NOSUPERUSER NOCREATEROLE CREATEDB NOREPLICATION;
\password growthsathi_app_dev
CREATE DATABASE growthsathi_class_dev OWNER growthsathi_app_dev;
\q
```

The password command prompts interactively. CREATEDB is only for the local test runner. Django creates and drops growthsathi_class_test; keep that name dedicated to disposable test data. Do not use these role privileges in production.

## Backend

```powershell
& 'C:/Users/Harsh Desai/AppData/Local/Python/pythoncore-3.14-64/python.exe' -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install --require-hashes -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe backend/manage.py check
backend/.venv/Scripts/python.exe backend/manage.py test tests --settings=config.settings.test
backend/.venv/Scripts/python.exe -m ruff check backend
backend/.venv/Scripts/python.exe -m ruff format --check backend
backend/.venv/Scripts/python.exe backend/manage.py runserver
```

On Linux/macOS use python3.14 and backend/.venv/bin/python. The health endpoint is http://127.0.0.1:8000/health/ and checks process liveness, not database readiness.

Always use the test settings and enable the complete PostgreSQL suite:

```powershell
$env:RUN_DATABASE_TESTS = 'true'
backend/.venv/Scripts/python.exe backend/manage.py test tests --settings=config.settings.test --noinput
Remove-Item Env:RUN_DATABASE_TESTS
```

Initial application migrations include the custom accounts.User and business modules and have been applied to the development database. On a fresh dedicated PostgreSQL database run backend/manage.py migrate using the configured virtual-environment interpreter.

Settings modules: config.settings.local, config.settings.test, config.settings.production. Local .env selects local settings; production must explicitly set DJANGO_SETTINGS_MODULE=config.settings.production in its environment. Production settings are a secure baseline, not a completed deployment.

## Frontend

```powershell
cd frontend
npm.cmd ci
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd run dev
```

Open http://localhost:3000. The frontend proxies API requests to Django. See docs/OPERATIONS.md for the two demo institute hosts, platform login and locally stored synthetic access details. No external font fetch is required for builds.

## Dependency maintenance

Backend direct dependencies are in requirements.in and requirements-dev.in. The corresponding .txt files contain exact transitive versions and hashes. To intentionally update locks from backend:

```powershell
.venv/Scripts/python.exe -m piptools compile --allow-unsafe --no-strip-extras --generate-hashes --no-emit-index-url --no-emit-trusted-host --output-file requirements.txt requirements.in
.venv/Scripts/python.exe -m piptools compile --allow-unsafe --no-strip-extras --generate-hashes --no-emit-index-url --no-emit-trusted-host --output-file requirements-dev.txt requirements-dev.in
```

Review both locks together and rerun checks. Frontend direct versions and npm lockfile must change together. Do not use floating latest versions in reproducible setup.

## CI and next review

GitHub Actions runs backend lint/format/system tests with an ephemeral PostgreSQL service, and frontend lint/typecheck/build. CI generates an ephemeral Django key. Its disposable PostgreSQL container uses loopback-only trust authentication and a non-superuser application role; no production secrets are required. Never use trust authentication in deployed environments.

Full V1 continuation is authorized. The PostgreSQL authentication blocker is resolved. See docs/V1_PROGRESS.md for current verification and remaining work; CHECKPOINT_1_REPORT.md and CHECKPOINT_2_PROGRESS.md preserve historical checkpoint evidence.
