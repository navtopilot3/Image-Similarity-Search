FROM python:3.10-slim

WORKDIR /app

# Устанавливаем актуальные библиотеки для работы FAISS, OpenCV и графики в новых Debian
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Копируем исходный код проекта
COPY . .

# Открываем порт для FastAPI
EXPOSE 8000

# Запуск бэкенда
CMD ["uvicorn", "app_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]