#!/usr/bin/env bash
# Artisan Crust & Crumb - Launcher Script
echo "========================================================"
echo " Artisan Crust & Crumb - Bakery Order Register"
echo "========================================================"
echo "1. Launch Graphical Interface (Streamlit, app.py)"
echo "2. Launch Interactive Terminal CLI (main.py)"
echo "3. Run Automated Unit Test Suite (test_bakery.py)"
echo "========================================================"
read -p "Select option [1-3]: " opt

if [ "$opt" = "1" ]; then
    python3 -m streamlit run app.py
elif [ "$opt" = "2" ]; then
    python3 main.py
elif [ "$opt" = "3" ]; then
    python3 -m unittest tests/test_bakery.py
else
    echo "Invalid option. Exiting."
fi
