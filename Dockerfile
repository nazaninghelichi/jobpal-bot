# Use a small Python image
FROM python:3.12.2-slim

# Set working directory
WORKDIR /app

# Copy everything from your project into the image
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run your bot
CMD ["python", "main.py"]
