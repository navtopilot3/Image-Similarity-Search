import base64
import io

from PIL import Image
import requests
import streamlit as st

# ==================== КОНФИГУРАЦИЯ FASTAPI ====================
FASTAPI_URL = "http://localhost:8000"

# ==================== НАСТРОЙКА СТРАНИЦЫ ====================
st.set_page_config(
    page_title="Поиск похожих товаров",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== СТИЛИ CSS ====================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5em;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5em;
    }
    .sub-header {
        font-size: 1.2em;
        color: #555;
        margin-bottom: 1em;
    }
    .card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px;
        background-color: #f9f9f9;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        text-align: center;
    }
    .card img {
        max-width: 100%;
        border-radius: 5px;
    }
    .badge {
        display: inline-block;
        background-color: #1f77b4;
        color: white;
        padding: 5px 10px;
        border-radius: 20px;
        font-size: 0.9em;
        margin: 5px;
    }
    .footer {
        text-align: center;
        color: #aaa;
        margin-top: 2em;
    }
</style>
""", unsafe_allow_html=True)

# ==================== САЙДБАР ====================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3081/3081559.png", width=100)
    st.title("О сервисе")
    st.markdown("""
    Этот сервис использует **искусственный интеллект** для поиска визуально похожих товаров в каталоге Shopee.
    """)


# ==================== ОСНОВНОЙ ИНТЕРФЕЙС ====================
st.markdown('<div class="main-header">Поиск похожих товаров</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Загрузите изображение товара, и мы найдём самые похожие позиции в каталоге</div>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 2])
with col1:
    uploaded_file = st.file_uploader(
        "Перетащите изображение сюда или нажмите для выбора",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=False
    )

if uploaded_file is not None:
    # Отображаем загруженное изображение
    query_img = Image.open(uploaded_file)
    with col1:
        st.image(query_img, caption="Загруженный товар", use_container_width=True)
    
    # Кнопка поиска
    if st.button("🔍 Найти похожие", type="primary"):
        with st.spinner("Ищем похожие товары..."):
            # Отправляем запрос в FastAPI
            buf = io.BytesIO()
            query_img.save(buf, format='PNG')
            buf.seek(0)
            files = {'file': ('query.png', buf, 'image/png')}
            params = {'top_k': 6}
            try:
                response = requests.post(f"{FASTAPI_URL}/search", files=files, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                st.error(f"Ошибка соединения с сервером: {e}")
                st.stop()
        
        results = data.get('results', [])

        # Фильтруем по порогу сходства 0.5
        results = [r for r in results if r['similarity'] >= 0.5]
        
        if results:
            with col2:
                st.subheader(f"Найдено {len(results)} товаров")
                num_cols = 3 if len(results) >= 3 else len(results)
                cols = st.columns(num_cols)
                for i, res in enumerate(results):
                    col_idx = i % num_cols
                    with cols[col_idx]:
                        with st.container():
                            try:
                                img_bytes = base64.b64decode(res['image_base64'])
                                result_img = Image.open(io.BytesIO(img_bytes))
                                st.image(result_img, use_container_width=True)
                            except Exception:
                                st.warning("Изображение недоступно")
                            st.markdown("[Перейти к товару](https://example.com)") 
                            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning("Похожие товары не найдены. Попробуйте другое изображение.")
else:
    st.info("Загрузите изображение товара, чтобы начать поиск")

# ==================== ПОДВАЛ ====================
st.markdown("---")
st.markdown('<div class="footer">Сервис поиска похожих товаров © 2026.</div>', unsafe_allow_html=True)