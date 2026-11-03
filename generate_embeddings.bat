@echo off
title AURA AI - Batch Face Embedding Generator
echo =================================================================
echo   AURA AI // Biometric Facial Embedding Batch Generator
echo =================================================================
echo.
.\venv\Scripts\python.exe generate_embeddings.py %*
echo.
pause
