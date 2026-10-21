FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY sitecheck ./sitecheck
ENV SITECHECK_REPORTS=/data/rapporten PYTHONUNBUFFERED=1
RUN mkdir -p /data/rapporten
EXPOSE 10000
# 1 worker met threads: de job-status leeft in het geheugen van dat ene proces
CMD gunicorn -w 1 --threads 8 --timeout 120 -b 0.0.0.0:${PORT:-10000} "sitecheck.web:app"
