@echo off
setlocal EnableDelayedExpansion

rem Script de lancement pour l'application DataInclusion avec interface Gradio (Windows)
rem Ce script configure et lance tous les services nécessaires sur Windows

echo ========================================
echo 🚀 Lancement de DataInclusion avec Gradio
echo ========================================

rem Vérifier si Docker est installé
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker n'est pas installé ou n'est pas dans le PATH.
    echo 💡 Veuillez installer Docker Desktop pour Windows.
    pause
    exit /b 1
)

rem Vérifier si docker-compose est installé
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ docker-compose n'est pas installé ou n'est pas dans le PATH.
    echo 💡 Veuillez installer docker-compose.
    pause
    exit /b 1
)

rem Vérifier si le fichier .env existe
if not exist .env (
    echo ⚠️  Fichier .env manquant. Création depuis .env.example...
    if exist .env.example (
        copy .env.example .env >nul
        echo ✅ Fichier .env créé. Veuillez le configurer avec vos clés API.
        echo 📝 Éditez .env et ajoutez votre OPENAI_API_KEY et DATA_INCLUSION_API_KEY
        echo.
        echo Une fois configuré, relancez: start.bat
        pause
        exit /b 0
    ) else (
        echo ❌ Fichier .env.example introuvable. Veuillez le créer.
        pause
        exit /b 1
    )
)

rem Vérifier les variables critiques dans .env
echo 🔍 Vérification de la configuration...

rem Lire le fichier .env pour vérifier les clés API
set "OPENAI_FOUND=0"
set "DATA_INCLUSION_FOUND=0"

for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="OPENAI_API_KEY" (
        if not "%%b"=="" if not "%%b"=="your-openai-key-here" (
            set "OPENAI_FOUND=1"
        )
    )
    if "%%a"=="DATA_INCLUSION_API_KEY" (
        if not "%%b"=="" if not "%%b"=="your-api-key-here" (
            set "DATA_INCLUSION_FOUND=1"
        )
    )
)

if "!OPENAI_FOUND!"=="0" (
    echo ❌ OPENAI_API_KEY manquante ou invalide dans .env
    echo 💡 Ajoutez votre clé OpenAI dans le fichier .env
    pause
    exit /b 1
)

if "!DATA_INCLUSION_FOUND!"=="0" (
    echo ❌ DATA_INCLUSION_API_KEY manquante ou invalide dans .env
    echo 💡 Ajoutez votre clé DataInclusion dans le fichier .env
    pause
    exit /b 1
)

echo ✅ Configuration validée
echo.

rem Nettoyer les anciens conteneurs si demandé
if "%1"=="--clean" (
    echo 🧹 Nettoyage des anciens conteneurs...
    docker-compose down --volumes --remove-orphans
    docker system prune -f
    echo ✅ Nettoyage terminé
    echo.
)

rem Construire et lancer les services
echo 🔨 Construction des images Docker...
docker-compose build
if errorlevel 1 (
    echo ❌ Erreur lors de la construction des images
    pause
    exit /b 1
)

echo.
echo 🚀 Démarrage des services...
docker-compose up -d
if errorlevel 1 (
    echo ❌ Erreur lors du démarrage des services
    pause
    exit /b 1
)

echo.
echo ⏳ Attente du démarrage complet des services...

rem Attendre que tous les services soient prêts
echo 📡 Vérification du serveur MCP...
:check_mcp
timeout /t 5 /nobreak >nul
docker-compose exec -T mcp_server curl -f http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo    ⏳ MCP Server démarrage en cours...
    goto check_mcp
)
echo    ✅ MCP Server opérationnel

echo 🤖 Vérification du serveur Agent...
:check_agent
timeout /t 5 /nobreak >nul
docker-compose exec -T agent_server curl -f http://localhost:8001/.well-known/agent.json >nul 2>&1
if errorlevel 1 (
    echo    ⏳ Agent Server démarrage en cours...
    goto check_agent
)
echo    ✅ Agent Server opérationnel

echo 🎨 Vérification de l'interface Gradio...
:check_gradio
timeout /t 5 /nobreak >nul
docker-compose exec -T gradio_interface curl -f http://localhost:7860 >nul 2>&1
if errorlevel 1 (
    echo    ⏳ Interface Gradio démarrage en cours...
    goto check_gradio
)
echo    ✅ Interface Gradio opérationnelle

echo.
echo ========================================
echo 🎉 Tous les services sont opérationnels !
echo ========================================
echo.
echo 📱 Interfaces disponibles :
echo    🎨 Interface Gradio:     http://localhost:7860
echo    🤖 Agent API:           http://localhost:8001
echo    🛠️  MCP Server:          http://localhost:8000
echo    🗄️  Redis:               localhost:6379
echo.
echo 📊 Monitoring :
echo    📋 Logs en temps réel:   docker-compose logs -f
echo    📈 État des services:    docker-compose ps
echo    🔍 Logs spécifiques:
echo        - Gradio:           docker-compose logs -f gradio_interface
echo        - Agent:            docker-compose logs -f agent_server
echo        - MCP:              docker-compose logs -f mcp_server
echo.
echo 🛑 Pour arrêter :
echo    docker-compose down
echo.
echo 🔄 Pour redémarrer :
echo    docker-compose restart
echo.
echo 🧹 Pour nettoyer complètement :
echo    start.bat --clean
echo.
echo ✨ Interface Gradio prête à l'usage sur http://localhost:7860
echo ========================================

rem Ouvrir automatiquement l'interface Gradio dans le navigateur par défaut
echo.
echo 🌐 Ouverture automatique de l'interface Gradio...
timeout /t 3 /nobreak >nul
start http://localhost:7860

echo.
echo 💡 Appuyez sur une touche pour fermer cette fenêtre...
pause >nul 