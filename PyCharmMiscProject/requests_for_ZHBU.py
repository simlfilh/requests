import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time


SUPABASE_URL = "https://ptdxlveqzmrrdlbtuxck.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB0ZHhsdmVxem1ycmRsYnR1eGNrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4Nzc0NTQsImV4cCI6MjA5NTQ1MzQ1NH0.nquoPERBIhu0IMdTKKv3qTQQStjdECtAOM-hsFMIx0A"


SMTP_EMAIL = "valeraforumsch@gmail.com"
SMTP_PASSWORD = "zwny cinl ejom qgsk"  

PASSWORD = "admin123"  


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def load_requests():
    supabase = get_supabase()
    response = supabase.table('requests').select('*').order('id', desc=False).execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame()

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
    st.title("🔐 Панель работника ЖБУ")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

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

    # ===== АВТООБНОВЛЕНИЕ (РАБОТАЮЩАЯ ВЕРСИЯ) =====
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        auto_refresh = st.checkbox("🔄 Автообновление (каждые 10 секунд)", value=False)
    
    with col2:
        if st.button("🔄 Обновить сейчас"):
            st.rerun()
    
    with col3:
        # Счетчик до следующего обновления
        if auto_refresh:
            placeholder = st.empty()
            for i in range(10, 0, -1):
                placeholder.caption(f"Следующее обновление через {i} сек...")
                time.sleep(1)
            placeholder.caption("🔄 Обновление...")
            st.rerun()
    
    if st.button("🚪 Выйти"):
        st.session_state.authenticated = False
        st.rerun()
    # ===== КОНЕЦ АВТООБНОВЛЕНИЯ =====

    st.header("📋 Все заявки студентов")

    df = load_requests()

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

    st.dataframe(filtered_df, use_container_width=True)

    
    st.subheader("✏️ Изменить статус заявки")

    col1, col2 = st.columns(2)

    with col1:
        if not filtered_df.empty:
            selected_id = st.selectbox("Выберите ID заявки", filtered_df["ID"].tolist())
        else:
            selected_id = None
            st.warning("Нет заявок для изменения")

    with col2:
        new_status = st.selectbox("Новый статус", ["Новая", "В работе", "Выполнена"])

    if st.button("Обновить статус") and selected_id:
        if update_status_with_notification(selected_id, new_status):
            st.success(f"✅ Статус заявки #{selected_id} изменён на '{new_status}', студент уведомлён")
            st.rerun()
        else:
            st.error("❌ Ошибка при обновлении статуса")

   
    st.subheader("📥 Экспорт данных")

    export_type = st.radio(
        "Что экспортировать?",
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
