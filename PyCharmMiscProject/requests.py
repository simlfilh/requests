import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- НАСТРОЙКИ ---
EXCEL_FILE = "zayavki.xlsx"
PASSWORD = "admin123"  # Пароль для доступа работника (смени на свой)


# --- ФУНКЦИИ РАБОТЫ С EXCEL ---
def init_excel():
    """Создает Excel файл с нужными колонками, если его нет"""
    if not os.path.exists(EXCEL_FILE):
        df = pd.DataFrame(columns=[
            "ID", "Дата", "Время", "ФИО студента", "Комната",
            "Тип заявки", "Описание проблемы", "Статус"
        ])
        df.to_csv(EXCEL_FILE, index=False)


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
    df.to_csv(EXCEL_FILE, index=False)


def load_requests():
    """Загружает все заявки из Excel"""
    return pd.read_excel(EXCEL_FILE)


def update_status(request_id, new_status):
    """Обновляет статус заявки"""
    df = pd.read_excel(EXCEL_FILE)
    df.loc[df["ID"] == request_id, "Статус"] = new_status
    df.to_csv(EXCEL_FILE, index=False)


# --- ИНТЕРФЕЙС СТУДЕНТА ---
def student_interface():
    st.title("🏠 ЖБУ Общежитие - Подать заявку")
    st.markdown("Заполните форму ниже, чтобы оставить заявку или вопрос для работников ЖБУ.")

    with st.form("student_form"):
        fio = st.text_input("Ваше ФИО *")
        room = st.text_input("Номер комнаты *")

        type_map = {
            "🔧 Сантехника": "santeh",
            "⚡ Электрика": "electric",
            "🧹 Уборка": "cleaning",
            "🪑 Мебель": "furniture",
            "❓ Вопрос / Другое": "other"
        }
        type_display = st.selectbox("Тип заявки *", list(type_map.keys()))

        description = st.text_area("Описание проблемы / Текст вопроса *", height=150)

        submitted = st.form_submit_button("Отправить заявку")

        if submitted:
            if not fio or not room or not description:
                st.error("Пожалуйста, заполните все обязательные поля (*)")
            else:
                now = datetime.now()
                request_data = {
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M:%S"),
                    "fio": fio,
                    "room": room,
                    "type": type_map[type_display],
                    "description": description
                }
                save_request(request_data)
                st.success("✅ Заявка успешно отправлена! Работники ЖБУ скоро её увидят.")
                st.balloons()


# --- ИНТЕРФЕЙС РАБОТНИКА ---
def worker_interface():
    st.title("🔐 Панель работника ЖБУ")

    # Проверка пароля
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        password_input = st.text_input("Введите пароль для доступа", type="password")
        if st.button("Войти"):
            if password_input == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Неверный пароль!")
        return

    # Отображение заявок
    st.success("✅ Вы вошли как работник ЖБУ")
    if st.button("Выйти"):
        st.session_state.authenticated = False
        st.rerun()

    st.header("📋 Все заявки студентов")

    df = load_requests()

    if df.empty:
        st.info("Пока нет ни одной заявки.")
        return

    # Статистика
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Всего заявок", len(df))
    with col2:
        st.metric("Новых", len(df[df["Статус"] == "Новая"]))
    with col3:
        st.metric("В работе", len(df[df["Статус"] == "В работе"]))

    # Фильтр по статусу
    status_filter = st.selectbox("Фильтр по статусу", ["Все", "Новая", "В работе", "Выполнена"])
    if status_filter != "Все":
        df = df[df["Статус"] == status_filter]

    # Отображаем таблицу
    st.dataframe(df, use_container_width=True)

    # Редактирование статуса
    st.subheader("✏️ Изменить статус заявки")
    col1, col2 = st.columns(2)

    with col1:
        request_ids = df["ID"].tolist()
        if request_ids:
            selected_id = st.selectbox("Выберите ID заявки", request_ids)
        else:
            selected_id = None

    with col2:
        new_status = st.selectbox("Новый статус", ["Новая", "В работе", "Выполнена"])

    if st.button("Обновить статус") and selected_id:
        update_status(selected_id, new_status)
        st.success(f"Статус заявки #{selected_id} изменён на '{new_status}'")
        st.rerun()

    # Кнопка скачать Excel (только для работника)
    st.subheader("📥 Экспорт данных")
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="Скачать все заявки в CSV",
        data=csv,
        file_name=f"zayavki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


# --- ГЛАВНАЯ ЛОГИКА ---
def main():
    init_excel()

    st.sidebar.title("Навигация")
    role = st.sidebar.radio("Выберите роль:", ["👨‍🎓 Студент", "👷 Работник ЖБУ"])

    if role == "👨‍🎓 Студент":
        student_interface()
    else:
        worker_interface()


if __name__ == "__main__":
    main()
