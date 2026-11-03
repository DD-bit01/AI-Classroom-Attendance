@echo off
if "%~1"=="" (
    echo Usage: test_clean_detect.bat ^<path_to_group_photo^>
    echo Example: test_clean_detect.bat test_images\grp_bday.jpeg
    pause
    exit /b
)

.\venv\Scripts\python.exe test_clean_detect.py "%~1" "%~2"
pause
