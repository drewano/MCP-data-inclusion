from fastapi import Depends, Request, HTTPException
from pydantic_ai import Agent
from typing import Annotated


def get_agent_from_app_state(request: Request) -> Agent:
    """
    Retrieve the Agent instance from the FastAPI application's state.
    
    Raises:
        HTTPException: If the Agent is not initialized in the application state.
    
    Returns:
        Agent: The Agent instance stored in the application's state.
    """
    if not hasattr(request.app.state, "agent"):
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return request.app.state.agent


# Type alias pour l'injection de dépendance
AgentDep = Annotated[Agent, Depends(get_agent_from_app_state)]
