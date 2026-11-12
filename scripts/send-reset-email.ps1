# Envoie un lien de reinitialisation FinOVA a benrebehn@gmail.com via Gmail SMTP.
# Usage : .\scripts\send-reset-email.ps1
# Prerequis : SMTP_PASSWORD renseigne dans .env (mot de passe d'application Google).
[CmdletBinding()]
param(
    [string]$Email = "benrebehn@gmail.com"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:PYTHONPATH = "src"

$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "ERREUR : .env absent. Copiez .env.example en .env." -ForegroundColor Red
    exit 1
}
if (-not (Select-String -Path $envFile -Pattern '^SMTP_PASSWORD=\S+' -Quiet)) {
    Write-Host "ERREUR : SMTP_PASSWORD est vide dans .env." -ForegroundColor Red
    Write-Host "Collez-y un mot de passe d'application Google (16 caracteres, sans espaces),"
    Write-Host "cree sur https://myaccount.google.com/apppasswords (validation en deux etapes requise)."
    exit 1
}

& .\.venv\Scripts\python.exe -m dashboard_app.auth.cli reset --email $Email
exit $LASTEXITCODE
