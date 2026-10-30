@echo off
set OMNIROUTE_SERVER_HOST=127.0.0.1
set OMNIROUTE_READY_TIMEOUT_MS=120000
omniroute > "%~dp0..\docs\omniroute-safe-start.log" 2>&1
