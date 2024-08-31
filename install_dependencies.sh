#!/bin/bash

# Обновление списка пакетов
sudo apt-get update

# Установка ffmpeg
sudo apt-get install -y ffmpeg

# Обновление pip
pip install --upgrade pip

# Установка Python-зависимостей из requirements.txt
pip install -r requirements.txt

# Сообщение об успешной установке
echo "Все зависимости установлены."
