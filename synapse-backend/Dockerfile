# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies
# tesseract-ocr: for OCR functionality
# libgl1-mesa-glx: often needed for modern CV/Imaging libraries
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure necessary directories exist
RUN mkdir -p instance uploads

# Set environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Expose the port
EXPOSE 5000

# Command to run the application using Gunicorn
# Using a longer timeout because AI/OCR processing can be slow
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "run:app"]
