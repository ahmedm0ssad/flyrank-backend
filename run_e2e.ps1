$ErrorActionPreference = "Stop"
$REDIS_URL = "redis://localhost:6379/0"
$ROOT = $PSScriptRoot

Write-Host "=== Starting Redis server ==="
Stop-Process -Name "redis-server" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
$redisProc = Start-Process -FilePath "C:\Program Files\Redis\redis-server.exe" -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2

Write-Host "=== Starting FastAPI server ==="
$env:REDIS_URL = $REDIS_URL
$env:SUPABASE_URL = "https://test.supabase.co"
$env:SUPABASE_KEY = "test-anon-key"
$serverProc = Start-Process -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -Environment @{REDIS_URL=$REDIS_URL}
Start-Sleep -Seconds 4

Write-Host "=== Starting RQ worker ==="
$workerProc = Start-Process -FilePath "python" -ArgumentList "-m rq worker ai-jobs --url $REDIS_URL" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2

Write-Host "=== Running E2E tests ==="
$env:REDIS_URL = $REDIS_URL
$env:E2E_BASE_URL = "http://localhost:8000"
python -m pytest tests/test_ai_e2e.py -v -s 2>&1

Write-Host "=== Cleanup ==="
Stop-Process -Id $workerProc.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $redisProc.Id -Force -ErrorAction SilentlyContinue
$redisProc.Kill()
Write-Host "=== Done ==="