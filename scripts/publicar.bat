@echo off
REM Rotina diária — chamada pelo Task Scheduler do Windows.
REM Ajuste o caminho do Python e do GDAL (ogr2ogr) abaixo se necessário.

REM Caminhos explicitos — nao depende do PATH herdado do processo que
REM chama este .bat, que varia (Task Scheduler S4U tem o PATH completo do
REM usuario, mas um QGIS aberto direto pode nao ter o gh CLI no PATH).
set "PATH=C:\Program Files\PostgreSQL\16\bin;C:\Program Files\GitHub CLI;C:\Program Files\Git\cmd;C:\Program Files\Git\mingw64\bin;C:\Program Files\Git\usr\bin;%PATH%"
cd /d "%~dp0.."
if not exist logs mkdir logs
python scripts\publicar.py >> logs\publicar.log 2>&1
