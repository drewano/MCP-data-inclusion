"""
Configuration du logging pour l'application.

Ce module configure un système de logging cohérent pour tous les composants
de l'application, avec des niveaux et formatages appropriés pour le debugging
et la surveillance en production.
"""

import logging
import sys


def setup_logging(name: str, level: str = "INFO") -> logging.Logger:
    """
    Set up and return a logger with the specified name and log level, configured for consistent console output.
    
    Parameters:
        name (str): The name of the logger to create or retrieve.
        level (str, optional): The log level as a string ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"). Defaults to "INFO".
    
    Returns:
        logging.Logger: A logger instance configured with the specified name and level, outputting formatted logs to standard output.
    """

    # Configuration des niveaux de log
    log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    log_level = log_levels.get(level.upper(), logging.INFO)

    # Configuration du format de log
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configuration du logger principal
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Supprimer les handlers existants pour éviter les doublons
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Créer un handler pour la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Créer un formatter
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)

    # Ajouter le handler au logger
    logger.addHandler(console_handler)

    # Éviter la propagation vers le logger racine
    logger.propagate = False

    return logger


# Configuration par défaut si le module est importé
if __name__ != "__main__":
    # Configuration automatique lors de l'import
    setup_logging("mcp_server")
