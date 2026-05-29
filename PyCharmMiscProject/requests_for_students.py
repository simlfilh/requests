import streamlit as st
from datetime import datetime
from supabase import create_client
import pandas as pd
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== НАСТРОЙКИ =====
SUPABASE_URL = "https://ptdxlveqzmrrdlbtuxck.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB0ZHhsdmVxem1ycmRsYnR1eGNrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4Nzc0NTQsImV4cCI6MjA5NTQ1MzQ1NH0.nquoPERBIhu0IMdTKKv3qTQQStjdECtAOM-hsFMIx0A"

# Email настройки (замени на свои)
SMTP_EMAIL = "valeraforumsch@gmail.com"
SMTP_PASSWORD = "zwny cinl ejom qgsk"  # Вставь сюда свой 16-значный пароль

# Email работников (кто будет получать уведомления о новых заявках)
WORKER_EMAILS = [
    "valeraforumsch@gmail.com",  # Временный email для теста, потом заменишь
]

# ===== ФУНКЦИИ =====
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def save_request(data):
    supabase = get_supabase()
    result = supabase.table('requests').insert({
        "date": data["date"],
        "time": data["time"],
        "fio": data["fio"],
        "email": data["email"],
        "room": data["room"],
        "type": data["type"],
        "description": data["description"],
        "status": "Новая"
    }).execute()
    if result.data:
        return result.data[0]['id']
    return None

def send_email(to_email, subject, body):
    """Отправляет email"""
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

def send_confirmation_to_student(student_email, student_name, request_id, description):
    """Отправляет подтверждение студенту"""
    subject = f"✅ ЖБУ Общежитие - Заявка #{request_id} принята"
    body = f"""
Здравствуйте, {student_name}!

Ваша заявка #{request_id} успешно принята в работу.

📝 Описание: {description[:200]}...
📌 Статус: Новая

Ожидайте ответа от работников ЖБУ.

С уважением,
Администрация ЖБУ
"""
    return send_email(student_email, subject, body)

def send_notification_to_workers(student_name, student_email, student_room, request_id, request_type, description):
    """Отправляет уведомление работникам"""
    type_names = {
        "santeh": "🔧 Сантехника",
        "electric": "⚡ Электрика",
        "cleaning": "🧹 Уборка",
        "furniture": "🪑 Мебель",
        "other": "❓ Вопрос"
    }
    type_name = type_names.get(request_type, "Другое")
    
    subject = f"🔔 НОВАЯ ЗАЯВКА #{request_id} - ЖБУ"
    body = f"""
📢 Поступила новая заявка!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 ЗАЯВКА #{request_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Тип: {type_name}
• Приоритет: Средний

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 СТУДЕНТ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• ФИО: {student_name}
• Комната: {student_room}
• Email: {student_email}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 ОПИСАНИЕ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Зайдите в панель управления ЖБУ для обработки заявки.
"""
    # Отправляем всем работникам
    for worker_email in WORKER_EMAILS:
        send_email(worker_email, subject, body)
    return True

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# ===== ОСНОВНОЕ ПРИЛОЖЕНИЕ =====
def main():
    st.title("🏠 ЖБУ Общежитие - Подать заявку")
    st.markdown("Заполните форму ниже, чтобы оставить заявку или вопрос для работников ЖБУ.")

    with st.form("student_form"):
        fio = st.text_input("Ваше ФИО *")
        email = st.text_input("Email для связи *", 
                              placeholder="example@mail.ru",
                              help="На этот email придет подтверждение заявки")
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
            if not fio or not email or not room or not description:
                st.error("❌ Пожалуйста, заполните все обязательные поля (*)")
            elif not validate_email(email):
                st.error("❌ Пожалуйста, введите корректный email адрес")
            else:
                now = datetime.now()
                request_data = {
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M:%S"),
                    "fio": fio,
                    "email": email,
                    "room": room,
                    "type": type_map[type_display],
                    "description": description
                }
                try:
                    # Сохраняем заявку
                    new_id = save_request(request_data)
                    
                    if new_id:
                        # Отправляем подтверждение студенту
                        send_confirmation_to_student(email, fio, new_id, description)
                        # Отправляем уведомление работникам
                        send_notification_to_workers(fio, email, room, new_id, type_map[type_display], description)
                        
                        st.success("✅ Заявка успешно отправлена! Подтверждение придет на вашу почту.")
                        st.balloons()
                    else:
                        st.error("❌ Ошибка при сохранении заявки")
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
