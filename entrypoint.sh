#!/bin/bash
set -e

echo "1. Khoi dong man hinh hien thi ao Xvfb..."
Xvfb :1 -screen 0 1920x1080x24 &
sleep 2

echo "2. Khoi dong trinh quan ly cua so Fluxbox (Duy tri giao dien cho MT5)..."
fluxbox &
sleep 2

echo "3. Tu dong khoi chay terminal MetaTrader 5 qua Wine..."
# Khoi chay MT5 Terminal o che do portable de dam bao du lieu ghi vao cung thu muc
wine /root/.wine/drive_c/Program\ Files/MetaTrader\ 5/terminal64.exe /portable &
sleep 5

echo "4. Kich hoat V9 Continuum Bot Core qua Wine Python..."
wine python -m v9_continuum.main
