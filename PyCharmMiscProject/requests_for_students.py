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

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]

DORMITORIES = [
    "Общежитие №2 | Чкаловский пр-т, д. 27",
    "Общежитие №3 | пр-т Косыгина, д. 19, к. 2",
    "Общежитие №4 | ул. Воронежская, д. 69",
    "Общежитие №4 | наб. канала Грибоедова, д. 30-32, лит. Б",
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
        "status": "Новая",
        "is_anonymous": data.get("is_anonymous", False),
        "completed_confirmed": False
    }).execute()
    if result.data:
        return result.data[0]['id']
    return None

def get_user_requests(email):
    try:
        supabase = get_supabase()
        result = supabase.table('requests').select('*').eq('email', email).order('date', desc=True).order('time', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Ошибка при получении заявок: {e}")
        return []

def confirm_completion(request_id, email):
    try:
        supabase = get_supabase()
        result = supabase.table('requests').select('*').eq('id', request_id).eq('email', email).execute()
        
        if not result.data:
            return False, "Заявка не найдена или у вас нет прав"
        
        request = result.data[0]
        
        if request['status'] != "Выполнена":
            return False, "Заявка ещё не выполнена. Дождитесь изменения статуса."
        
        if request.get('completed_confirmed', False):
            return False, "Заявка уже подтверждена как выполненная"
        
        supabase.table('requests').update({
            'completed_confirmed': True,
            'status': "Выполнена ✅"
        }).eq('id', request_id).execute()
        
        notify_workers_about_confirmation(request, email)
        
        return True, "✅ Заявка успешно подтверждена!"
    except Exception as e:
        return False, f"Ошибка: {str(e)}"

def notify_workers_about_confirmation(request, student_email):
    subject = f"✅ Заявка №{request['id']} подтверждена студентом"
    body = f"""
Студент подтвердил выполнение заявки №{request['id']}

🏠 {request['dormitory']}
📋 Тип: {request['type']}
👤 Студент: {request['fio']}
📧 Email: {student_email}

Заявка успешно выполнена и подтверждена студентом.
"""
    for worker_email in WORKER_EMAILS:
        send_email(worker_email, subject, body)

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

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def show_student_requests(email):
    """Отображение заявок студента в стиле админ-панели"""
    
    # Загружаем заявки студента
    user_requests = get_user_requests(email)
    
    if not user_requests:
        st.info("У вас пока нет заявок")
        return
    
    # Преобразуем в DataFrame
    df = pd.DataFrame(user_requests)
    
    # Переименовываем колонки
    display_df = df.rename(columns={
        "id": "ID",
        "date": "Дата",
        "time": "Время",
        "fio": "ФИО",
        "email": "Email",
        "dormitory": "Общежитие",
        "room": "Комната",
        "type": "Тип заявки",
        "description": "Описание",
        "status": "Статус"
    })
    
    # Добавляем статус с подтверждением
    def format_status(row):
        if row['status'] == "Выполнена" and row.get('completed_confirmed', False):
            return "✅ Выполнена (подтверждено)"
        return row['status']
    
    display_df["Статус"] = display_df.apply(format_status, axis=1)
    
    # Фильтры
    st.subheader("🔍 Фильтры")
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Статус", ["Все", "Новая", "В работе", "Выполнена", "Выполнена (подтверждено)"], key="status_filter")
    with col2:
        type_filter = st.selectbox("Тип заявки", ["Все", "🔧 Сантехника", "⚡ Электрика", "🔨 Плотник", "🍵 Плиты", "🧹 Уборка", "❓ Вопрос / Другое"], key="type_filter")
    with col3:
        date_filter = st.selectbox("Период", ["Все", "Сегодня", "Вчера", "Последние 7 дней", "Последние 30 дней"], key="date_filter")
    
    # Применяем фильтры
    filtered_df = display_df.copy()
    
    if status_filter != "Все":
        filtered_df = filtered_df[filtered_df["Статус"] == status_filter]
    
    if type_filter != "Все":
        filtered_df = filtered_df[filtered_df["Тип заявки"] == type_filter]
    
    today = datetime.now().date()
    if date_filter == "Сегодня":
        filtered_df = filtered_df[pd.to_datetime(filtered_df["Дата"]).dt.date == today]
    elif date_filter == "Вчера":
        yesterday = today - timedelta(days=1)
        filtered_df = filtered_df[pd.to_datetime(filtered_df["Дата"]).dt.date == yesterday]
    elif date_filter == "Последние 7 дней":
        week_ago = today - timedelta(days=7)
        filtered_df = filtered_df[pd.to_datetime(filtered_df["Дата"]).dt.date >= week_ago]
    elif date_filter == "Последние 30 дней":
        month_ago = today - timedelta(days=30)
        filtered_df = filtered_df[pd.to_datetime(filtered_df["Дата"]).dt.date >= month_ago]
    
    # Форматируем дату
    filtered_df["Дата"] = pd.to_datetime(filtered_df["Дата"]).dt.strftime("%d.%m.%Y")
    
    # Показываем метрики
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего", len(filtered_df))
    with col2:
        st.metric("Новых", len(filtered_df[filtered_df["Статус"] == "Новая"]))
    with col3:
        st.metric("В работе", len(filtered_df[filtered_df["Статус"] == "В работе"]))
    with col4:
        st.metric("Выполнено", len(filtered_df[filtered_df["Статус"].str.contains("Выполнена", na=False)]))
    
    st.markdown("---")
    
    if not filtered_df.empty:
        # Отображаем таблицу с кнопками
        st.subheader("📋 Мои заявки")
        
        # Создаем копию для отображения
        display_cols = ["ID", "Дата", "Время", "Тип заявки", "Общежитие", "Комната", "Описание", "Статус"]
        df_display = filtered_df[display_cols].copy()
        
        # Показываем таблицу
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Секция подтверждения выполнения
        st.markdown("---")
        st.subheader("✅ Подтверждение выполнения заявки")
        
        # Находим заявки со статусом "Выполнена" и без подтверждения
        completed_requests = []
        for _, row in filtered_df.iterrows():
            if row["Статус"] == "Выполнена" and not row.get('completed_confirmed', False):
                completed_requests.append(row)
        
        if completed_requests:
            st.success(f"Найдено {len(completed_requests)} выполненных заявок, которые можно подтвердить")
            
            for req in completed_requests:
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"""
                        **Заявка №{req['ID']}**  
                        📋 Тип: {req['Тип заявки']}  
                        🏠 {req['Общежитие']}  
                        📝 Описание: {req['Описание'][:100]}...
                        """)
                    with col2:
                        if st.button(f"✅ Подтвердить", key=f"confirm_{req['ID']}"):
                            success, message = confirm_completion(req['ID'], email)
                            if success:
                                st.success(f"✅ {message}")
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                    st.markdown("---")
        else:
            st.info("Нет заявок, требующих подтверждения")
        
        # Показываем уже подтвержденные заявки
        confirmed_requests = filtered_df[filtered_df["Статус"] == "✅ Выполнена (подтверждено)"]
        if not confirmed_requests.empty:
            st.markdown("---")
            st.subheader("✅ Подтвержденные заявки")
            for _, req in confirmed_requests.iterrows():
                st.info(f"Заявка №{req['ID']} - {req['Тип заявки']} - ✅ Подтверждена")
        
        # Кнопка удаления заявки
        st.markdown("---")
        st.subheader("🗑️ Удаление заявки")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            delete_id = st.number_input("Введите номер заявки для удаления", min_value=1, step=1, key="delete_id_input")
        with col2:
            if st.button("🗑️ Удалить заявку", key="delete_btn", use_container_width=True):
                if delete_id:
                    success, message = delete_request(delete_id, email)
                    if success:
                        st.success(f"✅ {message}")
                        # Уведомляем сотрудников
                        notification_body = f"Заявка №{delete_id} была удалена студентом {email}"
                        for worker_email in WORKER_EMAILS:
                            send_email(worker_email, f"🗑️ Заявка №{delete_id} удалена студентом", notification_body)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.warning("⚠️ Введите номер заявки")
    
    else:
        st.info("Нет заявок, соответствующих выбранным фильтрам")

def main():
    st.title("🏠 ЖБУ СПбГЭУ | Электронные заявки")

    tab1, tab2 = st.tabs(["📝 Создать заявку", "📋 Мои заявки"])

    with tab1:
        st.markdown("Заполните форму ниже, чтобы оставить заявку на ремонт.")
        
        with st.form("student_form"):
            fio = st.text_input("Ваше ФИО", 
                              placeholder="Можно не указывать для анонимности")
            
            email = st.text_input("Email для связи", 
                                placeholder="example@mail.ru | Можно не указывать для анонимности",
                                help="На этот email придет подтверждение заявки, если вы его укажете")
            
            if email and not validate_email(email):
                st.warning("⚠️ Введите корректный email адрес или оставьте поле пустым для анонимности")
            
            dormitory = st.selectbox("Выберите общежитие", DORMITORIES)
            
            room = st.text_input("Номер блока и комнаты | Пространство: кухня, коридор и т.п.")

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

            if submitted:
                errors = []
                
                if not room:
                    errors.append("Номер комнаты")
                if not description:
                    errors.append("Описание проблемы")
                
                if email and not validate_email(email):
                    errors.append("Некорректный email адрес")
                
                if errors:
                    st.error(f"❌ Пожалуйста, заполните обязательные поля: {', '.join(errors)}")
                else:
                    utc_now = datetime.now(timezone.utc)
                    local_now = utc_now + timedelta(hours=3)
                    
                    is_anonymous = not fio and not email
                    
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
                    
                    try:
                        new_id = save_request(request_data)

                        if new_id:
                            if email and validate_email(email) and not is_anonymous:
                                send_confirmation_to_student(email, fio_for_db, new_id, description, dormitory)
                            
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

                            if is_anonymous:
                                st.success(f"✅ Анонимная заявка №{new_id} успешно отправлена!")
                                st.info("ℹ️ Вы не указали ФИО и Email, поэтому уведомления не будут отправлены. Статус заявки можно проверить в разделе 'Мои заявки'.")
                            else:
                                if email and validate_email(email):
                                    st.success(f"✅ Заявка №{new_id} успешно отправлена! Подтверждение придет на вашу почту.")
                                else:
                                    st.success(f"✅ Заявка №{new_id} успешно отправлена!")
                        else:
                            st.error("❌ Ошибка при сохранении заявки. Попробуйте еще раз.")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")

    with tab2:
        st.markdown("### 📋 Управление моими заявками")
        
        # Ввод email для просмотра заявок
        view_email = st.text_input("Введите ваш email для просмотра заявок", 
                                  placeholder="example@mail.ru",
                                  help="Введите email, который вы указывали при создании заявки")
        
        if view_email and validate_email(view_email):
            show_student_requests(view_email)
        elif view_email:
            st.warning("⚠️ Введите корректный email адрес")
        else:
            st.info("👆 Введите ваш email, чтобы увидеть свои заявки")

    st.markdown("---")
    st.markdown("### 🛠 Техническая поддержка")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        📧 **Email:** savchenko.va@unecon.ru
        
        📞 **Телефон:** 8 (812) 458-97-30 доб. 4299

        🕐 **Часы работы технической поддержки:**
        
        ПН-ВТ: 11:00 – 17:00
        """)

if __name__ == "__main__":
    main()
