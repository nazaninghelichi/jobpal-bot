# Use a small Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy everything from your project into the image
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run Gunicorn (production server) with your app
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
