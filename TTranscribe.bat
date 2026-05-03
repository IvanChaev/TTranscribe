@echo off
:: Проверяем, что pythonw доступен
where pythonw >nul 2>nul
if %errorlevel% neq 0 (
    echo Pythonw.exe не найден в системном PATH.
    echo Убедитесь, что Python установлен и добавлен в переменную PATH, затем повторите запуск.
    pause
    exit /b 1
)
start "" pythonw.exe transcriber.py
exit