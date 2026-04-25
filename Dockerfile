FROM python:3.12-slim

WORKDIR /app

# System deps (optional but safe)
RUN apt-get update && apt-get install -y gcc

# Copy project
COPY . .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Run app (Render compatible)
CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:$PORT"]