import json
from pathlib import Path
import pytest

CONTRACT_PATH = Path(__file__).parents[2] / "contracts" / "GenQMAShield.py"


def test_contract_contains_slashing_and_bond_mechanisms():
    source = CONTRACT_PATH.read_text(encoding="utf-8")
    
    # Verify bond registration and slashes state
    assert "slashes: TreeMap[str, int]" in source
    assert "provider_bonds: TreeMap[str, int]" in source
    assert "def get_provider_slashes(" in source
    assert "def register_provider_bond(" in source
    assert "order[\"slashed\"] = True" in source
    assert "self.slashes[provider_address.lower()] = current_slashes + 1" in source


def test_contract_maintains_safety_rules():
    source = CONTRACT_PATH.read_text(encoding="utf-8")
    
    assert "gl.vm.run_nondet(leader_fn, validator_fn)" in source
    assert "run_nondet_unsafe" not in source
    assert "mock" not in source.lower()
    assert 'verdict = "VALID"' not in source
