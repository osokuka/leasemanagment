# Lease Management — Building Management System

Django full-stack web application with PostgreSQL, containerized via Docker.

## Tech Stack
- **Backend:** Django 5.1
- **Database:** PostgreSQL 16
- **Frontend:** Django templates + HTMX
- **Containerization:** Docker & Docker Compose
- **Languages:** English / Albanian (i18n)
- **Themes:** Dark / Light

## Quick Start

```bash
# Start all services
docker compose up -d

# Seed initial users (first time only)
docker compose exec web python seed.py

# Access the app
# http://localhost:8800/login/
```

## Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Super User | admin | admin123 |
| Admin | manager | manager123 |
| Data Entry Clerk | clerk | clerk123 |

## Project Structure

```
├── config/               # Django project settings
│   ├── settings/
│   │   ├── base.py       # Shared settings
│   │   ├── local.py      # Development settings
│   │   └── production.py # Production settings
│   ├── urls.py           # Root URL configuration
│   └── wsgi.py
├── accounts/             # User management app
│   ├── models.py         # Custom User model with roles
│   ├── views.py          # CRUD views
│   ├── forms.py          # User forms
│   ├── urls.py           # Route definitions
│   └── templates/accounts/
├── templates/            # Global templates (base.html)
├── static/               # CSS, JS assets
├── locale/               # Translation files (en, sq)
├── working_scope/        # Branding & style guidelines
├── docker-compose.yml
├── Dockerfile
└── seed.py               # Initial data seeder
```

## User Roles

- **Super User** — Full access, can delete any user
- **Admin** — Can create/edit/delete users (except Super Users)
- **Data Entry Clerk** — Can view users only

## Useful Commands

```bash
# View logs
docker compose logs -f web

# Run migrations
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Compile translations
docker compose exec web python manage.py compilemessages

# Create superuser manually
docker compose exec web python manage.py createsuperuser

# Stop services
docker compose down

# Rebuild after code changes
docker compose build && docker compose up -d
```

## Branding

See `working_scope/branding.md` for design guidelines including color palette, typography, and component styles.
