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

def main():
    st.title("🏠 ЖБУ СПбГЭУ | Электронные заявки")

    tab1, tab2 = st.tabs(["📝 Создать заявку", "🗑️ Управление заявками"])

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

    with tab2:
        st.markdown("### Управление заявками")
        
        st.info("💡 Введите ваш email, чтобы увидеть свои заявки")
        
        view_email = st.text_input("Ваш email для просмотра заявок", key="view_email")
        
        if view_email and validate_email(view_email):
            user_requests = get_user_requests(view_email)
            
            if user_requests:
                st.success(f"Найдено {len(user_requests)} заявок")
                
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
                
                # Убеждаемся, что поле completed_confirmed существует
                if 'completed_confirmed' not in display_df.columns:
                    display_df['completed_confirmed'] = False
                
                # Форматируем статус с учетом подтверждения
                def format_status(row):
                    try:
                        if row['Статус'] == "Выполнена" and row.get('completed_confirmed', False):
                            return "✅ Выполнена (подтверждено)"
                        return row['Статус']
                    except:
                        return row['Статус']
                
                display_df["Статус"] = display_df.apply(format_status, axis=1)
                
                # Добавляем чекбоксы для выбора
                checkbox_key = f"checkbox_student_{view_email}"
                
                if checkbox_key not in st.session_state:
                    st.session_state[checkbox_key] = {i: False for i in range(len(display_df))}
                
                # Создаем копию для редактирования
                edit_df = display_df.copy()
                edit_df = edit_df.reset_index(drop=True)
                
                checkbox_values = []
                for i in range(len(edit_df)):
                    checkbox_values.append(st.session_state[checkbox_key].get(i, False))
                
                edit_df.insert(0, "Выбрать", checkbox_values)
                
                # Выбираем колонки для отображения
                columns_to_show = ["Выбрать", "ID", "Дата", "Время", "Тип заявки", "Общежитие", "Комната", "Описание", "Статус"]
                display_columns = [col for col in columns_to_show if col in edit_df.columns]
                edit_df_display = edit_df[display_columns]
                
                # Настраиваем отображение
                column_config = {
                    "Выбрать": st.column_config.CheckboxColumn(
                        "Выбрать",
                        help="Отметьте заявки для управления",
                        default=False,
                    ),
                    "ID": st.column_config.NumberColumn("№", width="small"),
                    "Статус": st.column_config.TextColumn("Статус", width="small"),
                    "Дата": st.column_config.TextColumn("Дата", width="small"),
                    "Время": st.column_config.TextColumn("Время", width="small"),
                    "Комната": st.column_config.TextColumn("Комната", width="small"),
                    "Тип заявки": st.column_config.TextColumn("Тип заявки", width="medium"),
                }
                
                edited_df = st.data_editor(
                    edit_df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config,
                    disabled=["ID", "Дата", "Время", "ФИО", "Email", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус"],
                    key=f"student_data_editor_{view_email}"
                )
                
                # Сохраняем состояние чекбоксов
                for i in range(len(edited_df)):
                    if i < len(edited_df):
                        st.session_state[checkbox_key][i] = edited_df.loc[i, "Выбрать"]
                
                # Получаем выбранные ID
                selected_ids = []
                for i in range(len(edited_df)):
                    if i < len(edited_df) and edited_df.loc[i, "Выбрать"]:
                        selected_ids.append(edit_df.loc[i, "ID"])
                
                if selected_ids:
                    st.success(f"✅ Выбрано заявок: {len(selected_ids)}")
                else:
                    st.info("ℹ️ Отметьте заявки в колонке 'Выбрать' для управления")
                
                # Кнопки управления
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✅ Выбрать все", use_container_width=True, key="select_all_student"):
                        for i in range(len(edit_df)):
                            st.session_state[checkbox_key][i] = True
                        st.rerun()
                    
                    if st.button("❌ Снять все", use_container_width=True, key="deselect_all_student"):
                        for i in range(len(edit_df)):
                            st.session_state[checkbox_key][i] = False
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ Удалить выбранные", use_container_width=True, key="delete_selected_student", type="primary"):
                        if selected_ids:
                            success_count = 0
                            for id in selected_ids:
                                success, message = delete_request(id, view_email)
                                if success:
                                    success_count += 1
                                    notification_body = f"Заявка №{id} была удалена студентом {view_email}"
                                    for worker_email in WORKER_EMAILS:
                                        send_email(worker_email, f"🗑️ Заявка №{id} удалена студентом", notification_body)
                            if success_count > 0:
                                st.success(f"✅ Удалено заявок: {success_count}")
                                for i in range(len(edit_df)):
                                    st.session_state[checkbox_key][i] = False
                                st.rerun()
                            else:
                                st.error("❌ Ошибка при удалении")
                        else:
                            st.warning("⚠️ Выберите заявки для удаления")
                
                # Кнопка подтверждения выполнения
                st.markdown("---")
                st.subheader("✅ Подтверждение выполнения")
                
                if st.button("✅ Подтвердить выполнение выбранных", use_container_width=True, key="confirm_selected_student"):
                    if selected_ids:
                        success_count = 0
                        for id in selected_ids:
                            success, message = confirm_completion(id, view_email)
                            if success:
                                success_count += 1
                        if success_count > 0:
                            st.success(f"✅ Подтверждено заявок: {success_count}")
                            for i in range(len(edit_df)):
                                st.session_state[checkbox_key][i] = False
                            st.rerun()
                        else:
                            st.error("❌ Ошибка при подтверждении. Убедитесь, что выбраны заявки со статусом 'Выполнена'.")
                    else:
                        st.warning("⚠️ Выберите заявки для подтверждения")
                
            else:
                st.warning("Заявки не найдены")
        elif view_email:
            st.error("Введите корректный email")
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
