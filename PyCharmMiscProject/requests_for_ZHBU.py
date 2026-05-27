# requests_for_ZHBU.py - интерфейс для работников ЖБУ

import streamlit as st
from datetime import datetime
from common import init_excel, load_requests, update_status, PASSWORD


def main():
    # Инициализируем Excel файл при запуске
    init_excel()

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


if __name__ == "__main__":
    main()