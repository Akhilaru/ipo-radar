# Load environment variables from .env file
# Usage: .\load-env.ps1

$envFile = Join-Path $PSScriptRoot ".env"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        # Skip comments and empty lines
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "Loaded: $key" -ForegroundColor Green
        }
    }
    Write-Host "`nEnvironment loaded from .env" -ForegroundColor Cyan
} else {
    Write-Host "Error: .env file not found at $envFile" -ForegroundColor Red
    exit 1
}
