from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Reflection MCP Server PoC",
    description="A Proof of Concept Micro-Capability Platform server for agent reflection.",
    version="0.1.0",
)

# In-memory store for agent events and generated feedback (PoC)
agent_events: Dict[str, List[Dict[str, Any]]] = {}
agent_feedback: Dict[str, List[str]] = {}

class ReflectionEvent(BaseModel):
    agent_id: str
    task_id: str
    action_type: str  # e.g., "tool_use", "observation", "decision"
    details: Dict[str, Any]

@app.post("/reflect", summary="Submit an agent's execution event for reflection")
async def reflect_event(event: ReflectionEvent):
    """
    Receives an event from an agent, stores it, and processes it for reflection.
    """
    agent_id = event.agent_id

    if agent_id not in agent_events:
        agent_events[agent_id] = []
    agent_events[agent_id].append(event.dict())

    logger.info(f"Received reflection event from agent '{agent_id}' for task '{event.task_id}' ({event.action_type})")

    # --- PoC Reflection Logic ---
    # This is a very simple, rule-based reflection. In a real system, this would be more sophisticated.

    if event.action_type == "tool_use" and event.details.get("status") == "failure":
        tool_name = event.details.get("tool_name", "unknown_tool")
        error_msg = event.details.get("error", "An unspecified error occurred.")
        feedback_item = (
            f"Agent {agent_id} has encountered '{error_msg}' "
            f"with tool_use:'{tool_name}' on task '{event.task_id}'. "
            "Consider alternative approaches or verifying preconditions before using this tool again." 
        )
        if agent_id not in agent_feedback:
            agent_feedback[agent_id] = []
        agent_feedback[agent_id].append(feedback_item)
        logger.warning(f"Generated feedback for agent '{agent_id}': {feedback_item}")

    return {"message": "Reflection event processed successfully", "event_id": len(agent_events[agent_id]) - 1}

@app.get("/feedback/{agent_id}", summary="Retrieve reflection feedback for a specific agent")
async def get_feedback(agent_id: str):
    """
    Retrieves all accumulated reflection feedback for a given agent.
    """
    if agent_id not in agent_feedback or not agent_feedback[agent_id]:
        return {"feedback": [], "message": f"No new feedback for agent '{agent_id}'"}

    # In a real system, feedback might be consumed and then cleared, or marked as read.
    # For PoC, we just return it.
    feedback_to_return = agent_feedback[agent_id]
    # Optional: Clear feedback after retrieval for PoC simplicity or specific interaction model        
    # agent_feedback[agent_id] = []

    logger.info(f"Provided {len(feedback_to_return)} feedback items for agent '{agent_id}'")
    return {"feedback": feedback_to_return}

@app.get("/events/{agent_id}", summary="Retrieve all recorded events for a specific agent (for debugging)")
async def get_agent_events(agent_id: str):
    """
    Retrieves all recorded reflection events for a given agent. (Debugging endpoint)
    """
    return {"events": agent_events.get(agent_id, [])}
