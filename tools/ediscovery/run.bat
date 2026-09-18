@echo off
REM One-click run. Edit the three paths below, then double click this file.
REM Everything stays on this machine. Metadata only. No content is read.

set EXPORTS=C:\ediscovery\exports
set DB=C:\ediscovery\itar.db
set REPORTS=C:\ediscovery\reports

echo.
echo === Checking what is in the export folder ===
python "%~dp0edisc.py" inspect --exports "%EXPORTS%"

echo.
echo === Loading, scoring and reporting ===
python "%~dp0edisc.py" all --db "%DB%" --exports "%EXPORTS%" --keywords "%~dp0keywords.csv" --config "%~dp0config.json" --out "%REPORTS%"

echo.
echo Done. Reports are in %REPORTS%
pause
