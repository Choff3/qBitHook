FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .

# Create a non-root user
RUN useradd -m -u 1000 qbithook && chown -R qbithook:qbithook /app
USER qbithook

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]