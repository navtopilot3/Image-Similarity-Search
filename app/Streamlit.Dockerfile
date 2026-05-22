FROM python:3.10-slim
WORKDIR /app

# Копируем легкие зависимости фронтенда
COPY requirements_fe.txt .
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements_fe.txt

COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]