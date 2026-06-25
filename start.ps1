# 启动 Flask 后端（自动选择 Python：venv > 本机 Python）
param(
    [switch]$Init,
    [switch]$Reset
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

# 从 Config 获取实际数据库路径（尊重 SQLITE_DATABASE_PATH 环境变量）
$dbPath = (& $python -c "from dotenv import load_dotenv; load_dotenv(); from steeltech_db.config import BaseConfig; print(BaseConfig.SQLITE_DATABASE_PATH)").Trim()
Write-Host "数据库路径: $dbPath"

# -Init 或 -Reset：删除现有数据库文件，由 create_app() 重建
if ($Init -or $Reset) {
    if (Test-Path $dbPath) {
        Write-Host "删除现有数据库: $dbPath"
        Remove-Item $dbPath -Force
    } else {
        Write-Host "数据库文件不存在，将新建: $dbPath"
    }
}

Write-Host "启动后端: http://localhost:5000"
Write-Host "健康检查: http://localhost:5000/api/health"
Write-Host ""

# run.py → create_app() 会自动完成:
#   1. bootstrap_sqlite_file  – 创建数据库文件 + 执行 schema.sql
#   2. ensure_schema         – db.create_all() + 迁移旧字段 + 同步权限
#   3. seed_if_empty         – 填充种子数据（仅首次）
& $python (Join-Path $Root "run.py")
