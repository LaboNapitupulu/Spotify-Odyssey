# Gunakan base image Python yang ringan
FROM python:3.11-slim

# Atur working directory di dalam container
WORKDIR /app

# Salin requirements dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode aplikasi (termasuk backend, frontend, dll)
COPY . .

# Expose port 7860 (Standar untuk Hugging Face Spaces)
EXPOSE 7860

# Jalankan aplikasi FastAPI dengan Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
