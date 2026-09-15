@echo off
REM Instala o plugin "Mapa Base - GeoDourados" no QGIS (se ainda nao
REM estiver instalado/atualizado), baixa a versao mais recente da base
REM cartografica e abre o projeto. Depois desta primeira execucao, o
REM proprio plugin cuida de avisar sobre atualizacoes toda vez que o QGIS
REM abrir (icone com aviso na barra de ferramentas).

setlocal enabledelayedexpansion

set "DEST_DIR=C:\GeoDourados-Offline"
set "DEST_GPKG=%DEST_DIR%\Mapa_GeoDourados.gpkg"
set "URL_GPKG=https://github.com/geodourados/mapabase/releases/download/latest/Mapa_GeoDourados.gpkg"
set "URL_PLUGIN=https://github.com/geodourados/mapabase/releases/download/latest/MapaBase_GeoDourados_plugin.zip"
set "NOME_PROJETO=GeoDourados-Offline"
set "PLUGIN_DIR=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\MapaBase_GeoDourados"
set "QGIS3_INI=%APPDATA%\QGIS\QGIS3\profiles\default\QGIS\QGIS3.ini"

if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"

echo.
echo Instalando/atualizando o plugin do Mapa Base no QGIS...
powershell -NoProfile -Command ^
    "try {" ^
    "  $tmpZip = Join-Path $env:TEMP 'MapaBase_GeoDourados_plugin.zip';" ^
    "  Invoke-WebRequest -Uri '%URL_PLUGIN%' -OutFile $tmpZip -UseBasicParsing;" ^
    "  $destino = '%PLUGIN_DIR%';" ^
    "  if (Test-Path $destino) { Remove-Item $destino -Recurse -Force };" ^
    "  Expand-Archive -Path $tmpZip -DestinationPath (Split-Path $destino -Parent) -Force;" ^
    "  Remove-Item $tmpZip -Force;" ^
    "  $iniPath = '%QGIS3_INI%';" ^
    "  New-Item -ItemType Directory -Force -Path (Split-Path $iniPath -Parent) | Out-Null;" ^
    "  if (Test-Path $iniPath) { $c = Get-Content $iniPath -Raw -Encoding UTF8 } else { $c = '' };" ^
    "  if ($c -notmatch '\[PythonPlugins\]') { $c += \"`r`n[PythonPlugins]`r`n\" };" ^
    "  if ($c -match 'MapaBase_GeoDourados\s*=.*') { $c = $c -replace 'MapaBase_GeoDourados\s*=.*', 'MapaBase_GeoDourados=true' }" ^
    "  else { $c = $c -replace '(\[PythonPlugins\]\r?\n)', \"`$1MapaBase_GeoDourados=true`r`n\" };" ^
    "  Set-Content -Path $iniPath -Value $c -Encoding UTF8 -NoNewline;" ^
    "} catch { Write-Output ('ERRO: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo AVISO: falha ao instalar o plugin — a base ainda sera baixada, mas sem o aviso automatico de atualizacao.
)

set "PRECISA_BAIXAR=1"
if exist "%DEST_GPKG%" (
    echo Verificando se ha atualizacao disponivel...
    set "STATUS="
    for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command ^
        "$ErrorActionPreference='Stop'; $l=(Get-Item '%DEST_GPKG%').Length; try { $r=(Invoke-WebRequest -Uri '%URL_GPKG%' -Method Head -UseBasicParsing).Headers['Content-Length']; $r=[int64]$r[0] } catch { Write-Output 'erro'; exit }; if ([Math]::Abs($r-$l) -le 1024) { Write-Output 'atualizado' } else { Write-Output 'desatualizado' }"`) do set "STATUS=%%S"

    if "!STATUS!"=="atualizado" (
        echo Ja esta na versao mais recente — pulando download.
        set "PRECISA_BAIXAR=0"
    ) else if "!STATUS!"=="desatualizado" (
        echo Nova versao disponivel.
    ) else (
        echo Nao foi possivel verificar — baixando por seguranca.
    )
)

if "!PRECISA_BAIXAR!"=="1" (
    echo.
    echo Baixando base cartografica mais recente...
    echo   %URL_GPKG%
    echo   -^> %DEST_GPKG%
    echo.
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%URL_GPKG%' -OutFile '%DEST_GPKG%.tmp' -UseBasicParsing } catch { exit 1 }"
    if errorlevel 1 (
        echo.
        echo ERRO: falha no download. Verifique sua conexao com a internet.
        pause
        exit /b 1
    )
    move /y "%DEST_GPKG%.tmp" "%DEST_GPKG%" >nul
    if errorlevel 1 (
        echo.
        echo ERRO: nao foi possivel substituir o arquivo atual.
        echo Feche todas as janelas do QGIS que estejam com o Mapa Base aberto e tente de novo.
        del "%DEST_GPKG%.tmp" >nul 2>nul
        pause
        exit /b 1
    )
)

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
REM "--project" e necessario — passar a URI geopackage: como argumento
REM posicional simples faz o QGIS tratar como caminho relativo e falhar
REM ("nao e uma fonte de dados valida"), mesmo sendo um caminho absoluto.
start "" "%QGIS_EXE%" --project "geopackage:%DEST_GPKG%?projectName=%NOME_PROJETO%"

endlocal
