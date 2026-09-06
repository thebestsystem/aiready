FROM python:3.11-slim

WORKDIR /app

# Empecher Python d'ecrire les fichiers .pyc et forcer l'affichage direct des logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Installation des dependances requises
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie de l'ensemble du projet (code backend et frontend statique)
COPY . .

# Port expose (sera surcharge par la variable $PORT de Railway/Render)
EXPOSE 8000

# Commande d'execution en production
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
