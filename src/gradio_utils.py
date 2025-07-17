"""
Utilitaires Gradio pour l'affichage des appels aux outils MCP.

Ce module contient des fonctions utilitaires pour créer des messages Gradio
avec des métadonnées appropriées pour afficher les appels aux outils MCP
de manière claire et informative.
"""

import gradio as gr
from typing import Dict, Any, Optional, Literal, NotRequired, TypedDict
import json
import logging
from datetime import datetime

# Configuration du logger
logger = logging.getLogger("datainclusion.agent")


# Types Gradio corrects selon la documentation
class MetadataDict(TypedDict):
    """Structure des métadonnées pour les messages Gradio ChatMessage."""

    title: NotRequired[str]
    id: NotRequired[int | str]
    parent_id: NotRequired[int | str]
    log: NotRequired[str]
    duration: NotRequired[float]
    status: NotRequired[Literal["pending", "done"]]


def create_tool_call_message(
    tool_name: str,
    arguments: Dict[str, Any] | str | None,
    call_id: Optional[str] = None,
) -> gr.ChatMessage:
    """
    Create a Gradio chat message representing a tool call, including formatted arguments and metadata.
    
    Parameters:
        tool_name (str): The name of the tool being called.
        arguments (dict, str, or None): Arguments passed to the tool, which may be a dictionary, a JSON string, or None.
        call_id (str, optional): Unique identifier for the tool call. If not provided, a timestamp-based ID is generated.
    
    Returns:
        gr.ChatMessage: A Gradio chat message with the tool call details and associated metadata.
    """

    # Normaliser les arguments en dict pour le formatage
    if isinstance(arguments, str):
        try:
            # Tenter de parser comme JSON
            import json

            parsed_args = json.loads(arguments)
            if isinstance(parsed_args, dict):
                normalized_args = parsed_args
            else:
                normalized_args = {"value": arguments}
        except (json.JSONDecodeError, ValueError):
            # Si ce n'est pas du JSON, traiter comme string
            normalized_args = {"value": arguments}
    elif isinstance(arguments, dict):
        normalized_args = arguments
    else:
        # arguments est None ou autre type
        normalized_args = {}

    # Formatage des arguments pour l'affichage
    args_formatted = format_arguments_for_display(normalized_args)

    # Contenu du message
    content = f"**🛠️ Appel d'outil: {tool_name}**\n\n"
    if normalized_args:
        content += f"**Arguments:**\n{args_formatted}"
    else:
        content += "*Aucun argument*"

    # Métadonnées pour l'affichage - utiliser MetadataDict
    metadata: MetadataDict = {
        "title": f"🛠️ {tool_name}",
        "id": call_id or f"tool_{tool_name}_{datetime.now().strftime('%H%M%S')}",
    }

    return gr.ChatMessage(role="assistant", content=content, metadata=metadata)


def create_tool_result_message(
    tool_name: str,
    result: Any,
    call_id: Optional[str] = None,
    duration: Optional[float] = None,
    is_error: bool = False,
) -> gr.ChatMessage:
    """
    Create a Gradio chat message displaying the result or error of an MCP tool execution.
    
    The message includes formatted result content, a status indicator (success or error), and metadata such as title, unique ID, status, and optional execution duration.
    
    Parameters:
        tool_name (str): Name of the tool whose result is being displayed.
        result (Any): The result or output returned by the tool.
        call_id (Optional[str]): Unique identifier for the tool call, used for message tracking.
        duration (Optional[float]): Execution time in seconds, included if provided.
        is_error (bool): If True, formats the message as an error.
    
    Returns:
        gr.ChatMessage: A Gradio chat message representing the tool's result or error, with appropriate formatting and metadata.
    """

    # Formatage du résultat pour l'affichage
    result_formatted = format_result_for_display(result)

    # Emoji et titre selon le statut
    if is_error:
        title = f"❌ Erreur - {tool_name}"
        content = f"**❌ Erreur lors de l'exécution de {tool_name}**\n\n"
        status: Literal["pending", "done"] = "done"
    else:
        title = f"✅ Résultat - {tool_name}"
        content = f"**✅ Résultat de {tool_name}**\n\n"
        status = "done"

    # Ajouter la durée si disponible
    if duration is not None:
        content += f"**Durée:** {duration:.3f}s\n\n"

    # Ajouter le résultat
    content += f"**Résultat:**\n{result_formatted}"

    # Métadonnées pour l'affichage - utiliser MetadataDict
    metadata: MetadataDict = {
        "title": title,
        "id": f"result_{call_id}"
        if call_id
        else f"result_{tool_name}_{datetime.now().strftime('%H%M%S')}",
        "status": status,
    }

    if duration is not None:
        metadata["duration"] = duration

    return gr.ChatMessage(role="assistant", content=content, metadata=metadata)


def create_error_message(error_msg: str, title: str = "⚠️ Erreur") -> gr.ChatMessage:
    """
    Create a Gradio chat message representing an error.
    
    Parameters:
        error_msg (str): The error message to display.
        title (str, optional): The title for the error message. Defaults to "⚠️ Erreur".
    
    Returns:
        gr.ChatMessage: A Gradio chat message with error content and metadata.
    """

    metadata: MetadataDict = {
        "title": title,
        "id": f"error_{datetime.now().strftime('%H%M%S')}",
        "status": "done",
    }

    return gr.ChatMessage(
        role="assistant", content=f"❌ {error_msg}", metadata=metadata
    )


def format_arguments_for_display(arguments: Dict[str, Any]) -> str:
    """
    Format tool arguments into a readable string for display in Gradio chat messages.
    
    Arguments are presented as a list, with long strings and JSON structures truncated for brevity. Returns "*Aucun argument*" if the input is empty.
    
    Returns:
        str: Formatted arguments as a display string.
    """

    if not arguments:
        return "*Aucun argument*"

    formatted_args = []

    for key, value in arguments.items():
        # Formatage spécial selon le type
        if isinstance(value, str):
            if len(value) > 100:
                formatted_value = f'"{value[:100]}..."'
            else:
                formatted_value = f'"{value}"'
        elif isinstance(value, (dict, list)):
            formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
            if len(formatted_value) > 200:
                formatted_value = formatted_value[:200] + "..."
        else:
            formatted_value = str(value)

        formatted_args.append(f"- **{key}**: {formatted_value}")

    return "\n".join(formatted_args)


def format_result_for_display(result: Any) -> str:
    """
    Format a tool result for display in Gradio chat messages.
    
    Returns:
        A formatted string representation of the result, using markdown code blocks and truncating long outputs for readability.
    """

    if result is None:
        return "*Aucun résultat*"

    # Formatage selon le type
    if isinstance(result, str):
        if len(result) > 500:
            return f"```\n{result[:500]}...\n```"
        else:
            return f"```\n{result}\n```"
    elif isinstance(result, (dict, list)):
        formatted_json = json.dumps(result, ensure_ascii=False, indent=2)
        if len(formatted_json) > 500:
            formatted_json = formatted_json[:500] + "..."
        return f"```json\n{formatted_json}\n```"
    else:
        result_str = str(result)
        if len(result_str) > 500:
            result_str = result_str[:500] + "..."
        return f"```\n{result_str}\n```"


def log_gradio_message(message: gr.ChatMessage, context: str = "GRADIO") -> None:
    """
    Logs a Gradio chat message for debugging purposes, including its role, metadata, and a summary of its content.
    """

    logger.debug(f"[{context}] Message: {message.role} - {message.metadata}")
    if isinstance(message.content, str) and len(message.content) < 200:
        logger.debug(f"[{context}] Content: {message.content}")
    else:
        logger.debug(f"[{context}] Content: {len(str(message.content))} caractères")
