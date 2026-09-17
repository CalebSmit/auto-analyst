@echo off
rem Start the Automated Analyst: sets up what is missing, checks, and opens the dashboard.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start.ps1" %*
