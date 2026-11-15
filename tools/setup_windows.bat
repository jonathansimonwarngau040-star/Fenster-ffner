@echo off
REM Einmalige Einrichtung auf dem Windows-PC
winget install --id ArduinoSA.CLI -e
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
echo.
echo Bitte dieses Fenster schliessen und ein NEUES oeffnen, dann:
echo   arduino-cli core update-index
echo   arduino-cli core install arduino:mbed_nano
echo   pip install pyserial
pause
