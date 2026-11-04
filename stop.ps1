# Arrête le serveur FinOVA lancé par start.ps1, et seulement lui (PID dans .finova.pid).
$ErrorActionPreference = "Stop"
$pidFile = Join-Path $PSScriptRoot ".finova.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "Aucun serveur lancé par start.ps1 (.finova.pid absent)."
    exit 0
}
$serverPid = (Get-Content $pidFile -Raw).Trim()
$process = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
if (-not $process) {
    Write-Host "Le serveur (PID $serverPid) n'est plus actif ; .finova.pid supprimé."
} elseif ($process.ProcessName -notlike "python*") {
    # PID réutilisé par un autre programme : on ne touche à rien
    Write-Host "Le PID $serverPid appartient maintenant à $($process.ProcessName), pas à FinOVA : rien n'est arrêté." -ForegroundColor Yellow
} else {
    # le python.exe du venv est un lanceur : on arrête aussi son processus enfant (uvicorn)
    & taskkill.exe /PID $serverPid /T /F | Out-Null
    Write-Host "FinOVA arrêté (PID $serverPid)." -ForegroundColor Green
}
Remove-Item $pidFile -Force
