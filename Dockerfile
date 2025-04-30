# Use a specific, up-to-date Python release on Debian Bookworm for security patches
FROM python:3.12.8-slim-bookworm

# Set working directory
WORKDIR /app

# Install minimal system dependencies and apply security upgrades
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for layer caching
COPY requirements.txt ./

# Upgrade pip and install Python dependencies
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools \
    && python3 -m pip install --no-cache-dir -r requirements.txt

# Copy application code into the image
COPY . .

# Ensure logs are not buffered
ENV PYTHONUNBUFFERED=1

# Expose port for optional health checks (not used by Telegram but good practice)
EXPOSE 8080

# Start the bot
CMD ["python3", "main.py"]
