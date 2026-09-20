@echo off
echo Starting PhD Assistant UTM Command Center...
call venv\Scripts\activate
streamlit run src/dashboard.py
pause
