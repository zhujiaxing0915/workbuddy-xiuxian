@echo off
setlocal
:: 一键注册「修仙自动结算」计划任务（每天 09:00 / 21:00 自动结算修为）
:: 需要管理员权限：双击后若未提权会自动弹出 UAC 确认框

net session >nul 2>&1
if not %errorlevel%==0 (
  echo Requesting administrator privileges...
  powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "PY=C:\Python313\python.exe"
set "SCR=C:\Users\Administrator\.workbuddy\skills\xiuxian\scripts\auto_reconcile.py"

schtasks /Create /TN "xiuxian-auto-am" /TR "\"%PY%\" \"%SCR%\" --commit" /SC DAILY /ST 09:00 /F
schtasks /Create /TN "xiuxian-auto-pm" /TR "\"%PY%\" \"%SCR%\" --commit" /SC DAILY /ST 21:00 /F

echo.
echo === 已注册任务 ===
schtasks /Query /TN "xiuxian-auto-am" /FO LIST /V | findstr /I "TaskName Next Run Status"
schtasks /Query /TN "xiuxian-auto-pm" /FO LIST /V | findstr /I "TaskName Next Run Status"
echo.
echo 完成。每天 09:00 / 21:00 会自动扫描 WorkBuddy 会话并按真实使用结算修为。
echo 卸载：schtasks /Delete /TN xiuxian-auto-am /F ^& schtasks /Delete /TN xiuxian-auto-pm /F
pause