# requests_for_ZHBU.py
import streamlit as st
from datetime import datetime
import pandas as pd
from supabase import create_client, Client

# НАСТРОЙКИ SUPABASE (те же самые!)
SUPABASE_URL = "https://ptdxlveqzmrrdlbtuxck.supabase.co"
SUPABASE_KEY = "sb_publishable_JlbWpuP2kvzMdOpyDwIOzg_XCI3VWNv"
PASSWORD = "admin123"  # Пароль для входа

def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def load_requests():
    """Загружает все заявки из Supabase"""
    supabase = init_supabase()
    response = supabase.table('requests').select('*').order('id', desc=False).execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame()

def update_status(request_id, new_status):
    """Обновляет статус заявки"""
    supabase = init_supabase()
    response = supabase.table('requests').update({'status': new_status}).eq('id', request_id).execute()
    return response

def check_auth():
    """Проверяет авторизацию с сохранением при обновлении"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if "password_verified" not in st.session_state:
        st.session_state.password_verified = False
    
    return st.session_state.authenticated

def main():
    st.title("🔐 Панель работника ЖБУ")
    
    # Проверка авторизации
    if not check_auth():
        with st.form("login_form"):
            password_input = st.text_input("Введите пароль для доступа", type="password")
            submitted = st.form_submit_button("Войти")
            
            if submitted:
                if password_input == PASSWORD:
                    st.session_state.authenticated = True
                    st.session_state.password_verified = True
                    st.success("✅ Вход выполнен!")
                    st.rerun()
                else:
                    st.error("❌ Неверный пароль!")
        return
    
    # Работник авторизован - показываем панель
    st.success("✅ Вы вошли как работник ЖБУ")
    
    # Кнопка выхода
    if st.button("🚪 Выйти"):
        st.session_state.authenticated = False
        st.session_state.password_verified = False
        st.rerun()
    
    st.header("📋 Все заявки студентов")
    
    # Загружаем данные
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
    
    # Фильтр по статусу
    status_filter = st.selectbox("Фильтр по статусу", ["Все", "Новая", "В работе", "Выполнена"])
    if status_filter != "Все":
        filtered_df = display_df[display_df["Статус"] == status_filter]
    else:
        filtered_df = display_df
    
    # Отображаем таблицу
    st.dataframe(filtered_df, use_container_width=True)
    
    # Редактирование статуса
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
    
    # Экспорт данных
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
