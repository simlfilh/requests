import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

st.set_page_config(
    page_title="Управление электронными заявками | Общежития СПбГЭУ",
    page_icon="📲",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    try:
        supabase = get_supabase()
        response = supabase.table('requests').select('*').eq('id', request_id).execute()
        if response.data:
            request_data = response.data[0]
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
    return output.getvalue()

def show_statistics():
    """Функция для отображения статистики"""
    st.header("📊 Статистика по общежитиям")
    
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

def show_dormitory_requests_with_control(dormitory):
    """Отображение заявок конкретного общежития с разделением по типам работ"""
    df = load_requests_by_dormitory(dormitory)
    
    if df.empty:
        st.info(f"Нет заявок для {dormitory}")
        return
    
    # ---------- Общие фильтры ----------
    st.subheader("🔍 Фильтры")
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Статус", ["Все", "Новая", "В работе", "Выполнена"], key=f"status_{dormitory}")
    with col2:
        date_options = ["Все", "Сегодня", "Вчера", "Выбрать дату", "Выбрать период"]
        date_filter = st.selectbox("Период", date_options, key=f"date_{dormitory}")
    
    # Применяем фильтры к общему DataFrame
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
        filtered_df["date"] = filtered_df["date"].dt.strftime("%Y-%m-%d")
    
    # Переименовываем для отображения
    display_df = filtered_df.rename(columns={
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
    
    # ---------- Метрики ----------
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
    
    # ---------- ТОЧНЫЕ названия из базы данных (со смайликами) ----------
    types_to_show = [
        "🔧 Сантехника",
        "⚡ Электрика",
        "🔨 Плотник",
        "🍵 Плиты",
        "🧹 Уборка",
        "❓ Вопрос / Другое"
    ]
    
    # Для каждого типа создаём отдельную таблицу
    for category in types_to_show:
        st.subheader(category)
        
        # Фильтруем данные по типу (точное совпадение с иконкой)
        cat_df = display_df[display_df["Тип заявки"] == category]
        
        if cat_df.empty:
            st.info(f"📭 Нет заявок типа «{category}»")
            st.markdown("---")
            continue
        
        # Показываем количество заявок данного типа
        st.caption(f"Всего: {len(cat_df)} заявок")
        
        # ---------- РАБОТА С ЧЕКБОКСАМИ ЧЕРЕЗ SESSION_STATE ----------
        # Создаем ключ для хранения состояния чекбоксов
        checkbox_key = f"checkboxes_{dormitory}_{category}"
        
        # Инициализируем состояние чекбоксов, если его нет
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = {i: False for i in range(len(cat_df))}
        
        # Создаем копию DataFrame для отображения с чекбоксами
        display_cat_df = cat_df.copy()
        display_cat_df = display_cat_df.reset_index(drop=True)  # Сбрасываем индексы
        
        # Добавляем колонку с чекбоксами
        checkbox_values = []
        for i in range(len(display_cat_df)):
            checkbox_values.append(st.session_state[checkbox_key].get(i, False))
        
        display_cat_df.insert(0, "Выбрать", checkbox_values)
        
        # Выбираем только нужные колонки для отображения
        columns_to_show = ["Выбрать", "Дата", "ФИО студента", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус"]
        display_columns = [col for col in columns_to_show if col in display_cat_df.columns]
        edit_df_display = display_cat_df[display_columns]
        
        # Уникальный ключ для data_editor
        editor_key = f"data_editor_{dormitory}_{category}"
        
        # Отображаем редактируемую таблицу
        edited_df = st.data_editor(
            edit_df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Выбрать": st.column_config.CheckboxColumn(
                    "Выбрать",
                    help="Отметьте заявки для массового управления",
                    default=False,
                ),
                "Статус": st.column_config.TextColumn(
                    "Статус",
                    width="small",
                ),
                "Дата": st.column_config.TextColumn(
                    "Дата",
                    width="small",
                ),
                "Комната": st.column_config.TextColumn(
                    "Комната",
                    width="small",
                ),
                "Тип заявки": st.column_config.TextColumn(
                    "Тип заявки",
                    width="medium",
                ),
            },
            disabled=["Дата", "ФИО студента", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус"],
            key=editor_key
        )
        
        # Обновляем состояние чекбоксов из отредактированной таблицы
        for i in range(len(edited_df)):
            st.session_state[checkbox_key][i] = edited_df.loc[i, "Выбрать"]
        
        # Получаем выбранные ID
        selected_ids = []
        for i in range(len(edited_df)):
            if edited_df.loc[i, "Выбрать"]:
                selected_ids.append(display_cat_df.loc[i, "ID"])
        
        # Кнопки управления
        col_buttons = st.columns(3)
        
        with col_buttons[0]:
            if st.button("✅ Выбрать все", use_container_width=True, key=f"select_all_{dormitory}_{category}"):
                # Устанавливаем все чекбоксы в True
                for i in range(len(display_cat_df)):
                    st.session_state[checkbox_key][i] = True
                st.rerun()
            
            if st.button("❌ Снять все", use_container_width=True, key=f"deselect_all_{dormitory}_{category}"):
                # Устанавливаем все чекбоксы в False
                for i in range(len(display_cat_df)):
                    st.session_state[checkbox_key][i] = False
                st.rerun()
        
        if selected_ids:
            st.success(f"✅ Выбрано заявок: {len(selected_ids)}")
            
            with col_buttons[1]:
                new_status_bulk = st.selectbox(
                    "Новый статус", 
                    ["Новая", "В работе", "Выполнена"], 
                    key=f"bulk_status_{dormitory}_{category}"
                )
                if st.button(f"🔄 Изменить статус ({len(selected_ids)})", use_container_width=True, key=f"bulk_update_{dormitory}_{category}"):
                    success_count = 0
                    for id in selected_ids:
                        if update_status_with_notification(id, new_status_bulk):
                            success_count += 1
                    if success_count > 0:
                        st.success(f"✅ Статус изменен для {success_count} заявок")
                        # Сбрасываем чекбоксы после успешного обновления
                        for i in range(len(display_cat_df)):
                            st.session_state[checkbox_key][i] = False
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Ошибка при обновлении статусов")
            
            with col_buttons[2]:
                if st.button(f"🗑️ Удалить ({len(selected_ids)})", use_container_width=True, key=f"bulk_delete_{dormitory}_{category}", type="primary"):
                    st.session_state[f"show_bulk_delete_confirm_{dormitory}_{category}"] = True
                    st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = selected_ids
            
            # Диалог подтверждения массового удаления
            confirm_key = f"show_bulk_delete_confirm_{dormitory}_{category}"
            if st.session_state.get(confirm_key, False):
                with st.container():
                    st.warning(f"⚠️ Удалить {len(st.session_state[f'bulk_delete_ids_{dormitory}_{category}'])} заявок?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Да", key=f"confirm_bulk_{dormitory}_{category}"):
                            success_count = 0
                            for id in st.session_state[f"bulk_delete_ids_{dormitory}_{category}"]:
                                success, _ = delete_request(id)
                                if success:
                                    success_count += 1
                            if success_count > 0:
                                st.success(f"✅ Удалено {success_count} заявок")
                                # Сбрасываем чекбоксы после успешного удаления
                                for i in range(len(display_cat_df)):
                                    st.session_state[checkbox_key][i] = False
                                st.session_state[confirm_key] = False
                                st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = []
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Ошибка при удалении")
                    with col_no:
                        if st.button("❌ Нет", key=f"cancel_bulk_{dormitory}_{category}"):
                            st.session_state[confirm_key] = False
                            st.session_state[f"bulk_delete_ids_{dormitory}_{category}"] = []
                            st.rerun()
        else:
            st.info("ℹ️ Отметьте заявки в колонке 'Выбрать' для массового управления")
        
        # Экспорт для данного типа
        excel_data = to_excel(cat_df)
        st.download_button(
            label=f"📊 Скачать {category} в Excel",
            data=excel_data,
            file_name=f"{dormitory.split('|')[0].strip()}_{category}_{datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"export_{dormitory}_{category}"
        )
        
        st.markdown("---")  # Разделитель между типами
        
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
        st.session_state.show_bulk_delete_confirm_all = False
    if "bulk_delete_ids_all" not in st.session_state:
        st.session_state.bulk_delete_ids_all = []

    # Шапка и аутентификация
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title("🔐 Панель сотрудника ЖБУ | Управление электронными заявками")
    
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
    with col2:
        if st.button("🚪 Выйти"):
            st.session_state.authenticated = False
            st.rerun()

    # Кнопки навигации
    cols = st.columns(4)
    dormitories_short = ["№2", "№3", "№4", "№7"]
    dormitories_full = [
        "Общежитие №2 | Чкаловский пр-т, д. 27",
        "Общежитие №3 | пр-т Косыгина, д. 19, к. 2",
        "Общежитие №4 | ул. Воронежская, д. 69",
        "Общежитие №7 | ул. Воронежская, д. 38"
    ]
        
    for i, (short, full) in enumerate(zip(dormitories_short, dormitories_full)):
        with cols[i]:
            if st.button(f"🏢 {full}", use_container_width=True, key=f"dorm_{i+2}"):
                st.session_state.selected_dormitory = full
                st.session_state.show_stats = False
                st.session_state.show_all_requests = False
                st.rerun()

    # Кнопка "Все заявки"
    col_full = st.columns(1)[0]
    with col_full:
        if st.button("📋 Все заявки", use_container_width=True, key="dorm_all"):
            st.session_state.show_all_requests = not st.session_state.show_all_requests
            st.session_state.show_stats = False
            st.rerun()

    # Кнопка "Статистика"
    col_full2 = st.columns(1)[0]
    with col_full2:
        if st.button("📊 Статистика", use_container_width=True, key="show_stats_btn"):
            st.session_state.show_stats = not st.session_state.show_stats
            st.session_state.show_all_requests = False
            st.rerun()
                    
    st.divider()
    
    # Отображение статистики
    if st.session_state.show_stats:
        show_statistics()
        st.divider()
    
    # Отображение всех заявок
    elif st.session_state.show_all_requests:
        show_all_requests_with_control()
        st.divider()
    
    # Основная таблица с заявками (по умолчанию)
    else:
        st.header("📋 Электронные заявки студентов")
        
        if st.session_state.selected_dormitory == "Все":
            st.info("🏠 Выберите общежитие для просмотра заявок или нажмите 'Все заявки'")
            
            # Показываем статистику по всем общежитиям
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
            # Для конкретного общежития показываем заявки с управлением
            st.subheader(st.session_state.selected_dormitory)
            show_dormitory_requests_with_control(st.session_state.selected_dormitory)

if __name__ == "__main__":
    main()
