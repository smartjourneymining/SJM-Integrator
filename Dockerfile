FROM python:3.11-slim

# System deps for psycopg2-binary are bundled in the wheel; pm4py/graphviz removed.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "app.py"]
