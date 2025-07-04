"""
Client pour la connexion à l'agent IA d'inclusion sociale via le protocole FastA2A.

Ce module fournit un client simple et robuste pour interagir avec l'agent
IA d'inclusion sociale à travers le protocole Agent-to-Agent (A2A).
"""

from .datainclusion_client import DataInclusionClient, DataInclusionClientError

__all__ = ["DataInclusionClient", "DataInclusionClientError"] 