# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y tesseract-ocr poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# Set working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080 for Render's default HTTP traffic
EXPOSE 8080

# Start the app with Gunicorn for handling multiple requests
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--worker-class", "gevent", "app:app"]

