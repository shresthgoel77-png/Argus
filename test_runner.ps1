$ErrorActionPreference = "Continue"

Write-Host "Starting DB..."
docker compose up -d postgres

Write-Host "Starting Backend..."
$backendJob = Start-Job -ScriptBlock {
    cd backend
    .\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

}

Write-Host "Starting Frontend..."
$frontendJob = Start-Job -ScriptBlock {
    cd frontend
    npm run dev
}

Write-Host "Waiting for backend..."
$backendUp = $false
for ($i=0; $i -lt 30; $i++) {
    try {
        $res = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -UseBasicParsing -ErrorAction Stop
        if ($res.StatusCode -eq 200) { $backendUp = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $backendUp) { Write-Host "Backend failed"; exit 1 }

Write-Host "Waiting for frontend..."
$frontendUp = $false
for ($i=0; $i -lt 60; $i++) {
    try {
        $res = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -ErrorAction Stop
        if ($res.StatusCode -eq 200) { $frontendUp = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $frontendUp) { Write-Host "Frontend failed"; exit 1 }

Write-Host "Running Playwright Tests..."
cd frontend
npx playwright test --reporter=list > test_output.txt
$testExitCode = $LASTEXITCODE
cat test_output.txt
$testExitCode = $LASTEXITCODE

Write-Host "Cleaning up background jobs..."
Stop-Job $backendJob -ErrorAction SilentlyContinue
Stop-Job $frontendJob -ErrorAction SilentlyContinue
Remove-Job $backendJob -ErrorAction SilentlyContinue
Remove-Job $frontendJob -ErrorAction SilentlyContinue

Write-Host "Done with exit code: $testExitCode"
exit $testExitCode
