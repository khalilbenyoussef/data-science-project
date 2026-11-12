# Lance le dashboard FinOVA (API FastAPI + front buildé) sur http://127.0.0.1:8000.
# Usage : .\start.ps1            (ouvre le navigateur)
#         .\start.ps1 -NoBrowser
# Arrêt : .\stop.ps1 (n'arrête que le serveur lancé par ce script, PID dans .finova.pid)
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$dist = Join-Path $root "dashboard_app\web\dist\index.html"
$pidFile = Join-Path $root ".finova.pid"
$logOut = Join-Path $root "outputs\logs\finova-server.out.log"
$logErr = Join-Path $root "outputs\logs\finova-server.err.log"
$url = "http://127.0.0.1:$Port"

function Fail([string]$message) {
    Write-Host "ERREUR : $message" -ForegroundColor Red
    exit 1
}

# 1. Environnement Python et front buildé
if (-not (Test-Path $python)) {
    Fail "environnement .venv introuvable. Créez-le : python -m venv .venv ; .\.venv\Scripts\python -m pip install --require-hashes -r requirements.lock"
}
if (-not (Test-Path $dist)) {
    Fail "front non buildé (dashboard_app\web\dist absent). Lancez : cd dashboard_app\web ; npm ci ; npm run build"
}

# 2. Serveur déjà lancé par ce script ?
if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile -Raw).Trim()
    $old = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($old) {
        Fail "FinOVA tourne déjà (PID $oldPid). Ouvrez $url ou arrêtez-le avec .\stop.ps1"
    }
    Remove-Item $pidFile -Force   # PID périmé (serveur arrêté autrement)
}

# 3. Port libre ?
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $owner = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    $name = if ($owner) { $owner.ProcessName } else { "inconnu" }
    Fail "le port $Port est déjà utilisé par le processus $name (PID $($listener.OwningProcess)). Libérez-le ou utilisez -Port."
}

# 4. Lancement (PYTHONPATH=src, depuis la racine du projet)
New-Item -ItemType Directory -Force (Split-Path $logOut) | Out-Null
$env:PYTHONPATH = "src"
# Les liens d'invitation/reset envoyes par email doivent pointer vers ce port.
$env:BIFLOW_PUBLIC_URL = $url
$process = Start-Process -FilePath $python -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $logOut -RedirectStandardError $logErr `
    -ArgumentList @("-m", "uvicorn", "dashboard_app.api.app:app", "--host", "127.0.0.1", "--port", "$Port")
Set-Content -Path $pidFile -Value $process.Id -Encoding ascii

# 5. Attente de l'API (60 s max). /api/health est protégé : on sonde la page
#    publique de connexion, servie par le même serveur.
$ready = $false
for ($i = 0; $i -lt 120; $i++) {
    if ($process.HasExited) { break }
    try {
        Invoke-WebRequest -Uri "$url/login" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
if (-not $ready) {
    if (-not $process.HasExited) { & taskkill.exe /PID $process.Id /T /F | Out-Null }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    Fail "le serveur n'a pas démarré. Voir $logErr"
}

Write-Host "FinOVA démarré : $url (PID $($process.Id), journaux dans outputs\logs\)" -ForegroundColor Green
Write-Host "Arrêt : .\stop.ps1"
if (-not $NoBrowser) { Start-Process $url }
