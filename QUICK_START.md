# 🚀 Démarrage Rapide - Interface Gradio DataInclusion

Une interface moderne et intuitive pour interagir avec l'agent IA d'inclusion sociale en France.

## ⚡ Installation et Lancement en 3 Étapes

### 1️⃣ **Configurer les clés API**

```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer le fichier .env et ajouter vos clés
nano .env  # ou votre éditeur préféré
```

Dans `.env`, ajoutez :

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DATA_INCLUSION_API_KEY=votre-cle-data-inclusion
```

### 2️⃣ **Lancer l'application**

**Option A - Script automatique (recommandé) :**

```bash
# Linux/Mac
./start.sh

# Windows
start.bat
```

**Option B - Commandes Docker manuelles :**

```bash
docker-compose up -d --build
```

### 3️⃣ **Accéder à l'interface**

Ouvrez votre navigateur sur : **<http://localhost:7860>**

---

## 🎯 Interface Utilisateur

L'interface Gradio offre :

- **💬 Chat en temps réel** avec l'agent IA spécialisé
- **🔍 Affichage visuel** des appels aux outils MCP
- **📋 Exemples prédéfinis** pour commencer facilement
- **🎨 Interface moderne** et responsive

### Exemples de questions à poser

- *"Trouve-moi des structures d'aide au logement à Paris"*
- *"Quels sont les services d'insertion professionnelle en région PACA ?"*
- *"Comment trouver de l'aide alimentaire près de chez moi à Lyon ?"*
- *"Recherche des centres d'accueil pour personnes sans domicile en Île-de-France"*

---

## 🛠️ Gestion des Services

### **Vérifier l'état :**

```bash
docker-compose ps
```

### **Voir les logs :**

```bash
# Tous les services
docker-compose logs -f

# Service spécifique
docker-compose logs -f gradio_interface
```

### **Redémarrer un service :**

```bash
docker-compose restart gradio_interface
```

### **Arrêter tout :**

```bash
docker-compose down
```

---

## 🔧 Résolution Rapide des Problèmes

| Problème | Solution |
|----------|----------|
| Port 7860 déjà utilisé | `netstat -an \| findstr :7860` puis tuer le processus ou changer le port |
| Service ne démarre pas | `docker-compose logs nom_du_service` pour voir les erreurs |
| Clé API manquante | Vérifier le fichier `.env` et relancer |
| Erreur de connexion | `docker-compose restart` ou `./start.sh --clean` |

---

## 📊 Ports utilisés

| Service | Port | URL |
|---------|------|-----|
| **Gradio Interface** | 7860 | <http://localhost:7860> |
| Agent Server | 8001 | <http://localhost:8001> |
| MCP Server | 8000 | <http://localhost:8000> |

---

## 📖 Documentation Complète

- **[Guide Docker Complet](DOCKER_README.md)** - Configuration avancée et dépannage
- **[Architecture Backend](README.md)** - Détails techniques du système

---

✨ **C'est tout !** Votre interface Gradio est maintenant prête à l'usage sur <http://localhost:7860>
