@echo off
title NEXORA
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Nexora.ps1"
if errorlevel 1 pause
