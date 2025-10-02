"""
AI Framework API routes for LangChain and AutoGen integration.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.core.ai_framework_manager import AIFrameworkManager
from src.core.vm_manager import VMManager
from src.utils.security import check_api_key, SecurityContext
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ai-frameworks", tags=["ai-frameworks"])

# Initialize managers
vm_manager = VMManager()
ai_manager = AIFrameworkManager(vm_manager)


class CreateSessionRequest(BaseModel):
    """Request to create an AI framework session."""
    framework: str = Field(..., description="Framework name: 'langchain' or 'autogen'")
    template: Optional[str] = Field(None, description="VM template to use")
    vcpus: Optional[int] = Field(4, description="Number of vCPUs")
    memory_mb: Optional[int] = Field(4096, description="Memory in MB")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Framework-specific configuration")


class SessionInfo(BaseModel):
    """AI framework session information."""
    session_id: str
    vm_name: str
    framework: str
    status: str
    created_at: str
    last_activity: str
    execution_count: int
    vm_status: str
    config: Dict[str, Any]


class FrameworkOperationRequest(BaseModel):
    """Request to execute a framework operation."""
    session_id: str = Field(..., description="Session identifier")
    operation: str = Field(..., description="Operation name")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters")


class LangChainChainRequest(BaseModel):
    """Request to execute a LangChain chain."""
    session_id: str = Field(..., description="Session identifier")
    llm: Optional[Dict[str, Any]] = Field(default_factory=dict, description="LLM configuration")
    prompt_template: str = Field(..., description="Prompt template string")
    input_variables: List[str] = Field(default_factory=list, description="Input variable names")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input values")
    use_memory: bool = Field(False, description="Use conversation memory")
    verbose: bool = Field(False, description="Verbose output")


class LangChainAgentRequest(BaseModel):
    """Request to create a LangChain agent."""
    session_id: str = Field(..., description="Session identifier")
    llm: Optional[Dict[str, Any]] = Field(default_factory=dict, description="LLM configuration")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="Tool configurations")
    agent_type: str = Field("ZERO_SHOT_REACT_DESCRIPTION", description="Agent type")
    verbose: bool = Field(False, description="Verbose output")


class AutoGenSystemRequest(BaseModel):
    """Request to create an AutoGen multi-agent system."""
    session_id: str = Field(..., description="Session identifier")
    llm_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="LLM configuration")
    agents: List[Dict[str, Any]] = Field(..., description="Agent configurations")
    max_rounds: int = Field(10, description="Maximum conversation rounds")


class AutoGenConversationRequest(BaseModel):
    """Request to execute an AutoGen conversation."""
    session_id: str = Field(..., description="Session identifier")
    llm_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="LLM configuration")
    initial_message: str = Field(..., description="Initial message to start conversation")
    max_turns: int = Field(5, description="Maximum conversation turns")


@router.post("/sessions", response_model=SessionInfo)
async def create_session(
    request: CreateSessionRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> SessionInfo:
    """
    Create a new AI framework session.
    
    Creates an isolated MicroVM environment for running AI frameworks
    like LangChain or AutoGen with proper resource allocation.
    """
    try:
        # Validate framework
        if request.framework.lower() not in ['langchain', 'autogen']:
            raise HTTPException(
                status_code=400,
                detail="Unsupported framework. Use 'langchain' or 'autogen'"
            )
        
        # Prepare configuration
        config = request.config.copy()
        config.update({
            'template': request.template,
            'vcpus': request.vcpus,
            'memory_mb': request.memory_mb
        })
        
        # Create session
        session = await ai_manager.create_session(request.framework, config)
        
        # Get session info
        session_info = await ai_manager.get_session_info(session.session_id)
        return SessionInfo(**session_info)
        
    except Exception as e:
        logger.error(f"Failed to create AI framework session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[SessionInfo])
async def list_sessions(
    security_context: SecurityContext = Depends(check_api_key)
) -> List[SessionInfo]:
    """
    List all active AI framework sessions.
    
    Returns information about all currently running AI framework sessions.
    """
    try:
        sessions = await ai_manager.list_sessions()
        return [SessionInfo(**session) for session in sessions]
        
    except Exception as e:
        logger.error(f"Failed to list AI framework sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=Optional[SessionInfo])
async def get_session(
    session_id: str,
    security_context: SecurityContext = Depends(check_api_key)
) -> Optional[SessionInfo]:
    """
    Get information about a specific session.
    
    Returns detailed information about the AI framework session.
    """
    try:
        session_info = await ai_manager.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        
        return SessionInfo(**session_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, str]:
    """
    Delete an AI framework session.
    
    Terminates the session and cleans up all associated resources.
    """
    try:
        await ai_manager.cleanup_session(session_id)
        return {"status": "success", "message": f"Session {session_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_operation(
    request: FrameworkOperationRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, Any]:
    """
    Execute a framework-specific operation.
    
    Executes operations like creating agents, running chains, or starting conversations
    within the specified AI framework session.
    """
    try:
        result = await ai_manager.execute_framework_operation(
            request.session_id,
            request.operation,
            request.parameters
        )
        
        return {
            "session_id": request.session_id,
            "operation": request.operation,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to execute operation {request.operation}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# LangChain-specific endpoints

@router.post("/langchain/execute-chain")
async def execute_langchain_chain(
    request: LangChainChainRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, Any]:
    """
    Execute a LangChain chain.
    
    Creates and executes a LangChain chain with the specified configuration.
    """
    try:
        # Prepare chain configuration
        chain_config = {
            "llm": request.llm,
            "prompt_template": request.prompt_template,
            "input_variables": request.input_variables,
            "inputs": request.inputs,
            "use_memory": request.use_memory,
            "verbose": request.verbose
        }
        
        # Execute chain
        result = await ai_manager.execute_framework_operation(
            request.session_id,
            "execute_chain",
            chain_config
        )
        
        return {
            "session_id": request.session_id,
            "operation": "execute_chain",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to execute LangChain chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/langchain/create-agent")
async def create_langchain_agent(
    request: LangChainAgentRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, Any]:
    """
    Create a LangChain agent with tools.
    
    Creates an agent with the specified tools and configuration.
    """
    try:
        # Prepare agent configuration
        agent_config = {
            "llm": request.llm,
            "tools": request.tools,
            "agent_type": request.agent_type,
            "verbose": request.verbose
        }
        
        # Create agent
        result = await ai_manager.execute_framework_operation(
            request.session_id,
            "create_agent",
            agent_config
        )
        
        return {
            "session_id": request.session_id,
            "operation": "create_agent",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to create LangChain agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# AutoGen-specific endpoints

@router.post("/autogen/create-system")
async def create_autogen_system(
    request: AutoGenSystemRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, Any]:
    """
    Create an AutoGen multi-agent system.
    
    Creates a system with multiple agents for collaborative conversations.
    """
    try:
        # Prepare system configuration
        system_config = {
            "llm_config": request.llm_config,
            "agents": request.agents,
            "max_rounds": request.max_rounds
        }
        
        # Create system
        result = await ai_manager.execute_framework_operation(
            request.session_id,
            "create_multi_agent_system",
            system_config
        )
        
        return {
            "session_id": request.session_id,
            "operation": "create_multi_agent_system",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to create AutoGen system: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autogen/execute-conversation")
async def execute_autogen_conversation(
    request: AutoGenConversationRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, Any]:
    """
    Execute a conversation between AutoGen agents.
    
    Starts a conversation with the specified initial message and runs
    until completion or maximum turns reached.
    """
    try:
        # Prepare conversation configuration
        conversation_config = {
            "llm_config": request.llm_config,
            "initial_message": request.initial_message,
            "max_turns": request.max_turns
        }
        
        # Execute conversation
        result = await ai_manager.execute_framework_operation(
            request.session_id,
            "execute_conversation",
            conversation_config
        )
        
        return {
            "session_id": request.session_id,
            "operation": "execute_conversation",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to execute AutoGen conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))