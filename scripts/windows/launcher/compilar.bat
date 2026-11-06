@echo off
rem Recompila o GalviTracks.exe da raiz do projeto a partir de GalviTracks.cs.
rem Usa o compilador C# do .NET Framework 4, que já vem no Windows 10/11.
setlocal
cd /d "%~dp0"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    echo [ERRO] csc.exe do .NET Framework 4 nao encontrado.
    exit /b 1
)
if not exist galvitracks.ico powershell -NoProfile -ExecutionPolicy Bypass -File gerar_icone.ps1 || exit /b 1
"%CSC%" /nologo /optimize+ /target:exe /platform:anycpu /win32icon:galvitracks.ico /out:..\..\..\GalviTracks.exe GalviTracks.cs || exit /b 1
echo [OK] GalviTracks.exe gerado na raiz do projeto.
