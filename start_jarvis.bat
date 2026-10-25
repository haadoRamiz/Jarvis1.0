@echo off
title Jarvis
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Installing it now...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo Python installed. Close this window and double-click this file again.
    pause
    exit /b
)
python -c "import customtkinter, speech_recognition, sounddevice, numpy, edge_tts, anthropic, google.genai, pystray, PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing Jarvis packages, one moment...
    python -m pip install --quiet --upgrade customtkinter SpeechRecognition sounddevice numpy edge-tts anthropic google-genai pystray pillow
)
python -m pip install --quiet --upgrade edge-tts >nul 2>nul
start "" pythonw jarvis.py
