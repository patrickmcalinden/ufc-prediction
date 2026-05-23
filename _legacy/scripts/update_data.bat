@echo off
REM Refresh the static JSON snapshot served by the GitHub Pages site.
REM
REM 1. Re-exports every API endpoint to frontend\public\data\ from the
REM    live local Postgres database.
REM 2. Stages the refreshed JSON files for commit.
REM
REM Does NOT push. Review with `git diff --stat --cached`, then commit
REM and push when ready.

setlocal
pushd "%~dp0\.."

echo ==^> Exporting static JSON to frontend\public\data\
python -m data.loaders.export_static_api
if errorlevel 1 goto :error

echo ==^> Staging refreshed data files
git add frontend/public/data blog
if errorlevel 1 goto :error

echo.
echo Done. Review with:
echo     git diff --stat --cached
echo Then commit + push:
echo     git commit -m "Refresh static data"
echo     git push

popd
endlocal
exit /b 0

:error
echo.
echo Update failed. See output above.
popd
endlocal
exit /b 1
