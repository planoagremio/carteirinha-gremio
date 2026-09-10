FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema para psycopg2 e bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia backend
COPY backend/ ./backend/

# Copia frontend (servido pelo FastAPI)
COPY index.html login-socio.html scanner.html socio.html ./
COPY assets/ ./assets/

WORKDIR /app/backend

EXPOSE 8000

CMD ["bash", "start.sh"]
