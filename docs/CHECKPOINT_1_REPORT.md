# Milestone 1 - Checkpoint 1 report

Scope: approved project foundations only. No Checkpoint 2 work, business models, application migrations, authentication implementation, feature pages, RLS, commits, or pushes.

## Work and architecture

- Added explicit product-owner precedence and V1 decisions in DEVELOPMENT_DECISIONS.md; all eight DOCX files remain byte-for-byte unchanged against HEAD.
- Established Django/DRF settings split (base/local/test/production), WSGI/ASGI, management entry point, process-liveness endpoint, and foundation tests.
- PostgreSQL/Psycopg is the sole configured database engine.
- Deferred contrib.auth/admin/session apps and migrations until the custom User exists.
- API defaults deny anonymous access; health is the only route.
- Added Next.js App Router/TypeScript scaffold with a minimal placeholder, not a feature UI.
- Added Ruff backend checks, Biome frontend lint/format, TypeScript check, production build, and minimal CI.
- Generated backend exact hash locks and npm package-lock.json.
- Added ignored local .env with a generated Django key; no secret value was printed or placed in candidate tracked files.

## Files

Root: README.md (updated), .gitignore, .env.example.
Documentation: docs/DEVELOPMENT_DECISIONS.md, this report.
CI: .github/workflows/ci.yml.
Backend: manage.py; config/{__init__,urls,views,asgi,wsgi}.py; config/settings/{__init__,base,local,test,production}.py; tests/{__init__,test_foundation}.py; pyproject.toml; requirements.in, requirements.txt, requirements-dev.in, requirements-dev.txt.
Frontend: package.json, package-lock.json, tsconfig.json, next-env.d.ts, next.config.ts, biome.json, src/app/{layout.tsx,page.tsx,globals.css}.
Local ignored artifacts: .env, backend/.venv, frontend/node_modules, frontend/.next, tool caches/build metadata.
Existing .gitkeep files remain harmless placeholders.

## Selected direct dependencies

| Component | Pin |
| --- | --- |
| Django | 5.2.17 LTS |
| Django REST Framework | 3.18.1 |
| Psycopg / binary | 3.3.6 |
| python-dotenv | 1.2.3 |
| tzdata | 2026.4 |
| pip-tools | 7.6.1 |
| Ruff | 0.16.8 |
| colorama (portable tooling lock) | 0.4.6 |
| Next.js | 16.3.5 |
| React / React DOM | 19.3.0 |
| TypeScript | 5.9.3 |
| Biome | 2.5.14 |
| @types/node | 24.13.6 |
| @types/react / @types/react-dom | 19.3.0 |

Runtime observations: Python 3.14.5, Node 24.19.0, npm 11.17.0. PostgreSQL installation/owner-reported manual verification: 18.6.

## Verification

- Django system check: PASS, no issues.
- Foundation tests: PASS, three non-database tests; one PostgreSQL test explicitly skipped without opt-in.
- Ruff lint and formatting: PASS (13 Python files).
- pip check and hash-locked dependency installation: PASS.
- Frontend Biome checks: PASS without warnings.
- TypeScript route generation/typecheck: PASS.
- Next.js production build: PASS.
- npm package audit during final dependency installation: zero reported vulnerabilities (not a comprehensive security audit).
- Final clean npm ci verification: PASS; lint, typecheck, and production build also passed from the clean install.
- git diff --check: PASS.
- DOCX integrity: eight files match HEAD byte-for-byte.
- Local secret-value scan across tracked/candidate files: no matches.
- .env, virtual environment, node_modules, and .next: confirmed ignored.
- GitHub Actions workflow: authored, not executed remotely; no push was authorized.

## PostgreSQL status and limitation

Configured names: growthsathi_class_dev, disposable growthsathi_class_test, application role growthsathi_app_dev.
Owner approved and elected to run local role/database setup interactively.
Live application-role connection and test-database creation were attempted but failed with: no password supplied.
A secret-safe read of the root .env still found PGPASSWORD empty, despite readiness confirmations. No alternate credential source or superuser fallback was used.
Therefore application-role privileges, project DB ownership, and create/drop test-database lifecycle have NOT been verified by this checkpoint.
The ordinary test command remains usable without PostgreSQL access and reports the skipped test explicitly. CI enables the database test.

## Warnings and corrections

- Python's WindowsApps alias failed; the real Python 3.14 installation works. README documents it.
- npm.ps1 is blocked by local execution policy; npm.cmd works.
- Package registry access required approved execution outside the sandbox.
- Initial ESLint 9 was marked unsupported; ESLint 10 exposed an incompatible React plugin. Final configuration uses maintained Biome and removes the ESLint chain.
- Initial optional database test discovery incorrectly requested database setup despite its skip marker. Fixed by disabling its database requirement unless explicitly opted in.
- An unrelated parent-directory package-lock warning was resolved by explicitly setting the frontend Turbopack root.
- Production deployment check reports security.W005 (HSTS subdomains) and security.W021 (HSTS preload). Both are intentionally deferred until verified domain/HTTPS topology is known; production is not deployment-ready.
- CI uses a disposable loopback-bound PostgreSQL container with trust authentication and a non-superuser application role. This is CI-only, never production configuration.

## Commands executed

Representative exact final commands from repository root unless a directory is stated:

```powershell
& 'C:/Users/Harsh Desai/AppData/Local/Python/pythoncore-3.14-64/python.exe' --version
& 'C:/Users/Harsh Desai/AppData/Local/Python/pythoncore-3.14-64/python.exe' -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install --require-hashes -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m pip check
backend/.venv/Scripts/python.exe -m ruff check backend
backend/.venv/Scripts/python.exe -m ruff format --check backend
backend/.venv/Scripts/python.exe backend/manage.py check
backend/.venv/Scripts/python.exe backend/manage.py test tests --settings=config.settings.test
backend/.venv/Scripts/python.exe backend/manage.py check --deploy --settings=config.settings.production
$env:RUN_DATABASE_TESTS = 'true'
backend/.venv/Scripts/python.exe backend/manage.py test tests --settings=config.settings.test --noinput
Remove-Item Env:RUN_DATABASE_TESTS
git status --short --branch
git diff --check
git check-ignore .env backend/.venv frontend/node_modules frontend/.next
git diff --exit-code -- docs/*.docx
```

From backend, lock generation:
```powershell
.venv/Scripts/python.exe -m piptools compile --quiet --allow-unsafe --no-strip-extras --generate-hashes --no-emit-index-url --no-emit-trusted-host --output-file requirements.txt requirements.in
.venv/Scripts/python.exe -m piptools compile --quiet --allow-unsafe --no-strip-extras --generate-hashes --no-emit-index-url --no-emit-trusted-host --output-file requirements-dev.txt requirements-dev.in
```

From frontend:
```powershell
npm.cmd install --no-fund --fetch-retries=1 --fetch-timeout=20000
node_modules/.bin/biome.cmd check . --write
node_modules/.bin/biome.cmd migrate --write
npm.cmd ci --no-fund --fetch-retries=1 --fetch-timeout=20000
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

Also ran read-only file/runtime discovery, npm/PyPI version queries, a Django database SELECT probe (failed without a password), secret-safe environment presence checks, Python SHA-256 comparisons against git blobs, and a local secret-value scan. Initial failed lint/install/test commands were corrected or recorded above. File authoring used apply_patch and local PowerShell/Python writes. No secret input/output is included.

## Proposed commit (not executed)

chore: establish checkpoint 1 Django and Next.js foundations

## Checkpoint 2 recommendation

First complete live project-role PostgreSQL verification, then review/approve Checkpoint 1. Only after explicit authorization add Institute/InstituteDomain/custom User, exactly five roles, tenant-unique normalized usernames, non-unique contact fields, role profiles, statuses, and audit foundation. Define the custom User before enabling account migrations. Do not start authentication flows, business modules, or RLS at Checkpoint 2.
