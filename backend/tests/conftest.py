"""Shared pytest fixtures for the whole test suite.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the tests/fixtures directory, for tests that need a real file."""
    return FIXTURES_DIR


@pytest.fixture
def sample_sales_xlsx(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_sales.xlsx"


@pytest.fixture
def sample_report_pdf(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_report.pdf"


@pytest.fixture
def sample_sales_extended_xlsx(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_sales_extended.xlsx"


@pytest.fixture
def sample_report_extended_pdf(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_report_extended.pdf"
