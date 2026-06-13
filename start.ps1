# 启动 Flask 后端（自动选择 Python：venv > 本机 Python）
param(
    [switch]$Init
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Test-PythonExe {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $false
    }

    try {
        & $Path -c "import sys" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-PythonExe {
    $candidates = @(
        (Join-Path $Root "venv\Scripts\python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-PythonExe $candidate) {
            return $candidate
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            & $pyLauncher.Source -3.11 -c "import sys; print(sys.executable)" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $resolved = & $pyLauncher.Source -3.11 -c "import sys; print(sys.executable)"
                if (Test-PythonExe $resolved) {
                    return $resolved.Trim()
                }
            }
        } catch {
            # fall through
        }
    }

    foreach ($command in @("python", "py")) {
        $found = Get-Command $command -ErrorAction SilentlyContinue
        if (-not $found) {
            continue
        }

        try {
            & $found.Source -c "import sys" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return $found.Source
            }
        } catch {
            continue
        }
    }

    throw @"
未找到可用的 Python。

可选方案：
  1. 安装 Python 3.11+ 后执行：py -3.11 -m venv venv && .\install.ps1
  2. 若已安装 Python 但未加入 PATH，可使用：py -3.11 -m venv venv
"@
}

$python = Resolve-PythonExe
$env:PYTHONPATH = $Root
$env:NO_PROXY = "*"
$env:no_proxy = "*"

Write-Host "Python: $python"
Write-Host "工作目录: $Root"

$dbPath = Join-Path $Root "instance\steeltech.db"
if ($Init -or -not (Test-Path $dbPath)) {
    if (-not (Test-Path $dbPath)) {
        Write-Host "未找到数据库，正在初始化 instance\steeltech.db ..."
    } else {
        Write-Host "正在重新初始化数据库 ..."
    }
    & $python (Join-Path $Root "init_db.py")
}

Write-Host "启动后端: http://localhost:5000"
Write-Host "健康检查: http://localhost:5000/api/health"
Write-Host ""

& $python (Join-Path $Root "run.py")
