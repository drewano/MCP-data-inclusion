# Étape 1: Base - Image de base avec Node.js Alpine
FROM node:20-alpine AS base
WORKDIR /app

# Étape 2: Dependencies - Installation des dépendances
FROM base AS dependencies
# Copie des fichiers de configuration des paquets
COPY package.json package-lock.json ./
# Installation de toutes les dépendances
RUN npm install

# Étape 3: Builder - Construction de l'application
FROM dependencies AS builder
# Copie de tout le code source
COPY . .
# Construction de l'application Next.js
RUN npm run build

# Étape 4: Runner - Image finale de production
FROM base AS runner

# Création d'un utilisateur non-root pour la sécurité
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 appuser

# Copie des artefacts de build depuis l'étape builder
COPY --from=builder /app/public ./public

# Copie du build standalone
COPY --from=builder --chown=appuser:nodejs /app/.next/standalone ./
COPY --from=builder --chown=appuser:nodejs /app/.next/static ./.next/static

# Changement vers l'utilisateur non-root
USER appuser

# Exposition du port 3000
EXPOSE 3000

# Configuration de la variable d'environnement PORT
ENV PORT=3000

# Commande de démarrage
CMD ["node", "server.js"] 