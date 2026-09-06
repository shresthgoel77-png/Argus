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
