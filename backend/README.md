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
