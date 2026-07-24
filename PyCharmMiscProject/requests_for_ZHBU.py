def show_dormitory_requests_with_control(dormitory):
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
        
        # Фильтруем данные по типу
        cat_df = display_df[display_df["Тип заявки"] == category]
        
        if cat_df.empty:
            st.info(f"Нет заявок")
            st.markdown("---")
            continue
        
        st.caption(f"Количество заявок: {len(cat_df)}")
        
        # ---------- ЗАГРУЖАЕМ КОММЕНТАРИИ ----------
        comments_dict = {}
        for _, row in cat_df.iterrows():
            request_id = row['ID']
            comments_df = load_comments(request_id)
            if not comments_df.empty:
                comments_list = []
                for _, comment in comments_df.iterrows():
                    text = comment.get('comment', '')
                    comments_list.append(text)
                # Объединяем все комментарии в один текст с переносами строк
                comments_dict[request_id] = "\n".join(comments_list)
            else:
                comments_dict[request_id] = ""
        
        cat_df_with_comments = cat_df.copy()
        cat_df_with_comments["Комментарии"] = cat_df_with_comments["ID"].map(comments_dict)
        
        # ---------- РАБОТА С ЧЕКБОКСАМИ ----------
        checkbox_key = f"checkboxes_{dormitory}_{category}"
        
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = {i: False for i in range(len(cat_df_with_comments))}
        
        # Создаем копию для редактирования
        edit_df = cat_df_with_comments.copy()
        edit_df = edit_df.reset_index(drop=True)
        
        # Добавляем колонку с чекбоксами
        checkbox_values = []
        for i in range(len(edit_df)):
            checkbox_values.append(st.session_state[checkbox_key].get(i, False))
        
        edit_df.insert(0, "Выбрать", checkbox_values)
        
        # Выбираем только нужные колонки для отображения
        columns_to_show = ["Выбрать", "ID", "Дата", "ФИО студента", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус", "Комментарии"]
        display_columns = [col for col in columns_to_show if col in edit_df.columns]
        edit_df_display = edit_df[display_columns]
        
        # Уникальный ключ для data_editor
        editor_key = f"data_editor_{dormitory}_{category}"
        
        # Настройка колонок для data_editor
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
        
        # Отображаем редактируемую таблицу
        edited_df = st.data_editor(
            edit_df_display,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            disabled=["ID", "Дата", "Время", "ФИО студента", "Общежитие", "Комната", "Тип заявки", "Описание", "Статус"],
            key=editor_key
        )
        
        # Обновляем состояние чекбоксов из отредактированной таблицы
        for i in range(len(edited_df)):
            st.session_state[checkbox_key][i] = edited_df.loc[i, "Выбрать"]
        
        # ---------- НОВАЯ ЛОГИКА ОБРАБОТКИ КОММЕНТАРИЕВ ----------
        comments_changed = False
        for i in range(len(edited_df)):
            request_id = int(edit_df.loc[i, "ID"])
            old_comments = edit_df.loc[i, "Комментарии"] if i < len(edit_df) else ""
            new_comments = edited_df.loc[i, "Комментарии"] if i < len(edited_df) else ""
            
            # Если комментарии изменились
            if new_comments != old_comments:
                # Удаляем все старые комментарии для этой заявки
                supabase = get_supabase()
                supabase.table('comments').delete().eq('request_id', request_id).execute()
                
                # Если есть новые комментарии, добавляем их
                if new_comments and new_comments.strip():
                    # Разбиваем на строки и фильтруем пустые
                    lines = [line.strip() for line in new_comments.split('\n') if line.strip()]
                    
                    # Добавляем каждый комментарий
                    for line in lines:
                        success, msg = add_comment(request_id, line, author="Заведующий")
                        if success:
                            comments_changed = True
                else:
                    comments_changed = True
        
        # Если были изменения, обновляем страницу
        if comments_changed:
            st.success("✅ Комментарии обновлены")
            time.sleep(0.5)
            st.rerun()
        
        # Получаем выбранные ID
        selected_ids = []
        for i in range(len(edited_df)):
            if edited_df.loc[i, "Выбрать"]:
                selected_ids.append(edit_df.loc[i, "ID"])
        
        # ---------- УПРАВЛЕНИЕ: ДВА СТОЛБЦА ----------
        col_left, col_right = st.columns(2)
        
        # ЛЕВЫЙ СТОЛБЕЦ: Выбрать все, Снять все, Удалить
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
        
        # Диалог подтверждения массового удаления
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
