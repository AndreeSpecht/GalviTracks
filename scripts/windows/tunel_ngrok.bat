@echo off
setlocal
chcp 65001 >nul
title Radar Tracker - Tunel ngrok
cd /d "%~dp0..\.."

rem Le NGROK_DOMAIN e PORT do arquivo .env
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
rem .env.local guarda as senhas deste PC (fora do git) e tem prioridade
if exist .env.local for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env.local") do set "%%a=%%b"
if not defined PORT set "PORT=5000"

rem Sem token qualquer pessoa na internet poderia enviar posicoes falsas
if not defined OWNTRACKS_TOKEN (
    echo [ERRO] Defina OWNTRACKS_TOKEN no .env antes de abrir o tunel.
    echo        Use a mesma senha configurada no app OwnTracks dos motoboys.
    pause
    exit /b 1
)

set "NGROK=ngrok"
if exist tools\ngrok.exe set "NGROK=tools\ngrok.exe"

if defined NGROK_DOMAIN (
    echo Publicando http://localhost:%PORT% em https://%NGROK_DOMAIN%
    "%NGROK%" http --domain=%NGROK_DOMAIN% %PORT%
) else (
    echo NGROK_DOMAIN nao definido no .env - usando endereco temporario.
    "%NGROK%" http %PORT%
)
pause
