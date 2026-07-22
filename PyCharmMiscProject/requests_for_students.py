import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client
import pandas as pd
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(
    page_title="Электронные заявки | Общежития СПбГЭУ",
    page_icon="📲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ссылки для взаимодействия с базой данных, которая хранит:
# id PK, дату и время подачи заявки, 
# ФИО, email, общежитие, № блока студента, 
# тип, описание и статус заявки.
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
    "valeraforumsch@gmail.com" # временный адрес, который потом станет dom@unecon.ru
]


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Функция для сохранения и извлечения заявки  
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
        "status": "Новая",
        "is_anonymous": data.get("is_anonymous", False)
    }).execute()
    if result.data:
        return result.data[0]['id']
    return None

# Функция для удаления заявки
def delete_request(request_id, request_email=None):
    try:
        supabase = get_supabase()
        
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

# Функция для отображения всех заявок
def get_user_requests(email):
    try:
        supabase = get_supabase()
        result = supabase.table('requests').select('*').eq('email', email).order('date', desc=True).order('time', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Ошибка при получении заявок: {e}")
        return []

# Функция для автоматической рассылки сообщений на email
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

# Функция, с помощью которой студент получает уведомление о принятой заявке
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

# Функция, которая отправляет уведомление сотруднику ЖБУ о поступлении новой заявки
def send_notification_to_workers(student_name, student_email, student_room, request_id, request_type, description, dormitory, is_anonymous=False):
    type_names = {
        "Сантехника": "🔧 Сантехника",
        "Электрика": "⚡ Электрика",
        "Плиты": "🍵 Плиты",
        "Уборка": "🧹 Уборка",
        "Вопрос / Другое": "❓ Вопрос / Другое"
    }
    type_name = type_names.get(request_type, "Вопрос / Другое")
    
    subject = f"🔔 НОВАЯ ЗАЯВКА №{request_id}"
    
    if is_anonymous:
        body = f"""
🏠 {dormitory}

📋 ЗАЯВКА №{request_id}: {type_name}

👤 АНОНИМНАЯ ЗАЯВКА
• Комната: {student_room}

📝 ОПИСАНИЕ
{description}

Зайдите в панель управления ЖБУ для обработки заявки.
"""
    else:
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

# Функция для проверки корректности email-адреса
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Интерфейс студента
def main():
    # Заголовок страницы
    st.title("🏠 ЖБУ СПбГЭУ | Электронные заявки")

    # Вкладки для создания и управления заявкой
    tab1, tab2 = st.tabs(["📝 Создать заявку", "🗑️ Управление заявками"])

    # Окно заполнения заявки
    with tab1:
        st.markdown("Заполните форму ниже, чтобы оставить заявку на ремонт.")
        
        with st.form("student_form"):
            # Поля для заполнения заявки студентом
            fio = st.text_input("Ваше ФИО (необязательно)", 
                              placeholder="Можно не указывать для анонимности")
            
            email = st.text_input("Email для связи (необязательно)", 
                                placeholder="example@mail.ru | Можно не указывать для анонимности",
                                help="На этот email придет подтверждение заявки, если вы его укажете")
            
            # Предупреждение если email указан но невалидный
            if email and not validate_email(email):
                st.warning("⚠️ Введите корректный email адрес или оставьте поле пустым для анонимности")
            
            dormitory = st.selectbox("Выберите общежитие *", DORMITORIES)
            
            room = st.text_input("Номер блока/комнаты, например: 10/1 *")

            type_map = {
                "Сантехника": "🔧 Сантехника",
                "Электрика": "⚡ Электрика",
                "Плотник": "🔨 Плотник",
                "Плиты": "🍵 Плиты",
                "Уборка": "🧹 Уборка",
                "Вопрос / Другое": "❓ Вопрос / Другое"
            }
            type_display = st.selectbox("Тип заявки", list(type_map.keys()))

            description = st.text_area("Описание проблемы / Текст вопроса *", height=150)

            submitted = st.form_submit_button("Отправить заявку")

            # Проверка ошибок при заполнении формы заявки
            if submitted:
                # Проверяем только обязательные поля (комната и описание)
                errors = []
                
                if not room:
                    errors.append("Номер комнаты")
                if not description:
                    errors.append("Описание проблемы")
                
                # Если email указан, проверяем его корректность
                if email and not validate_email(email):
                    errors.append("Некорректный email адрес")
                
                if errors:
                    st.error(f"❌ Пожалуйста, заполните обязательные поля: {', '.join(errors)}")
                else:
                    # Определение текущего времени
                    utc_now = datetime.now(timezone.utc)
                    local_now = utc_now + timedelta(hours=3)
                    
                    # Определяем, анонимная ли заявка
                    is_anonymous = not fio and not email
                    
                    # Подготовка данных для базы
                    if is_anonymous:
                        fio_for_db = "Аноним"
                        email_for_db = "anonymous@dorm.ru"
                    else:
                        fio_for_db = fio if fio else "Не указано"
                        email_for_db = email if email else "no-email@dorm.ru"
                    
                    request_data = {
                        "date": local_now.strftime("%Y-%m-%d"),
                        "time": local_now.strftime("%H:%M:%S"),
                        "fio": fio_for_db,
                        "email": email_for_db,
                        "dormitory": dormitory,
                        "room": room,
                        "type": type_map[type_display],
                        "description": description,
                        "is_anonymous": is_anonymous
                    }
                    
                    # Если все корректно, то сохраняем заявку в базу данных.
                    try:
                        new_id = save_request(request_data)

                        # Если заявка сохранилась, то...
                        if new_id:
                            # Отправляем уведомления только если указан корректный email и это не анонимная заявка
                            if email and validate_email(email) and not is_anonymous:
                                send_confirmation_to_student(email, fio_for_db, new_id, description, dormitory)
                            
                            # Уведомление сотрудникам
                            send_notification_to_workers(
                                fio_for_db, 
                                email_for_db, 
                                room, 
                                new_id, 
                                type_map[type_display], 
                                description, 
                                dormitory,
                                is_anonymous
                            )

                            # Всплывающее окно при успешной отправке заявки
                            if is_anonymous:
                                st.success(f"✅ Анонимная заявка №{new_id} успешно отправлена!")
                                st.info("ℹ️ Вы не указали ФИО и Email, поэтому уведомления не будут отправлены. Статус заявки можно проверить в разделе 'Управление заявками'.")
                            else:
                                if email and validate_email(email):
                                    st.success(f"✅ Заявка №{new_id} успешно отправлена! Подтверждение придет на вашу почту.")
                                else:
                                    st.success(f"✅ Заявка №{new_id} успешно отправлена!")
                        else:
                            st.error("❌ Ошибка при сохранении заявки. Попробуйте еще раз.")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")

    # Окно управления заявкой
    with tab2:
        st.markdown("### Удаление заявки")
        st.markdown("Введите ваш email и ID заявки, чтобы удалить её")
        
        st.info("💡 **Для анонимных заявок** (без указания email) удаление через этот интерфейс невозможно. Обратитесь к сотрудникам ЖБУ для удаления анонимной заявки.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Окно для заполнения email-а студента
            delete_email = st.text_input("Ваш email", key="delete_email")

            # Кнопка для удаления заявки по ее №
            if st.button("🔍 Показать мои заявки", key="show_requests"):
                # Если email является корректным, то...
                if delete_email and validate_email(delete_email):
                    # Извлекаем заявки студента по email адресу
                    user_requests = get_user_requests(delete_email)
                    if user_requests:
                        #... отображае количество найденных заявок
                        st.success(f"Найдено {len(user_requests)} заявок")

                        # Формируем таблицу заявок 
                        df = pd.DataFrame(user_requests)
                        df_display = df[['id', 'date', 'time', 'type', 'dormitory', 'room', 'status', 'description']]
                        df_display.columns = ['ID', 'Дата', 'Время', 'Тип', 'Общежитие', 'Комната', 'Статус', 'Описание']
                        st.dataframe(df_display, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Заявки не найдены")
                else:
                    st.error("Введите корректный email")
        
        with col2:
            # Поле для заполнения № заявки
            delete_request_id = st.text_input("Номер заявки", key="delete_id")

            # Кнопка для удаления заявки по ее №
            if st.button("🗑️ Удалить заявку", key="delete_button"):
                # Если оба поля заполнены, то...
                if delete_email and delete_request_id:
                    # Проверяем email на корректность
                    if not validate_email(delete_email):
                        st.error("❌ Неверный формат email")
                    else:
                        try:
                            # Номер заявки
                            request_id_int = int(delete_request_id)
                            # Удаляем заявку по указанному №
                            success, message = delete_request(request_id_int, delete_email)
                            if success:
                                st.success(f"✅ {message}")
                                notification_body = f"Заявка №{request_id_int} была удалена пользователем {delete_email}"
                                # Уведомляем сотрудника ЖБУ об удалении заявки студентом
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
