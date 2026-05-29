import streamlit as st
from datetime import datetime
from supabase import create_client
import pandas as pd
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SUPABASE_URL = "https://ptdxlveqzmrrdlbtuxck.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB0ZHhsdmVxem1ycmRsYnR1eGNrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4Nzc0NTQsImV4cCI6MjA5NTQ1MzQ1NH0.nquoPERBIhu0IMdTKKv3qTQQStjdECtAOM-hsFMIx0A"

# Email для уведомлений работников (можно добавить несколько через запятую)
WORKER_EMAILS = [
    "rabotnik1@zhbu.kz",  # Замени на реальные email работников
    "rabotnik2@zhbu.kz",
    # "dispetcher@zhbu.kz"  # Можно добавить сколько угодно
]

# Настройки SMTP (добавь в Streamlit Secrets)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = st.secrets.get("SMTP_EMAIL", "your_email@gmail.com")
SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD", "your_app_password")

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def send_email(to_emails, subject, body):
    """Отправляет email одному или нескольким получателям"""
    try:
        # Если передан список, объединяем в строку
        if isinstance(to_emails, list):
            to_emails = ", ".join(to_emails)
        
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_emails
        msg["Subject"] = subject
        
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False

def send_request_confirmation(student_email, student_name, request_id, description):
    """Отправляет подтверждение студенту о создании заявки"""
    subject = f"✅ ЖБУ Общежитие - Заявка #{request_id} принята"
    
    body = f"""
Здравствуйте, {student_name}!

Ваша заявка #{request_id} успешно принята в работу.

📋 Детали заявки:
• Описание: {description[:200]}...
• Статус: Новая

⏱ Ожидайте ответа от работников ЖБУ.

С уважением,
Администрация ЖБУ Общежития
"""
    
    return send_email(student_email, subject, body)

def send_worker_notification(student_name, student_email, student_room, request_id, request_type, description):
    """Отправляет уведомление работникам о новой заявке"""
    subject = f"🔔 НОВАЯ ЗАЯВКА #{request_id} - ЖБУ Общежитие"
    
    # Определяем приоритет и ответственного
    type_priority = {
        "santeh": ("🔧 Сантехника", "Сантехник", "Высокий"),
        "electric": ("⚡ Электрика", "Электрик", "Высокий"),
        "cleaning": ("🧹 Уборка", "Уборщик", "Средний"),
        "furniture": ("🪑 Мебель", "Столяр", "Средний"),
        "other": ("❓ Вопрос", "Диспетчер", "Низкий")
    }
    
    type_info = type_priority.get(request_type, ("Другое", "Диспетчер", "Средний"))
    
    body = f"""
📢 Поступила новая заявка от студента!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 ИНФОРМАЦИЯ О ЗАЯВКЕ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Номер заявки: #{request_id}
• Тип: {type_info[0]}
• Приоритет: {type_info[2]}
• Ответственный: {type_info[1]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 ИНФОРМАЦИЯ О СТУДЕНТЕ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• ФИО: {student_name}
• Комната: {student_room}
• Email для связи: {student_email}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 ОПИСАНИЕ ПРОБЛЕМЫ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ Действия:
1. Зайдите в панель управления ЖБУ
2. Назначьте ответственного
3. Измените статус заявки на "В работе"

📱 Ссылка на панель управления: [ссылка на твой сайт для работников]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

С уважением,
Автоматическая система уведомлений ЖБУ
"""
    
    return send_email(WORKER_EMAILS, subject, body)

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

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def main():
    st.title("🏠 ЖБУ Общежитие - Подать заявку")
    st.markdown("Заполните форму ниже, чтобы оставить заявку или вопрос для работников ЖБУ.")

    with st.form("student_form"):
        fio = st.text_input("Ваше ФИО *")
        email = st.text_input("Email для связи *", 
                              placeholder="example@university.com",
                              help="На этот email придет подтверждение заявки и уведомления об изменении статуса")
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
                st.error("Пожалуйста, заполните все обязательные поля (*)")
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
                    # Сохраняем заявку и получаем ID
                    new_id = save_request(request_data)
                    
                    if new_id:
                        # 1. Отправляем подтверждение студенту
                        student_email_sent = send_request_confirmation(email, fio, new_id, description)
                        
                        # 2. Отправляем уведомление работникам
                        worker_email_sent = send_worker_notification(
                            fio, email, room, new_id, 
                            type_map[type_display], description
                        )
                        
                        # Показываем результат
                        if student_email_sent and worker_email_sent:
                            st.success("✅ Заявка успешно отправлена! Подтверждение отправлено вам на почту. Работники ЖБУ уведомлены.")
                        elif student_email_sent:
                            st.warning("⚠️ Заявка отправлена, но не удалось уведомить работников. Они увидят её в панели управления.")
                        else:
                            st.warning("⚠️ Заявка отправлена, но не удалось отправить подтверждение на вашу почту.")
                        
                        st.balloons()
                    else:
                        st.error("Ошибка при сохранении заявки")
                        
                except Exception as e:
                    st.error(f"Ошибка: {e}")

if __name__ == "__main__":
    main()
