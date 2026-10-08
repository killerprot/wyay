#!/bin/bash

# 1. Вызываем меню Fuzzel со списком пакетов
chosen=$(yay -Slq | fuzzel --dmenu --prompt="Установка пакета: " --width=40)

# 2. Если пакет выбран (строка не пустая)
if [ -n "$chosen" ]; then
    # 3. Запуск foot для установки выбранного пакета
    foot -e yay -S "$chosen"
fi
