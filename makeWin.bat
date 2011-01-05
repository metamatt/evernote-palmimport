@echo off

:: Build steps:
:: (assuming using a Mac OS machine as the primary build host, and
:: desiring to build both Mac OS and Windows packages, from a
:: Windows host which doesn't have make installed)
::
:: 1) On Mac: run make-clean
:: 2) on Mac: run make
:: 3) on Win: mount source directory shared from Mac
:: 4) on Win: run this, makeWin.bat
:: 5) on Mac: run make all-packages

c:\Python26\python.exe setupWin.py py2exe 
