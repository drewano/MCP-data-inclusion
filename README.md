# Data Inclusion MCP Server

Un serveur MCP (Model Context Protocol) qui expose l'API [data.inclusion.beta.gouv.fr](https://data.inclusion.beta.gouv.fr) pour faciliter l'accès aux données d'inclusion en France via des assistants IA compatibles MCP.

[![Licence: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

## 📋 Description

Ce projet transforme automatiquement l'API REST de `data.inclusion` en outils MCP, permettant aux assistants IA (comme Claude Desktop) d'interroger facilement les données sur les structures, services et ressources d'inclusion sociale en France. Il charge la spécification OpenAPI de l'API à la volée pour générer les outils.

### ✨ Fonctionnalités

- **🔄 Conversion Automatique** : Transforme les endpoints de l'API en outils MCP à la volée.
- **🔧 Outils Conviviaux** : Noms d'outils renommés pour une meilleure compréhension par les IA.
- **🐳 Support Docker** : Prêt à l'emploi avec une configuration Docker simple.
- **🔑 Authentification Sécurisée** : Gère l'authentification par `Bearer Token` via les variables d'environnement.
- **⚙️ Pagination Intelligente** : Limite automatiquement le nombre de résultats pour des réponses plus rapides et ciblées.

### 🛠️ Outils Disponibles

Le serveur expose plus d'une dizaine d'outils, dont les principaux :

- `list_all_structures` : Liste les structures d'inclusion.
- `get_structure_details` : Obtient les détails d'une structure spécifique.
- `search_services` : Recherche des services selon des critères (code postal, thématique, etc.).
- `list_all_services` : Liste l'ensemble des services disponibles.
- `doc_list_*` : Accède aux différents référentiels (thématiques, types de frais, etc.).

## 🚀 Démarrage Rapide avec Docker (Recommandé)

Le moyen le plus simple de lancer le serveur est d'utiliser Docker.

### Prérequis

- **Docker**
- **Git**

### Étapes

1. **Cloner le repository :**

    ```bash
    git clone https://github.com/votre-user/datainclusion-mcp-server.git
    cd datainclusion-mcp-server
    ```

2. **Configurer l'environnement :**
    - Copiez le fichier d'exemple : `cp env.example .env`
    - Ouvrez le fichier `.env` et ajoutez votre clé API : `DATA_INCLUSION_API_KEY=votre_cle_api_ici`
    - **Important :** Laissez `MCP_HOST=0.0.0.0` pour que le conteneur soit accessible depuis votre machine.

3. **Construire l'image Docker :**

    ```bash
    docker build -t datainclusion-mcp .
    ```

4. **Lancer le conteneur :**

    ```bash
    docker run -d --rm -p 8000:8000 --env-file .env --name mcp-server datainclusion-mcp
    ```

5. **Vérifier les logs :**

    ```bash
    docker logs mcp-server
    ```

    Vous devriez voir `Starting MCP server on http://0.0.0.0:8000/mcp`. Votre serveur est prêt !

## 🔌 Intégration Client MCP (Claude Desktop, etc.)

Une fois le serveur lancé (localement ou via Docker), ajoutez cette configuration à votre client MCP :

```json
{
  "mcpServers": {
    "data-inclusion": {
      "transport": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

> **Localisation du fichier de config Claude :**
>
> - **Windows** : `%APPDATA%\Claude\claude_desktop_config.json`
> - **macOS** : `~/Library/Application Support/Claude/claude_desktop_config.json`
> - **Linux** : `~/.config/Claude/claude_desktop_config.json`

## ⚙️ Installation et Lancement Manuels

Si vous ne souhaitez pas utiliser Docker.

### Prérequis

- **Python 3.12+**

### Étapes

1. **Cloner le repository et naviguer dans le dossier.**
2. **Installer les dépendances :**

    ```bash
    # Avec uv (recommandé)
    uv pip install -e .
    
    # Ou avec pip
    pip install -e .
    ```

3. **Configurer l'environnement :**
    - `cp env.example .env`
    - Ouvrez `.env` et ajoutez votre clé API.
    - Pour un lancement local, `MCP_HOST=127.0.0.1` est suffisant.
4. **Lancer le serveur :**

    ```bash
    python src/main.py
    ```

## 🛠️ Configuration des Variables d'Environnement

Configurez ces variables dans votre fichier `.env` :

| Variable                 | Description                                                               | Défaut                                                    |
| ------------------------ | ------------------------------------------------------------------------- | --------------------------------------------------------- |
| `MCP_HOST`               | Adresse IP d'écoute. **Utiliser `0.0.0.0` pour Docker.**                   | `127.0.0.1`                                               |
| `MCP_PORT`               | Port d'écoute du serveur.                                                 | `8000`                                                    |
| `MCP_API_PATH`           | Chemin de l'endpoint de l'API MCP.                                        | `/mcp`                                                    |
| `OPENAPI_URL`            | URL de la spécification OpenAPI à charger.                                | `https://api.data.inclusion.beta.gouv.fr/api/openapi.json` |
| `MCP_SERVER_NAME`        | Nom du serveur affiché dans les clients.                                  | `DataInclusionAPI`                                        |
| `DATA_INCLUSION_API_KEY` | **(Requis)** Votre clé API pour l'API `data.inclusion`.                   | **(Obligatoire)**                                         |

## 🏗️ Structure du Projet

```
datainclusion-mcp-server/
├── src/
│   ├── main.py              # Point d'entrée principal du serveur
│   └── utils.py             # Fonctions utilitaires (client HTTP, inspection)
├── .env.example             # Template de configuration d'environnement
├── .gitignore               # Fichiers ignorés par Git
├── Dockerfile               # Instructions pour construire l'image Docker
├── pyproject.toml           # Dépendances et métadonnées du projet
└── README.md                # Cette documentation
```

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une *Pull Request* ou une *Issue*.

1. Forker le projet.
2. Créer une branche pour votre fonctionnalité (`git checkout -b feature/ma-super-feature`).
3. Commiter vos changements (`git commit -m 'Ajout de ma-super-feature'`).
4. Pousser vers la branche (`git push origin feature/ma-super-feature`).
5. Ouvrir une Pull Request.

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

# MCP Data Inclusion Agent

Un agent IA pour l'accompagnement social utilisant l'API Data Inclusion via le protocole MCP (Model Context Protocol).

## Architecture

Le projet utilise une architecture multi-services avec :
- **Frontend** : Next.js avec TypeScript et React
- **Backend** : Serveur d'agent utilisant Pydantic-AI et FastA2A
- **MCP Server** : Serveur MCP exposant l'API Data Inclusion
- **Redis** : Pour la persistance et la gestion des tâches

## Démarrage rapide

1. **Configuration**
   ```bash
   cp .env.example .env.local
   # Éditer .env.local avec vos clés d'API
   ```

2. **Lancement avec Docker**
   ```bash
   docker-compose up --build
   ```

3. **Accès**
   - Frontend : http://localhost:3000
   - Agent API : http://localhost:8001
   - MCP Server : http://localhost:8000

## Dépannage

### Erreur "fetch called on an object that does not implement interface Window"

Cette erreur survient quand le client A2A tente de s'exécuter côté serveur (SSR). Solutions :

1. **Vérifier que le composant est client-side** :
   ```typescript
   'use client' // En haut du fichier
   ```

2. **Attendre l'hydratation** :
   ```typescript
   const [isMounted, setIsMounted] = useState(false);
   useEffect(() => setIsMounted(true), []);
   if (!isMounted) return <div>Chargement...</div>;
   ```

3. **Vérifier la configuration** :
   - S'assurer que les services backend sont démarrés
   - Vérifier les ports (8001 pour l'agent, 8000 pour MCP)
   - Contrôler les logs Docker : `docker-compose logs`

### Erreur de connexion à l'agent

1. **Vérifier les services** :
   ```bash
   docker-compose ps
   ```

2. **Tester la connectivité** :
   ```bash
   curl http://localhost:8001/.well-known/agent.json
   ```

3. **Vérifier les logs** :
   ```bash
   docker-compose logs agent_server
   docker-compose logs mcp_server
   ```

### Variables d'environnement manquantes

Créer un fichier `.env.local` avec au minimum :
```env
# Clés API requises
DATA_INCLUSION_API_KEY=your_api_key_here
GEMINI_API_KEY=your_gemini_key_here

# Configuration optionnelle
LOGFIRE_TOKEN=your_logfire_token
MCP_SERVER_SECRET_KEY=your_secret_key
```

## Développement

### Structure du projet

```
MCP-data-inclusion/
├── frontend/           # Application Next.js
│   ├── components/     # Composants React
│   ├── hooks/         # Hooks personnalisés
│   ├── lib/           # Bibliothèques (api.ts)
│   └── stores/        # État global (Zustand)
├── backend/           # Services Python
│   ├── src/agent/     # Serveur d'agent
│   └── src/mcp/       # Serveur MCP
└── docker-compose.yml # Orchestration des services
```

### Développement frontend

```bash
cd frontend
npm install
npm run dev
```

### Développement backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -e .
```

## API et Intégration

Le frontend utilise le protocole A2A (Agent-to-Agent) pour communiquer avec le backend :

- **Client A2A** : Gestion de la communication
- **Streaming** : Réponses en temps réel
- **Gestion d'état** : Zustand pour l'état global
- **Types TypeScript** : Typage strict pour toute l'API

Pour plus de détails sur l'API, voir `frontend/lib/api.ts`.

## Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.
