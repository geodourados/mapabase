@echo off
REM Baixa a versao mais recente do Mapa Base Digital de Dourados-MS e abre
REM o projeto QGIS que fica embutido dentro do proprio GeoPackage.
REM Nao depende do plugin QGIS antigo — so precisa do QGIS instalado.

setlocal

set "DEST_DIR=C:\GeoDourados-Offline"
set "DEST_GPKG=%DEST_DIR%\Mapa_GeoDourados.gpkg"
set "URL=https://github.com/geodourados/mapabase/releases/download/latest/Mapa_GeoDourados.gpkg"
set "NOME_PROJETO=GeoDourados-Offline"

if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"

echo.
echo Baixando base cartografica mais recente...
echo   %URL%
echo   -> %DEST_GPKG%
echo.
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%URL%' -OutFile '%DEST_GPKG%.tmp' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
    echo.
    echo ERRO: falha no download. Verifique sua conexao com a internet.
    pause
    exit /b 1
)
move /y "%DEST_GPKG%.tmp" "%DEST_GPKG%" >nul

echo Procurando instalacao do QGIS...
set "QGIS_EXE="

REM Instalador standalone (C:\Program Files\QGIS x.y\bin\qgis-bin.exe)
if not defined QGIS_EXE (
    for /f "delims=" %%Q in ('dir /b /s "C:\Program Files\QGIS*\bin\qgis-bin.exe" 2^>nul') do (
        if not defined QGIS_EXE set "QGIS_EXE=%%Q"
    )
)

REM Instalador OSGeo4W (padrao ou LTR)
if not defined QGIS_EXE if exist "C:\OSGeo4W\bin\qgis-bin.exe" set "QGIS_EXE=C:\OSGeo4W\bin\qgis-bin.exe"
if not defined QGIS_EXE if exist "C:\OSGeo4W\bin\qgis-ltr-bin.exe" set "QGIS_EXE=C:\OSGeo4W\bin\qgis-ltr-bin.exe"
if not defined QGIS_EXE if exist "C:\OSGeo4W64\bin\qgis-bin.exe" set "QGIS_EXE=C:\OSGeo4W64\bin\qgis-bin.exe"
if not defined QGIS_EXE if exist "C:\OSGeo4W64\bin\qgis-ltr-bin.exe" set "QGIS_EXE=C:\OSGeo4W64\bin\qgis-ltr-bin.exe"

if not defined QGIS_EXE (
    echo.
    echo QGIS nao foi encontrado em "C:\Program Files".
    echo O download terminou normalmente — abra manualmente pelo QGIS:
    echo   %DEST_GPKG%
    echo ^(projeto: %NOME_PROJETO%^)
    pause
    exit /b 1
)

echo Abrindo o projeto no QGIS...
start "" "%QGIS_EXE%" "geopackage:%DEST_GPKG%?projectName=%NOME_PROJETO%"

endlocal
