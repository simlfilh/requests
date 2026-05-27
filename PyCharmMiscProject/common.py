# common.py - общие функции для обоих приложений

import pandas as pd
import os
from datetime import datetime

EXCEL_FILE = "zayavki.xlsx"
PASSWORD = "admin123"  # Смени на свой пароль


def init_excel():
    """Создает Excel файл с нужными колонками, если его нет"""
    if not os.path.exists(EXCEL_FILE):
        df = pd.DataFrame(columns=[
            "ID", "Дата", "Время", "ФИО студента", "Комната",
            "Тип заявки", "Описание проблемы", "Статус"
        ])
        df.to_excel(EXCEL_FILE, index=False)


def save_request(data):
    """Сохраняет новую заявку в Excel"""
    df = pd.read_excel(EXCEL_FILE)

    # Генерируем ID
    new_id = len(df) + 1

    new_row = pd.DataFrame([{
        "ID": new_id,
        "Дата": data["date"],
        "Время": data["time"],
        "ФИО студента": data["fio"],
        "Комната": data["room"],
        "Тип заявки": data["type"],
        "Описание проблемы": data["description"],
        "Статус": "Новая"
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)


def load_requests():
    """Загружает все заявки из Excel"""
    return pd.read_excel(EXCEL_FILE)


def update_status(request_id, new_status):
    """Обновляет статус заявки"""
    df = pd.read_excel(EXCEL_FILE)
    df.loc[df["ID"] == request_id, "Статус"] = new_status
    df.to_excel(EXCEL_FILE, index=False)