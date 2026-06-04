import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client
import pandas as pd
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]


DORMITORIES = [
    "Общежитие №2 | Чкаловский пр-т, д. 27",
    "Общежитие №3 | пр-т Косыгина, д. 19, к. 2",
    "Общежитие №4 | ул. Воронежская, д. 69",
    "Общежитие №7 | ул. Воронежская, д. 38"
]


WORKER_EMAILS = [
    "valeraforumsch@gmail.com"
]


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def save_request(data):
    supabase = get_supabase()
    result = supabase.table('requests').insert({
        "date": data["date"],
        "time": data["time"],
        "fio": data["fio"],
        "email": data["email"],
        "dormitory": data["dormitory"],
        "room": data["room"],
        "type": data["type"],
        "description": data["description"],
        "status": "Новая"
    }).execute()
    if result.data:
        return result.data[0]['id']
    return None

def delete_request(request_id, request_email=None):
    """Удаление заявки по ID"""
    try:
        supabase = get_supabase()
        
        # Если указан email, проверяем, что заявка принадлежит этому email
        if request_email:
            result = supabase.table('requests').delete().eq('id', request_id).eq('email', request_email).execute()
        else:
            result = supabase.table('requests').delete().eq('id', request_id).execute()
        
        if result.data:
            return True, "Заявка успешно удалена"
        else:
            return False, "Заявка не найдена или у вас нет прав на её удаление"
    except Exception as e:
        return False, f"Ошибка при удалении: {str(e)}"

def get_user_requests(email):
    """Получение всех заявок пользователя по email"""
    try:
        supabase = get_supabase()
        result = supabase.table('requests').select('*').eq('email', email).order('date', desc=True).order('time', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Ошибка при получении заявок: {e}")
        return []

def send_email(to_email, subject, body):
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
        
def send_confirmation_to_student(student_email, student_name, request_id, description, dormitory):
    subject = f"✅ Заявка №{request_id} принята"
    body = f"""
Здравствуйте, {student_name}!

Ваша заявка №{request_id} успешно принята в работу.

🏠 {dormitory}
📝 Описание: {description[:200]}...
📌 Статус: Новая

Ожидайте ответа от работников ЖБУ.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""
    return send_email(student_email, subject, body)

def send_notification_to_workers(student_name, student_email, student_room, request_id, request_type, description, dormitory):
    type_names = {
        "Сантехника": "🔧 Сантехника",
        "Электрика": "⚡ Электрика",
        "Уборка": "🧹 Уборка",
        "Вопрос / Другое": "❓ Вопрос / Другое"
    }
    type_name = type_names.get(request_type, "Вопрос / Другое")
    
    subject = f"🔔 НОВАЯ ЗАЯВКА №{request_id}"
    body = f"""
🏠 {dormitory}

📋 ЗАЯВКА №{request_id}: {type_name}

👤 СТУДЕНТ
• ФИО: {student_name}
• Комната: {student_room}
• Email: {student_email}

📝 ОПИСАНИЕ
{description}

Зайдите в панель управления ЖБУ для обработки заявки.
"""
    for worker_email in WORKER_EMAILS:
        send_email(worker_email, subject, body)
    return True

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def main():
    st.title("🏠 ЖБУ СПбГЭУ | Электронные заявки")
    
    # Создаем вкладки
    tab1, tab2 = st.tabs(["📝 Создать заявку", "🗑️ Управление заявками"])
    
    with tab1:
        st.markdown("Заполните форму ниже, чтобы оставить заявку на ремонт.")
        
        with st.form("student_form"):
            fio = st.text_input("Ваше ФИО")
            email = st.text_input("Email для связи", 
                                  placeholder="example@mail.ru",
                                  help="На этот email придет подтверждение заявки")
            
            dormitory = st.selectbox("Выберите общежитие *", DORMITORIES)
            
            room = st.text_input("Номер блока/комнаты, например: 10/1")

            type_map = {
                "🔧 Сантехника": "Сантехника",
                "⚡ Электрика": "Электрика",
                "🧹 Уборка": "Уборка",
                "❓ Вопрос / Другое": "Вопрос / Другое"
            }
            type_display = st.selectbox("Тип заявки", list(type_map.keys()))

            description = st.text_area("Описание проблемы / Текст вопроса", height=150)

            submitted = st.form_submit_button("Отправить заявку")

            if submitted:
                if not fio or not email or not room or not description:
                    st.error("❌ Пожалуйста, заполните все поля")
                elif not validate_email(email):
                    st.error("❌ Пожалуйста, введите корректный email адрес")
                else:
                    utc_now = datetime.now(timezone.utc)
                    local_now = utc_now + timedelta(hours=3)
                    
                    request_data = {
                        "date": local_now.strftime("%Y-%m-%d"),
                        "time": local_now.strftime("%H:%M:%S"),
                        "fio": fio,
                        "email": email,
                        "dormitory": dormitory,
                        "room": room,
                        "type": type_map[type_display],
                        "description": description
                    }
                    try:
                        new_id = save_request(request_data)
                        
                        if new_id:
                            send_confirmation_to_student(email, fio, new_id, description, dormitory)
                            send_notification_to_workers(fio, email, room, new_id, type_map[type_display], description, dormitory)
                            
                            st.success(f"✅ Заявка №{new_id} успешно отправлена! Подтверждение придет на вашу почту.")
                            st.balloons()
                        else:
                            st.error("❌ Ошибка при сохранении заявки. Попробуйте еще раз.")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")
    
    with tab2:
        st.markdown("### Удаление заявки")
        st.markdown("Введите ваш email и ID заявки, чтобы удалить её")
        
        col1, col2 = st.columns(2)
        
        with col1:
            delete_email = st.text_input("Ваш email", key="delete_email")
        
        with col2:
            delete_request_id = st.text_input("Номер заявки", key="delete_id")
        
        if st.button("🔍 Показать мои заявки", key="show_requests"):
            if delete_email and validate_email(delete_email):
                user_requests = get_user_requests(delete_email)
                if user_requests:
                    st.success(f"Найдено {len(user_requests)} заявок")
                    
                    # Создаем DataFrame для отображения
                    df = pd.DataFrame(user_requests)
                    df_display = df[['id', 'date', 'time', 'type', 'dormitory', 'room', 'status', 'description']]
                    df_display.columns = ['ID', 'Дата', 'Время', 'Тип', 'Общежитие', 'Комната', 'Статус', 'Описание']
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    st.warning("Заявки не найдены")
            else:
                st.error("Введите корректный email")
        
        if st.button("🗑️ Удалить заявку", key="delete_button"):
            if delete_email and delete_request_id:
                if not validate_email(delete_email):
                    st.error("❌ Неверный формат email")
                else:
                    try:
                        request_id_int = int(delete_request_id)
                        success, message = delete_request(request_id_int, delete_email)
                        if success:
                            st.success(f"✅ {message}")
                            st.balloons()
                            # Отправляем уведомление работникам об удалении
                            notification_body = f"Заявка №{request_id_int} была удалена пользователем {delete_email}"
                            for worker_email in WORKER_EMAILS:
                                send_email(worker_email, f"🗑️ Заявка №{request_id_int} удалена", notification_body)
                        else:
                            st.error(f"❌ {message}")
                    except ValueError:
                        st.error("❌ ID заявки должен быть числом")
            else:
                st.error("❌ Введите email и ID заявки для удаления")
        

if __name__ == "__main__":
    main()
