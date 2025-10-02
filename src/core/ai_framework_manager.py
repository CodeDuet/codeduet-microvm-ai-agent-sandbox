"""
AI Framework Manager for LangChain and AutoGen integration.

Provides sandboxed execution environments for AI frameworks with MicroVM isolation.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
import uuid

from src.core.vm_manager import VMManager
from src.core.guest_client import GuestClient
from src.utils.config import get_settings
from src.utils.logging import get_logger
from src.utils.helpers import generate_vm_id

logger = get_logger(__name__)


class AIFrameworkSession:
    """Represents an active AI framework session in a MicroVM."""
    
    def __init__(self, session_id: str, vm_name: str, framework: str, config: Dict[str, Any]):
        self.session_id = session_id
        self.vm_name = vm_name
        self.framework = framework
        self.config = config
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.status = "initializing"
        self.execution_count = 0


class LangChainExecutor:
    """Handles LangChain execution in MicroVM sandboxes."""
    
    def __init__(self, vm_manager: VMManager, guest_client: GuestClient):
        self.vm_manager = vm_manager
        self.guest_client = guest_client
    
    async def create_chain_environment(self, session: AIFrameworkSession) -> Dict[str, Any]:
        """Create LangChain execution environment."""
        setup_script = """
import sys
import json
import asyncio
from pathlib import Path

# Install LangChain if not present
try:
    import langchain
    from langchain.llms import OpenAI
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    from langchain.memory import ConversationBufferMemory
    from langchain.agents import initialize_agent, AgentType
    from langchain.tools import Tool
    from langchain.schema import BaseOutputParser
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "langchain", "openai"])
    import langchain
    from langchain.llms import OpenAI
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    from langchain.memory import ConversationBufferMemory
    from langchain.agents import initialize_agent, AgentType
    from langchain.tools import Tool

# Setup working directory
work_dir = Path("/tmp/langchain_session")
work_dir.mkdir(exist_ok=True)

print(json.dumps({
    "status": "ready",
    "langchain_version": langchain.__version__,
    "work_dir": str(work_dir),
    "python_version": sys.version
}))
"""
        
        result = await self.guest_client.execute_command(
            session.vm_name,
            ["python3", "-c", setup_script]
        )
        
        if result.get("return_code") != 0:
            raise RuntimeError(f"Failed to setup LangChain environment: {result.get('stderr')}")
        
        # Parse setup result
        try:
            setup_info = json.loads(result.get("stdout", "{}"))
            session.status = "ready"
            return setup_info
        except json.JSONDecodeError:
            raise RuntimeError("Invalid setup response from LangChain environment")
    
    async def execute_chain(self, session: AIFrameworkSession, chain_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a LangChain chain."""
        execution_script = f"""
import json
import sys
from pathlib import Path

# Configure LangChain
chain_config = {json.dumps(chain_config)}

try:
    from langchain.llms import OpenAI
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    from langchain.memory import ConversationBufferMemory
    
    # Initialize LLM
    llm_config = chain_config.get('llm', {{}})
    llm = OpenAI(
        temperature=llm_config.get('temperature', 0.7),
        max_tokens=llm_config.get('max_tokens', 1000),
        model_name=llm_config.get('model', 'text-davinci-003')
    )
    
    # Create prompt template
    prompt_template = PromptTemplate(
        input_variables=chain_config.get('input_variables', ['input']),
        template=chain_config.get('prompt_template', '{{input}}')
    )
    
    # Setup memory if requested
    memory = None
    if chain_config.get('use_memory', False):
        memory = ConversationBufferMemory()
    
    # Create chain
    chain = LLMChain(
        llm=llm,
        prompt=prompt_template,
        memory=memory,
        verbose=chain_config.get('verbose', False)
    )
    
    # Execute chain
    inputs = chain_config.get('inputs', {{}})
    result = chain.run(**inputs)
    
    print(json.dumps({{
        "status": "success",
        "result": result,
        "memory": str(memory.buffer) if memory else None
    }}))
    
except Exception as e:
    print(json.dumps({{
        "status": "error",
        "error": str(e),
        "error_type": type(e).__name__
    }}))
    sys.exit(1)
"""
        
        result = await self.guest_client.execute_command(
            session.vm_name,
            ["python3", "-c", execution_script]
        )
        
        session.execution_count += 1
        session.last_activity = datetime.now()
        
        # Parse execution result
        try:
            return json.loads(result.get("stdout", "{}"))
        except json.JSONDecodeError:
            return {
                "status": "error",
                "error": "Invalid execution response",
                "raw_output": result.get("stdout"),
                "stderr": result.get("stderr")
            }
    
    async def create_agent(self, session: AIFrameworkSession, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a LangChain agent with tools."""
        agent_script = f"""
import json
import sys
from pathlib import Path

agent_config = {json.dumps(agent_config)}

try:
    from langchain.llms import OpenAI
    from langchain.agents import initialize_agent, AgentType, Tool
    from langchain.memory import ConversationBufferMemory
    
    # Initialize LLM
    llm_config = agent_config.get('llm', {{}})
    llm = OpenAI(
        temperature=llm_config.get('temperature', 0.7),
        max_tokens=llm_config.get('max_tokens', 1000)
    )
    
    # Define tools
    tools = []
    for tool_config in agent_config.get('tools', []):
        if tool_config['name'] == 'python_repl':
            from langchain.tools import PythonREPLTool
            tools.append(PythonREPLTool())
        elif tool_config['name'] == 'shell':
            from langchain.tools import ShellTool
            tools.append(ShellTool())
        elif tool_config['name'] == 'file_management':
            # Custom file management tool
            def read_file(filename):
                try:
                    with open(filename, 'r') as f:
                        return f.read()
                except Exception as e:
                    return f"Error reading file: {{e}}"
            
            def write_file(filename, content):
                try:
                    with open(filename, 'w') as f:
                        f.write(content)
                    return f"File {{filename}} written successfully"
                except Exception as e:
                    return f"Error writing file: {{e}}"
            
            tools.extend([
                Tool(name="read_file", description="Read a file", func=read_file),
                Tool(name="write_file", description="Write content to a file", func=write_file)
            ])
    
    # Setup memory
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    # Create agent
    agent_type = getattr(AgentType, agent_config.get('agent_type', 'ZERO_SHOT_REACT_DESCRIPTION'))
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=agent_type,
        memory=memory,
        verbose=agent_config.get('verbose', False)
    )
    
    print(json.dumps({{
        "status": "success",
        "agent_type": str(agent_type),
        "tools": [tool.name for tool in tools],
        "memory_enabled": True
    }}))
    
except Exception as e:
    print(json.dumps({{
        "status": "error",
        "error": str(e),
        "error_type": type(e).__name__
    }}))
    sys.exit(1)
"""
        
        result = await self.guest_client.execute_command(
            session.vm_name,
            ["python3", "-c", agent_script]
        )
        
        # Parse result
        try:
            return json.loads(result.get("stdout", "{}"))
        except json.JSONDecodeError:
            return {
                "status": "error",
                "error": "Invalid agent creation response",
                "raw_output": result.get("stdout"),
                "stderr": result.get("stderr")
            }


class AutoGenExecutor:
    """Handles AutoGen multi-agent execution in MicroVM sandboxes."""
    
    def __init__(self, vm_manager: VMManager, guest_client: GuestClient):
        self.vm_manager = vm_manager
        self.guest_client = guest_client
    
    async def create_autogen_environment(self, session: AIFrameworkSession) -> Dict[str, Any]:
        """Create AutoGen execution environment."""
        setup_script = """
import sys
import json
import asyncio
from pathlib import Path

# Install AutoGen if not present
try:
    import autogen
    from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyautogen"])
    import autogen
    from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# Setup working directory
work_dir = Path("/tmp/autogen_session")
work_dir.mkdir(exist_ok=True)

print(json.dumps({
    "status": "ready",
    "autogen_version": autogen.__version__,
    "work_dir": str(work_dir),
    "python_version": sys.version
}))
"""
        
        result = await self.guest_client.execute_command(
            session.vm_name,
            ["python3", "-c", setup_script]
        )
        
        if result.get("return_code") != 0:
            raise RuntimeError(f"Failed to setup AutoGen environment: {result.get('stderr')}")
        
        # Parse setup result
        try:
            setup_info = json.loads(result.get("stdout", "{}"))
            session.status = "ready"
            return setup_info
        except json.JSONDecodeError:
            raise RuntimeError("Invalid setup response from AutoGen environment")
    
    async def create_multi_agent_system(self, session: AIFrameworkSession, agents_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a multi-agent system with AutoGen."""
        system_script = f"""
import json
import sys
import tempfile
from pathlib import Path

agents_config = {json.dumps(agents_config)}

try:
    from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
    
    # Create agents
    agents = []
    agent_info = []
    
    # Common LLM config
    llm_config = agents_config.get('llm_config', {{
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "timeout": 60,
        "seed": 42
    }})
    
    for agent_config in agents_config.get('agents', []):
        agent_type = agent_config.get('type', 'assistant')
        
        if agent_type == 'assistant':
            agent = AssistantAgent(
                name=agent_config['name'],
                system_message=agent_config.get('system_message', 'You are a helpful assistant.'),
                llm_config=llm_config
            )
        elif agent_type == 'user_proxy':
            agent = UserProxyAgent(
                name=agent_config['name'],
                system_message=agent_config.get('system_message', 'You are a user proxy agent.'),
                human_input_mode=agent_config.get('human_input_mode', 'NEVER'),
                max_consecutive_auto_reply=agent_config.get('max_auto_reply', 10),
                code_execution_config=agent_config.get('code_execution_config', {{
                    "work_dir": "/tmp/autogen_code",
                    "use_docker": False
                }})
            )
        
        agents.append(agent)
        agent_info.append({{
            "name": agent.name,
            "type": agent_type,
            "system_message": agent.system_message
        }})
    
    # Create group chat if multiple agents
    if len(agents) > 2:
        groupchat = GroupChat(
            agents=agents,
            messages=[],
            max_round=agents_config.get('max_rounds', 10)
        )
        
        manager = GroupChatManager(
            groupchat=groupchat,
            llm_config=llm_config
        )
        
        print(json.dumps({{
            "status": "success",
            "system_type": "group_chat",
            "agents": agent_info,
            "max_rounds": groupchat.max_round
        }}))
    else:
        print(json.dumps({{
            "status": "success",
            "system_type": "two_agent",
            "agents": agent_info
        }}))
    
except Exception as e:
    print(json.dumps({{
        "status": "error",
        "error": str(e),
        "error_type": type(e).__name__
    }}))
    sys.exit(1)
"""
        
        result = await self.guest_client.execute_command(
            session.vm_name,
            ["python3", "-c", system_script]
        )
        
        # Parse result
        try:
            return json.loads(result.get("stdout", "{}"))
        except json.JSONDecodeError:
            return {
                "status": "error",
                "error": "Invalid system creation response",
                "raw_output": result.get("stdout"),
                "stderr": result.get("stderr")
            }
    
    async def execute_conversation(self, session: AIFrameworkSession, conversation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a conversation between agents."""
        conversation_script = f"""
import json
import sys
from pathlib import Path

conversation_config = {json.dumps(conversation_config)}

try:
    from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
    
    # Recreate agents (simplified for execution)
    llm_config = conversation_config.get('llm_config', {{}})
    
    # Get initial message
    initial_message = conversation_config.get('initial_message', 'Hello!')
    
    # Create simple two-agent conversation for demo
    assistant = AssistantAgent(
        name="assistant",
        system_message="You are a helpful AI assistant.",
        llm_config=llm_config
    )
    
    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=conversation_config.get('max_turns', 5),
        code_execution_config={{"work_dir": "/tmp", "use_docker": False}}
    )
    
    # Start conversation
    chat_result = user_proxy.initiate_chat(
        assistant,
        message=initial_message
    )
    
    # Extract conversation history
    messages = []
    if hasattr(chat_result, 'chat_history'):
        for msg in chat_result.chat_history:
            messages.append({{
                "role": msg.get("role", "unknown"),
                "content": msg.get("content", ""),
                "name": msg.get("name", "")
            }})
    
    print(json.dumps({{
        "status": "success",
        "messages": messages,
        "total_turns": len(messages)
    }}))
    
except Exception as e:
    print(json.dumps({{
        "status": "error",
        "error": str(e),
        "error_type": type(e).__name__
    }}))
    sys.exit(1)
"""
        
        result = await self.guest_client.execute_command(
            session.vm_name,
            ["python3", "-c", conversation_script]
        )
        
        session.execution_count += 1
        session.last_activity = datetime.now()
        
        # Parse result
        try:
            return json.loads(result.get("stdout", "{}"))
        except json.JSONDecodeError:
            return {
                "status": "error",
                "error": "Invalid conversation response",
                "raw_output": result.get("stdout"),
                "stderr": result.get("stderr")
            }


class AIFrameworkManager:
    """
    Manages AI framework execution in MicroVM sandboxes.
    
    Provides isolated environments for LangChain, AutoGen, and other AI frameworks
    with proper resource management and security isolation.
    """
    
    def __init__(self, vm_manager: VMManager):
        self.vm_manager = vm_manager
        self.sessions: Dict[str, AIFrameworkSession] = {}
        self.settings = get_settings()
        
        logger.info("AI Framework Manager initialized")
    
    async def create_session(self, framework: str, config: Dict[str, Any]) -> AIFrameworkSession:
        """
        Create a new AI framework session.
        
        Args:
            framework: Framework name ('langchain', 'autogen')
            config: Framework-specific configuration
            
        Returns:
            AIFrameworkSession object
        """
        session_id = str(uuid.uuid4())
        vm_name = f"ai-{framework}-{session_id[:8]}"
        
        logger.info(f"Creating {framework} session: {session_id}")
        
        # Determine VM template based on framework
        template = config.get('template')
        if not template:
            if framework.lower() == 'langchain':
                template = 'ai-agent'
            elif framework.lower() == 'autogen':
                template = 'ai-agent'  # Use same template for now
            else:
                template = 'linux-default'
        
        # Create VM for the session
        from src.api.models.vm import VMCreateRequest, OSType
        vm_request = VMCreateRequest(
            name=vm_name,
            template=template,
            os_type=OSType.LINUX,
            vcpus=config.get('vcpus', 4),
            memory_mb=config.get('memory_mb', 4096),
            guest_agent=True,
            metadata={
                'framework': framework,
                'session_id': session_id,
                'created_by': 'ai_framework_manager'
            }
        )
        
        # Create and start VM
        vm_info = await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Create session
        session = AIFrameworkSession(session_id, vm_name, framework, config)
        self.sessions[session_id] = session
        
        # Initialize framework-specific environment
        guest_client = GuestClient()
        
        try:
            if framework.lower() == 'langchain':
                executor = LangChainExecutor(self.vm_manager, guest_client)
                setup_info = await executor.create_chain_environment(session)
            elif framework.lower() == 'autogen':
                executor = AutoGenExecutor(self.vm_manager, guest_client)
                setup_info = await executor.create_autogen_environment(session)
            else:
                raise ValueError(f"Unsupported framework: {framework}")
            
            session.status = "ready"
            logger.info(f"AI framework session {session_id} created successfully")
            
        except Exception as e:
            # Cleanup on failure
            await self.cleanup_session(session_id)
            raise RuntimeError(f"Failed to initialize {framework} environment: {e}")
        
        return session
    
    async def execute_framework_operation(self, session_id: str, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an operation in an AI framework session.
        
        Args:
            session_id: Session identifier
            operation: Operation name
            params: Operation parameters
            
        Returns:
            Operation result
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")
        
        session = self.sessions[session_id]
        guest_client = GuestClient()
        
        try:
            if session.framework.lower() == 'langchain':
                executor = LangChainExecutor(self.vm_manager, guest_client)
                
                if operation == 'execute_chain':
                    return await executor.execute_chain(session, params)
                elif operation == 'create_agent':
                    return await executor.create_agent(session, params)
                else:
                    raise ValueError(f"Unknown LangChain operation: {operation}")
            
            elif session.framework.lower() == 'autogen':
                executor = AutoGenExecutor(self.vm_manager, guest_client)
                
                if operation == 'create_multi_agent_system':
                    return await executor.create_multi_agent_system(session, params)
                elif operation == 'execute_conversation':
                    return await executor.execute_conversation(session, params)
                else:
                    raise ValueError(f"Unknown AutoGen operation: {operation}")
            
            else:
                raise ValueError(f"Unsupported framework: {session.framework}")
                
        except Exception as e:
            logger.error(f"Framework operation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session."""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        vm_info = await self.vm_manager.get_vm(session.vm_name)
        
        return {
            "session_id": session.session_id,
            "vm_name": session.vm_name,
            "framework": session.framework,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "execution_count": session.execution_count,
            "vm_status": vm_info.state.value if vm_info else "unknown",
            "config": session.config
        }
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        sessions = []
        for session_id in list(self.sessions.keys()):
            info = await self.get_session_info(session_id)
            if info:
                sessions.append(info)
        return sessions
    
    async def cleanup_session(self, session_id: str) -> None:
        """Cleanup a session and its resources."""
        if session_id not in self.sessions:
            logger.warning(f"Session not found for cleanup: {session_id}")
            return
        
        session = self.sessions[session_id]
        logger.info(f"Cleaning up AI framework session: {session_id}")
        
        try:
            # Stop and delete VM
            await self.vm_manager.stop_vm(session.vm_name)
            await self.vm_manager.delete_vm(session.vm_name)
            
            # Remove session
            del self.sessions[session_id]
            
            logger.info(f"Session {session_id} cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")
            raise
    
    async def cleanup_all_sessions(self) -> None:
        """Cleanup all active sessions."""
        logger.info("Cleaning up all AI framework sessions")
        
        for session_id in list(self.sessions.keys()):
            try:
                await self.cleanup_session(session_id)
            except Exception as e:
                logger.warning(f"Error cleaning up session {session_id}: {e}")
        
        logger.info("AI framework cleanup complete")