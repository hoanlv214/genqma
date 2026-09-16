from pathlib import Path


CONTRACT_PATH = Path(__file__).parents[2] / "contracts" / "GenQMAShield.py"


def test_contract_has_studio_compatible_header_and_single_contract_class():
    source = CONTRACT_PATH.read_text(encoding="utf-8")

    assert source.splitlines()[0].startswith('# { "Depends": "py-genlayer:')
    assert (
        source.count("class Contract(gl.contract.Contract):") == 1
        or source.count("class Contract(gl.Contract):") == 1
    )
    assert "class GenQMAShield" not in source


def test_contract_uses_safe_consensus_without_mock_or_unsafe_fallback():
    source = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "gl.vm.run_nondet(leader_fn, validator_fn)" in source
    assert "run_nondet_unsafe" not in source
    assert "simulate_hallucination" not in source
    assert "mock" not in source.lower()
    assert 'verdict = "VALID"' not in source
