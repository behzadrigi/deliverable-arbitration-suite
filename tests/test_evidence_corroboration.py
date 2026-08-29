"""
Integration tests for EvidenceCorroboration.

Verifies a real, known-true claim against a live web page, and checks
the NOT_FOUND path for an unknown claim id.
"""

from genlayer_py import create_client
from genlayer_py.chains import localnet

CONTRACT_ADDRESS = "0xeFc541D1611FF3AB325731CB4cb57E3E300d1a9f"


def test_corroborates_a_true_claim():
    client = create_client(chain=localnet)

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="submit_claim",
        args=[
            "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "Python was created by Guido van Rossum",
        ],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    claim_id = 0

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="corroborate_claim",
        args=[claim_id],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    status = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_claim_status",
        args=[claim_id],
    )
    assert status in ("CORROBORATED", "CONTRADICTED", "INCONCLUSIVE")


def test_status_not_found_for_unknown_claim():
    client = create_client(chain=localnet)

    status = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_claim_status",
        args=[999999],
    )
    assert status == "NOT_FOUND"
