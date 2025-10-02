#!/usr/bin/env python3
"""
AI Framework Integration Examples

Demonstrates how to use LangChain and AutoGen in isolated MicroVM environments
for safe AI development and experimentation.
"""

import asyncio
import json
import os
from typing import Dict, Any, List

import httpx


class AIFrameworkExamples:
    """Example class demonstrating AI framework integrations."""
    
    def __init__(self, api_url: str = "http://localhost:8000", api_token: str = None):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        self.client = httpx.AsyncClient()
        
    async def langchain_basic_example(self) -> None:
        """Demonstrate basic LangChain usage."""
        print("🦜 LangChain Basic Example")
        print("=" * 40)
        
        # Create LangChain session
        session_response = await self.client.post(
            f"{self.api_url}/api/v1/ai-frameworks/sessions",
            headers=self.headers,
            json={
                "framework": "langchain",
                "template": "ai-agent",
                "vcpus": 4,
                "memory_mb": 4096,
                "config": {
                    "environment_variables": {
                        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "demo-key")
                    }
                }
            }
        )
        session_response.raise_for_status()
        session = session_response.json()
        session_id = session["session_id"]
        
        print(f"✅ Created LangChain session: {session_id}")
        
        try:
            # Example 1: Simple text generation chain
            print("\n📝 Example 1: Text Generation Chain")
            
            chain_response = await self.client.post(
                f"{self.api_url}/api/v1/ai-frameworks/langchain/execute-chain",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "prompt_template": "Write a short {style} about {topic}:",
                    "input_variables": ["style", "topic"],
                    "inputs": {
                        "style": "haiku",
                        "topic": "artificial intelligence"
                    },
                    "llm": {
                        "model": "gpt-3.5-turbo",
                        "temperature": 0.8,
                        "max_tokens": 100
                    }
                }
            )
            chain_response.raise_for_status()
            result = chain_response.json()
            print(f"Result: {result['result']}")
            
            # Example 2: Conversational chain with memory
            print("\n💭 Example 2: Conversational Chain with Memory")
            
            conversation_response = await self.client.post(
                f"{self.api_url}/api/v1/ai-frameworks/langchain/execute-chain",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "prompt_template": """
                    You are a helpful programming assistant. Use the conversation history for context.
                    
                    Chat History: {chat_history}
                    Human: {human_input}
                    Assistant: """,
                    "input_variables": ["chat_history", "human_input"],
                    "inputs": {
                        "human_input": "How do I implement a binary search algorithm?"
                    },
                    "use_memory": True,
                    "verbose": True
                }
            )
            conversation_response.raise_for_status()
            conv_result = conversation_response.json()
            print(f"Assistant Response: {conv_result['result']}")
            
            # Example 3: Code analysis chain
            print("\n🔍 Example 3: Code Analysis Chain")
            
            code_to_analyze = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
            
            analysis_response = await self.client.post(
                f"{self.api_url}/api/v1/ai-frameworks/langchain/execute-chain",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "prompt_template": """
                    Analyze this code and provide insights:
                    
                    Code:
                    {code}
                    
                    Please provide:
                    1. What the code does
                    2. Time complexity
                    3. Potential improvements
                    4. Any bugs or issues
                    """,
                    "input_variables": ["code"],
                    "inputs": {"code": code_to_analyze},
                    "llm": {
                        "model": "gpt-4",
                        "temperature": 0.2
                    }
                }
            )
            analysis_response.raise_for_status()
            analysis_result = analysis_response.json()
            print(f"Code Analysis: {analysis_result['result']}")
            
        finally:
            # Cleanup session
            await self.client.delete(
                f"{self.api_url}/api/v1/ai-frameworks/sessions/{session_id}",
                headers=self.headers
            )
            print(f"🧹 Cleaned up session: {session_id}")
    
    async def langchain_agent_example(self) -> None:
        """Demonstrate LangChain agent with tools."""
        print("\n🤖 LangChain Agent Example")
        print("=" * 40)
        
        # Create session
        session_response = await self.client.post(
            f"{self.api_url}/api/v1/ai-frameworks/sessions",
            headers=self.headers,
            json={
                "framework": "langchain",
                "template": "ai-agent",
                "vcpus": 4,
                "memory_mb": 4096
            }
        )
        session_response.raise_for_status()
        session_id = session_response.json()["session_id"]
        
        try:
            # Create agent with tools
            print("🛠️  Creating agent with tools...")
            
            agent_response = await self.client.post(
                f"{self.api_url}/api/v1/ai-frameworks/langchain/create-agent",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "tools": [
                        {
                            "name": "python_repl",
                            "description": "Execute Python code and return results"
                        },
                        {
                            "name": "file_management",
                            "description": "Read and write files on the system"
                        }
                    ],
                    "agent_type": "ZERO_SHOT_REACT_DESCRIPTION",
                    "llm": {
                        "model": "gpt-4",
                        "temperature": 0.1
                    },
                    "verbose": True
                }
            )
            agent_response.raise_for_status()
            agent_result = agent_response.json()
            print(f"✅ Agent created: {agent_result}")
            
        finally:
            await self.client.delete(
                f"{self.api_url}/api/v1/ai-frameworks/sessions/{session_id}",
                headers=self.headers
            )
    
    async def autogen_basic_example(self) -> None:
        """Demonstrate basic AutoGen multi-agent system."""
        print("\n👥 AutoGen Multi-Agent Example")
        print("=" * 40)
        
        # Create AutoGen session
        session_response = await self.client.post(
            f"{self.api_url}/api/v1/ai-frameworks/sessions",
            headers=self.headers,
            json={
                "framework": "autogen",
                "template": "ai-agent",
                "vcpus": 6,
                "memory_mb": 8192,
                "config": {
                    "environment_variables": {
                        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "demo-key")
                    }
                }
            }
        )
        session_response.raise_for_status()
        session_id = session_response.json()["session_id"]
        
        print(f"✅ Created AutoGen session: {session_id}")
        
        try:
            # Create multi-agent system
            print("\n🏗️  Creating multi-agent system...")
            
            system_response = await self.client.post(
                f"{self.api_url}/api/v1/ai-frameworks/autogen/create-system",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "llm_config": {
                        "model": "gpt-4",
                        "temperature": 0.7,
                        "timeout": 60
                    },
                    "agents": [
                        {
                            "name": "product_manager",
                            "type": "assistant",
                            "system_message": """You are a senior product manager with expertise in defining 
                            technical requirements and prioritizing features. You focus on user needs, 
                            business value, and feasibility."""
                        },
                        {
                            "name": "software_engineer",
                            "type": "assistant",
                            "system_message": """You are an experienced software engineer who designs and 
                            implements solutions. You focus on code quality, performance, and maintainability. 
                            You can write code and explain technical concepts."""
                        },
                        {
                            "name": "qa_engineer",
                            "type": "assistant",
                            "system_message": """You are a quality assurance engineer who ensures software 
                            quality through testing strategies, test cases, and identifying potential issues. 
                            You focus on edge cases and user experience."""
                        },
                        {
                            "name": "code_executor",
                            "type": "user_proxy",
                            "system_message": """You execute code and provide feedback on results. 
                            You can run tests and validate implementations.""",
                            "human_input_mode": "NEVER",
                            "max_auto_reply": 10,
                            "code_execution_config": {
                                "work_dir": "/tmp/autogen_project",
                                "use_docker": False
                            }
                        }
                    ],
                    "max_rounds": 20
                }
            )
            system_response.raise_for_status()
            system_result = system_response.json()
            print(f"✅ Multi-agent system created: {system_result}")
            
            # Start collaborative conversation
            print("\n💬 Starting collaborative conversation...")
            
            conversation_response = await self.client.post(
                f"{self.api_url}/api/v1/ai-frameworks/autogen/execute-conversation",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "initial_message": """
                    We need to build a simple web-based todo list application. The requirements are:
                    
                    1. Users can add, edit, and delete todo items
                    2. Items can be marked as completed
                    3. Data should persist between sessions
                    4. Clean, responsive user interface
                    5. Basic error handling
                    
                    Please collaborate to:
                    1. Define detailed requirements and architecture
                    2. Implement the solution
                    3. Create test cases and validate the implementation
                    
                    Let's start by discussing the technical approach and breaking down the work.
                    """,
                    "max_turns": 15
                }
            )
            conversation_response.raise_for_status()
            conversation_result = conversation_response.json()
            
            print("\n📋 Conversation Summary:")
            print(f"Status: {conversation_result['result']['status']}")
            
            if conversation_result['result']['status'] == 'success':
                messages = conversation_result['result']['messages']
                print(f"Total messages exchanged: {len(messages)}")
                
                # Show summary of conversation
                for i, message in enumerate(messages[:6]):  # Show first 6 messages
                    print(f"\n{i+1}. {message.get('name', 'Unknown')}: {message.get('content', '')[:200]}...")
                
                if len(messages) > 6:
                    print(f"\n... and {len(messages) - 6} more messages")
            
        finally:
            # Cleanup session
            await self.client.delete(
                f"{self.api_url}/api/v1/ai-frameworks/sessions/{session_id}",
                headers=self.headers
            )
            print(f"\n🧹 Cleaned up session: {session_id}")
    
    async def autogen_code_review_example(self) -> None:
        """Demonstrate AutoGen for code review workflow."""
        print("\n👀 AutoGen Code Review Example")
        print("=" * 40)
        
        # Create session
        session_response = await self.client.post(
            f"{self.api_url}/api/v1/ai-frameworks/sessions",
            headers=self.headers,
            json={
                "framework": "autogen",
                "vcpus": 6,
                "memory_mb": 8192
            }
        )
        session_response.raise_for_status()
        session_id = session_response.json()["session_id"]
        
        try:
            # Create code review agents
            system_response = await self.client.post(
                f"{self.api_url}/api/v1/ai-frameworks/autogen/create-system",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "agents": [
                        {
                            "name": "senior_developer",
                            "type": "assistant",
                            "system_message": """You are a senior developer responsible for code review. 
                            Focus on code quality, best practices, security, and maintainability."""
                        },
                        {
                            "name": "security_specialist",
                            "type": "assistant",
                            "system_message": """You are a security specialist who reviews code for 
                            security vulnerabilities, authentication issues, and data protection concerns."""
                        },
                        {
                            "name": "performance_expert",
                            "type": "assistant",
                            "system_message": """You are a performance expert who reviews code for 
                            efficiency, scalability, and optimization opportunities."""
                        }
                    ],
                    "max_rounds": 12
                }
            )
            system_response.raise_for_status()
            
            # Submit code for review
            code_to_review = """
def user_login(username, password):
    import sqlite3
    
    # Connect to database
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Check user credentials
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    cursor.execute(query)
    user = cursor.fetchone()
    
    conn.close()
    
    if user:
        return {"success": True, "user_id": user[0], "role": user[3]}
    else:
        return {"success": False, "message": "Invalid credentials"}

def get_user_data(user_id):
    import sqlite3
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    query = f"SELECT * FROM user_data WHERE user_id = {user_id}"
    cursor.execute(query)
    data = cursor.fetchall()
    
    conn.close()
    return data
"""
            
            conversation_response = await self.client.post(
                f"{self.api_url}/api/v1/ai-frameworks/autogen/execute-conversation",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "initial_message": f"""
                    Please review this code for security, performance, and quality issues:
                    
                    ```python
                    {code_to_review}
                    ```
                    
                    Each specialist should provide their analysis and recommendations.
                    """,
                    "max_turns": 10
                }
            )
            conversation_response.raise_for_status()
            
            print("✅ Code review completed by multi-agent team")
            
        finally:
            await self.client.delete(
                f"{self.api_url}/api/v1/ai-frameworks/sessions/{session_id}",
                headers=self.headers
            )
    
    async def custom_ai_workflow_example(self) -> None:
        """Demonstrate custom AI workflow with mixed frameworks."""
        print("\n🔬 Custom AI Workflow Example")
        print("=" * 40)
        
        # This example shows how to combine multiple AI frameworks
        # and custom code in isolated environments
        
        print("🏗️  Setting up custom AI environment...")
        
        # Create custom VM
        vm_response = await self.client.post(
            f"{self.api_url}/api/v1/vms",
            headers=self.headers,
            json={
                "name": "custom-ai-workflow",
                "template": "ai-agent",
                "vcpus": 8,
                "memory_mb": 16384,
                "metadata": {
                    "purpose": "custom-ai-research",
                    "frameworks": ["transformers", "langchain", "autogen"]
                }
            }
        )
        vm_response.raise_for_status()
        vm_name = vm_response.json()["name"]
        
        try:
            # Start VM
            await self.client.post(
                f"{self.api_url}/api/v1/vms/{vm_name}/start",
                headers=self.headers
            )
            
            print("⏳ Waiting for VM to initialize...")
            await asyncio.sleep(20)
            
            # Install additional packages
            print("📦 Installing additional AI packages...")
            
            install_response = await self.client.post(
                f"{self.api_url}/api/v1/guest/execute",
                headers=self.headers,
                json={
                    "vm_name": vm_name,
                    "command": "pip install transformers torch datasets accelerate",
                    "timeout": 300
                }
            )
            install_response.raise_for_status()
            
            # Run custom AI workflow
            print("🤖 Running custom AI workflow...")
            
            ai_workflow_code = """
import torch
from transformers import pipeline
import json

# Create a sentiment analysis pipeline
sentiment_analyzer = pipeline("sentiment-analysis")

# Sample texts to analyze
texts = [
    "I love this new AI framework integration!",
    "The MicroVM isolation is really impressive.",
    "This could revolutionize AI development workflows.",
    "I'm not sure about the performance implications.",
    "Security isolation for AI workloads is crucial."
]

# Analyze sentiments
results = []
for text in texts:
    result = sentiment_analyzer(text)
    results.append({
        "text": text,
        "sentiment": result[0]["label"],
        "confidence": result[0]["score"]
    })

# Output results
print("Sentiment Analysis Results:")
print("=" * 50)
for result in results:
    print(f"Text: {result['text']}")
    print(f"Sentiment: {result['sentiment']} (confidence: {result['confidence']:.3f})")
    print("-" * 30)

# Save results
with open("/tmp/sentiment_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Results saved to /tmp/sentiment_results.json")
"""
            
            execution_response = await self.client.post(
                f"{self.api_url}/api/v1/guest/execute",
                headers=self.headers,
                json={
                    "vm_name": vm_name,
                    "command": f"python3 -c '{ai_workflow_code}'",
                    "timeout": 180
                }
            )
            execution_response.raise_for_status()
            
            exec_result = execution_response.json()
            print("✅ Custom AI workflow completed:")
            print(exec_result.get("stdout", "No output"))
            
            # Download results
            download_response = await self.client.post(
                f"{self.api_url}/api/v1/guest/download",
                headers=self.headers,
                json={
                    "vm_name": vm_name,
                    "remote_path": "/tmp/sentiment_results.json",
                    "encoding": "text"
                }
            )
            
            if download_response.status_code == 200:
                results_data = download_response.json()
                print("📄 Analysis results:")
                print(results_data.get("content", "No content"))
            
        finally:
            # Cleanup
            await self.client.delete(
                f"{self.api_url}/api/v1/vms/{vm_name}",
                headers=self.headers
            )
            print(f"🧹 Cleaned up VM: {vm_name}")
    
    async def run_all_examples(self) -> None:
        """Run all AI framework examples."""
        print("🚀 AI Framework Integration Examples")
        print("=" * 50)
        
        try:
            # Check if OpenAI API key is available
            if not os.getenv("OPENAI_API_KEY"):
                print("⚠️  Warning: OPENAI_API_KEY not set. Some examples may use demo mode.")
            
            # Run examples
            await self.langchain_basic_example()
            await asyncio.sleep(2)
            
            await self.langchain_agent_example()
            await asyncio.sleep(2)
            
            await self.autogen_basic_example()
            await asyncio.sleep(2)
            
            await self.autogen_code_review_example()
            await asyncio.sleep(2)
            
            await self.custom_ai_workflow_example()
            
            print("\n✅ All AI framework examples completed successfully!")
            
        except Exception as e:
            print(f"❌ Examples failed: {e}")
            raise
        finally:
            await self.client.aclose()


async def main():
    """Main function to run AI framework examples."""
    api_token = os.getenv("MICROVM_API_TOKEN")
    if not api_token:
        print("⚠️  Warning: No API token found. Set MICROVM_API_TOKEN environment variable.")
    
    examples = AIFrameworkExamples(api_token=api_token)
    await examples.run_all_examples()


if __name__ == "__main__":
    asyncio.run(main())