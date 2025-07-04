# 🐳 Guide Docker - Interface Gradio DataInclusion

Ce guide explique comment lancer l'application complète avec l'interface Gradio en utilisant Docker.

## 📋 Architecture des Services

L'application est composée de **3 services** orchestrés par Docker Compose :

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│  Gradio UI      │◄───┤  Agent Server   │◄───┤  MCP Server     │
│  Port: 7860     │    │  Port: 8001     │    │  Port: 8000     │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
       🎨                      🤖                      📡
   Interface Web         Agent IA              Serveur MCP
```

### 🎨 **Gradio Interface** (`gradio_interface`)

- **Rôle**: Interface utilisateur web moderne et interactive
- **Port**: 7860
- **URL**: <http://localhost:7860>
- **Fonctionnalités**:
  - Chat en temps réel avec l'agent IA
  - Affichage visuel des appels aux outils MCP
  - Interface responsive et moderne
  - Exemples de questions prédéfinies

### 🤖 **Agent Server** (`agent_server`)

- **Rôle**: Agent IA spécialisé dans l'inclusion sociale
- **Port**: 8001
- **Protocole**: FastA2A (Agent-to-Agent)
- **Fonctionnalités**:
  - Traitement intelligent des questions
  - Utilisation des outils MCP pour rechercher des données
  - Persistance des conversations en mémoire

### 📡 **MCP Server** (`mcp_server`)

- **Rôle**: Passerelle vers l'API DataInclusion
- **Port**: 8000
- **Protocole**: Model Context Protocol (MCP)
- **Fonctionnalités**:
  - Conversion de l'API REST en outils MCP
  - Authentication avec l'API DataInclusion
  - Gestion des erreurs et retry automatique

## 🚀 Démarrage Rapide

### 1. **Configuration initiale**

```bash
# Cloner le projet
git clone <url-du-repo>
cd MCP-data-inclusion

# Copier et configurer l'environnement
cp .env.example .env
```

### 2. **Configurer les clés API dans `.env`**

```bash
# Éditer le fichier .env
nano .env

# Ajouter vos clés API
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DATA_INCLUSION_API_KEY=votre-cle-data-inclusion
```

### 3. **Lancement automatique**

```bash
# Utiliser le script de lancement automatique
./start.sh
```

Le script va :

- ✅ Vérifier les prérequis (Docker, docker-compose)
- ✅ Valider la configuration (.env)
- ✅ Construire les images Docker
- ✅ Lancer tous les services
- ✅ Attendre que tous soient opérationnels
- ✅ Afficher les URLs d'accès

### 4. **Accès à l'interface**

Une fois le démarrage terminé, ouvrez votre navigateur :

**🎨 Interface Gradio**: <http://localhost:7860>

## 📋 Commandes Utiles

### **Démarrage et arrêt**

```bash
# Démarrage simple
docker-compose up -d

# Démarrage avec reconstruction
docker-compose up -d --build

# Arrêt
docker-compose down

# Arrêt avec suppression des volumes
docker-compose down -v
```

### **Monitoring et debugging**

```bash
# Voir l'état des services
docker-compose ps

# Logs en temps réel (tous services)
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f gradio_interface
docker-compose logs -f agent_server
docker-compose logs -f mcp_server

# Redémarrer un service spécifique
docker-compose restart gradio_interface
```

### **Développement**

```bash
# Reconstruire une image spécifique
docker-compose build gradio_interface

# Entrer dans un conteneur
docker-compose exec gradio_interface bash
docker-compose exec agent_server bash

# Voir les ressources utilisées
docker stats

# Nettoyer complètement
./start.sh --clean
```

## 🔧 Configuration Avancée

### **Variables d'environnement importantes**

```bash
# Dans .env
OPENAI_API_KEY=sk-xxxxx              # Clé OpenAI (obligatoire)
DATA_INCLUSION_API_KEY=xxxxx         # Clé DataInclusion (obligatoire)
AGENT_MODEL_NAME=gpt-4.1             # Modèle OpenAI à utiliser
MCP_SERVER_URL=http://mcp_server:8000/mcp  # URL interne du serveur MCP
```

### **Personnalisation des ports**

Pour changer les ports par défaut, modifiez `docker-compose.yml` :

```yaml
services:
  gradio_interface:
    ports:
      - "8080:7860"  # Interface sur le port 8080 au lieu de 7860
```

### **Développement avec volumes**

Les volumes sont déjà configurés pour le développement :

```yaml
volumes:
  - ./src:/app/src              # Code synchronisé en temps réel
  - ./gradio_app.py:/app/gradio_app.py  # Script Gradio synchronisé
```

Vos modifications seront automatiquement prises en compte.

## 🚨 Résolution des Problèmes

### **Problème : Service ne démarre pas**

```bash
# Vérifier les logs
docker-compose logs nom_du_service

# Vérifier l'état
docker-compose ps

# Redémarrer
docker-compose restart nom_du_service
```

### **Problème : Port déjà utilisé**

```bash
# Vérifier les ports utilisés
netstat -tulpn | grep :7860

# Ou sous Windows
netstat -an | findstr :7860

# Arrêter le processus ou changer le port dans docker-compose.yml
```

### **Problème : Connexion entre services**

```bash
# Tester la connectivité réseau
docker-compose exec gradio_interface curl http://agent_server:8001/.well-known/agent.json
docker-compose exec agent_server curl http://mcp_server:8000/health
```

### **Problème : Clé API manquante**

```bash
# Vérifier le fichier .env
cat .env | grep -E "(OPENAI|DATA_INCLUSION)"

# Le script start.sh vérifie automatiquement les clés
./start.sh
```

### **Problème : Mémoire insuffisante**

```bash
# Vérifier l'utilisation des ressources
docker stats

# Libérer de l'espace
docker system prune -f
docker volume prune -f
```

## 📊 Surveillance et Performance

### **Health Checks**

Tous les services ont des health checks configurés :

```bash
# Vérifier l'état de santé
docker-compose ps

# Les services montrent "healthy" quand tout va bien
```

### **Métriques de performance**

```bash
# Ressources utilisées par service
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# Logs de performance (si configurés)
docker-compose logs -f | grep -E "(timing|performance|latency)"
```

## 🔄 Mise à Jour

### **Mettre à jour le code**

```bash
# Récupérer les dernières modifications
git pull

# Reconstruire et redémarrer
docker-compose up -d --build
```

### **Mettre à jour les dépendances**

```bash
# Reconstruire l'image avec --no-cache
docker-compose build --no-cache

# Redémarrer les services
docker-compose up -d
```

## 📝 Développement de l'Interface

### **Modifier l'interface Gradio**

1. Éditez `src/gradio_interface.py` ou `gradio_app.py`
2. Les modifications sont automatiquement synchronisées
3. Redémarrez le service si nécessaire :

```bash
docker-compose restart gradio_interface
```

### **Ajouter de nouvelles fonctionnalités**

1. Modifiez le code dans `src/`
2. Les volumes synchronisent automatiquement
3. Pour les nouvelles dépendances, mettez à jour `pyproject.toml` et reconstruisez :

```bash
docker-compose build gradio_interface
docker-compose up -d gradio_interface
```

## 🎯 URLs d'Accès Rapide

- **🎨 Interface Gradio**: <http://localhost:7860>
- **🤖 Agent API**: <http://localhost:8001>
- **📡 MCP Server**: <http://localhost:8000>

## 💡 Conseils d'Utilisation

1. **Première utilisation** : Utilisez `./start.sh` pour un démarrage guidé
2. **Développement** : Les volumes permettent de modifier le code en temps réel
3. **Production** : Configurez des secrets Docker pour les clés API
4. **Monitoring** : Utilisez `docker-compose logs -f` pour surveiller les services
5. **Performance** : L'architecture en mémoire optimise les performances

---

✨ **L'interface Gradio est maintenant prête !** Visitez <http://localhost:7860> pour commencer à interagir avec l'agent IA d'inclusion sociale.
