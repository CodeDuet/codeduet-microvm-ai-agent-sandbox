# AI Frameworks Integration Guide

This guide covers how to use LangChain, AutoGen, and other AI frameworks in isolated MicroVM environments for safe AI development and execution.

## Overview

The MicroVM Sandbox provides dedicated support for popular AI frameworks:

- **LangChain** - Building applications with Large Language Models
- **AutoGen** - Multi-agent conversational AI systems
- **Custom AI Workflows** - Isolated environments for AI experimentation

Each framework runs in its own MicroVM with proper resource isolation and security controls.

## LangChain Integration

### Creating a LangChain Session

```python
import requests

# Create LangChain session
response = requests.post(
    "http://localhost:8000/api/v1/ai-frameworks/sessions",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "framework": "langchain",
        "template": "ai-agent",
        "vcpus": 4,
        "memory_mb": 4096,
        "config": {
            "environment_variables": {
                "OPENAI_API_KEY": "your-openai-key"
            }
        }
    }
)

session = response.json()
session_id = session["session_id"]
print(f"LangChain session created: {session_id}")
```

### Executing LangChain Chains

```python
# Execute a simple chain
chain_response = requests.post(
    "http://localhost:8000/api/v1/ai-frameworks/langchain/execute-chain",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "session_id": session_id,
        "prompt_template": "Translate the following text to {language}: {text}",
        "input_variables": ["language", "text"],
        "inputs": {
            "language": "French",
            "text": "Hello, how are you?"
        },
        "llm": {
            "model": "gpt-3.5-turbo",
            "temperature": 0.7
        }
    }
)

result = chain_response.json()
print(f"Translation: {result['result']}")
```

### Creating LangChain Agents

```python
# Create an agent with tools
agent_response = requests.post(
    "http://localhost:8000/api/v1/ai-frameworks/langchain/create-agent",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "session_id": session_id,
        "tools": [
            {
                "name": "python_repl",
                "description": "Execute Python code"
            },
            {
                "name": "file_management", 
                "description": "Read and write files"
            }
        ],
        "agent_type": "ZERO_SHOT_REACT_DESCRIPTION",
        "llm": {
            "model": "gpt-4",
            "temperature": 0.1
        }
    }
)

agent_result = agent_response.json()
print(f"Agent created: {agent_result}")
```

### Advanced LangChain Workflows

```python
# Complex chain with memory
complex_chain = requests.post(
    "http://localhost:8000/api/v1/ai-frameworks/langchain/execute-chain",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "session_id": session_id,
        "prompt_template": """
        You are a helpful coding assistant. Use the conversation history to provide context.
        
        Previous conversation: {chat_history}
        Human: {human_input}
        AI: """,
        "input_variables": ["chat_history", "human_input"],
        "inputs": {
            "human_input": "Can you write a Python function to calculate fibonacci numbers?"
        },
        "use_memory": True,
        "verbose": True
    }
)

print(complex_chain.json())
```

## AutoGen Integration

### Creating Multi-Agent Systems

```python
# Create AutoGen session
autogen_response = requests.post(
    "http://localhost:8000/api/v1/ai-frameworks/sessions",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "framework": "autogen",
        "template": "ai-agent",
        "vcpus": 6,
        "memory_mb": 8192,
        "config": {
            "environment_variables": {
                "OPENAI_API_KEY": "your-openai-key"
            }
        }
    }
)

autogen_session_id = autogen_response.json()["session_id"]
```

### Defining Agents

```python
# Create multi-agent system
system_response = requests.post(
    "http://localhost:8000/api/v1/ai-frameworks/autogen/create-system",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "session_id": autogen_session_id,
        "llm_config": {
            "model": "gpt-4",
            "temperature": 0.7,
            "timeout": 60
        },
        "agents": [
            {
                "name": "product_manager",
                "type": "assistant",
                "system_message": "You are a product manager who defines requirements and priorities."
            },
            {
                "name": "engineer",
                "type": "assistant", 
                "system_message": "You are a software engineer who implements solutions."
            },
            {
                "name": "code_executor",
                "type": "user_proxy",
                "system_message": "You execute code and provide feedback.",
                "human_input_mode": "NEVER",
                "max_auto_reply": 10,
                "code_execution_config": {
                    "work_dir": "/tmp/autogen_code",
                    "use_docker": False
                }
            }
        ],
        "max_rounds": 15
    }
)

print(f"Multi-agent system created: {system_response.json()}")
```

### Running Agent Conversations

```python
# Start a conversation between agents
conversation_response = requests.post(
    "http://localhost:8000/api/v1/ai-frameworks/autogen/execute-conversation",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "session_id": autogen_session_id,
        "initial_message": """
        We need to build a web scraper that can extract product information 
        from e-commerce websites. The scraper should be respectful of robots.txt 
        and include rate limiting. Please collaborate to design and implement this.
        """,
        "max_turns": 10
    }
)

conversation = conversation_response.json()
for message in conversation["result"]["messages"]:
    print(f"{message['name']}: {message['content'][:200]}...")
```

## SDK Integration

### Using the Python SDK

```python
from src.sdk import MicroVMManager, SecurityContext

# Initialize manager
security_context = SecurityContext(api_token="your_token")
manager = MicroVMManager(
    api_url="http://localhost:8000",
    security_context=security_context
)

# Create AI framework session through SDK
async def create_ai_session():
    # This would be implemented in the SDK
    session = await manager.create_ai_session(
        framework="langchain",
        config={
            "vcpus": 4,
            "memory_mb": 4096,
            "template": "ai-agent"
        }
    )
    return session
```

## MCP Tools for AI Frameworks

### Available MCP Tools

The MCP server provides specialized tools for AI framework workflows:

```json
{
  "tool": "create_langchain_session",
  "arguments": {
    "vcpus": 4,
    "memory_mb": 4096
  }
}

{
  "tool": "execute_langchain", 
  "arguments": {
    "session_id": "session-123",
    "operation": "execute_chain",
    "config": {
      "prompt_template": "Summarize: {text}",
      "input_variables": ["text"],
      "inputs": {"text": "Long article content..."}
    }
  }
}

{
  "tool": "create_autogen_session",
  "arguments": {
    "vcpus": 6,
    "memory_mb": 8192
  }
}

{
  "tool": "execute_autogen",
  "arguments": {
    "session_id": "autogen-456", 
    "operation": "start_conversation",
    "config": {
      "initial_message": "Let's solve this problem together",
      "max_rounds": 10
    }
  }
}
```

## Custom AI Workflows

### Creating Custom Environments

```python
# Create custom AI sandbox
custom_response = requests.post(
    "http://localhost:8000/api/v1/vms",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "name": "custom-ai-env",
        "template": "ai-agent",
        "vcpus": 8,
        "memory_mb": 16384,
        "metadata": {
            "purpose": "custom-ai-research",
            "frameworks": ["transformers", "pytorch", "tensorflow"]
        }
    }
)

# Install additional packages
install_response = requests.post(
    "http://localhost:8000/api/v1/guest/execute",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "vm_name": "custom-ai-env",
        "command": "pip install transformers torch datasets accelerate",
        "timeout": 300
    }
)
```

### Running Custom AI Code

```python
# Execute custom AI workflow
ai_code = """
import torch
from transformers import AutoTokenizer, AutoModel

# Load a pre-trained model
tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
model = AutoModel.from_pretrained('bert-base-uncased')

# Example inference
text = "Hello, this is a test of BERT embeddings"
inputs = tokenizer(text, return_tensors='pt')
outputs = model(**inputs)

print(f"Embeddings shape: {outputs.last_hidden_state.shape}")
print(f"Pooled output shape: {outputs.pooler_output.shape}")
"""

code_response = requests.post(
    "http://localhost:8000/api/v1/guest/execute",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "vm_name": "custom-ai-env",
        "command": f"python3 -c '{ai_code}'",
        "timeout": 120
    }
)

print(code_response.json())
```

## Security and Isolation

### Framework Isolation

Each AI framework session runs in its own MicroVM with:

- **Process isolation** - Complete separation from host system
- **Network isolation** - Controlled network access
- **Resource limits** - CPU and memory constraints
- **File system isolation** - Sandboxed file access

### API Key Security

```python
# Secure API key handling
session_config = {
    "framework": "langchain",
    "config": {
        "environment_variables": {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            # Keys are isolated within the VM
        },
        "security": {
            "network_restrictions": ["api.openai.com"],
            "file_access": "restricted"
        }
    }
}
```

### Resource Management

```python
# Monitor resource usage
metrics_response = requests.get(
    f"http://localhost:8000/api/v1/ai-frameworks/sessions/{session_id}",
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

session_info = metrics_response.json()
print(f"CPU usage: {session_info.get('cpu_percent', 'N/A')}%")
print(f"Memory usage: {session_info.get('memory_percent', 'N/A')}%")
```

## Best Practices

### Performance Optimization

1. **Right-size Resources**
   ```python
   # For LangChain: 4 vCPUs, 4GB RAM
   # For AutoGen: 6 vCPUs, 8GB RAM
   # For Custom ML: 8+ vCPUs, 16GB+ RAM
   ```

2. **Session Management**
   ```python
   # Clean up sessions when done
   requests.delete(
       f"http://localhost:8000/api/v1/ai-frameworks/sessions/{session_id}",
       headers={"Authorization": "Bearer YOUR_TOKEN"}
   )
   ```

3. **Error Handling**
   ```python
   try:
       result = requests.post(endpoint, json=payload)
       result.raise_for_status()
   except requests.exceptions.RequestException as e:
       print(f"AI framework operation failed: {e}")
   ```

### Development Workflow

1. **Start with Templates** - Use pre-configured AI templates
2. **Iterative Development** - Test code in isolated environments
3. **Resource Monitoring** - Watch CPU/memory usage
4. **Session Cleanup** - Always clean up when done
5. **Error Recovery** - Handle framework-specific errors

### Integration Patterns

1. **Chain Multiple Operations** - Build complex workflows
2. **Use Snapshots** - Save progress at key points
3. **Monitor Outputs** - Log all AI framework interactions
4. **Scale Resources** - Adjust based on workload

This provides a secure, scalable platform for AI framework development and experimentation with proper isolation and resource management.