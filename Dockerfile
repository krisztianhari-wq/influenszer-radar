FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY influradar ./influradar
COPY data/telepulesek.csv data/import_sablon.csv ./data/
ENV INFLURADAR_DATA=/data
VOLUME ["/data"]
EXPOSE 8790
CMD ["python", "-m", "influradar", "gui", "--host", "0.0.0.0", "--port", "8790"]
