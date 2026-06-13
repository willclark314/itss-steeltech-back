# 绕过 Windows 系统代理（如 Clash 127.0.0.1:7897）导致的 pip SSL 错误
$env:NO_PROXY = "*"
$env:no_proxy = "*"

.\venv\Scripts\pip install -r requirements.txt @args
