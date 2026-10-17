# RepoMedic Backend

## Prerequisites

Python 3.10+ recommended.

## Development Setup

1. Navigation and Virutal Env creation
   ```bash
   cd backend
   python -m venv venv
   ```

2. Activate the virtual environment
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

3. Install requirements
   ```bash
   pip install -r requirements.txt
   ```

## Running the Server

Start the application with Uvicorn in development mode:
```bash
uvicorn app.main:app --reload
```

## Database Migrations

This project uses Alembic for database migrations.

To apply migrations:
```bash
alembic upgrade head
```

To autogenerate a new migration after updating models:
```bash
alembic revision --autogenerate -m "description of changes"
```

## GitHub issue confirmation emails

Optional confirmation emails use the existing SMTP provider. Set `SMTP_HOST`,
`SMTP_USERNAME`, and `SMTP_PASSWORD` in the backend environment. Optional settings:
`SMTP_PORT` (587 with TLS, otherwise 25), `SMTP_FROM_ADDRESS` (defaults to the SMTP
username), and `SMTP_USE_TLS` (defaults to true). `CLERK_SECRET_KEY` is also needed
to confirm that the initiating authenticated user's registered email is verified.
Missing configuration or a missing verified address skips the email.

Only a newly created GitHub issue with a confirmed issue URL schedules an email;
failed, skipped, duplicate, and reconciled requests do not. Delivery runs in
FastAPI background tasks after the response, with a separate database session
for an optional saved, completed finding AI summary. It does not generate AI
content or change notification preferences. This confirmation is independent of
severity-filtered finding alerts. Delivery is best effort and is not durable
across a process restart; failures are logged without email content or secrets.

## Integration Tests

Integration tests run against a real PostgreSQL database instance to ensure database interactions work accurately. They use a separate test database so as not to interfere with development data.

### One-Time Setup

Create the test database in the PostgreSQL container:
```bash
docker exec -it repomedic-postgres psql -U repomedic_user -d postgres -c "CREATE DATABASE repomedic_test;"
```

### Running the Tests

Ensure the `TEST_DATABASE_URL` is set appropriately in your `.env` (it is already in `.env.example`).
Then, execute pytest focusing on the integration tests directory:
```bash
pytest backend/tests/integration/ -v
```
