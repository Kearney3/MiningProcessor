"""Shared test fixtures for MiningProcessor test suite."""
import pytest
import pandas as pd
from pathlib import Path


@pytest.fixture
def sample_equipment_ledger():
    """Create a minimal EquipmentLedger for testing."""
    from func.equipment_ledger import EquipmentLedger
    ledger = EquipmentLedger()
    # Add a minimal in-memory ledger for tests that don't need file I/O
    return ledger


@pytest.fixture
def sample_excel_fuel(tmp_path):
    """Create a minimal fuel Excel file for testing."""
    df = pd.DataFrame({
        0: ["日期", "2025-01-15", "2025-01-16"],
        1: ["设备名称", "矿卡-001", "矿卡-002"],
        2: ["白班柴油(L)", 150.5, 200.0],
        3: ["夜班柴油(L)", 80.0, 120.5],
    })
    path = tmp_path / "test_fuel.xlsx"
    df.to_excel(path, sheet_name="设备柴油消耗", index=False, header=False)
    return path


@pytest.fixture
def sample_excel_electrical(tmp_path):
    """Create a minimal electrical Excel file for testing."""
    df = pd.DataFrame({
        0: ["日期", "2025-01-15"],
        1: ["设备名称", "挖掘机-001"],
        2: ["白班电量(kWh)", 500.0],
    })
    path = tmp_path / "test_electrical.xlsx"
    df.to_excel(path, sheet_name="Electrical", index=False, header=False)
    return path
