"""
Module de transformation des outils MCP.

Ce module contient la classe ToolTransformer qui encapsule toute la logique pour transformer
et enrichir les outils MCP générés à partir de la spécification OpenAPI de l'API Data Inclusion.

La classe ToolTransformer permet de :
- Personnaliser les noms des outils pour une meilleure lisibilité
- Enrichir les descriptions des outils et de leurs paramètres
- Optimiser les schémas pour une meilleure compatibilité avec les LLMs
- Ajouter des tags pour l'organisation des outils

Le processus de transformation se déroule en plusieurs étapes :
1. Génération des outils de base par FastMCP avec callback de personnalisation
2. Transformation et enrichissement des outils
3. Remplacement des outils originaux par les versions transformées
"""

import logging
from fastmcp import FastMCP
from fastmcp.tools import Tool
from fastmcp.tools.tool_transform import ArgTransform
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.openapi import HTTPRoute

from .utils import deep_clean_schema, find_route_by_id


def customize_for_gemini(route, component, logger: logging.Logger):
    """
    Simplifies and cleans the input and output JSON schemas of a FastMCP component for improved compatibility with strict LLMs like Gemini.
    
    Removes problematic elements such as titles from the component's schemas using `deep_clean_schema`. Modifies the component's schemas in-place. Logs the cleaning actions performed.
    """
    tool_name = getattr(component, "name", "Unknown")
    cleaned_schemas = []

    # Nettoyer le schéma d'entrée
    if hasattr(component, "input_schema") and component.input_schema:
        deep_clean_schema(component.input_schema)
        cleaned_schemas.append("input schema")
        logger.info(f"Input schema cleaned for tool: {tool_name}")

    # Nettoyer le schéma de sortie
    if hasattr(component, "output_schema") and component.output_schema:
        deep_clean_schema(component.output_schema)
        cleaned_schemas.append("output schema")
        logger.info(f"Output schema cleaned for tool: {tool_name}")

    # Message de résumé si des schémas ont été nettoyés
    if cleaned_schemas:
        logger.info(
            f"Schema cleaning completed for tool '{tool_name}': {', '.join(cleaned_schemas)}"
        )
    else:
        logger.debug(f"No schemas found to clean for tool: {tool_name}")


class ToolTransformer:
    """
    Classe responsable de la transformation et de l'enrichissement des outils MCP.

    Cette classe encapsule toute la logique de transformation des outils MCP générés
    automatiquement par FastMCP depuis la spécification OpenAPI, en les enrichissant
    avec des noms personnalisés, des descriptions améliorées et des métadonnées.
    """

    def __init__(
        self,
        mcp_server: FastMCP,
        http_routes: list[HTTPRoute],
        custom_tool_names: dict[str, str],
        op_id_map: dict[str, str],
        logger: logging.Logger,
    ):
        """
        Initialize the ToolTransformer with the MCP server, OpenAPI routes, tool name mappings, and logger.
        
        This sets up the transformer to customize and enrich MCP tools generated from an OpenAPI specification.
        """
        self.mcp_server = mcp_server
        self.http_routes = http_routes
        self.custom_tool_names = custom_tool_names
        self.op_id_map = op_id_map
        self.logger = logger

    def discover_and_customize(
        self,
        route: HTTPRoute,
        component: FastMCPComponent,
    ):
        """
        Customize the FastMCP component's schemas for Gemini compatibility and map the OpenAPI operation_id to the generated tool name.
        
        This method is intended as a callback during automatic tool generation. It cleans the component's input and output schemas for strict LLM compatibility and records the mapping between the OpenAPI operation_id and the generated tool name in the instance's op_id_map.
        """
        # Appel de la fonction de personnalisation existante
        customize_for_gemini(route, component, self.logger)

        # Découverte du nom de l'outil et stockage dans la map
        if (
            hasattr(route, "operation_id")
            and route.operation_id
            and hasattr(component, "name")
            and component.name
        ):
            self.op_id_map[route.operation_id] = component.name

    async def transform_tools(self) -> None:
        """
        Transforms and enriches MCP tools with custom names, improved descriptions, and metadata.
        
        This asynchronous method processes all tools defined in the custom tool names mapping. For each tool, it finds the corresponding OpenAPI route and generated tool, enriches the tool with enhanced descriptions (using route description, summary, or a default), adds parameter descriptions from OpenAPI, and assigns organizational tags. The transformed tool replaces the original on the MCP server, ensuring no duplicates remain. The method logs progress, warnings, errors, and a summary of the transformation, including unmapped operation IDs for debugging.
        
        Raises:
            Exceptions encountered during individual tool transformations are logged, but do not interrupt processing of other tools.
        """
        self.logger.info(
            "Applying advanced tool transformations using Tool.from_tool()..."
        )

        successful_renames = 0
        total_tools = len(self.custom_tool_names)

        for original_name, new_name in self.custom_tool_names.items():
            # Rechercher la route correspondante dans les données OpenAPI
            route = await find_route_by_id(original_name, self.http_routes)
            if route is None:
                self.logger.warning(
                    f"  ✗ Route not found for operation_id: '{original_name}' - skipping transformation"
                )
                continue

            # Utilise la map pour obtenir le nom de l'outil généré par FastMCP
            mangled_tool_name = self.op_id_map.get(original_name)
            if not mangled_tool_name:
                self.logger.warning(
                    f"  ✗ Could not find a generated tool for operation_id: '{original_name}' - skipping transformation"
                )
                continue

            try:
                # Récupérer l'outil original en utilisant son nom "manglé"
                original_tool = await self.mcp_server.get_tool(mangled_tool_name)
                if not original_tool:
                    self.logger.warning(
                        f"  ✗ Tool not found: '{mangled_tool_name}' (may have been renamed during OpenAPI processing)"
                    )
                    continue

                # === ENRICHISSEMENT DES ARGUMENTS ===
                arg_transforms = {}
                param_count = 0

                # Enrichir les descriptions des paramètres depuis l'OpenAPI
                if hasattr(route, "parameters") and route.parameters:
                    for param in route.parameters:
                        if hasattr(param, "name") and param.name:
                            transforms = {}

                            # Ajouter une description si disponible
                            if (
                                hasattr(param, "description")
                                and param.description
                                and param.description.strip()
                            ):
                                transforms["description"] = param.description.strip()
                                param_count += 1

                            # Note: L'attribut 'example' n'est pas disponible sur ParameterInfo
                            # Les exemples peuvent être ajoutés via d'autres moyens si nécessaire

                            # Créer l'ArgTransform seulement s'il y a des transformations
                            if transforms:
                                arg_transforms[param.name] = ArgTransform(**transforms)
                                self.logger.debug(
                                    f"    - Enriching parameter '{param.name}': {list(transforms.keys())}"
                                )

                # === CRÉATION DE LA DESCRIPTION ENRICHIE ===
                tool_description = None
                if (
                    hasattr(route, "description")
                    and route.description
                    and route.description.strip()
                ):
                    tool_description = route.description.strip()
                elif (
                    hasattr(route, "summary")
                    and route.summary
                    and route.summary.strip()
                ):
                    # Fallback vers le summary si pas de description
                    tool_description = route.summary.strip()
                else:
                    # Description par défaut basée sur le nom de l'outil
                    tool_description = (
                        f"Execute the {new_name} operation on the Data Inclusion API"
                    )

                # === AJOUT DE TAGS POUR ORGANISATION ===
                tool_tags = {"data-inclusion", "api"}

                # Ajouter des tags spécifiques selon le type d'endpoint
                if "list_all" in new_name or "search" in new_name:
                    tool_tags.add("listing")
                if "get_" in new_name and "details" in new_name:
                    tool_tags.add("details")
                if "doc_" in new_name:
                    tool_tags.add("documentation")
                if any(
                    endpoint in new_name
                    for endpoint in ["structures", "services", "sources"]
                ):
                    tool_tags.add("core-data")

                # === CRÉATION DU NOUVEL OUTIL TRANSFORMÉ ===
                transformed_tool = Tool.from_tool(
                    tool=original_tool,
                    name=new_name,
                    description=tool_description,
                    transform_args=arg_transforms if arg_transforms else None,
                    tags=tool_tags,
                )

                # === AJOUT ET SUPPRESSION ===
                # Ajouter le nouvel outil au serveur
                self.mcp_server.add_tool(transformed_tool)

                # IMPORTANT: Supprimer l'outil original pour éviter les doublons
                # et la confusion pour le LLM
                try:
                    self.mcp_server.remove_tool(mangled_tool_name)
                    self.logger.debug(
                        f"    - Removed original tool: '{mangled_tool_name}'"
                    )
                except Exception as remove_error:
                    # En cas d'échec de suppression, désactiver au moins l'outil
                    self.logger.debug(
                        f"    - Could not remove '{mangled_tool_name}', disabling instead: {remove_error}"
                    )
                    original_tool.disable()

                # === LOGGING DE SUCCÈS ===
                successful_renames += 1
                enrichment_info = []

                if tool_description:
                    enrichment_info.append("description")
                if param_count > 0:
                    enrichment_info.append(f"{param_count} param descriptions")
                if tool_tags:
                    enrichment_info.append(f"{len(tool_tags)} tags")

                enrichment_msg = (
                    f" (enriched: {', '.join(enrichment_info)})"
                    if enrichment_info
                    else ""
                )
                self.logger.info(
                    f"  ✓ Transformed tool: '{original_name}' -> '{new_name}'{enrichment_msg}"
                )

            except Exception as e:
                self.logger.error(
                    f"  ✗ Failed to transform tool '{original_name}' -> '{new_name}': {e}"
                )
                self.logger.debug(
                    f"    Exception details: {type(e).__name__}: {str(e)}"
                )

        # === RÉSUMÉ FINAL ===
        if successful_renames > 0:
            self.logger.info(
                f"✓ Tool transformation completed: {successful_renames}/{total_tools} tools successfully transformed"
            )
        else:
            self.logger.warning(
                f"⚠️  No tools were successfully transformed out of {total_tools} attempted"
            )

        # Vérifier que nous avons encore des outils après transformation
        final_tools = await self.mcp_server.get_tools()
        enabled_tools = [name for name, tool in final_tools.items() if tool.enabled]
        self.logger.info(
            f"📊 Final tool count: {len(enabled_tools)} enabled tools available"
        )

        # === DEBUG: AFFICHER LES OPERATION_IDS DISPONIBLES ===
        # Afficher les operation_ids non mappés pour aider au debug
        self.logger.info("=== OpenAPI Route Analysis ===")
        available_ops = [
            route.operation_id
            for route in self.http_routes
            if hasattr(route, "operation_id") and route.operation_id
        ]
        unmapped_ops = [
            op_id for op_id in available_ops if op_id not in self.custom_tool_names
        ]

        self.logger.info(f"Total OpenAPI routes: {len(available_ops)}")
        self.logger.info(f"Mapped routes: {len(self.custom_tool_names)}")
        self.logger.info(f"Unmapped routes: {len(unmapped_ops)}")

        if unmapped_ops:
            self.logger.info(
                "⚠️  Unmapped operation_ids (should be added to custom_mcp_tool_names):"
            )
            for op_id in sorted(unmapped_ops):
                self.logger.info(f"  - '{op_id}'")
