import streamlit as st
from datetime import datetime
from supabase import create_client
import pandas as pd

SUPABASE_URL = "https://ptdxlveqzmrrdlbtuxck.supabase.co"  # Вставь свой URL
SUPABASE_KEY = "sb_secret_-rTuKDRU5nrlcVfX6ukZoQ_pwnG6nub"  # Вставь свой ключ

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def save_request(data):
    supabase = get_supabase()
    supabase.table('requests').insert({
        "date": data["date"],
        "time": data["time"],
        "fio": data["fio"],
        "room": data["room"],
        "type": data["type"],
        "description": data["description"],
        "status": "Новая"
    }).execute()

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

def main():
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
                try:
                    save_request(request_data)
                    st.success("✅ Заявка успешно отправлена!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Ошибка: {e}")


if __name__ == "__main__":
    main()
