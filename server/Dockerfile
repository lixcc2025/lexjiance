# CPU 版。构建：docker build -t avserver .   运行见 docker-compose.yml
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 10001 -m avs
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY avserver ./avserver
ENV AVS_MODELS_DIR=/models AVS_TOKENS_FILE=/data/tokens.txt PYTHONUNBUFFERED=1
USER avs
EXPOSE 8000
CMD ["python", "-m", "avserver", "serve", "--host", "0.0.0.0", "--port", "8000"]
