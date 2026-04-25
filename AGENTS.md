# Repository Guidelines

## Project Structure & Module Organization

This is a Django 5.1 building management application. The Django project lives in `config/`, with shared, local, and production settings under `config/settings/`. Domain apps are `accounts/` for users, roles, authentication, and middleware, and `locations/` for buildings, units, leases, parking, meters, and ledgers. Shared templates are in `templates/`, app templates live under each app's `templates/`, static assets are in `static/`, development uploads are in `media/`, Albanian translations are in `locale/sq/LC_MESSAGES/`, and planning notes are in `working_scope/`.

## Build, Test, and Development Commands

Run the full local stack with Docker Compose:

```bash
docker compose up -d
```

The `web` service runs migrations and serves Django at `http://localhost:8800/`. Seed default users on a fresh database with:

```bash
docker compose exec web python seed.py
```

Common maintenance commands:

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py compilemessages
docker compose logs -f web
docker compose down
```

Use `docker compose build` after dependency or Dockerfile changes.

## Coding Style & Naming Conventions

Follow standard Django conventions. Use 4-space indentation in Python, snake_case for functions and fields, PascalCase for classes and models, and descriptive template names such as `lease_ledger_form.html`. Keep domain logic inside the relevant app. Prefer names that match existing business concepts: `Lease`, `Unit`, `MeterLedger`, `ParkingPlace`. Reuse `templates/base.html` for shared layout.

## Testing Guidelines

No test suite is currently checked in. Add tests in each app using Django's default patterns, for example `accounts/tests.py` or `locations/tests/test_leases.py`. Name tests for behavior, such as `test_admin_can_create_user`. Run tests with:

```bash
docker compose exec web python manage.py test
```

For model or migration changes, also run `makemigrations --check --dry-run` before opening a pull request.

## Commit & Pull Request Guidelines

Git history is not available in this workspace, so use clear imperative commit subjects, for example `Add lease ledger payment slip upload`. Keep commits focused by feature or fix. Pull requests should include a short summary, testing notes, linked issue or task reference, and screenshots for UI changes. Mention any migrations, seed data changes, or configuration changes explicitly.

## Security & Configuration Tips

Do not commit real secrets or production uploads. Local configuration comes from `.env` and Docker Compose defaults. Production deployments must set `SECRET_KEY`, database credentials, `DEBUG=0`, and trusted host/origin values outside the repository.
