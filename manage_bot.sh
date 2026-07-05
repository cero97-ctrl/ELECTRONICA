#!/bin/bash

# Script para gestionar el orquestador del bot de Telegram
# Debe ejecutarse en sistemas con systemd

SERVICE_NAME="telegram_gateway.service"

echo "========================================="
echo "   Gestor del Bot de Telegram (Gateway)  "
echo "========================================="

# Mostrar el estado actual
echo -n "Estado actual del Bot: "
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "\033[32mACTIVO (Corriendo)\033[0m"
else
    echo -e "\033[31mDETENIDO\033[0m"
fi

echo "-----------------------------------------"
echo "¿Qué deseas hacer?"
echo "1) Start (Iniciar el bot)"
echo "2) Stop (Detener el bot)"
echo "3) Restart (Reiniciar el bot)"
echo "4) Status (Ver logs detallados)"
echo "5) Salir"
echo "-----------------------------------------"

read -p "Elige una opción (1-5): " opcion

case $opcion in
    1)
        echo "Iniciando el bot..."
        sudo systemctl start $SERVICE_NAME
        echo "¡Bot iniciado!"
        ;;
    2)
        echo "Deteniendo el bot..."
        sudo systemctl stop $SERVICE_NAME
        echo "¡Bot detenido!"
        ;;
    3)
        echo "Reiniciando el bot..."
        sudo systemctl restart $SERVICE_NAME
        echo "¡Bot reiniciado!"
        ;;
    4)
        echo "Mostrando el estado detallado (presiona 'q' para salir):"
        systemctl status $SERVICE_NAME
        ;;
    5)
        echo "Saliendo..."
        exit 0
        ;;
    *)
        echo "Opción no válida."
        exit 1
        ;;
esac
