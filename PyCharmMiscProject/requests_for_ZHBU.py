import streamlit as st
from datetime import datetime
from common import load_requests, update_status

PASSWORD = "admin123"


def main():
    st.title("🔐 Панель работника ЖБУ")

    # Сохраняем авторизацию при обновлении
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.form("login_form"):
            password_input = st.text_input("Введите пароль для доступа", type="password")
            submitted = st.form_submit_button("Войти")

            if submitted:
                if password_input == PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Неверный пароль!")
        return

    # Панель работника
    st.success("✅ Вы вошли как работник ЖБУ")

    if st.button("🚪 Выйти"):
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
        st.metric("Новых", len(df[df["status"] == "Новая"]))
    with col3:
        st.metric("В работе", len(df[df["status"] == "В работе"]))

    # Переименовываем колонки
    display_df = df.rename(columns={
        "id": "ID", "date": "Дата", "time": "Время",
        "fio": "ФИО студента", "room": "Комната",
        "type": "Тип заявки", "description": "Описание", "status": "Статус"
    })

    # Фильтр
    status_filter = st.selectbox("Фильтр по статусу", ["Все", "Новая", "В работе", "Выполнена"])
    if status_filter != "Все":
        display_df = display_df[display_df["Статус"] == status_filter]

    st.dataframe(display_df, use_container_width=True)

    # Изменение статуса
    st.subheader("✏️ Изменить статус заявки")
    col1, col2 = st.columns(2)

    with col1:
        if not df.empty:
            selected_id = st.selectbox("Выберите ID заявки", df["id"].tolist())
        else:
            selected_id = None

    with col2:
        new_status = st.selectbox("Новый статус", ["Новая", "В работе", "Выполнена"])

    if st.button("Обновить статус") and selected_id:
        update_status(selected_id, new_status)
        st.success(f"✅ Статус заявки #{selected_id} изменён на '{new_status}'")
        st.rerun()

    # Экспорт
    st.subheader("📥 Экспорт данных")
    csv = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="Скачать все заявки в CSV",
        data=csv,
        file_name=f"zayavki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


if __name__ == "__main__":
    main()