import streamlit as st
from datetime import datetime
from common import save_request


def main():
    st.title("🏠 ЖБУ Общежитие - Подать заявку")
    st.markdown("Заполните форму ниже, чтобы оставить заявку или вопрос для работников ЖБУ.")

    with st.form("student_form"):
        fio = st.text_input("Ваше ФИО *")
        room = st.text_input("Номер комнаты *")

        type_map = {
            "🔧 Сантехника": "santeh",
            "⚡ Электрика": "electric",
            "🧹 Уборка": "cleaning",
            "🪑 Мебель": "furniture",
            "❓ Вопрос / Другое": "other"
        }
        type_display = st.selectbox("Тип заявки *", list(type_map.keys()))

        description = st.text_area("Описание проблемы / Текст вопроса *", height=150)

        submitted = st.form_submit_button("Отправить заявку")

        if submitted:
            if not fio or not room or not description:
                st.error("Пожалуйста, заполните все обязательные поля (*)")
            else:
                now = datetime.now()
                request_data = {
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M:%S"),
                    "fio": fio,
                    "room": room,
                    "type": type_map[type_display],
                    "description": description
                }
                try:
                    save_request(request_data)
                    st.success("✅ Заявка успешно отправлена!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Ошибка: {e}")


if __name__ == "__main__":
    main()