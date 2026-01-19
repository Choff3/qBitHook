FROM python:slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY config.json /config/config.json

# Create a non-root user
RUN useradd -m -u 1000 qbithook && chown -R qbithook:qbithook /app
USER qbithook

# Expose port
EXPOSE 5338

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5338", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]