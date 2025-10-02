"""
OpenAI Codex integration for intelligent code execution in MicroVM Sandbox.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    print("OpenAI not available. Install with: pip install openai", file=sys.stderr)
    openai = None
    AsyncOpenAI = None

from src.sdk import MicroVMManager
from src.sdk.models import SandboxConfig

logger = logging.getLogger(__name__)


class CodexMicroVMIntegration:
    """
    OpenAI Codex integration for intelligent code execution in MicroVM sandboxes.
    
    Features:
    - Generate code using GPT-4 or Codex models
    - Execute generated code safely in MicroVM sandboxes
    - Analyze errors and generate fixes
    - Generate comprehensive unit tests
    - Multi-language support (Python, JavaScript, Go, etc.)
    """
    
    def __init__(self, api_key: str, sandbox_manager: MicroVMManager, model: str = "gpt-4-turbo"):
        """
        Initialize Codex integration.
        
        Args:
            api_key: OpenAI API key
            sandbox_manager: MicroVM manager instance
            model: OpenAI model to use (gpt-4-turbo, gpt-3.5-turbo, etc.)
        """
        if not openai:
            raise ImportError("OpenAI library not available. Install with: pip install openai")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.sandbox_manager = sandbox_manager
        self.model = model
        
        # Track execution history for context
        self.execution_history: List[Dict[str, Any]] = []
        
        logger.info(f"Codex integration initialized with model: {model}")
    
    async def codex_execute_with_context(
        self, 
        prompt: str, 
        language: str = "python",
        sandbox_name: Optional[str] = None,
        include_tests: bool = False,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Generate and execute code using Codex in MicroVM.
        
        Args:
            prompt: Natural language prompt describing what to code
            language: Programming language (python, javascript, go, etc.)
            sandbox_name: Optional sandbox name (creates new if not provided)
            include_tests: Whether to generate unit tests
            max_retries: Maximum retry attempts on errors
        
        Returns:
            Dict containing generated code, execution results, and metadata
        """
        execution_id = f"codex-{int(datetime.now().timestamp())}"
        
        try:
            # Generate code using Codex
            generated_code = await self._generate_code(prompt, language, include_tests)
            
            # Create or get sandbox
            if not sandbox_name:
                # Create AI agent sandbox for code execution
                config = SandboxConfig(
                    name=f"codex-{execution_id}",
                    template="code-interpreter",
                    vcpus=2,
                    memory_mb=2048
                )
                sandbox = await self.sandbox_manager.start_sandbox(config=config)
                sandbox_name = sandbox.name
                cleanup_sandbox = True
            else:
                sandbox = await self.sandbox_manager.get_sandbox(sandbox_name)
                cleanup_sandbox = False
            
            # Execute generated code with retries
            execution_result = None
            final_code = generated_code
            
            for attempt in range(max_retries + 1):
                try:
                    # Execute in MicroVM sandbox
                    execution_result = await self._execute_code_in_sandbox(
                        sandbox, final_code, language
                    )
                    
                    if execution_result["success"]:
                        break
                    
                    # If failed and we have retries left, try to fix the code
                    if attempt < max_retries:
                        logger.info(f"Execution failed, attempting fix (attempt {attempt + 1})")
                        fixed_code = await self._fix_code_error(
                            final_code, execution_result["error"], language
                        )
                        if fixed_code:
                            final_code = fixed_code
                        else:
                            break
                
                except Exception as e:
                    logger.error(f"Execution attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries:
                        execution_result = {
                            "success": False,
                            "error": str(e),
                            "output": "",
                            "execution_time_ms": 0
                        }
            
            # Generate tests if requested
            test_code = None
            test_result = None
            if include_tests and execution_result.get("success", False):
                test_code = await self._generate_tests(final_code, language)
                if test_code:
                    test_result = await self._execute_code_in_sandbox(
                        sandbox, test_code, language
                    )
            
            # Cleanup sandbox if we created it
            if cleanup_sandbox:
                try:
                    await sandbox.destroy()
                except Exception as e:
                    logger.warning(f"Failed to cleanup sandbox: {e}")
            
            # Build result
            result = {
                "execution_id": execution_id,
                "prompt": prompt,
                "language": language,
                "generated_code": generated_code,
                "final_code": final_code,
                "execution_result": execution_result,
                "model": self.model,
                "sandbox_name": sandbox_name,
                "timestamp": datetime.now().isoformat(),
                "retries_used": max_retries + 1 - (max_retries + 1 - len([r for r in range(max_retries + 1) if execution_result])),
                "success": execution_result.get("success", False) if execution_result else False
            }
            
            # Add test results if generated
            if test_code:
                result.update({
                    "test_code": test_code,
                    "test_result": test_result
                })
            
            # Store in execution history
            self.execution_history.append(result)
            
            return result
        
        except Exception as e:
            logger.error(f"Codex execution failed: {e}")
            return {
                "execution_id": execution_id,
                "prompt": prompt,
                "language": language,
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat()
            }
    
    async def _generate_code(self, prompt: str, language: str, include_tests: bool = False) -> str:
        """Generate code using OpenAI."""
        system_prompt = f"""You are an expert {language} programmer. Generate clean, efficient, and well-documented code.

Guidelines:
1. Write production-quality code with proper error handling
2. Include comments explaining complex logic
3. Follow {language} best practices and conventions
4. Ensure code is safe and doesn't perform dangerous operations
5. Only return the code, no explanations or markdown formatting
6. Don't include imports unless absolutely necessary
"""
        
        if include_tests:
            system_prompt += f"\n7. Include comprehensive unit tests using {language}'s standard testing framework"
        
        # Add context from recent executions
        context = self._build_execution_context()
        if context:
            system_prompt += f"\n\nContext from recent executions:\n{context}"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.1  # Low temperature for more deterministic code
            )
            
            generated_code = response.choices[0].message.content.strip()
            
            # Clean up markdown formatting if present
            if generated_code.startswith("```"):
                lines = generated_code.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                generated_code = '\n'.join(lines)
            
            return generated_code
        
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            raise
    
    async def _execute_code_in_sandbox(self, sandbox, code: str, language: str) -> Dict[str, Any]:
        """Execute code in MicroVM sandbox."""
        try:
            # Build execution command based on language
            if language.lower() == "python":
                # Save code to file and execute
                await sandbox.run_command(f"cat > /tmp/codex_script.py << 'CODEX_EOF'\n{code}\nCODEX_EOF")
                result = await sandbox.run_command("python3 /tmp/codex_script.py", timeout=60)
            
            elif language.lower() == "javascript":
                await sandbox.run_command(f"cat > /tmp/codex_script.js << 'CODEX_EOF'\n{code}\nCODEX_EOF")
                result = await sandbox.run_command("node /tmp/codex_script.js", timeout=60)
            
            elif language.lower() == "go":
                await sandbox.run_command(f"cat > /tmp/codex_script.go << 'CODEX_EOF'\n{code}\nCODEX_EOF")
                result = await sandbox.run_command("cd /tmp && go run codex_script.go", timeout=60)
            
            elif language.lower() == "bash":
                await sandbox.run_command(f"cat > /tmp/codex_script.sh << 'CODEX_EOF'\n{code}\nCODEX_EOF")
                result = await sandbox.run_command("bash /tmp/codex_script.sh", timeout=60)
            
            else:
                # Generic execution
                result = await sandbox.run_command(code, timeout=60)
            
            return {
                "success": result.success,
                "output": result.output,
                "exit_code": result.exit_code,
                "error": result.stderr or result.error,
                "execution_time_ms": result.execution_time_ms
            }
        
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "execution_time_ms": 0
            }
    
    async def _fix_code_error(self, code: str, error: str, language: str) -> Optional[str]:
        """Generate fixed code using error message."""
        fix_prompt = f"""The following {language} code produced an error:

Code:
```{language}
{code}
```

Error:
{error}

Please provide a corrected version of the code that fixes this error. Return only the corrected code without explanations or markdown formatting."""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are an expert {language} debugger. Fix code errors efficiently."},
                    {"role": "user", "content": fix_prompt}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            fixed_code = response.choices[0].message.content.strip()
            
            # Clean up markdown formatting
            if fixed_code.startswith("```"):
                lines = fixed_code.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                fixed_code = '\n'.join(lines)
            
            return fixed_code
        
        except Exception as e:
            logger.error(f"Code fix generation failed: {e}")
            return None
    
    async def _generate_tests(self, code: str, language: str) -> Optional[str]:
        """Generate unit tests for code."""
        test_prompt = f"""Generate comprehensive unit tests for the following {language} code:

```{language}
{code}
```

Requirements:
1. Use the standard testing framework for {language}
2. Test normal cases, edge cases, and error conditions
3. Ensure good test coverage
4. Include setup and teardown if needed
5. Return only the test code without explanations

Test framework to use:
- Python: unittest or pytest
- JavaScript: Jest or Mocha
- Go: testing package
- Other languages: appropriate standard framework"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are an expert {language} test writer. Generate comprehensive tests."},
                    {"role": "user", "content": test_prompt}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            test_code = response.choices[0].message.content.strip()
            
            # Clean up markdown formatting
            if test_code.startswith("```"):
                lines = test_code.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                test_code = '\n'.join(lines)
            
            return test_code
        
        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            return None
    
    def _build_execution_context(self, max_history: int = 3) -> str:
        """Build context from recent successful executions."""
        recent_successes = [
            ex for ex in self.execution_history[-max_history:]
            if ex.get("success", False)
        ]
        
        if not recent_successes:
            return ""
        
        context_parts = []
        for ex in recent_successes:
            context_parts.append(f"Task: {ex['prompt']}")
            context_parts.append(f"Code: {ex['final_code'][:200]}...")
            context_parts.append(f"Result: Success")
            context_parts.append("---")
        
        return "\n".join(context_parts)
    
    async def codex_analyze_and_fix(self, code: str, error: str, language: str = "python") -> Dict[str, Any]:
        """
        Analyze error and generate fixed code using Codex.
        
        This is a standalone method that doesn't require sandbox execution.
        """
        try:
            fixed_code = await self._fix_code_error(code, error, language)
            
            if fixed_code:
                return {
                    "success": True,
                    "original_code": code,
                    "fixed_code": fixed_code,
                    "error": error,
                    "language": language,
                    "model": self.model,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to generate fixed code",
                    "original_code": code,
                    "language": language
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "original_code": code,
                "language": language
            }
    
    async def codex_generate_tests(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Generate unit tests for code using Codex."""
        try:
            test_code = await self._generate_tests(code, language)
            
            if test_code:
                return {
                    "success": True,
                    "original_code": code,
                    "test_code": test_code,
                    "language": language,
                    "model": self.model,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to generate test code",
                    "original_code": code,
                    "language": language
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "original_code": code,
                "language": language
            }
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        return self.execution_history[-limit:] if self.execution_history else []
    
    def clear_execution_history(self):
        """Clear execution history."""
        self.execution_history.clear()
        logger.info("Execution history cleared")