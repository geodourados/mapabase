@echo off
REM Rotina diária — chamada pelo Task Scheduler do Windows.
REM Ajuste o caminho do Python e do GDAL (ogr2ogr) abaixo se necessário.

set "PATH=C:\Program Files\PostgreSQL\16\bin;%PATH%"
cd /d "%~dp0.."
if not exist logs mkdir logs
python scripts\publicar.py >> logs\publicar.log 2>&1
