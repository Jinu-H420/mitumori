@echo off
chcp 65001 >nul
rem 曲げ逆算ダッシュボードをブラウザで開く（このPCの中だけで動く。データは外に出ない）
rem 8765 = このフォルダ（ダッシュボード）、8766 = 見積回答PDF
cd /d "%~dp0"

rem Python を探す
set PY=python
where python >nul 2>&1 || set PY=py
%PY% --version >nul 2>&1 || (
  echo Python が見つかりません。https://www.python.org/ から入れてください。
  pause & exit /b 1
)

rem 見積回答PDFの場所を探す（環境変数 MITUMORI_PDF_ROOT が最優先）
set "PDFDIR=%MITUMORI_PDF_ROOT%"
if not defined PDFDIR set "PDFDIR=Z:\データフォルダ\社内データ用\70_蓄積データ\50_見積回答"
if not exist "%PDFDIR%" set "PDFDIR=\\srv02\共有\データフォルダ\社内データ用\70_蓄積データ\50_見積回答"

if not exist "曲げ逆算ダッシュボード.html" (
  echo ダッシュボードがまだありません。先に作ります。
  %PY% tools\update_gyakusan.py || (pause & exit /b 1)
)

start "mitumori-8765" /min %PY% -m http.server 8765 --bind 127.0.0.1
if exist "%PDFDIR%" (
  start "mitumori-8766" /min %PY% -m http.server 8766 --bind 127.0.0.1 --directory "%PDFDIR%"
) else (
  echo 見積回答PDFのフォルダが見つかりません。PDFは表示されません。
  echo 場所を指定するには、環境変数 MITUMORI_PDF_ROOT にパスを入れてください。
)
timeout /t 2 /nobreak >nul
start "" "http://localhost:8765/曲げ逆算ダッシュボード.html"
