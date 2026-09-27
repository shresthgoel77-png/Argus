$ErrorActionPreference = "Stop"

# Start the test postgres DB if not started
docker compose up -d postgres

# Start Backend
Start-Job -Name BackendClerk -ScriptBlock {
    cd "backend"
    if (!(Test-Path venv)) { python -m venv venv }
    .\venv\Scripts\Activate.ps1
    
    $env:APP_ENV = "test"
    $env:AUTH_PROVIDER = "clerk"
    $env:DATABASE_URL = "postgresql+psycopg2://repomedic_user:repomedic_password@localhost:5432/repomedic_db"
    $env:CORS_ORIGINS = "http://localhost:3000,http://localhost:3005"
    $env:CLERK_AUTHORIZED_PARTIES = '["http://localhost:3005"]'
    
    # Read variables from backend/.env if needed or mock them
    $env:GITHUB_APP_ID = "4929962"
    $env:GITHUB_APP_SLUG = "argus-test-67"
    $env:GITHUB_APP_WEBHOOK_SECRET = "my-dev-secret-1"
    
    # Needs CLERK_SECRET_KEY
    $envContent = Get-Content "..\frontend\.env"
    foreach ($line in $envContent) {
        if ($line.StartsWith("CLERK_SECRET_KEY=")) {
            $env:CLERK_SECRET_KEY = $line.Substring("CLERK_SECRET_KEY=".Length).Trim()
        }
    }
    
    pip install -r requirements.txt
    python -m alembic upgrade head
    python -m uvicorn app.main:app --port 8005 --reload
}

# Start Frontend
Start-Job -Name FrontendClerk -ScriptBlock {
    cd "frontend"
    $envContent = Get-Content ".env"
    foreach ($line in $envContent) {
        if ($line.Contains("=")) {
            $parts = $line.Split("=", 2)
            Set-Item -Path "Env:$($parts[0])" -Value $parts[1].Trim().Trim('"')
        }
    }
    
    $env:NEXT_PUBLIC_API_URL = "http://localhost:8005"
    $env:NEXT_PUBLIC_CLERK_SIGN_IN_URL = "/sign-in"
    $env:NEXT_PUBLIC_CLERK_SIGN_UP_URL = "/sign-up"
    $env:NEXT_DIST_DIR = ".next-clerk-e2e"
    
    npm install
    npm run dev -- -p 3005
}

Write-Output "Clerk E2E services starting on ports 8005 and 3005 in background jobs."
