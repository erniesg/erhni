from __future__ import annotations

from pathlib import Path

import pytest

from erhni.config import load_method, load_sources
from erhni.disclosure import load_disclosure


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def method():
    return load_method(ROOT / "config" / "method.toml")


@pytest.fixture
def sources():
    return load_sources(ROOT / "config" / "sources.toml")


@pytest.fixture
def disclosure():
    return load_disclosure(ROOT / "config" / "disclosure.toml")
