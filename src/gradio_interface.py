"""
Interface Gradio moderne pour l'agent IA d'inclusion sociale.

Ce module fournit une interface utilisateur web élégante utilisant Gradio
pour interagir avec l'agent IA d'inclusion sociale et visualiser les appels
aux outils MCP en temps réel.
"""

import asyncio
import logging
import time
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator
from contextlib import asynccontextmanager

import gradio as gr
from gradio import ChatMessage
import httpx
from fasta2a.schema import Artifact

from .client import DataInclusionClient, DataInclusionClientError
from .client.datainclusion_client import TaskNotFoundError, ConnectionError, TaskFailedError

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GradioInterface:
    """
    Interface Gradio pour l'agent IA d'inclusion sociale.
    
    Cette classe encapsule toute la logique d'interface utilisateur
    et la communication avec l'agent via le client DataInclusion.
    """
    
    def __init__(
        self,
        agent_url: str = "http://localhost:8001",
        title: str = "🏠 Assistant IA - Inclusion Sociale en France",
        description: Optional[str] = None
    ):
        """
        Initialise l'interface Gradio.
        
        Args:
            agent_url: URL du serveur agent
            title: Titre de l'interface
            description: Description de l'interface
        """
        self.agent_url = agent_url
        self.title = title
        if description is None:
            self.description = (
                "Votre assistant IA spécialisé pour trouver des informations sur "
                "les services d'inclusion sociale, les structures d'aide et les "
                "ressources disponibles en France. 🇫🇷"
            )
        else:
            self.description = description
        self.client = None
        self.demo = None
        
    async def _create_client(self) -> DataInclusionClient:
        """Crée une nouvelle instance du client DataInclusion."""
        return DataInclusionClient(
            base_url=self.agent_url,
            timeout=120.0,  # Timeout plus long pour les requêtes complexes
            max_retries=3,
            poll_interval=0.5  # Polling plus fréquent pour une meilleure réactivité
        )
    
    def _format_artifact_as_tool_message(self, artifact: Artifact, index: int) -> ChatMessage:
        """
        Formate un artifact en message d'outil pour l'affichage.
        
        Args:
            artifact: Artifact à formater
            index: Index de l'artifact
            
        Returns:
            ChatMessage formaté pour afficher l'utilisation d'outil
        """
        name = artifact.get('name', f'Outil #{index + 1}')
        description = artifact.get('description', '')
        
        # Extraire le contenu des parties de l'artifact
        content_parts = []
        parts = artifact.get('parts', [])
        
        for part in parts:
            if isinstance(part, dict):
                part_type = part.get('type', 'unknown')
                if part_type == 'text':
                    text = part.get('text', '')
                    if text:
                        content_parts.append(text)
                elif part_type == 'data':
                    data = part.get('data', {})
                    if data:
                        # Formater les données de manière lisible
                        if isinstance(data, dict):
                            formatted_data = "\n".join([f"**{k}:** {v}" for k, v in data.items() if v is not None])
                            if formatted_data:
                                content_parts.append(formatted_data)
        
        # Construire le contenu du message
        content = ""
        if description:
            content += f"*{description}*\n\n"
        
        if content_parts:
            content += "\n\n".join(content_parts)
        else:
            content = "Outil utilisé avec succès ✅"
        
        # Déterminer l'icône en fonction du nom de l'outil
        icon = "🛠️"
        if "search" in name.lower() or "recherche" in name.lower():
            icon = "🔍"
        elif "geo" in name.lower() or "location" in name.lower():
            icon = "📍"
        elif "structure" in name.lower() or "service" in name.lower():
            icon = "🏢"
        elif "list" in name.lower() or "liste" in name.lower():
            icon = "📋"
        
        return ChatMessage(
            role="assistant",
            content=content,
            metadata={"title": f"{icon} Outil utilisé: {name}"}
        )
    
    def _extract_agent_response_from_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        Extrait la réponse finale de l'agent depuis les messages du protocole A2A.
        
        Args:
            messages: Liste des messages de l'historique du protocole A2A
            
        Returns:
            Réponse finale de l'agent ou message par défaut
        """
        # Chercher le dernier message de l'agent
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get('role') == 'agent':
                parts = msg.get('parts', [])
                for part in parts:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        text = part.get('text', '').strip()
                        if text:
                            return text
        
        return "L'agent a terminé le traitement avec succès."
    
    async def _poll_task_with_streaming(
        self,
        client: DataInclusionClient,
        task_id: str,
        history: List[ChatMessage],
        max_wait_time: Optional[float] = 120.0
    ) -> AsyncGenerator[List[ChatMessage], None]:
        """
        Fait du polling sur l'état de la tâche et affiche les mises à jour en temps réel.
        
        Args:
            client: Client DataInclusion
            task_id: ID de la tâche à surveiller
            history: Historique actuel des messages
            max_wait_time: Temps maximum d'attente
            
        Yields:
            Historique mis à jour avec les nouvelles informations
        """
        start_time = asyncio.get_event_loop().time()
        last_artifacts_count = 0
        processing_msg_index = len(history) - 1  # Index du message "Traitement en cours..."
        
        while True:
            try:
                # Vérifier l'état de la tâche
                result = await client.get_task_status(task_id)
                
                # Afficher les nouveaux artifacts (appels d'outils)
                current_artifacts_count = len(result.artifacts)
                if current_artifacts_count > last_artifacts_count:
                    # Insérer les nouveaux artifacts avant le message de traitement
                    new_artifacts = result.artifacts[last_artifacts_count:]
                    for i, artifact in enumerate(new_artifacts):
                        tool_msg = self._format_artifact_as_tool_message(
                            artifact, 
                            last_artifacts_count + i
                        )
                        history.insert(processing_msg_index, tool_msg)
                        processing_msg_index += 1
                    
                    last_artifacts_count = current_artifacts_count
                    yield history
                
                # Vérifier si la tâche est terminée
                if result.status in ['completed', 'failed', 'canceled']:
                    if result.status == 'failed':
                        error_msg = ChatMessage(
                            role="assistant",
                            content="❌ Une erreur s'est produite lors du traitement de votre demande.",
                            metadata={"title": "🚨 Erreur de traitement"}
                        )
                        history[processing_msg_index] = error_msg
                        yield history
                        return
                    elif result.status == 'canceled':
                        cancel_msg = ChatMessage(
                            role="assistant",
                            content="⏹️ Le traitement a été annulé.",
                            metadata={"title": "🚫 Traitement annulé"}
                        )
                        history[processing_msg_index] = cancel_msg
                        yield history
                        return
                    
                    # Tâche terminée avec succès - afficher la réponse finale
                    # Utiliser les messages du TaskResult qui sont des ChatMessage de notre client
                    if result.messages:
                        # Chercher le dernier message de l'agent
                        final_response = ""
                        for msg in reversed(result.messages):
                            if hasattr(msg, 'role') and msg.role == 'agent' and hasattr(msg, 'content'):
                                final_response = msg.content.strip()
                                if final_response:
                                    break
                        
                        if not final_response:
                            final_response = "L'agent a terminé le traitement avec succès."
                    else:
                        final_response = "L'agent a terminé le traitement avec succès."
                    
                    final_msg = ChatMessage(
                        role="assistant",
                        content=final_response,
                        metadata={"title": "✅ Réponse de l'assistant"}
                    )
                    history[processing_msg_index] = final_msg
                    
                    logger.info(f"Tâche {task_id} terminée avec succès")
                    yield history
                    return
                
                # Vérifier le timeout
                if max_wait_time:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > max_wait_time:
                        timeout_msg = ChatMessage(
                            role="assistant",
                            content="⏱️ Le traitement prend plus de temps que prévu. Vous pouvez réessayer plus tard.",
                            metadata={"title": "⚠️ Timeout"}
                        )
                        history[processing_msg_index] = timeout_msg
                        yield history
                        return
                
                # Attendre avant la prochaine vérification
                await asyncio.sleep(0.5)
                
            except TaskNotFoundError:
                error_msg = ChatMessage(
                    role="assistant",
                    content="❌ La tâche n'a pas été trouvée sur le serveur.",
                    metadata={"title": "🚨 Erreur de tâche"}
                )
                history[processing_msg_index] = error_msg
                yield history
                return
                
            except ConnectionError as e:
                error_msg = ChatMessage(
                    role="assistant",
                    content=f"❌ Problème de connexion: {str(e)}",
                    metadata={"title": "🚨 Erreur de connexion"}
                )
                history[processing_msg_index] = error_msg
                yield history
                return
                
            except Exception as e:
                logger.error(f"Erreur inattendue lors du polling: {e}")
                error_msg = ChatMessage(
                    role="assistant",
                    content="❌ Une erreur inattendue s'est produite. Veuillez réessayer.",
                    metadata={"title": "🚨 Erreur système"}
                )
                history[processing_msg_index] = error_msg
                yield history
                return

    async def process_user_message(self, history: List[ChatMessage], user_message: str, session_id: str) -> AsyncGenerator[List[ChatMessage], None]:
        """
        Traite un message utilisateur avec l'agent réel et affiche les résultats.
        
        Args:
            history: Historique de la conversation
            user_message: Message de l'utilisateur
            session_id: ID de session unique pour maintenir le contexte
            
        Yields:
            Liste des messages mis à jour avec les étapes de traitement
        """
        # Ajouter le message utilisateur
        history.append(ChatMessage(role="user", content=user_message))
        yield history
        
        # Indication que l'assistant réfléchit
        thinking_msg = ChatMessage(
            role="assistant", 
            content="🤔 Analyse de votre demande...",
            metadata={"title": "💭 Réflexion en cours"}
        )
        history.append(thinking_msg)
        yield history
        
        try:
            # Créer le client pour cette requête
            async with await self._create_client() as client:
                # Vérifier la santé du serveur
                is_healthy = await client.check_server_health()
                if not is_healthy:
                    error_msg = ChatMessage(
                        role="assistant",
                        content="❌ Le serveur agent n'est pas accessible. Veuillez vérifier que les services sont démarrés.",
                        metadata={"title": "🚨 Erreur de connexion"}
                    )
                    history[-1] = error_msg
                    yield history
                    return
                
                # Lancer la requête sans attendre la complétion
                result = await client.ask_question(
                    question=user_message,
                    session_id=session_id,
                    wait_for_completion=False
                )
                
                task_id = result.task_id
                logger.info(f"Tâche créée avec l'ID: {task_id}")
                
                # Mettre à jour le message pour indiquer que le traitement a commencé
                history[-1] = ChatMessage(
                    role="assistant",
                    content="⚙️ Traitement en cours avec l'agent IA...",
                    metadata={"title": "🔄 Agent en action"}
                )
                yield history
                
                # Démarrer le polling avec streaming pour afficher les mises à jour en temps réel
                async for updated_history in self._poll_task_with_streaming(
                    client, task_id, history, max_wait_time=120.0
                ):
                    yield updated_history
                
        except ConnectionError as e:
            logger.error(f"Erreur de connexion: {e}")
            error_msg = ChatMessage(
                role="assistant",
                content=f"❌ Problème de connexion avec le serveur: {str(e)}",
                metadata={"title": "🚨 Erreur de connexion"}
            )
            history[-1] = error_msg
            yield history
            
        except TaskNotFoundError as e:
            logger.error(f"Tâche non trouvée: {e}")
            error_msg = ChatMessage(
                role="assistant",
                content=f"❌ Tâche non trouvée: {str(e)}",
                metadata={"title": "🚨 Erreur de tâche"}
            )
            history[-1] = error_msg
            yield history
            
        except DataInclusionClientError as e:
            logger.error(f"Erreur client: {e}")
            error_msg = ChatMessage(
                role="assistant",
                content=f"❌ Erreur lors du traitement: {str(e)}",
                metadata={"title": "🚨 Erreur de traitement"}
            )
            history[-1] = error_msg
            yield history
            
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            error_msg = ChatMessage(
                role="assistant",
                content="❌ Une erreur inattendue s'est produite. Veuillez réessayer.",
                metadata={"title": "🚨 Erreur système"}
            )
            history[-1] = error_msg
            yield history
    
    def _create_example_conversations(self) -> List[str]:
        """Crée des exemples de conversations pour guider l'utilisateur."""
        return [
            "Trouve-moi des structures d'aide au logement à Paris",
            "Quels sont les services d'insertion professionnelle disponibles en région PACA ?",
            "Comment trouver de l'aide alimentaire près de chez moi à Lyon ?",
            "Existe-t-il des services de formation pour les demandeurs d'emploi à Marseille ?",
            "Recherche des centres d'accueil pour personnes sans domicile en Île-de-France",
            "Quelles sont les associations d'aide aux familles en difficulté dans le Nord ?",
        ]
    
    def _create_interface(self) -> gr.Blocks:
        """
        Crée l'interface Gradio complète.
        
        Returns:
            Interface Gradio configurée
        """
        # Thème moderne simple
        theme = "soft"
        
        with gr.Blocks(
            theme=theme,
            title=self.title,
            css="""
            .gradio-container {
                max-width: 800px !important;
                margin: auto;
            }
            .chat-message {
                border-radius: 18px !important;
            }
            .assistant-message {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
                color: white !important;
            }
            .user-message {
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
                color: white !important;
            }
            .tool-message {
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
                border: 1px solid #e5e7eb !important;
            }
            """
        ) as demo:
            
            # En-tête avec titre et description
            gr.Markdown(f"# {self.title}")
            gr.Markdown(f"*{self.description}*")
            
            # Zone d'état de connexion
            status_display = gr.Markdown(
                "🟡 **État:** Vérification de la connexion au serveur agent...",
                visible=True
            )
            
            # Interface de chat principale
            chatbot = gr.Chatbot(
                type="messages",
                height=500,
                label="💬 Conversation avec l'assistant IA",
                show_label=True,
                avatar_images=(
                    "https://raw.githubusercontent.com/gradio-app/gradio/main/guides/assets/chatbot/avatar_user.png",
                    "https://raw.githubusercontent.com/gradio-app/gradio/main/guides/assets/chatbot/avatar_assistant.png"
                ),
                render_markdown=True,
                show_copy_button=True
            )
            
            # Zone de saisie avec boutons
            with gr.Row():
                with gr.Column(scale=4):
                    msg_input = gr.Textbox(
                        label="💬 Votre message",
                        placeholder="Posez votre question sur l'inclusion sociale en France...",
                        lines=2,
                        max_lines=5,
                        show_label=False,
                        container=False
                    )
                with gr.Column(scale=1):
                    send_btn = gr.Button(
                        "Envoyer ➤",
                        variant="primary",
                        size="lg"
                    )
            
            # Boutons d'action
            with gr.Row():
                clear_btn = gr.Button("🗑️ Effacer", variant="secondary", size="sm")
                examples_btn = gr.Button("💡 Exemples", variant="secondary", size="sm")
            
            # Zone d'exemples (initialement cachée)
            with gr.Row(visible=False) as examples_row:
                with gr.Column():
                    gr.Markdown("### 💡 **Exemples de questions :**")
                    example_buttons = []
                    for example in self._create_example_conversations():
                        btn = gr.Button(
                            example,
                            variant="secondary",
                            size="sm",
                            elem_classes=["example-button"]
                        )
                        example_buttons.append(btn)
            
            # État pour gérer la visibilité des exemples
            examples_visible = gr.State(False)
            
            # État pour la session - ajout du session_id unique
            session_id = gr.State(str(uuid.uuid4()))
            
            # Fonctions de l'interface
            async def check_server_status():
                """Vérifie l'état du serveur et met à jour l'affichage."""
                try:
                    async with await self._create_client() as client:
                        is_healthy = await client.check_server_health()
                        if is_healthy:
                            return "🟢 **État:** Serveur agent connecté et opérationnel ✅"
                        else:
                            return "🔴 **État:** Serveur agent non accessible ❌"
                except Exception as e:
                    return f"🔴 **État:** Erreur de connexion - {str(e)} ❌"
            
            async def process_message(message: str, history: List[ChatMessage], current_session_id: str):
                """
                Traite un message utilisateur et génère la réponse de l'agent.
                
                Args:
                    message: Message de l'utilisateur
                    history: Historique de la conversation
                    current_session_id: ID de session unique pour maintenir le contexte
                    
                Returns:
                    Tuple: (input vide, historique mis à jour)
                """
                if not message.strip():
                    return
                
                # Générer la réponse avec streaming en utilisant le session_id
                async for updated_history in self.process_user_message(history, message.strip(), current_session_id):
                    yield "", updated_history
            
            def clear_conversation():
                """Efface la conversation et génère un nouveau session_id."""
                return [], "", str(uuid.uuid4())
            
            def toggle_examples(visible: bool):
                """Affiche/cache les exemples."""
                return not visible, gr.update(visible=not visible)
            
            def use_example(example_text: str):
                """Utilise un exemple comme message."""
                return example_text, gr.update(visible=False), False
            
            # Configuration des événements
            
            # Vérification initiale du serveur
            demo.load(
                check_server_status,
                outputs=[status_display]
            )
            
            # Envoi de message (bouton ou Entrée) - ajout de session_id dans les inputs
            msg_submit = msg_input.submit(
                process_message,
                inputs=[msg_input, chatbot, session_id],
                outputs=[msg_input, chatbot],
                show_progress="minimal"
            )
            
            send_submit = send_btn.click(
                process_message,
                inputs=[msg_input, chatbot, session_id],
                outputs=[msg_input, chatbot],
                show_progress="minimal"
            )
            
            # Bouton effacer - ajout de session_id dans les outputs
            clear_btn.click(
                clear_conversation,
                outputs=[chatbot, msg_input, session_id]
            )
            
            # Bouton exemples
            examples_btn.click(
                toggle_examples,
                inputs=[examples_visible],
                outputs=[examples_visible, examples_row]
            )
            
            # Boutons d'exemples
            for btn in example_buttons:
                btn.click(
                    use_example,
                    inputs=[btn],
                    outputs=[msg_input, examples_row, examples_visible]
                )
            
            # Informations supplémentaires en bas
            with gr.Accordion("ℹ️ Informations sur l'assistant", open=False):
                gr.Markdown("""
                ### 🤖 À propos de votre assistant IA
                
                Cet assistant spécialisé vous aide à naviguer dans l'écosystème de l'inclusion sociale en France. Il peut :
                
                - 🏢 **Rechercher des structures d'aide** par type de service et localisation
                - 📍 **Localiser des services** près de chez vous
                - 🎯 **Identifier des programmes spécifiques** selon vos besoins
                - 📋 **Fournir des informations détaillées** sur les démarches et contacts
                
                ### 🛠️ Outils utilisés
                
                L'assistant utilise plusieurs outils spécialisés :
                - **Base de données d'inclusion** : Accès aux structures référencées
                - **Géolocalisation** : Recherche par zone géographique
                - **Analyse sémantique** : Compréhension fine de vos besoins
                - **Filtrage intelligent** : Sélection des résultats les plus pertinents
                
                ### 📞 Support
                
                En cas de problème technique, vérifiez que les services backend sont démarrés avec `docker-compose up`.
                """)
        
        return demo
    
    def launch(
        self,
        share: bool = False,
        server_name: str = "0.0.0.0",
        server_port: int = 7860,
        debug: bool = False
    ):
        """
        Lance l'interface Gradio.
        
        Args:
            share: Créer un lien public
            server_name: Nom du serveur
            server_port: Port du serveur
            debug: Activer le mode de débogage
        """
        if self.demo is None:
            self.demo = self._create_interface()
        
        logger.info(f"🚀 Lancement de l'interface Gradio sur {server_name}:{server_port}")
        logger.info(f"📡 Agent URL configurée: {self.agent_url}")
        
        self.demo.launch(
            share=share,
            server_name=server_name,
            server_port=server_port,
            debug=debug
        )


def main():
    """Point d'entrée principal pour lancer l'interface Gradio."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Interface Gradio pour l'agent IA d'inclusion sociale")
    parser.add_argument(
        "--agent-url",
        default="http://localhost:8001",
        help="URL du serveur agent (défaut: http://localhost:8001)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port pour l'interface Gradio (défaut: 7860)"
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Créer un lien public partageable"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Nom du serveur (défaut: 0.0.0.0)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activer le mode de débogage"
    )
    
    args = parser.parse_args()
    
    # Créer et lancer l'interface
    interface = GradioInterface(agent_url=args.agent_url)
    interface.launch(
        share=args.share,
        server_name=args.host,
        server_port=args.port,
        debug=args.debug
    )


if __name__ == "__main__":
    main() 