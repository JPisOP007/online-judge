FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    g++ \                # C++
    openjdk-17-jdk \     # Java (use openjdk-17-jdk or version you need)
    nodejs \             # JavaScript runtime
    npm                  # Node.js package manager (needed for some JS execution)


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system packages
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files

EXPOSE 8000

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]
