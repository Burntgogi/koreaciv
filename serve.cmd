@echo off
cd /d "%~dp0site"
echo http://localhost:8000/  (koreaciv)
echo http://localhost:8000/yeojido/  (sinyeojido)
python -m http.server 8000
