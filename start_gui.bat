@echo off
cd /d "%~dp0"
title Artisan Crust & Crumb - Bakery Order Register
echo ========================================================
echo  ARTISAN CRUST & CRUMB - BAKERY ORDER REGISTER
echo  Starting the Streamlit interface...
echo ========================================================
echo.
python -m streamlit run app.py
if errorlevel 1 (
  echo.
  echo Could not start the application. Check that Python and Streamlit are installed.
  echo Install the requirements with: pip install -r requirements.txt
)
pause
