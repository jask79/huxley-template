"""
Backend Dev agentic loop integration.

Implements autonomous backend development with feedback iteration for:
- API endpoint development
- Database schema and queries
- Type checking and validation
- Testing and deployment
"""

import asyncio
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loop_executor import FoundationLoopExecutor, LoopResult
from remediation.backend_skills import seed_backend_skills
from remediation.skill_library import get_library


@dataclass
class BackendTask:
    """Backend development task specification."""

    description: str
    api_file: str | None = None  # Main API file to implement
    model_file: str | None = None  # Database models file
    test_file: str | None = None  # Test file
    validation_tools: list[str] = None  # Tools to validate with

    def __post_init__(self):
        """Set default validation tools if not provided."""
        if self.validation_tools is None:
            self.validation_tools = ["pytest", "mypy", "ruff"]


class BackendDevLoop:
    """
    Backend development agentic loop.

    Implements autonomous iteration for backend development:
    1. Execute implementation task
    2. Validate with pytest, mypy, ruff, API health checks
    3. Normalize feedback from tools
    4. Apply remediation skills
    5. Iterate until success or escalation
    """

    def __init__(self, project_root: str, max_iterations: int = 5, verbose: bool = False):
        """
        Initialize backend dev loop.

        Args:
            project_root: Root directory of the project
            max_iterations: Maximum iterations before escalation
            verbose: Whether to print detailed output
        """
        self.project_root = Path(project_root)
        self.verbose = verbose

        # Initialize foundation loop executor
        self.executor = FoundationLoopExecutor(
            agent_name="Backend Dev",
            max_iterations=max_iterations,
            use_state_isolation=False,  # Backend work modifies files directly
        )

        # Ensure backend skills are loaded
        library = get_library()
        if not any(s.skill_id.startswith("fix_sqlalchemy") for s in library.list_skills()):
            seed_backend_skills(library)

    def build_api(self, task: BackendTask) -> LoopResult:
        """
        Build API endpoint with autonomous iteration.

        Args:
            task: Backend task specification

        Returns:
            LoopResult with success status and feedback
        """
        print(f"🔨 Building API: {task.description}")

        # Create trace for learning
        self.executor.create_trace(
            task_description=task.description,
            initial_error="Starting implementation",
            error_category="build_error",
        )

        # Define execution function (placeholder - actual implementation would be LLM-driven)
        def execute_implementation(task_spec: dict[str, Any]) -> bool:
            """Execute the implementation step."""
            # In real implementation, this would:
            # 1. Analyze requirements from task_spec
            # 2. Generate code using LLM
            # 3. Write files using Write/Edit tools
            # 4. Return True if implementation successful
            print("  → Implementing task...")
            return True

        # Define validation function
        def validate_implementation() -> tuple[str, dict[str, Any]]:
            """Validate implementation with configured tools."""
            results = {}

            for tool in task.validation_tools:
                print(f"  → Running {tool}...")
                result = self._run_validation_tool(tool, task)
                results[tool] = result

            # Return primary tool name and combined results
            return task.validation_tools[0], results

        # Define success criteria
        criteria = {f"{tool}_passed": False for tool in task.validation_tools}

        # Run the loop
        result = self.executor.execute_loop(
            task={"description": task.description, "spec": task},
            execute_fn=execute_implementation,
            validate_fn=validate_implementation,
            criteria=criteria,
        )

        self._print_result(result)
        return result

    def _run_validation_tool(self, tool: str, task: BackendTask) -> dict[str, Any]:
        """
        Run a validation tool and return raw output.

        Args:
            tool: Tool name (pytest, mypy, ruff, api_test)
            task: Backend task with file paths

        Returns:
            Dictionary with exit_code, stdout, stderr
        """
        try:
            if tool == "pytest":
                cmd = ["pytest", "-v"]
                if task.test_file:
                    cmd.append(str(self.project_root / task.test_file))
                else:
                    cmd.append("tests/")

            elif tool == "mypy":
                cmd = ["mypy"]
                if task.api_file:
                    cmd.append(str(self.project_root / task.api_file))
                else:
                    cmd.append(".")

            elif tool == "ruff":
                cmd = ["ruff", "check"]
                if task.api_file:
                    cmd.append(str(self.project_root / task.api_file))
                else:
                    cmd.append(".")

            elif tool == "api_test":
                # Custom API health check
                cmd = ["pytest", "-v", "-k", "test_api_health"]

            else:
                raise ValueError(f"Unknown validation tool: {tool}")

            # Run tool
            process = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True, text=True, timeout=60
            )

            return {
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }

        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": f"{tool} timed out after 60 seconds"}
        except FileNotFoundError:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"{tool} not found. Install with: pip install {tool}",
            }
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": f"Error running {tool}: {str(e)}"}

    def _print_result(self, result: LoopResult) -> None:
        """Print loop result summary."""
        if result.success:
            print(f"\n✅ Success after {result.iterations} iteration(s)")
            print(f"   Execution time: {result.execution_time:.2f}s")
        else:
            print(f"\n❌ Failed after {result.iterations} iteration(s)")
            print(f"   Reason: {result.escalation_reason}")
            if result.final_feedback:
                primary_error = result.final_feedback.get_primary_error()
                if primary_error:
                    print(f"   Error: {primary_error.message}")

    async def build_api_async(self, task: BackendTask) -> LoopResult:
        """Async version of build_api for concurrent operations."""
        return await asyncio.to_thread(self.build_api, task)

    def batch_build(self, tasks: list[BackendTask]) -> list[LoopResult]:
        """
        Build multiple API endpoints in sequence.

        Args:
            tasks: List of backend tasks

        Returns:
            List of LoopResults
        """
        results = []
        for i, task in enumerate(tasks, 1):
            print(f"\n📦 Task {i}/{len(tasks)}")
            result = self.build_api(task)
            results.append(result)

            # Stop if any task fails
            if not result.success:
                print(f"\n⚠️  Stopping batch: Task {i} failed")
                break

        return results


# Example usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backend Dev Agentic Loop")
    parser.add_argument("--project", required=True, help="Project root directory")
    parser.add_argument("--description", required=True, help="Task description")
    parser.add_argument("--api-file", help="API file to implement")
    parser.add_argument("--model-file", help="Model file")
    parser.add_argument("--test-file", help="Test file")
    parser.add_argument(
        "--tools", nargs="+", default=["pytest", "mypy", "ruff"], help="Validation tools to use"
    )
    parser.add_argument("--max-iterations", type=int, default=5, help="Maximum iterations")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Create task
    task = BackendTask(
        description=args.description,
        api_file=args.api_file,
        model_file=args.model_file,
        test_file=args.test_file,
        validation_tools=args.tools,
    )

    # Run loop
    loop = BackendDevLoop(
        project_root=args.project, max_iterations=args.max_iterations, verbose=args.verbose
    )

    result = loop.build_api(task)

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)
