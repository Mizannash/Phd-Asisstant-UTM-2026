@echo off
set "VAULT_PATH=%~dp0output\Obsidian_Vault"

:: 1. Ensure the folder exists so Obsidian doesn't crash
if not exist "%VAULT_PATH%" (
    mkdir "%VAULT_PATH%"
)

:: 2. Use PowerShell to properly URL-encode the path and launch Obsidian
powershell -NoProfile -Command "$path = '%VAULT_PATH%'; $uri = 'obsidian://open?path=' + [uri]::EscapeDataString($path); Start-Process $uri"

exit
