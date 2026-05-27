import streamlit as st
from datetime import datetime
from supabase import create_client
import pandas as pd
from io import BytesIO

SUPABASE_URL = "https://ptdxlveqzmrrdlbtuxck.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB0ZHhsdmVxem1ycmRsYnR1eGNrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4Nzc0NTQsImV4cCI6MjA5NTQ1MzQ1NH0.nquoPERBIhu0IMdTKKv3qTQQStjdECtAOM-hsFMIx0A"

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def load_requests():
    supabase = get_supabase()
    response = supabase.table('requests').select('*').order('id', desc=False).execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame()

def update_status(request_id, new_status):
    supabase = get_supabase()
    supabase.table('requests').update({'status': new_status}).eq('id', request_id).execute()

PASSWORD = "admin123"

def to_excel(df):
    """Преобразует DataFrame в Excel файл (BytesIO)"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Заявки')
    processed_data = output.getvalue()
    return processed_data

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

    # Переименовываем колонки для красивого отображения
    display_df = df.rename(columns={
        "id": "ID", 
        "date": "Дата", 
        "time": "Время",
        "fio": "ФИО студента", 
        "room": "Комната",
        "type": "Тип заявки", 
        "description": "Описание", 
        "status": "Статус"
    })

    # Фильтр
    status_filter = st.selectbox("Фильтр по статусу", ["Все", "Новая", "В работе", "Выполнена"])
    if status_filter != "Все":
        filtered_df = display_df[display_df["Статус"] == status_filter]
    else:
        filtered_df = display_df

    st.dataframe(filtered_df, use_container_width=True)

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

    # Экспорт в Excel
    st.subheader("📥 Экспорт данных в Excel")
    
    # Выбор формата экспорта
    export_type = st.radio(
        "Что экспортировать?",
        ["Все заявки", "Только отфильтрованные"]
    )
    
    if export_type == "Только отфильтрованные":
        export_df = filtered_df
    else:
        export_df = display_df
    
    # Кнопка скачивания Excel
    excel_data = to_excel(export_df)
    st.download_button(
        label="📊 Скачать в Excel формате",
        data=excel_data,
        file_name=f"zayavki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    # Дополнительно: кнопка для CSV (на всякий случай)
    with st.expander("Дополнительные форматы"):
        csv = display_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📄 Скачать в CSV формате",
            data=csv,
            file_name=f"zayavki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
