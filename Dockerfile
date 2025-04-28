# Use a specific, up-to-date Python release on Debian Bookworm for security patches
FROM python:3.12.8-slim-bookworm

# Set working directory
WORKDIR /app

# Install OS-level dependencies and apply security upgrades
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first for better caching
COPY requirements.txt ./

# Install Python dependencies, upgrading pip and setuptools
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools \
    && python3 -m pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose the port for the health check endpoint (optional)
EXPOSE 8080

# Run the Telegram bot entrypoint
CMD ["python3", "main.py"]
