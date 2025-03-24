@echo off
echo Запуск бота в режиме отладки...
echo.
python -c "import sys; print('Python версии:', sys.version)"
echo.
echo Проверка файла .env:
if exist .env (
  echo Файл .env найден
) else (
  echo ОШИБКА: Файл .env не найден!
)
echo.
echo Запуск бота:
python bot.py
echo.
echo Нажмите любую клавишу для выхода.
pause 