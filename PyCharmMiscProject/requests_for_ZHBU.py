import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time


SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]
PASSWORD = st.secrets["PASSWORD"] 


DORMITORIES = [
    "Общежитие №2 | Чкаловский пр-т, д. 27",
    "Общежитие №3 | пр-т Косыгина, д. 19, к. 2",
    "Общежитие №4 | ул. Воронежская, д. 69",
    "Общежитие №7 | ул. Воронежская, д. 38"
]

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def load_requests():
    supabase = get_supabase()
    response = supabase.table('requests').select('*').order('id', desc=False).execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame()

def load_requests_by_dormitory(dormitory):
    supabase = get_supabase()
    response = supabase.table('requests').select('*').eq('dormitory', dormitory).order('id', desc=False).execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame()

def delete_request(request_id):
    """Удаление заявки по ID"""
    try:
        supabase = get_supabase()
        
        # Получаем данные заявки перед удалением для уведомления
        response = supabase.table('requests').select('*').eq('id', request_id).execute()
        if response.data:
            request_data = response.data[0]
            
            # Удаляем заявку
            supabase.table('requests').delete().eq('id', request_id).execute()
            
            # Отправляем уведомление работникам
            send_deletion_notification_to_workers(request_data)
            
            return True, f"Заявка №{request_id} успешно удалена"
        else:
            return False, "Заявка не найдена"
    except Exception as e:
        return False, f"Ошибка при удалении: {str(e)}"

def send_deletion_notification_to_workers(request_data):
    """Отправка уведомления работникам об удалении заявки"""
    subject = f"🗑️ ЗАЯВКА №{request_data['id']} УДАЛЕНА"
    body = f"""
Была удалена следующая заявка:

📋 ЗАЯВКА №{request_data['id']}
🏠 {request_data['dormitory']}
👤 Студент: {request_data['fio']}
📧 Email: {request_data['email']}
🚪 Комната: {request_data['room']}
🔧 Тип: {request_data['type']}
📝 Описание: {request_data['description']}
📅 Дата создания: {request_data['date']} {request_data['time']}
❌ Статус: УДАЛЕНА

Заявка была удалена из системы.
"""
    WORKER_EMAILS = [
        "valeraforumsch@gmail.com"
    ]
    
    for worker_email in WORKER_EMAILS:
        try:
            msg = MIMEMultipart()
            msg["From"] = SMTP_EMAIL
            msg["To"] = worker_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print(f"Ошибка отправки уведомления работнику {worker_email}: {e}")

def update_status_with_notification(request_id, new_status):
    supabase = get_supabase()
    
    response = supabase.table('requests').select('*').eq('id', request_id).execute()
    if response.data:
        request = response.data[0]
        student_email = request.get('email')
        student_name = request.get('fio')
        description = request.get('description')
        
        supabase.table('requests').update({'status': new_status}).eq('id', request_id).execute()
        
        if student_email and student_email != 'не указан':
            send_status_notification(student_email, student_name, request_id, new_status, description)
        
        return True
    return False

def send_status_notification(student_email, student_name, request_id, new_status, description):
    status_messages = {
        "Новая": "Ваша заявка принята и ожидает рассмотрения.",
        "В работе": "Специалисты ЖБУ приступили к выполнению вашей заявки.",
        "Выполнена": "✅ Ваша заявка выполнена! Спасибо за обращение."
    }
    message = status_messages.get(new_status, f"Статус заявки изменен на '{new_status}'")
    
    subject = f"📝 ЖБУ Общежитие - Обновление статуса заявки №{request_id}"
    body = f"""
Здравствуйте, {student_name}!

Статус вашей заявки №{request_id} изменился.

📋 Текущий статус: {new_status}
📝 Описание: {description[:200]}...

{message}

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = student_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Заявки')
    return output.getvalue()


def main():
    st.title("🔐 Панель сотрудника ЖБУ | Управление электронными заявками")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "selected_dormitory" not in st.session_state:
        st.session_state.selected_dormitory = "Все"
    if "show_delete_confirm" not in st.session_state:
        st.session_state.show_delete_confirm = False
    if "delete_id" not in st.session_state:
        st.session_state.delete_id = None

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

    st.success("✅ Вы вошли как работник ЖБУ")
    
    if st.button("🚪 Выйти"):
        st.session_state.authenticated = False
        st.rerun()
    
    st.header("📋 Электронные заявки студентов")
    
    if st.session_state.selected_dormitory == "Все":
        df = load_requests()
        title = "Общая таблица всех заявок"
    else:
        df = load_requests_by_dormitory(st.session_state.selected_dormitory)
        title = f"Заявки: {st.session_state.selected_dormitory}"
    
    st.subheader(title)

    if df.empty:
        st.info("Пока нет ни одной заявки.")
        return
        
    display_df = df.rename(columns={
                                    "id": "ID",
                                    "date": "Дата",
                                    "time": "Время",
                                    "fio": "ФИО студента",
                                    "email": "Email",
                                    "dormitory": "Общежитие",  
                                    "room": "Комната",
                                    "type": "Тип заявки",
                                    "description": "Описание",
                                    "status": "Статус"
                                   })

    with st.expander("📊 Статистика по каждому общежитию", expanded=False):
        
        stats_data = []
        for dorm in DORMITORIES:
            dorm_df = load_requests_by_dormitory(dorm)
            if not dorm_df.empty:
                stats_data.append({
                    "Общежитие": dorm,
                    "Всего": len(dorm_df),
                    "Новых": len(dorm_df[dorm_df["status"] == "Новая"]),
                    "В работе": len(dorm_df[dorm_df["status"] == "В работе"]),
                    "Выполнено": len(dorm_df[dorm_df["status"] == "Выполнена"])
                })
            else:
                stats_data.append({
                    "Общежитие": dorm,
                    "Всего": 0,
                    "Новых": 0,
                    "В работе": 0,
                    "Выполнено": 0
                })
        
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, use_container_width=True)
        
        for dorm in DORMITORIES:
            with st.expander(f"📋 {dorm}", expanded=False):
                dorm_df = load_requests_by_dormitory(dorm)
                if not dorm_df.empty:
                    dorm_display = dorm_df.rename(columns={
                        "id": "№", "date": "Дата", "time": "Время",
                        "fio": "ФИО студента", "email": "Email",
                        "room": "Комната", "type": "Тип заявки",
                        "description": "Описание", "status": "Статус"
                    })
                    st.dataframe(dorm_display, use_container_width=True)
                    
                    excel_data = to_excel(dorm_display)
                    st.download_button(
                        label=f"📊 Скачать в Excel формате",
                        data=excel_data,
                        file_name=f"Заявки_{dorm.replace(' | ', '_')}_{datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"export_{dorm}"
                    )
                else:
                    st.info(f"Нет заявок для {dorm}")

    col1, col2, col3 = st.columns(3)

    with col1:
        status_filter = st.selectbox("Статус", ["Все", "Новая", "В работе", "Выполнена"])

    with col2:
        date_options = ["Все", "Сегодня", "Вчера", "Выбрать дату"]
        date_filter_type = st.selectbox("Период", date_options)

    with col3:
        type_options = ["Все", "Сантехника", "Электрика", "Уборка", "Другое"]
        type_filter = st.selectbox("Тип заявки", type_options)

    filtered_df = display_df.copy()

    if status_filter != "Все":
        filtered_df = filtered_df[filtered_df["Статус"] == status_filter]

    if type_filter != "Все":
        type_map_filter = {
            "Сантехника": "Сантехника",
            "Электрика": "Электрика",
            "Уборка": "Уборка",
            "Другое": "Другое"
        }
        filtered_df = filtered_df[filtered_df["Тип заявки"] == type_map_filter[type_filter]]

    today = datetime.now().date()
    if date_filter_type == "Сегодня":
        filtered_df = filtered_df[filtered_df["Дата"] == today.strftime("%Y-%m-%d")]
    elif date_filter_type == "Вчера":
        yesterday = today - timedelta(days=1)
        filtered_df = filtered_df[filtered_df["Дата"] == yesterday.strftime("%Y-%m-%d")]
    elif date_filter_type == "Эта неделя":
        start_of_week = today - timedelta(days=today.weekday())
        filtered_df = filtered_df[pd.to_datetime(filtered_df["Дата"]) >= pd.Timestamp(start_of_week)]
    elif date_filter_type == "Выбрать дату":
        selected_date = st.date_input("Выберите дату", value=today)
        filtered_df = filtered_df[filtered_df["Дата"] == selected_date.strftime("%Y-%m-%d")]

    st.info(f"📊 Найдено заявок: {len(filtered_df)} из {len(display_df)}")

    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего в фильтре", len(filtered_df))
    with col2:
        st.metric("Новых", len(filtered_df[filtered_df["Статус"] == "Новая"]))
    with col3:
        st.metric("В работе", len(filtered_df[filtered_df["Статус"] == "В работе"]))
    with col4:
        st.metric("Выполнено", len(filtered_df[filtered_df["Статус"] == "Выполнена"]))

    if st.button("🔄 Обновить сейчас"):
        st.rerun()

    st.dataframe(filtered_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("✏️ Управление заявкой")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not filtered_df.empty:
            selected_id = st.selectbox("Выберите № заявки для изменения статуса", filtered_df["ID"].tolist(), key="select_id")
        else:
            selected_id = None
            st.warning("Нет заявок для изменения")
    
    with col2:
        new_status = st.selectbox("Новый статус", ["Новая", "В работе", "Выполнена"], key="new_status")
    
    if st.button("🔄 Обновить статус", key="update_status_btn") and selected_id:
        if update_status_with_notification(selected_id, new_status):
            st.success(f"✅ Статус заявки #{selected_id} изменён на '{new_status}', студент уведомлён")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Ошибка при обновлении статуса")
    
    st.markdown("---")
    st.subheader("🗑️ Удаление заявки")
    
    if not filtered_df.empty:
        delete_id = st.selectbox("Выберите № заявки для удаления", filtered_df["ID"].tolist(), key="delete_select_id")
    else:
        delete_id = None
        st.warning("Нет заявок для удаления")
    
    if st.button("🗑️ Удалить выбранную заявку", key="delete_btn"):
        if delete_id:
            st.session_state.show_delete_confirm = True
            st.session_state.delete_id = delete_id
        else:
            st.error("❌ Нет заявок для удаления")
    
    # Диалог подтверждения удаления
    if st.session_state.show_delete_confirm:
        with st.container():
            st.warning(f"⚠️ Вы уверены, что хотите удалить заявку №{st.session_state.delete_id}? Это действие невозможно отменить. Заявка будет полностью удалена из базы данных.")
            
            col_yes, col_no = st.columns(2)
            
            with col_yes:
                if st.button("✅ Удалить", key="confirm_delete_final"):
                    success, message = delete_request(st.session_state.delete_id)
                    if success:
                        st.success(f"✅ {message}")
                        st.session_state.show_delete_confirm = False
                        st.session_state.delete_id = None
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                        st.session_state.show_delete_confirm = False
                        st.session_state.delete_id = None
                        st.rerun()
            
            with col_no:
                if st.button("❌ Отмена", key="cancel_delete_final"):
                    st.session_state.show_delete_confirm = False
                    st.session_state.delete_id = None
                    st.rerun()
    
    st.markdown("---")
    st.subheader("📥 Экспорт данных")

    export_type = st.radio(
        "Какие заявки экспортировать:",
        ["Все заявки", "Только отфильтрованные"],
        horizontal=True
    )

    export_df = filtered_df if export_type == "Только отфильтрованные" else display_df

    excel_data = to_excel(export_df)
    st.download_button(
        label="📊 Скачать в Excel формате",
        data=excel_data,
        file_name=f"zayavki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

if __name__ == "__main__":
    main()
