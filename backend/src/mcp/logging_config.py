"""
Configuration du système de journalisation pour le serveur MCP.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure un logger standard pour le serveur MCP.
    
    Args:
        level: Niveau de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        logging.Logger: Instance du logger configuré
    """
    # Convertir le niveau string en constante logging
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Créer le logger principal
    logger = logging.getLogger("MCP_SERVER")
    logger.setLevel(numeric_level)
    
    # Éviter la duplication des handlers si déjà configuré
    if logger.handlers:
        return logger
    
    # Créer un formatter avec timestamp, niveau et message
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Créer un handler pour la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    
    # Ajouter le handler au logger
    logger.addHandler(console_handler)
    
    return logger 