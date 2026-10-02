@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"

set LOG_FILE=data\scheduler.log
if not exist "data" mkdir data

echo ======================================================== >> "%LOG_FILE%"
echo [%DATE% %TIME%] 定期自動キュレーション実行開始 >> "%LOG_FILE%"
echo ======================================================== >> "%LOG_FILE%"

uv run python -m src.main --run --push >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% equ 0 (
    echo [%DATE% %TIME%] [成功] キュレーションとGitHubプッシュが完了しました。 >> "%LOG_FILE%"
) else (
    echo [%DATE% %TIME%] [失敗] 実行中にエラーが発生しました（終了コード: %ERRORLEVEL%）。 >> "%LOG_FILE%"
)
echo. >> "%LOG_FILE%"
