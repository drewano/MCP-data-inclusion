# Étape 1: Choisir une image de base
# On utilise une image Python 3.12 "slim" pour qu'elle soit légère mais complète.
FROM python:3.12-slim

# Étape 2: Définir les arguments de build
# Permet de configurer le port au moment du build si nécessaire.
ARG PORT=8000

# Étape 3: Définir le répertoire de travail dans le conteneur
# C'est ici que les fichiers de notre application seront copiés.
WORKDIR /app

# Étape 4: Installer les dépendances système comme curl pour le healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Étape 5: Installer un gestionnaire de paquets plus rapide (optionnel mais recommandé)
# uv est une alternative très rapide à pip.
RUN pip install uv

# Étape 6: Copier les fichiers du projet
# On copie d'abord le fichier des dépendances pour profiter du cache de Docker.
COPY pyproject.toml ./

# Étape 7: Installer les dépendances
# uv va lire pyproject.toml et installer les paquets listés.
# L'option --system installe les paquets globalement dans l'environnement Python du conteneur.
RUN uv pip install --system -r pyproject.toml

# Étape 8: Copier le reste du code de l'application
COPY src/ ./src/
COPY main.py ./

# Étape 9: Exposer le port sur lequel l'application va écouter
# Le conteneur rendra ce port disponible pour être mappé sur l'hôte.
EXPOSE ${PORT}

# Étape 10: Définir les variables d'environnement par défaut
# MCP_HOST est mis à 0.0.0.0 pour être accessible depuis l'extérieur du conteneur.
# Les autres valeurs sont reprises de votre env.example.
# La clé API (DATA_INCLUSION_API_KEY) sera fournie au lancement, pas ici.
ENV TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=${PORT}
ENV MCP_API_PATH=/mcp
ENV OPENAPI_URL=https://api.data.inclusion.beta.gouv.fr/api/openapi.json
ENV MCP_SERVER_NAME=DataInclusionAPI

# Étape 11: Définir la commande pour lancer le serveur
# C'est la commande qui sera exécutée au démarrage du conteneur.
# Cette commande sera surchargée par docker-compose.yml pour chaque service
CMD ["python", "main.py"]