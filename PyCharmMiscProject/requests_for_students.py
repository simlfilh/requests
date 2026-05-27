# requests_for_students.py
import streamlit as st
from datetime import datetime
from supabase import create_client, Client

# НАСТРОЙКИ SUPABASE (вставь свои данные)
SUPABASE_URL = "https://ptdxlveqzmrrdlbtuxck.supabase.co"
SUPABASE_KEY = "sb_publishable_JlbWpuP2kvzMdOpyDwIOzg_XCI3VWNv"

def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def save_request(data):
    supabase = init_supabase()
    response = supabase.table('requests').insert({
        "date": data["date"],
        "time": data["time"],
        "fio": data["fio"],
        "room": data["room"],
        "type": data["type"],
        "description": data["description"],
        "status": "Новая"
    }).execute()
    return response

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
                    st.success("✅ Заявка успешно отправлена! Работники ЖБУ скоро её увидят.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Ошибка при отправке: {e}")

if __name__ == "__main__":
    main()
