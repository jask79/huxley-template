"""
Frontend Dev agentic loop - autonomous component building with feedback iteration.

Integrates with FoundationLoopExecutor to provide frontend-specific validation,
remediation, and iteration strategies.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import subprocess
from typing import Any

from core.loop_executor import FoundationLoopExecutor, LoopResult
from remediation.frontend_skills import seed_frontend_skills


class FrontendDevLoop:
    """
    Frontend Dev-specific agentic loop for autonomous component development.

    Workflow:
    1. Execute task (build component)
    2. Validate with: npm build, vitest, tsc, eslint
    3. Normalize feedback from all tools
    4. Apply frontend-specific remediation skills
    5. Iterate until all validations pass
    """

    def __init__(
        self, project_dir: str, max_iterations: int = 8, enable_state_isolation: bool = False
    ):
        """
        Initialize frontend dev loop.

        Args:
            project_dir: Project root directory
            max_iterations: Maximum iterations before escalation
            enable_state_isolation: Use isolated temp directories
        """
        self.project_dir = Path(project_dir)
        self.max_iterations = max_iterations

        # Initialize foundation loop executor
        self.executor = FoundationLoopExecutor(
            agent_name="Frontend Dev",
            max_iterations=max_iterations,
            use_state_isolation=enable_state_isolation,
        )

        # Seed frontend skills into library
        seed_frontend_skills(self.executor.skill_library)

        # Track validation results across iterations
        self.validation_history: list[dict[str, bool]] = []

    def build_component(self, task: dict[str, Any]) -> LoopResult:
        """
        Build component with autonomous iteration until success.

        Args:
            task: Task definition with keys:
                - description: Human-readable task description
                - component_path: Path to component file (relative to project_dir)
                - test_path: Optional path to test file
                - requirements: List of requirements (builds, tests, types, lint)

        Returns:
            LoopResult with success/failure and iteration details
        """
        # Create trace for learning
        self.executor.create_trace(
            task_description=task["description"],
            initial_error="Starting component build",
            error_category="build_start",
        )

        # Define execute function
        def execute_fn(task_data: dict[str, Any]) -> bool:
            """
            Execute the component build task.

            For Phase 1 pilot, this is a placeholder that returns False
            to trigger validation. In production, this would call the actual
            component generation/modification code.
            """
            # In production, this would:
            # 1. Generate/modify component code based on task
            # 2. Apply any pending remediation instructions
            # 3. Return True if modifications were successful

            # For now, just return False to proceed to validation
            return False

        # Define validate function
        def validate_fn() -> tuple:
            """
            Validate component with multiple tools.

            Returns:
                Tuple of (tool_name, raw_output_dict)
            """
            validation_results = self._run_all_validations(task)

            # Return the first failing validation, or last validation if all pass
            for tool, result in validation_results.items():
                if result["exit_code"] != 0:
                    return tool, result

            # All validations passed - return last one
            last_tool = list(validation_results.keys())[-1]
            return last_tool, validation_results[last_tool]

        # Define success criteria
        requirements = task.get("requirements", ["build", "test", "types", "lint"])
        criteria = {req: False for req in requirements}

        # Execute loop
        result = self.executor.execute_loop(
            task=task, execute_fn=execute_fn, validate_fn=validate_fn, criteria=criteria
        )

        return result

    def _run_all_validations(self, task: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """
        Run all validation tools and return results.

        Args:
            task: Task definition

        Returns:
            Dict mapping tool name to raw output
        """
        results = {}

        requirements = task.get("requirements", ["build", "test", "types", "lint"])

        # 1. TypeScript compilation (if required)
        if "types" in requirements:
            results["tsc"] = self._run_tsc(task)

        # 2. Build (if required)
        if "build" in requirements:
            results["build"] = self._run_build(task)

        # 3. Tests (if required)
        if "test" in requirements:
            results["vitest"] = self._run_vitest(task)

        # 4. Linting (if required)
        if "lint" in requirements:
            results["eslint"] = self._run_eslint(task)

        return results

    def _run_tsc(self, task: dict[str, Any]) -> dict[str, Any]:
        """Run TypeScript compiler."""
        try:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit", "--pretty", "false"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tool": "tsc",
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "TypeScript compilation timed out after 60 seconds",
                "tool": "tsc",
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Failed to run tsc: {str(e)}",
                "tool": "tsc",
            }

    def _run_build(self, task: dict[str, Any]) -> dict[str, Any]:
        """Run build command."""
        try:
            # Detect build command (next build, vite build, etc.)
            build_cmd = self._detect_build_command()

            result = subprocess.run(
                build_cmd, cwd=self.project_dir, capture_output=True, text=True, timeout=120
            )

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tool": "build",
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "Build timed out after 120 seconds",
                "tool": "build",
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Failed to run build: {str(e)}",
                "tool": "build",
            }

    def _run_vitest(self, task: dict[str, Any]) -> dict[str, Any]:
        """Run Vitest tests."""
        try:
            # Determine which tests to run
            test_path = task.get("test_path")
            cmd = ["npx", "vitest", "run"]

            if test_path:
                cmd.append(test_path)

            result = subprocess.run(
                cmd, cwd=self.project_dir, capture_output=True, text=True, timeout=60
            )

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tool": "vitest",
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "Tests timed out after 60 seconds",
                "tool": "vitest",
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Failed to run vitest: {str(e)}",
                "tool": "vitest",
            }

    def _run_eslint(self, task: dict[str, Any]) -> dict[str, Any]:
        """Run ESLint."""
        try:
            component_path = task.get("component_path", "")

            result = subprocess.run(
                ["npx", "eslint", component_path or ".", "--format=json"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tool": "eslint",
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "ESLint timed out after 30 seconds",
                "tool": "eslint",
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Failed to run eslint: {str(e)}",
                "tool": "eslint",
            }

    def _detect_build_command(self) -> list[str]:
        """
        Detect build command from package.json.

        Returns:
            Build command as list
        """
        package_json_path = self.project_dir / "package.json"

        if not package_json_path.exists():
            # Default to next build
            return ["npm", "run", "build"]

        try:
            with open(package_json_path) as f:
                package_data = json.load(f)

            scripts = package_data.get("scripts", {})

            # Check for common build scripts
            if "build" in scripts:
                return ["npm", "run", "build"]
            elif "vite:build" in scripts:
                return ["npm", "run", "vite:build"]
            elif "next:build" in scripts:
                return ["npm", "run", "next:build"]
            else:
                # Default
                return ["npm", "run", "build"]

        except Exception:
            # Fallback
            return ["npm", "run", "build"]

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about loop performance.

        Returns:
            Dict with iteration stats, skill usage, success rate
        """
        skill_stats = self.executor.skill_library.get_stats()

        return {
            "total_iterations": self.executor.adaptive_limits.iterations_completed,
            "max_iterations": self.max_iterations,
            "skill_library_stats": skill_stats,
            "validation_history": self.validation_history,
        }

    def reset(self) -> None:
        """Reset loop state for new task."""
        self.validation_history = []
        self.executor.adaptive_limits.reset()
        self.executor.stuck_detector.reset()
        self.executor.current_trace = None


def main():
    """Example usage of FrontendDevLoop."""

    # Example: Build a Button component
    loop = FrontendDevLoop(project_dir="/path/to/your/project", max_iterations=8)

    task = {
        "description": "Build accessible Button component with primary/secondary variants",
        "component_path": "src/components/Button.tsx",
        "test_path": "src/components/Button.test.tsx",
        "requirements": ["types", "build", "test", "lint"],
    }

    result = loop.build_component(task)

    print(f"✅ Success: {result.success}")
    print(f"🔄 Iterations: {result.iterations}")
    print(f"⏱️  Time: {result.execution_time:.2f}s")

    if result.escalation_triggered:
        print(f"⚠️  Escalated: {result.escalation_reason}")

    # Get stats
    stats = loop.get_stats()
    print("\n📊 Stats:")
    print(f"  - Total skills: {stats['skill_library_stats']['total_skills']}")
    print(f"  - Avg success rate: {stats['skill_library_stats']['avg_success_rate']:.1%}")


if __name__ == "__main__":
    main()
