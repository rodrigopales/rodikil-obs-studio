# Prepara uma máquina Windows para usar este repositório com o OBS (idempotente: pode rodar de novo).
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup_machine.ps1
#
# Faz: venv + dependências Python, cria .env (a partir do .env.example), instala o plugin de recorte de fundo
# (versão fixa, com verificação SHA-256) e aplica o perfil de saída do OBS (precisa do OBS FECHADO).
# NÃO faz: senha do WebSocket, chave de transmissão, login do YouTube e escolha de webcam/microfone — veja o README.

param(
    [switch]$SkipPlugin,
    [switch]$SkipProfile,
    [string]$ObsProfile = "Sem nome"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$PluginVersion = "1.4.1"
$PluginUrl = "https://github.com/royshil/obs-backgroundremoval/releases/download/$PluginVersion/obs-backgroundremoval-$PluginVersion-windows-x64.zip"
$PluginSha256 = "7F9C0118C348111BF384C71E23FD056FD26E999BCE90132D91DB3017C6FA1B94"
$PluginsDir = "C:\ProgramData\obs-studio\plugins"
$PluginDll = Join-Path $PluginsDir "obs-backgroundremoval\bin\64bit\obs-backgroundremoval.dll"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    [ok] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    [!] $msg" -ForegroundColor Yellow }

# 1) Python + venv -----------------------------------------------------------
Step "Ambiente Python"
$py = (Get-Command py -ErrorAction SilentlyContinue)
if ($py) { $pyExe = "py"; $pyArgs = @("-3") } elseif (Get-Command python -ErrorAction SilentlyContinue) { $pyExe = "python"; $pyArgs = @() }
else { throw "Python 3 não encontrado. Instale em https://www.python.org/downloads/ (marque 'Add to PATH') e rode de novo." }
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pyExe @pyArgs -m venv .venv
    Ok "venv criado"
} else { Ok "venv já existe" }
& .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
Ok "dependências instaladas (requirements.txt)"

# 2) .env --------------------------------------------------------------------
Step "Arquivo .env (segredos locais — nunca vai para o Git)"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Warn ".env criado a partir do .env.example — preencha OBS_PASSWORD e MIC_DEVICE_ID (veja o README)"
} else { Ok ".env já existe (não foi alterado)" }

# 3) Plugin de recorte de fundo ------------------------------------------------
Step "Plugin Background Removal $PluginVersion"
if ($SkipPlugin) { Warn "pulado (-SkipPlugin)" }
elseif (Test-Path $PluginDll) { Ok "já instalado em $PluginsDir" }
else {
    $tmp = Join-Path $env:TEMP "rodikil-bgremoval-$PluginVersion"
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $zip = Join-Path $tmp "plugin.zip"
    Invoke-WebRequest -Uri $PluginUrl -OutFile $zip -UseBasicParsing
    $hash = (Get-FileHash $zip -Algorithm SHA256).Hash
    if ($hash -ne $PluginSha256) { throw "SHA-256 do plugin não confere ($hash). Download corrompido ou alterado — abortado." }
    Ok "download conferido (SHA-256)"
    Expand-Archive $zip (Join-Path $tmp "x") -Force
    try {
        New-Item -ItemType Directory -Force $PluginsDir | Out-Null
        Copy-Item (Join-Path $tmp "x\obs-backgroundremoval") $PluginsDir -Recurse -Force
        Ok "instalado em $PluginsDir"
    } catch {
        Warn "sem permissão para gravar em $PluginsDir."
        Warn "Copie manualmente a pasta '$tmp\x\obs-backgroundremoval' para '$PluginsDir' (ou rode este script como Administrador)."
        Start-Process explorer.exe (Join-Path $tmp "x")
    }
}

# 4) Perfil de saída do OBS --------------------------------------------------
Step "Perfil do OBS ('$ObsProfile'): 1080p60, NVENC CBR 9000, AAC 160"
if ($SkipProfile) { Warn "pulado (-SkipProfile)" }
elseif (Get-Process obs64 -ErrorAction SilentlyContinue) { Warn "o OBS está aberto — feche-o e rode: .venv\Scripts\python scripts\setup_obs_profile.py" }
else {
    & .venv\Scripts\python.exe scripts\setup_obs_profile.py --profile $ObsProfile
    if ($LASTEXITCODE -ne 0) { Warn "perfil não aplicado — abra o OBS uma vez (para ele criar o perfil), feche e rode de novo" }
}

Step "Pronto. Próximos passos (README > 'Máquina nova'):"
Write-Host "    1. Abra o OBS > Ferramentas > Configurações do servidor WebSocket > ative e copie a senha para OBS_PASSWORD no .env"
Write-Host "    2. .venv\Scripts\python scripts\test_connection.py --devices   (copie o ID do Fifine para MIC_DEVICE_ID)"
Write-Host "    3. .venv\Scripts\python scripts\apply_scene.py --all --dry-run   e depois sem --dry-run"
Write-Host "    4. No OBS: escolha a webcam em Webcam_Main, conecte a conta do YouTube e desative o mic no Áudio Global"
