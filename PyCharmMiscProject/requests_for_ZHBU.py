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

# Настройка локали
try:
    if os.name == 'nt':
        locale.setlocale(locale.LC_TIME, 'Russian_Russia.1251')
    else:
        locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except:
    pass

# Настройка страницы
st.set_page_config(
    page_title="Управление электронными заявками | Общежития СПбГЭУ",
    page_icon="📲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Секреты
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

TYPES_TO_SHOW = [
    "🔧 Сантехника",
    "⚡ Электрика",
    "🔨 Плотник",
    "🍵 Плиты",
    "🧹 Уборка",
    "❓ Вопрос / Другое"
]

REQUEST_TYPES = ["Все"] + TYPES_TO_SHOW

WORKER_EMAILS = ["valeraforumsch@gmail.com"]

STATUS_MESSAGES = {
    "Новая": "Ваша заявка принята и ожидает рассмотрения.",
    "В работе": "Специалисты ЖБУ приступили к выполнению вашей заявки.",
    "Выполнена": "✅ Ваша заявка выполнена! Спасибо за обращение."
}

# ==================== РАБОТА С БАЗОЙ ДАННЫХ ====================

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def load_requests():
    supabase = get_supabase()
    response = supabase.table('requests').select('*').order('id', desc=False).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

@st.cache_data(ttl=5)
def load_requests_cached():
    return load_requests()

def load_requests_by_dormitory(dormitory):
    supabase = get_supabase()
    response = supabase.table('requests').select('*').eq('dormitory', dormitory).order('id', desc=False).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

@st.cache_data(ttl=5)
def load_requests_by_dormitory_cached(dormitory):
    return load_requests_by_dormitory(dormitory)

def load_comments(request_id):
    supabase = get_supabase()
    request_id = int(request_id)
    response = supabase.table('comments').select('*').eq('request_id', request_id).order('created_at', desc=False).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def add_comment(request_id, comment_text, author="Заведующий"):
    if not comment_text or not comment_text.strip():
        return False, "Комментарий не может быть пустым"
    
    supabase = get_supabase()
    try:
        data = {
            'request_id': int(request_id),
            'comment': comment_text.strip(),
            'author': author,
            'created_at': datetime.now().isoformat()
        }
        supabase.table('comments').insert(data).execute()
        return True, "Комментарий добавлен"
    except Exception as e:
        return False, f"Ошибка: {str(e)}"

def delete_comment(comment_id):
    supabase = get_supabase()
    try:
        supabase.table('comments').delete().eq('id', int(comment_id)).execute()
        return True, "Комментарий удален"
    except Exception as e:
        return False, f"Ошибка: {str(e)}"

def delete_request(request_id):
    supabase = get_supabase()
    try:
        response = supabase.table('requests').select('*').eq('id', request_id).execute()
        if not response.data:
            return False, "Заявка не найдена"
        
        request_data = response.data[0]
        supabase.table('comments').delete().eq('request_id', request_id).execute()
        supabase.table('requests').delete().eq('id', request_id).execute()
        send_deletion_notification(request_data)
        return True, f"Заявка №{request_id} удалена"
    except Exception as e:
        return False, f"Ошибка: {str(e)}"

def update_status_with_notification(request_id, new_status):
    supabase = get_supabase()
    response = supabase.table('requests').select('*').eq('id', request_id).execute()
    if not response.data:
        return False
    
    request = response.data[0]
    supabase.table('requests').update({'status': new_status}).eq('id', request_id).execute()
    
    student_email = request.get('email')
    if student_email and student_email != 'не указан':
        send_status_notification(student_email, request.get('fio'), request_id, new_status, request.get('description'))
    return True

# ==================== ОТПРАВКА УВЕДОМЛЕНИЙ ====================

def send_email(subject, body, to_email):
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
        print(f"Ошибка отправки: {e}")
        return False

def send_deletion_notification(request_data):
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
"""
    for email in WORKER_EMAILS:
        send_email(subject, body, email)

def send_status_notification(student_email, student_name, request_id, new_status, description):
    message = STATUS_MESSAGES.get(new_status, f"Статус изменен на '{new_status}'")
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
    send_email(subject, body, student_email)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def format_comments(comments_df):
    """Форматирует комментарии для отображения с датой и автором"""
    if comments_df.empty:
        return ""
    
    lines = []
    for _, comment in comments_df.iterrows():
        author = comment.get('author', '')
        text = comment.get('comment', '')
        created_at = comment.get('created_at', '')
        
        # Проверяем, что created_at не None и не пустой
        if created_at and isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_at = dt.strftime('%d.%m.%Y %H:%M')
            except:
                created_at = ''
        elif created_at and isinstance(created_at, datetime):
            created_at = created_at.strftime('%d.%m.%Y %H:%M')
        else:
            created_at = ''
        
        lines.append(f"[{created_at}] {author}: {text}")
    
    return "\n".join(lines)

def get_comments_text_only(comments_df):
    """Возвращает только тексты комментариев для сравнения (без даты и автора)"""
    if comments_df.empty:
        return ""
    
    texts = []
    for _, comment in comments_df.iterrows():
        text = comment.get('comment', '')
        if text:
            texts.append(text.strip())
    
    return "\n".join(texts)

def get_comments_dict(df):
    """Загружает отформатированные комментарии для всех заявок"""
    comments_dict = {}
    for _, row in df.iterrows():
        request_id = row['ID']
        comments_df = load_comments(request_id)
        comments_dict[request_id] = format_comments(comments_df)
    return comments_dict

def rename_columns(df):
    """Переименовывает колонки для отображения"""
    return df.rename(columns={
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

def format_date_for_display(df, date_column="Дата"):
    """Преобразует дату в формат DD.MM.YYYY"""
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column]).dt.strftime("%d.%m.%Y")
    return df

def create_column_config():
    """Создает конфигурацию колонок для data_editor"""
    return {
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
            help="Введите комментарии. Каждый новый комментарий с новой строки.\nФормат: [Дата] Автор: Текст"
        ),
    }

def get_disabled_columns():
    """Возвращает список колонок, которые нельзя редактировать"""
    return ["ID", "Дата", "Время", "ФИО студента", "Email", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус"]

def to_excel(df):
    """Экспорт данных в Excel"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Заявки')
        workbook = writer.book
        worksheet = writer.sheets['Заявки']
        
        from openpyxl.styles import Alignment
        
        for col in worksheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column].width = adjusted_width
        
        for row in worksheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        
        worksheet.freeze_panes = 'A2'
    
    return output.getvalue()

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

def show_statistics():
    st.header("📊 Статистика по общежитиям")
    
    stats_data = []
    for dorm in DORMITORIES:
        df = load_requests_by_dormitory_cached(dorm)
        stats_data.append({
            "Общежитие": dorm.split('|')[0].strip(),
            "Всего": len(df),
            "Новых": len(df[df["status"] == "Новая"]) if not df.empty else 0,
            "В работе": len(df[df["status"] == "В работе"]) if not df.empty else 0,
            "Выполнено": len(df[df["status"] == "Выполнена"]) if not df.empty else 0
        })
    
    stats_df = pd.DataFrame(stats_data)
    st.dataframe(stats_df, use_container_width=True, hide_index=True)

def process_comments_changes(edited_df, edit_df):
    """Обрабатывает изменения в комментариях"""
    comments_updated = False
    
    for i in range(len(edited_df)):
        request_id = int(edit_df.loc[i, "ID"])
        new_comments_text = edited_df.loc[i, "Комментарии"] if i < len(edited_df) else ""
        
        # Получаем текущие комментарии из базы (только текст)
        current_comments_df = load_comments(request_id)
        current_text = get_comments_text_only(current_comments_df)
        
        # Извлекаем только текст из новых комментариев (без даты и автора)
        new_raw_lines = []
        if new_comments_text and new_comments_text.strip():
            for line in new_comments_text.split('\n'):
                line = line.strip()
                if line:
                    # Пытаемся извлечь текст после "]: "
                    if ']: ' in line:
                        parts = line.split(']: ', 1)
                        if len(parts) == 2:
                            new_raw_lines.append(parts[1].strip())
                        else:
                            new_raw_lines.append(line)
                    else:
                        new_raw_lines.append(line)
        
        new_raw = "\n".join(new_raw_lines)
        
        # Сравниваем "сырые" тексты
        if new_raw != current_text:
            supabase = get_supabase()
            
            # Удаляем все старые комментарии
            supabase.table('comments').delete().eq('request_id', request_id).execute()
            
            # Добавляем новые комментарии
            if new_raw:
                for line in new_raw_lines:
                    if line:
                        add_comment(request_id, line, author="Заведующий")
                        comments_updated = True
            else:
                comments_updated = True
    
    return comments_updated

def show_comments_editor(dormitory, category, df):
    """Отображает таблицу с комментариями для конкретной категории"""
    if df.empty:
        st.info("Нет заявок")
        st.markdown("---")
        return
    
    st.caption(f"Количество заявок: {len(df)}")
    
    # Загружаем комментарии из базы
    comments_dict = get_comments_dict(df)
    df_with_comments = df.copy()
    df_with_comments["Комментарии"] = df_with_comments["ID"].map(comments_dict)
    
    # Настройка чекбоксов
    checkbox_key = f"checkboxes_{dormitory}_{category}"
    if checkbox_key not in st.session_state:
        st.session_state[checkbox_key] = {i: False for i in range(len(df_with_comments))}
    
    # Подготовка данных для редактирования
    edit_df = df_with_comments.reset_index(drop=True)
    edit_df.insert(0, "Выбрать", [st.session_state[checkbox_key].get(i, False) for i in range(len(edit_df))])
    
    # Отображение таблицы
    columns = ["Выбрать", "ID", "Дата", "ФИО студента", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус", "Комментарии"]
    edit_df_display = edit_df[[col for col in columns if col in edit_df.columns]]
    
    edited_df = st.data_editor(
        edit_df_display,
        use_container_width=True,
        hide_index=True,
        column_config=create_column_config(),
        disabled=get_disabled_columns(),
        key=f"data_editor_{dormitory}_{category}"
    )
    
    # Обновление чекбоксов
    for i in range(len(edited_df)):
        st.session_state[checkbox_key][i] = edited_df.loc[i, "Выбрать"]
    
    # Обработка изменений комментариев
    comments_updated = process_comments_changes(edited_df, edit_df)
    
    # Обновляем страницу ТОЛЬКО если были изменения
    if comments_updated:
        st.success("✅ Комментарии обновлены")
        time.sleep(0.5)
        st.rerun()
    
    # Управление выбранными заявками
    selected_ids = [edit_df.loc[i, "ID"] for i in range(len(edited_df)) if edited_df.loc[i, "Выбрать"]]
    
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
            st.session_state[f"show_bulk_delete_{dormitory}_{category}"] = True
            st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = selected_ids
    
    with col_right:
        new_status = st.selectbox(
            "Новый статус",
            ["Новая", "В работе", "Выполнена"],
            key=f"bulk_status_{dormitory}_{category}",
            label_visibility="collapsed"
        )
        
        if st.button(f"🔄 Изменить статус ({len(selected_ids)})", use_container_width=True, key=f"bulk_update_{dormitory}_{category}"):
            success_count = sum(1 for id in selected_ids if update_status_with_notification(id, new_status))
            if success_count > 0:
                st.success(f"✅ Статус изменен для {success_count} заявок")
                for i in range(len(edit_df)):
                    st.session_state[checkbox_key][i] = False
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Ошибка при обновлении статусов")
        
        excel_data = to_excel(df)
        st.download_button(
            label="📊 Скачать в Excel",
            data=excel_data,
            file_name=f"{dormitory.split('|')[0].strip()}_{category}_{datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"export_{dormitory}_{category}"
        )
    
    # Диалог подтверждения удаления
    confirm_key = f"show_bulk_delete_{dormitory}_{category}"
    if st.session_state.get(confirm_key, False):
        with st.container():
            st.warning(f"⚠️ Удалить {len(st.session_state[f'bulk_delete_ids_{dormitory}_{category}'])} заявок?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ Да", use_container_width=True, key=f"confirm_bulk_{dormitory}_{category}"):
                    success_count = 0
                    for id in st.session_state[f"bulk_delete_ids_{dormitory}_{category}"]:
                        success, _ = delete_request(id)
                        if success:
                            success_count += 1
                    if success_count > 0:
                        st.success(f"✅ Удалено {success_count} заявок")
                        st.session_state[confirm_key] = False
                        st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = []
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Ошибка при удалении")
            with col_no:
                if st.button("❌ Нет", use_container_width=True, key=f"cancel_bulk_{dormitory}_{category}"):
                    st.session_state[confirm_key] = False
                    st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = []
                    st.rerun()
    
    st.markdown("---")

def show_dormitory_requests_with_control(dormitory):
    df = load_requests_by_dormitory(dormitory)
    
    if df.empty:
        st.info(f"Нет заявок для {dormitory}")
        return
    
    # Фильтры
    st.subheader("🔍 Фильтры")
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Статус", ["Все", "Новая", "В работе", "Выполнена"], key=f"status_{dormitory}")
    with col2:
        date_options = ["Все", "Сегодня", "Вчера", "Выбрать дату", "Выбрать период"]
        date_filter = st.selectbox("Период", date_options, key=f"date_{dormitory}")
    
    # Применяем фильтры
    df = rename_columns(df)
    
    if status_filter != "Все":
        df = df[df["Статус"] == status_filter]
    
    today = datetime.now().date()
    if date_filter == "Сегодня":
        df = df[df["Дата"] == today.strftime("%Y-%m-%d")]
    elif date_filter == "Вчера":
        yesterday = today - timedelta(days=1)
        df = df[df["Дата"] == yesterday.strftime("%Y-%m-%d")]
    elif date_filter == "Выбрать дату":
        selected_date = st.date_input("Выберите дату", value=today, key=f"date_picker_{dormitory}")
        df = df[df["Дата"] == selected_date.strftime("%Y-%m-%d")]
    elif date_filter == "Выбрать период":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Начальная дата", value=today - timedelta(days=7), key=f"start_date_{dormitory}")
        with col2:
            end_date = st.date_input("Конечная дата", value=today, key=f"end_date_{dormitory}")
        df["Дата"] = pd.to_datetime(df["Дата"])
        df = df[(df["Дата"] >= pd.Timestamp(start_date)) & (df["Дата"] <= pd.Timestamp(end_date))]
    
    # Форматируем дату для отображения
    df = format_date_for_display(df)
    
    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего", len(df))
    with col2:
        st.metric("Новых", len(df[df["Статус"] == "Новая"]))
    with col3:
        st.metric("В работе", len(df[df["Статус"] == "В работе"]))
    with col4:
        st.metric("Выполнено", len(df[df["Статус"] == "Выполнена"]))
    
    st.markdown("---")
    
    # Отображение по категориям
    for category in TYPES_TO_SHOW:
        st.subheader(category)
        cat_df = df[df["Тип заявки"] == category]
        show_comments_editor(dormitory, category, cat_df)

def show_all_requests_with_control():
    st.header("📋 Все заявки")
    
    df = load_requests_cached()
    if df.empty:
        st.info("Пока нет ни одной заявки.")
        return
    
    df = rename_columns(df)
    
    # Фильтры
    st.subheader("🔍 Фильтры")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.selectbox("Статус", ["Все", "Новая", "В работе", "Выполнена"], key="status_all")
    with col2:
        dorm_filter = st.selectbox("Общежитие", ["Все"] + [d.split('|')[0].strip() for d in DORMITORIES], key="dorm_all_filter")
    with col3:
        type_filter = st.selectbox("Тип заявки", REQUEST_TYPES, key="type_all_filter")
    with col4:
        date_options = ["Все", "Сегодня", "Вчера", "Выбрать дату", "Выбрать период"]
        date_filter = st.selectbox("Период", date_options, key="date_all_filter")
    
    # Применяем фильтры
    if status_filter != "Все":
        df = df[df["Статус"] == status_filter]
    
    if dorm_filter != "Все":
        df = df[df["Общежитие"].str.contains(dorm_filter)]
    
    if type_filter != "Все":
        df = df[df["Тип заявки"] == type_filter]
    
    today = datetime.now().date()
    if date_filter == "Сегодня":
        df = df[df["Дата"] == today.strftime("%Y-%m-%d")]
    elif date_filter == "Вчера":
        yesterday = today - timedelta(days=1)
        df = df[df["Дата"] == yesterday.strftime("%Y-%m-%d")]
    elif date_filter == "Выбрать дату":
        selected_date = st.date_input("Выберите дату", value=today, key="date_picker_all")
        df = df[df["Дата"] == selected_date.strftime("%Y-%m-%d")]
    elif date_filter == "Выбрать период":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Начальная дата", value=today - timedelta(days=7), key="start_date_all")
        with col2:
            end_date = st.date_input("Конечная дата", value=today, key="end_date_all")
        df["Дата"] = pd.to_datetime(df["Дата"])
        df = df[(df["Дата"] >= pd.Timestamp(start_date)) & (df["Дата"] <= pd.Timestamp(end_date))]
    
    # Форматируем дату
    df = format_date_for_display(df)
    
    # Загружаем комментарии
    comments_dict = get_comments_dict(df)
    df["Комментарии"] = df["ID"].map(comments_dict)
    
    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего", len(df))
    with col2:
        st.metric("Новых", len(df[df["Статус"] == "Новая"]))
    with col3:
        st.metric("В работе", len(df[df["Статус"] == "В работе"]))
    with col4:
        st.metric("Выполнено", len(df[df["Статус"] == "Выполнена"]))
    
    st.markdown("---")
    
    if df.empty:
        st.warning("Нет заявок для отображения")
        return
    
    # Настройка чекбоксов
    checkbox_key = "checkbox_all_state"
    if checkbox_key not in st.session_state:
        st.session_state[checkbox_key] = {i: False for i in range(len(df))}
    
    # Подготовка данных
    edit_df = df.reset_index(drop=True)
    edit_df.insert(0, "Выбрать", [st.session_state[checkbox_key].get(i, False) for i in range(len(edit_df))])
    
    columns = ["Выбрать", "ID", "Дата", "Время", "ФИО студента", "Email", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус", "Комментарии"]
    edit_df_display = edit_df[[col for col in columns if col in edit_df.columns]]
    
    # Отображение таблицы
    edited_df = st.data_editor(
        edit_df_display,
        use_container_width=True,
        hide_index=True,
        column_config=create_column_config(),
        disabled=get_disabled_columns(),
        key="data_editor_all"
    )
    
    # Обновление чекбоксов
    for i in range(len(edited_df)):
        st.session_state[checkbox_key][i] = edited_df.loc[i, "Выбрать"]
    
    # Обработка изменений комментариев
    comments_updated = process_comments_changes(edited_df, edit_df)
    
    # Обновляем страницу ТОЛЬКО если были изменения
    if comments_updated:
        st.success("✅ Комментарии обновлены")
        time.sleep(0.5)
        st.rerun()
    
    # Управление выбранными заявками
    selected_ids = [edit_df.loc[i, "ID"] for i in range(len(edited_df)) if edited_df.loc[i, "Выбрать"]]
    
    if selected_ids:
        st.success(f"✅ Выбрано заявок: {len(selected_ids)}")
    else:
        st.info("ℹ️ Отметьте заявки в колонке 'Выбрать' для редактирования")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Выбрать все", use_container_width=True, key="select_all_all"):
            for i in range(len(edit_df)):
                st.session_state[checkbox_key][i] = True
            st.rerun()
        
        if st.button("❌ Снять все", use_container_width=True, key="deselect_all_all"):
            for i in range(len(edit_df)):
                st.session_state[checkbox_key][i] = False
            st.rerun()
    
    with col2:
        new_status = st.selectbox(
            "Новый статус",
            ["Новая", "В работе", "Выполнена"],
            key="bulk_status_all",
            label_visibility="collapsed"
        )
        
        if st.button(f"🔄 Изменить статус ({len(selected_ids)})", use_container_width=True, key="bulk_update_all"):
            success_count = sum(1 for id in selected_ids if update_status_with_notification(id, new_status))
            if success_count > 0:
                st.success(f"✅ Статус изменен для {success_count} заявок")
                for i in range(len(edit_df)):
                    st.session_state[checkbox_key][i] = False
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Ошибка при обновлении статусов")
    
    # Удаление
    if st.button(f"🗑️ Удалить ({len(selected_ids)})", use_container_width=True, key="bulk_delete_all", type="primary"):
        st.session_state.show_bulk_delete_confirm_all = True
        st.session_state.bulk_delete_ids_all = selected_ids
    
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
                        st.success(f"✅ Удалено {success_count} заявок")
                        st.session_state.show_bulk_delete_confirm_all = False
                        st.session_state.bulk_delete_ids_all = []
                        for i in range(len(edit_df)):
                            st.session_state[checkbox_key][i] = False
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Ошибка при удалении")
            with col_no:
                if st.button("❌ Нет", use_container_width=True, key="cancel_bulk_all"):
                    st.session_state.show_bulk_delete_confirm_all = False
                    st.session_state.bulk_delete_ids_all = []
                    st.rerun()
    
    # Экспорт в Excel
    excel_data = to_excel(df)
    st.download_button(
        label="📊 Скачать в Excel",
        data=excel_data,
        file_name=f"Все_заявки_{datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="export_all"
    )

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def main():
    # Инициализация session_state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "selected_dormitory" not in st.session_state:
        st.session_state.selected_dormitory = "Все"
    if "show_stats" not in st.session_state:
        st.session_state.show_stats = False
    if "show_all_requests" not in st.session_state:
        st.session_state.show_all_requests = False
    if "show_bulk_delete_confirm_all" not in st.session_state:
        st.session_state.show_bulk_delete_confirm_all = False    if "bulk_delete_ids_all" not in st.session_state:
        st.session_state.bulk_delete_ids_all = []
    
    st.title("🔐 Панель сотрудника ЖБУ | Управление электронными заявками")
    
    # Аутентификация
    if not st.session_state.authenticated:
        with st.form("login_form"):
            password_input = st.text_input("Введите пароль для доступа", type="password")
            if st.form_submit_button("Войти") and password_input == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            elif st.form_submit_button("Войти"):
                st.error("❌ Неверный пароль!")
        return
    
    # Кнопка выхода
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🚪 Выйти", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
    
    # Навигация
    cols = st.columns(4)
    for i, full in enumerate(DORMITORIES):
        with cols[i]:
            if st.button(f"🏢 {full}", use_container_width=True, key=f"dorm_{i+2}"):
                st.session_state.selected_dormitory = full
                st.session_state.show_stats = False
                st.session_state.show_all_requests = False
                st.rerun()
    
    if st.button("📋 Все заявки", use_container_width=True, key="dorm_all"):
        st.session_state.show_all_requests = not st.session_state.show_all_requests
        st.session_state.show_stats = False
        st.rerun()
    
    if st.button("📊 Статистика", use_container_width=True, key="show_stats_btn"):
        st.session_state.show_stats = not st.session_state.show_stats
        st.session_state.show_all_requests = False
        st.rerun()
    
    st.divider()
    
    # Отображение контента
    if st.session_state.show_stats:
        show_statistics()
        st.divider()
    elif st.session_state.show_all_requests:
        show_all_requests_with_control()
    else:
        st.header("📋 Электронные заявки студентов")
        
        if st.session_state.selected_dormitory == "Все":
            st.info("🏠 Выберите общежитие для просмотра заявок или нажмите 'Все заявки'")
            
            st.subheader("📊 Краткая статистика")
            stats_data = []
            for dorm in DORMITORIES:
                df = load_requests_by_dormitory(dorm)
                stats_data.append({
                    "Общежитие": dorm.split('|')[0].strip(),
                    "Всего": len(df),
                    "Новых": len(df[df["status"] == "Новая"]) if not df.empty else 0,
                    "В работе": len(df[df["status"] == "В работе"]) if not df.empty else 0,
                    "Выполнено": len(df[df["status"] == "Выполнена"]) if not df.empty else 0
                })
            
            stats_df = pd.DataFrame(stats_data)
            st.dataframe(stats_df, use_container_width=True, hide_index=True)
        else:
            st.subheader(st.session_state.selected_dormitory)
            show_dormitory_requests_with_control(st.session_state.selected_dormitory)

if __name__ == "__main__":
    main()
