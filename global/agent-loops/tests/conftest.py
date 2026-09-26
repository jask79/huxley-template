"""
Pytest configuration and fixtures for agent-loops tests.

Uses real local embeddings from sentence-transformers.
"""

from unittest.mock import Mock

import pytest


@pytest.fixture
def temp_skill_storage(tmp_path):
    """Provide temporary storage path for skill library tests."""
    storage_file = tmp_path / "test_skills.json"
    return str(storage_file)


@pytest.fixture
def mock_subprocess_success():
    """Mock subprocess.run for successful command execution."""
    mock_process = Mock()
    mock_process.returncode = 0
    mock_process.stdout = "Success"
    mock_process.stderr = ""

    with patch("subprocess.run", return_value=mock_process) as mock:
        yield mock


@pytest.fixture
def mock_subprocess_failure():
    """Mock subprocess.run for failed command execution."""
    mock_process = Mock()
    mock_process.returncode = 1
    mock_process.stdout = ""
    mock_process.stderr = "Error occurred"

    with patch("subprocess.run", return_value=mock_process) as mock:
        yield mock
