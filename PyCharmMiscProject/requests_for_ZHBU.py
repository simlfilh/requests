import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import locale
import os
import hashlib

try:
    if os.name == 'nt':  # Windows
        locale.setlocale(locale.LC_TIME, 'Russian_Russia.1251')
    else:  # Linux/Mac
        locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except:
    pass

st.set_page_config(
    page_title="Управление электронными заявками | Общежития СПбГЭУ",
    page_icon="📲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Получаем секреты
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]

# Система пользователей с паролями из secrets
USERS = {
    # Заведующие (5 человек)
    "4295": {
        "username": "4295",
        "password": hashlib.sha256(st.secrets["PASSWORD_HEAD_2"].encode()).hexdigest(),
        "role": "head",
        "name": "Беззубова Зоя Николаевна ",
        "dormitory": "Общежитие №2 | Чкаловский пр-т, д. 27"
    },
    "1132": {
        "username": "1132",
        "password": hashlib.sha256(st.secrets["PASSWORD_HEAD_3"].encode()).hexdigest(),
        "role": "head",
        "name": "Васильев Александр Владимирович",
        "dormitory": "Общежитие №3 | пр-т Косыгина, д. 19, к. 2"
    },
    "4938": {
        "username": "4938",
        "password": hashlib.sha256(st.secrets["PASSWORD_HEAD_41"].encode()).hexdigest(),
        "role": "head",
        "name": "Бровкина Наталья Анатольевна",
        "dormitory": "Общежитие №4 | ул. Воронежская, д. 69"
    },
    "4293": {
        "username": "4293",
        "password": hashlib.sha256(st.secrets["PASSWORD_HEAD_42"].encode()).hexdigest(),
        "role": "head",
        "name": "Гунько Валентина Шахиевна",
        "dormitory": "Общежитие №4 | наб. канала Грибоедова, д. 30-32, лит. Б"
    },
    "4961": {
        "username": "4961",
        "password": hashlib.sha256(st.secrets["PASSWORD_HEAD_7"].encode()).hexdigest(),
        "role": "head",
        "name": "Малышева Елена Андреевна",
        "dormitory": "Общежитие №7 | ул. Воронежская, д. 38"
    },
    # Сотрудник ЖБУ (1 человек)
    "414244": {
        "username": "414244",
        "password": hashlib.sha256(st.secrets["PASSWORD_JBU_WORKER"].encode()).hexdigest(),
        "role": "jbu",
        "name": "Сотрудник ЖБУ",
        "dormitory": None  # Видит все общежития
    }
}

DORMITORIES = [
    "Общежитие №2 | Чкаловский пр-т, д. 27",
    "Общежитие №3 | пр-т Косыгина, д. 19, к. 2",
    "Общежитие №4 | ул. Воронежская, д. 69",
    "Общежитие №4 | наб. канала Грибоедова, д. 30-32, лит. Б",
    "Общежитие №7 | ул. Воронежская, д. 38"
]

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def authenticate_user(username, password):
    """Проверяет учетные данные пользователя"""
    if username in USERS:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if USERS[username]["password"] == hashed_password:
            return USERS[username]
    return None

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

def load_comments(request_id):
    supabase = get_supabase()
    request_id = int(request_id)
    response = supabase.table('comments').select('*').eq('request_id', request_id).order('created_at', desc=False).execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame()

def add_comment(request_id, comment_text, author="Заведующий"):
    if not comment_text or comment_text.strip() == "":
        return False, "Комментарий не может быть пустым"
    
    supabase = get_supabase()
    try:
        request_id = int(request_id)
        data = {
            'request_id': request_id,
            'comment': comment_text.strip(),
            'author': author,
            'created_at': datetime.now().isoformat()
        }
        response = supabase.table('comments').insert(data).execute()
        return True, "Комментарий добавлен"
    except Exception as e:
        return False, f"Ошибка при добавлении комментария: {str(e)}"
        
def delete_comment(comment_id):
    supabase = get_supabase()
    try:
        supabase.table('comments').delete().eq('id', comment_id).execute()
        return True, "Комментарий удален"
    except Exception as e:
        return False, f"Ошибка при удалении комментария: {str(e)}"

def delete_request(request_id):
    try:
        supabase = get_supabase()
        response = supabase.table('requests').select('*').eq('id', request_id).execute()
        if response.data:
            request_data = response.data[0]
            supabase.table('comments').delete().eq('request_id', request_id).execute()
            supabase.table('requests').delete().eq('id', request_id).execute()
            send_deletion_notification_to_workers(request_data)
            return True, f"Заявка №{request_id} успешно удалена"
        else:
            return False, "Заявка не найдена"
    except Exception as e:
        return False, f"Ошибка при удалении: {str(e)}"

def send_deletion_notification_to_workers(request_data):
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
    WORKER_EMAILS = ["valeraforumsch@gmail.com"]
    
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
        
        workbook = writer.book
        worksheet = writer.sheets['Заявки']
        
        from openpyxl.styles import Alignment
        
        column_widths = {
            'A': 4, 'B': 11, 'C': 9, 'D': 30, 'E': 29,
            'F': 37, 'G': 8, 'H': 16, 'I': 60, 'J': 11
        }
        for col_letter, width in column_widths.items():
            worksheet.column_dimensions[col_letter].width = width
        
        for row_idx in range(2, worksheet.max_row + 1):
            max_height = 25
            
            for col_letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                cell = worksheet[f'{col_letter}{row_idx}']
                if cell.value:
                    text = str(cell.value)
                    
                    if col_letter == 'I':
                        chars_per_line = 60
                        lines = (len(text) // chars_per_line) + 1
                        height_needed = lines * 18
                        if height_needed > max_height:
                            max_height = min(height_needed, 150)
                    else:
                        if len(text) > 30:
                            lines = (len(text) // 30) + 1
                            height_needed = lines * 18
                            if height_needed > max_height:
                                max_height = min(height_needed, 80)
            
            worksheet.row_dimensions[row_idx].height = max_height
        
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.column_letter == 'I':
                    cell.alignment = Alignment(
                        horizontal='left',
                        vertical='center',
                        wrap_text=True
                    )
                else:
                    cell.alignment = Alignment(
                        horizontal='left',
                        vertical='center'
                    )
        
        worksheet.freeze_panes = 'A2'
        
    return output.getvalue()
    
def show_statistics(user_role, user_dormitory):
    st.header("📊 Статистика по общежитиям")
    
    stats_data = []
    for dorm in DORMITORIES:
        # Если пользователь - заведующий, показываем только его общежитие
        if user_role == "head" and user_dormitory and dorm != user_dormitory:
            continue
            
        dorm_df = load_requests_by_dormitory(dorm)
        if not dorm_df.empty:
            stats_data.append({
                "Общежитие": dorm.split('|')[0].strip(),
                "Всего": len(dorm_df),
                "Новых": len(dorm_df[dorm_df["status"] == "Новая"]),
                "В работе": len(dorm_df[dorm_df["status"] == "В работе"]),
                "Выполнено": len(dorm_df[dorm_df["status"] == "Выполнена"])
            })
        else:
            stats_data.append({
                "Общежитие": dorm.split('|')[0].strip(),
                "Всего": 0,
                "Новых": 0,
                "В работе": 0,
                "Выполнено": 0
            })
    
    if stats_data:
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
    else:
        st.info("Нет доступных общежитий для отображения статистики")

def show_comments_for_request(request_id, user_role):
    request_id = int(request_id)
    
    st.markdown("---")
    st.subheader("💬 Комментарии к заявке")
    
    comments_df = load_comments(request_id)
    
    if not comments_df.empty:
        for _, comment in comments_df.iterrows():
            col1, col2 = st.columns([10, 1])
            with col1:
                created_at = comment['created_at']
                if isinstance(created_at, str):
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = dt.strftime('%d.%m.%Y %H:%M')
                    except:
                        pass
                
                st.markdown(f"""
                <div style="background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 10px;">
                    <strong>👤 {comment['author']}</strong>
                    <span style="color: #666; font-size: 12px; margin-left: 10px;">{created_at}</span>
                    <br>
                    <span>{comment['comment']}</span>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                if st.button("🗑️", key=f"del_comment_{comment['id']}", help="Удалить комментарий"):
                    success, msg = delete_comment(comment['id'])
                    if success:
                        st.success("Комментарий удален")
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        st.info("Комментариев пока нет")
    
    st.markdown("### ✏️ Добавить комментарий")
    
    with st.form(key=f"add_comment_form_{request_id}"):
        comment_text = st.text_area("Текст комментария", placeholder="Введите ваш комментарий...", key=f"comment_text_{request_id}")
        col1, col2, col3 = st.columns([3, 1, 1])
        with col2:
            submitted = st.form_submit_button("💬 Отправить", use_container_width=True)
        
        if submitted:
            if comment_text and comment_text.strip():
                author = "Заведующий" if user_role == "head" else "Сотрудник ЖБУ"
                success, msg = add_comment(request_id, comment_text, author=author)
                if success:
                    st.success("✅ Комментарий добавлен")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
            else:
                st.warning("⚠️ Введите текст комментария")

def show_dormitory_requests_with_control(dormitory, user_role, user_name):
    df = load_requests_by_dormitory(dormitory)
    
    if df.empty:
        st.info(f"Нет заявок для {dormitory}")
        return
    
    st.subheader("🔍 Фильтры")
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Статус", ["Все", "Новая", "В работе", "Выполнена"], key=f"status_{dormitory}")
    with col2:
        date_options = ["Все", "Сегодня", "Вчера", "Выбрать дату", "Выбрать период"]
        date_filter = st.selectbox("Период", date_options, key=f"date_{dormitory}")
    
    filtered_df = df.copy()
    if status_filter != "Все":
        filtered_df = filtered_df[filtered_df["status"] == status_filter]
    
    today = datetime.now().date()
    
    if date_filter == "Сегодня":
        filtered_df = filtered_df[filtered_df["date"] == today.strftime("%Y-%m-%d")]
    elif date_filter == "Вчера":
        yesterday = today - timedelta(days=1)
        filtered_df = filtered_df[filtered_df["date"] == yesterday.strftime("%Y-%m-%d")]
    elif date_filter == "Выбрать дату":
        selected_date = st.date_input("Выберите дату", value=today, key=f"date_picker_{dormitory}")
        filtered_df = filtered_df[filtered_df["date"] == selected_date.strftime("%Y-%m-%d")]
    elif date_filter == "Выбрать период":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Начальная дата", value=today - timedelta(days=7), key=f"start_date_{dormitory}")
        with col2:
            end_date = st.date_input("Конечная дата", value=today, key=f"end_date_{dormitory}")
        filtered_df["date"] = pd.to_datetime(filtered_df["date"])
        filtered_df = filtered_df[(filtered_df["date"] >= pd.Timestamp(start_date)) & (filtered_df["date"] <= pd.Timestamp(end_date))]
    
    display_df = filtered_df.copy()
    display_df["date"] = pd.to_datetime(display_df["date"]).dt.strftime("%d.%m.%Y")
    
    display_df = display_df.rename(columns={
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
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего", len(display_df))
    with col2:
        st.metric("Новых", len(display_df[display_df["Статус"] == "Новая"]))
    with col3:
        st.metric("В работе", len(display_df[display_df["Статус"] == "В работе"]))
    with col4:
        st.metric("Выполнено", len(display_df[display_df["Статус"] == "Выполнена"]))
    
    st.markdown("---")
    
    types_to_show = [
        "🔧 Сантехника",
        "⚡ Электрика",
        "🔨 Плотник",
        "🍵 Плиты",
        "🧹 Уборка",
        "❓ Вопрос / Другое"
    ]
    
    for category in types_to_show:
        st.subheader(category)
        
        cat_df = display_df[display_df["Тип заявки"] == category]
        
        if cat_df.empty:
            st.info(f"Нет заявок")
            st.markdown("---")
            continue
        
        st.caption(f"Количество заявок: {len(cat_df)}")
        
        comments_dict = {}
        for _, row in cat_df.iterrows():
            request_id = row['ID']
            comments_df = load_comments(request_id)
            if not comments_df.empty:
                comments_list = []
                for _, comment in comments_df.iterrows():
                    text = comment.get('comment', '')
                    comments_list.append(text)
                comments_dict[request_id] = "\n".join(comments_list)
            else:
                comments_dict[request_id] = ""
        
        cat_df_with_comments = cat_df.copy()
        cat_df_with_comments["Комментарии"] = cat_df_with_comments["ID"].map(comments_dict)
        
        checkbox_key = f"checkboxes_{dormitory}_{category}"
        
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = {i: False for i in range(len(cat_df_with_comments))}
        
        edit_df = cat_df_with_comments.copy()
        edit_df = edit_df.reset_index(drop=True)
        
        checkbox_values = []
        for i in range(len(edit_df)):
            checkbox_values.append(st.session_state[checkbox_key].get(i, False))
        
        edit_df.insert(0, "Выбрать", checkbox_values)
        
        columns_to_show = ["Выбрать", "ID", "Дата", "ФИО студента", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус", "Комментарии"]
        display_columns = [col for col in columns_to_show if col in edit_df.columns]
        edit_df_display = edit_df[display_columns]
        
        editor_key = f"data_editor_{dormitory}_{category}"
        
        column_config = {
            "Выбрать": st.column_config.CheckboxColumn(
                "Выбрать",
                help="Отметьте заявки для массового управления",
                default=False,
            ),
            "ID": st.column_config.NumberColumn("№", width="small"),
            "Статус": st.column_config.TextColumn("Статус", width="small"),
            "Дата": st.column_config.TextColumn("Дата", width="small"),
            "Время": st.column_config.TextColumn("Время", width="small"),
            "Комната": st.column_config.TextColumn("Комната", width="small"),
            "Тип заявки": st.column_config.TextColumn("Тип заявки", width="medium"),
            "Комментарии": st.column_config.TextColumn(
                "💬 Комментарии",
                width="large",
                help="Введите комментарии. Каждый новый комментарий с новой строки"
            ),
        }
        
        edited_df = st.data_editor(
            edit_df_display,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            disabled=["ID", "Дата", "Время", "ФИО студента", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус"],
            key=editor_key
        )
        
        for i in range(len(edited_df)):
            st.session_state[checkbox_key][i] = edited_df.loc[i, "Выбрать"]
        
        comments_changed = False
        for i in range(len(edited_df)):
            request_id = int(edit_df.loc[i, "ID"])
            old_comments = edit_df.loc[i, "Комментарии"] if i < len(edit_df) else ""
            new_comments = edited_df.loc[i, "Комментарии"] if i < len(edited_df) else ""
            
            if new_comments != old_comments:
                supabase = get_supabase()
                supabase.table('comments').delete().eq('request_id', request_id).execute()
                
                if new_comments and new_comments.strip():
                    lines = [line.strip() for line in new_comments.split('\n') if line.strip()]
                    
                    for line in lines:
                        author = "Заведующий" if user_role == "head" else "Сотрудник ЖБУ"
                        success, msg = add_comment(request_id, line, author=author)
                        if success:
                            comments_changed = True
                else:
                    comments_changed = True
        
        if comments_changed:
            st.success("✅ Комментарии обновлены")
            time.sleep(0.5)
            st.rerun()
        
        selected_ids = []
        for i in range(len(edited_df)):
            if edited_df.loc[i, "Выбрать"]:
                selected_ids.append(edit_df.loc[i, "ID"])
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            if st.button("✅ Выбрать все", use_container_width=True, key=f"select_all_{dormitory}_{category}"):
                for i in range(len(edit_df)):
                    st.session_state[checkbox_key][i] = True
                st.rerun()
            
            if st.button("❌ Снять все", use_container_width=True, key=f"deselect_all_{dormitory}_{category}"):
                for i in range(len(edit_df)):
                    st.session_state[checkbox_key][i] = False
                st.rerun()
            
            if st.button(f"🗑️ Удалить ({len(selected_ids)})", use_container_width=True, key=f"bulk_delete_{dormitory}_{category}", type="primary"):
                st.session_state[f"show_bulk_delete_confirm_{dormitory}_{category}"] = True
                st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = selected_ids
        
        with col_right:
            new_status_bulk = st.selectbox(
                "Новый статус", 
                ["Новая", "В работе", "Выполнена"], 
                key=f"bulk_status_{dormitory}_{category}",
                label_visibility="collapsed"
            )

            if st.button(f"🔄 Изменить статус ({len(selected_ids)})", use_container_width=True, key=f"bulk_update_{dormitory}_{category}"):
                success_count = 0
                for id in selected_ids:
                    if update_status_with_notification(id, new_status_bulk):
                        success_count += 1
                if success_count > 0:
                    st.success(f"✅ Статус изменен для {success_count} заявок")
                    for i in range(len(edit_df)):
                        st.session_state[checkbox_key][i] = False
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Ошибка при обновлении статусов")
                    
            excel_data = to_excel(cat_df)
            st.download_button(
                label=f"📊 Скачать в Excel формате",
                data=excel_data,
                file_name=f"{dormitory.split('|')[0].strip()}_{category}_{datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"export_{dormitory}_{category}"
            )
        
        confirm_key = f"show_bulk_delete_confirm_{dormitory}_{category}"
        if st.session_state.get(confirm_key, False):
            with st.container():
                col_w0, col_w1 = st.columns(2)
                with col_w0:
                    st.warning(f"⚠️ Вы действительно хотите удалить количество заявок: {len(st.session_state[f'bulk_delete_ids_{dormitory}_{category}'])}?")
                col_yes, col_no, col1, col2 = st.columns(4)
                col_w2, col_w3 = st.columns(2)
                with col_yes:
                    if st.button("✅ Да", use_container_width=True, key=f"confirm_bulk_{dormitory}_{category}"):
                        success_count = 0
                        for id in st.session_state[f"bulk_delete_ids_{dormitory}_{category}"]:
                            success, _ = delete_request(id)
                            if success:
                                success_count += 1
                        if success_count > 0:
                            with col_w2:
                                st.success(f"✅ Удалено заявок: {success_count}")
                                for i in range(len(edit_df)):
                                    st.session_state[checkbox_key][i] = False
                                st.session_state[confirm_key] = False
                                st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = []
                                time.sleep(1)
                                st.rerun()
                        else:
                            with col_w2:
                                st.error("❌ Ошибка при удалении")
                with col_no:
                    if st.button("❌ Нет", use_container_width=True, key=f"cancel_bulk_{dormitory}_{category}"):
                        st.session_state[confirm_key] = False
                        st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = []
                        st.rerun()

def show_login_form():
    """Отображает форму входа"""
    st.title("🔐 Панель сотрудника ЖБУ | Управление электронными заявками")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 👤 Вход в систему")
        
        with st.form("login_form"):
            username = st.text_input("Логин", placeholder="Введите ваш логин")
            password = st.text_input("Пароль", type="password", placeholder="Введите пароль")
            submitted = st.form_submit_button("🔑 Войти", use_container_width=True)
            
            if submitted:
                if username and password:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("❌ Неверный логин или пароль!")
                else:
                    st.warning("⚠️ Пожалуйста, заполните все поля")

def main():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "selected_dormitory" not in st.session_state:
        st.session_state.selected_dormitory = "Все"
    if "show_stats" not in st.session_state:
        st.session_state.show_stats = False
    if "show_all_requests" not in st.session_state:
        st.session_state.show_all_requests = False
    if "show_bulk_delete_confirm_all" not in st.session_state:
        st.session_state.show_bulk_delete_confirm_all = False
    if "bulk_delete_ids_all" not in st.session_state:
        st.session_state.bulk_delete_ids_all = []
    if "refresh_count" not in st.session_state:
        st.session_state.refresh_count = 0

    # Если не авторизован - показываем форму входа
    if not st.session_state.authenticated:
        show_login_form()
        return
    
    # Получаем данные пользователя
    user = st.session_state.user
    user_role = user["role"]
    user_name = user["name"]
    user_dormitory = user.get("dormitory")
    
    # Показываем приветствие и кнопку выхода
    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        st.title(f"{user_name}")
        if user_role == "head":
            st.caption(f"🏢 Ваше общежитие: {user_dormitory.split('|')[0].strip()}")
        else:
            st.caption("🔧 Доступны все общежития")
    
    with col3:
        if st.button("🚪 Выйти", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()
    
    st.divider()
    
    # Навигация в зависимости от роли
    if user_role == "head":
        # Заведующий видит только свое общежитие
        show_dormitory_requests_with_control(user_dormitory, user_role, user_name)
        
        # Кнопка для статистики
        col_full2 = st.columns(1)[0]
        with col_full2:
            if st.button("📊 Статистика", use_container_width=True):
                st.session_state.show_stats = not st.session_state.show_stats
        
        if st.session_state.show_stats:
            show_statistics(user_role, user_dormitory)
    
    else:  # Сотрудник ЖБУ - полный доступ
        st.header("📋 Управление заявками")
        
        # Кнопки для быстрого перехода по общежитиям
        cols = st.columns(4)
        dormitories_short = ["Общежитие №2 | Чкаловский пр-т, д. 27", 
                             "Общежитие №3 | пр-т Косыгина, д. 19, к. 2", 
                             "Общежитие №4 | ул. Воронежская, д. 69", 
                             "Общежитие №4 | наб. канала Грибоедова, д. 30-32, лит. Б",
                             "Общежитие №7 | ул. Воронежская, д. 38"]
        
        for i, (short, full) in enumerate(zip(dormitories_short, DORMITORIES)):
            with cols[i]:
                if st.button(f"🏢 {full}", use_container_width=True, key=f"dorm_{i+2}"):
                    st.session_state.selected_dormitory = full
                    st.session_state.show_stats = False
                    st.session_state.show_all_requests = False
                    st.rerun()
        
        col_full = st.columns(1)[0]
        with col_full:
            if st.button("📋 Все заявки", use_container_width=True, key="dorm_all"):
                st.session_state.show_all_requests = not st.session_state.show_all_requests
                st.session_state.show_stats = False
                st.rerun()
        
        col_full2 = st.columns(1)[0]
        with col_full2:
            if st.button("📊 Статистика", use_container_width=True, key="show_stats_btn"):
                st.session_state.show_stats = not st.session_state.show_stats
                st.session_state.show_all_requests = False
                st.rerun()
        
        st.divider()
        
        if st.session_state.show_stats:
            show_statistics(user_role, None)
            st.divider()
        
        elif st.session_state.show_all_requests:
            show_all_requests_with_control()
        
        else:
            if st.session_state.selected_dormitory == "Все":
                st.info("🏠 Выберите общежитие для просмотра заявок или нажмите 'Все заявки'")
                
                st.subheader("📊 Краткая статистика")
                stats_data = []
                for dorm in DORMITORIES:
                    dorm_df = load_requests_by_dormitory(dorm)
                    if not dorm_df.empty:
                        stats_data.append({
                            "Общежитие": dorm.split('|')[0].strip(),
                            "Всего": len(dorm_df),
                            "Новых": len(dorm_df[dorm_df["status"] == "Новая"]),
                            "В работе": len(dorm_df[dorm_df["status"] == "В работе"]),
                            "Выполнено": len(dorm_df[dorm_df["status"] == "Выполнена"])
                        })
                    else:
                        stats_data.append({
                            "Общежитие": dorm.split('|')[0].strip(),
                            "Всего": 0,
                            "Новых": 0,
                            "В работе": 0,
                            "Выполнено": 0
                        })
                
                stats_df = pd.DataFrame(stats_data)
                st.dataframe(stats_df, use_container_width=True, hide_index=True)
                
            else:
                st.subheader(st.session_state.selected_dormitory)
                show_dormitory_requests_with_control(st.session_state.selected_dormitory, user_role, user_name)

def show_all_requests_with_control():
    """Функция для отображения всех заявок с управлением (только для сотрудника ЖБУ)"""
    st.header("📋 Все заявки")
    
    df_all = load_requests()
    if df_all.empty:
        st.info("Пока нет ни одной заявки.")
        return
    
    display_df_all = df_all.rename(columns={
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
    
    st.subheader("🔍 Фильтры")
    
    request_types = ["Все"] + [
        "🔧 Сантехника",
        "⚡ Электрика",
        "🔨 Плотник",
        "🍵 Плиты",
        "🧹 Уборка",
        "❓ Вопрос / Другое"
    ]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter_all = st.selectbox("Статус", ["Все", "Новая", "В работе", "Выполнена"], key="status_all")
    with col2:
        dorm_filter_all = st.selectbox("Общежитие", ["Все"] + [d.split('|')[0].strip() for d in DORMITORIES], key="dorm_all_filter")
    with col3:
        type_filter_all = st.selectbox("Тип заявки", request_types, key="type_all_filter")
    with col4:
        date_options_all = ["Все", "Сегодня", "Вчера", "Выбрать дату", "Выбрать период"]
        date_filter_all = st.selectbox("Период", date_options_all, key="date_all_filter")
    
    filtered_df = display_df_all.copy()
    
    if status_filter_all != "Все":
        filtered_df = filtered_df[filtered_df["Статус"] == status_filter_all]
    
    if dorm_filter_all != "Все":
        filtered_df = filtered_df[filtered_df["Общежитие"].str.contains(dorm_filter_all)]
    
    if type_filter_all != "Все":
        filtered_df = filtered_df[filtered_df["Тип заявки"] == type_filter_all]
    
    today = datetime.now().date()
    
    if date_filter_all == "Сегодня":
        filtered_df = filtered_df[filtered_df["Дата"] == today.strftime("%Y-%m-%d")]
    elif date_filter_all == "Вчера":
        yesterday = today - timedelta(days=1)
        filtered_df = filtered_df[filtered_df["Дата"] == yesterday.strftime("%Y-%m-%d")]
    elif date_filter_all == "Выбрать дату":
        selected_date = st.date_input("Выберите дату", value=today, key="date_picker_all")
        filtered_df = filtered_df[filtered_df["Дата"] == selected_date.strftime("%Y-%m-%d")]
    elif date_filter_all == "Выбрать период":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Начальная дата", value=today - timedelta(days=7), key="start_date_all")
        with col2:
            end_date = st.date_input("Конечная дата", value=today, key="end_date_all")
        filtered_df["Дата"] = pd.to_datetime(filtered_df["Дата"])
        filtered_df = filtered_df[(filtered_df["Дата"] >= pd.Timestamp(start_date)) & (filtered_df["Дата"] <= pd.Timestamp(end_date))]
    
    filtered_df["Дата"] = pd.to_datetime(filtered_df["Дата"]).dt.strftime("%d.%m.%Y")
    
    comments_dict = {}
    for _, row in filtered_df.iterrows():
        request_id = row['ID']
        comments_df = load_comments(request_id)
        if not comments_df.empty:
            comments_list = []
            for _, comment in comments_df.iterrows():
                author = comment.get('author', '')
                text = comment.get('comment', '')
                created_at = comment.get('created_at', '')
                if isinstance(created_at, str):
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = dt.strftime('%d.%m.%Y %H:%M')
                    except:
                        created_at = ''
                comments_list.append(f"[{created_at}] {author}: {text}")
            comments_dict[request_id] = "\n".join(comments_list)
        else:
            comments_dict[request_id] = ""
    
    filtered_df["Комментарии"] = filtered_df["ID"].map(comments_dict)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего", len(filtered_df))
    with col2:
        st.metric("Новых", len(filtered_df[filtered_df["Статус"] == "Новая"]))
    with col3:
        st.metric("В работе", len(filtered_df[filtered_df["Статус"] == "В работе"]))
    with col4:
        st.metric("Выполнено", len(filtered_df[filtered_df["Статус"] == "Выполнена"]))
    
    st.markdown("---")
    
    if not filtered_df.empty:
        checkbox_key_all = "checkbox_all_state"
        
        if checkbox_key_all not in st.session_state:
            st.session_state[checkbox_key_all] = {i: False for i in range(len(filtered_df))}
        
        edit_df = filtered_df.copy()
        edit_df = edit_df.reset_index(drop=True)
        
        checkbox_values = []
        for i in range(len(edit_df)):
            checkbox_values.append(st.session_state[checkbox_key_all].get(i, False))
        
        edit_df.insert(0, "Выбрать", checkbox_values)
        
        columns_for_editor = ["Выбрать", "ID", "Дата", "Время", "ФИО студента", "Email", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус", "Комментарии"]
        edit_df_display = edit_df[columns_for_editor]
        
        editor_key = "data_editor_all"
        
        edited_df = st.data_editor(
            edit_df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Выбрать": st.column_config.CheckboxColumn(
                    "Выбрать",
                    help="Отметьте заявки для редактирования",
                    default=False,
                ),
                "ID": st.column_config.NumberColumn(
                    "№",
                    help="Номер заявки",
                    width="small",
                ),
                "Статус": st.column_config.TextColumn(
                    "Статус",
                    width="small",
                ),
                "Комментарии": st.column_config.TextColumn(
                    "💬 Комментарии",
                    width="large",
                    help="Напишите комментарий к заявке. Каждый новый комментарий начинайте с новой строки"
                ),
            },
            disabled=["ID", "Дата", "Время", "ФИО студента", "Email", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус"],
            key=editor_key
        )
        
        for i in range(len(edited_df)):
            st.session_state[checkbox_key_all][i] = edited_df.loc[i, "Выбрать"]
        
        comments_added = False
        for i in range(len(edited_df)):
            request_id = int(edit_df.loc[i, "ID"])
            old_comments = edit_df.loc[i, "Комментарии"] if i < len(edit_df) else ""
            new_comments = edited_df.loc[i, "Комментарии"] if i < len(edited_df) else ""
            
            if new_comments != old_comments and new_comments:
                existing_comments_df = load_comments(request_id)
                existing_texts = set()
                if not existing_comments_df.empty:
                    for _, comm in existing_comments_df.iterrows():
                        existing_texts.add(comm.get('comment', ''))
                
                new_lines = [line.strip() for line in new_comments.split('\n') if line.strip()]
                
                for line in new_lines:
                    if line not in existing_texts and line:
                        success, msg = add_comment(request_id, line, author="Сотрудник ЖБУ")
                        if success:
                            comments_added = True
                            existing_texts.add(line)
        
        if comments_added:
            st.success("✅ Комментарии добавлены")
            time.sleep(0.5)
            st.rerun()
        
        selected_ids = []
        for i in range(len(edited_df)):
            if edited_df.loc[i, "Выбрать"]:
                selected_ids.append(edit_df.loc[i, "ID"])
        
        if selected_ids:
            st.success(f"✅ Выбрано заявок: {len(selected_ids)}")
        else:
            st.info("ℹ️ Отметьте заявки в колонке 'Выбрать' для редактирования")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Выбрать все", use_container_width=True, key="select_all_all"):
                for i in range(len(edit_df)):
                    st.session_state[checkbox_key_all][i] = True
                st.rerun()
            
            if st.button("❌ Снять все", use_container_width=True, key="deselect_all_all"):
                for i in range(len(edit_df)):
                    st.session_state[checkbox_key_all][i] = False
                st.rerun()
        
        with col2:
            new_status_bulk = st.selectbox(
                "Новый статус",
                ["Новая", "В работе", "Выполнена"],
                key="bulk_status_all",
                label_visibility="collapsed"
            )
            
            if st.button(f"🔄 Изменить статус ({len(selected_ids)})", use_container_width=True, key="bulk_update_all"):
                success_count = 0
                for id in selected_ids:
                    if update_status_with_notification(id, new_status_bulk):
                        success_count += 1
                if success_count > 0:
                    st.success(f"✅ Статус изменен для {success_count} заявок")
                    for i in range(len(edit_df)):
                        st.session_state[checkbox_key_all][i] = False
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Ошибка при обновлении статусов")
        
        if st.session_state.get('show_bulk_delete_confirm_all', False):
            with st.container():
                st.warning(f"⚠️ Удалить {len(st.session_state.bulk_delete_ids_all)} заявок?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Да", use_container_width=True, key="confirm_bulk_all"):
                        success_count = 0
                        for id in st.session_state.bulk_delete_ids_all:
                            success, _ = delete_request(id)
                            if success:
                                success_count += 1
                        if success_count > 0:
                            st.success(f"✅ Удалено заявок: {success_count}")
                            st.session_state.show_bulk_delete_confirm_all = False
                            st.session_state.bulk_delete_ids_all = []
                            for i in range(len(edit_df)):
                                st.session_state[checkbox_key_all][i] = False
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Ошибка при удалении")
                    with col_no:
                        if st.button("❌ Нет", use_container_width=True, key="cancel_bulk_all"):
                            st.session_state.show_bulk_delete_confirm_all = False
                            st.session_state.bulk_delete_ids_all = []
                            st.rerun()

        if st.button(f"🗑️ Удалить ({len(selected_ids)})", use_container_width=True, key="bulk_delete_all", type="primary"):
            st.session_state.show_bulk_delete_confirm_all = True
            st.session_state.bulk_delete_ids_all = selected_ids
        
        excel_data = to_excel(filtered_df)
        st.download_button(
            label="📊 Скачать в Excel формате",
            data=excel_data,
            file_name=f"Все_заявки_{datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="export_all"
        )
    else:
        st.warning("Нет заявок для отображения")
        
if __name__ == "__main__":
    main()
