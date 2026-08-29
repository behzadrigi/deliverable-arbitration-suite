"""
Integration tests for ReputationLedger.

Records a SUCCESS outcome for a party and verifies the counter
increments deterministically, with no LLM or consensus involved.
"""

from genlayer_py import create_client
from genlayer_py.chains import localnet

CONTRACT_ADDRESS = "0x57e3F975084C881f9dD5FF66156dD777Df69d912"
PARTY_ADDRESS = "0x69d353B9178e357Ce28FD1678486A7BcCf2d65C8"


def test_record_outcome_increments_success_count():
    client = create_client(chain=localnet)

    before = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_successes",
        args=[PARTY_ADDRESS],
    )

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="record_outcome",
        args=[PARTY_ADDRESS, "SUCCESS"],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    after = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_successes",
        args=[PARTY_ADDRESS],
    )

    assert after == before + 1


def test_zero_counts_for_unknown_party():
    client = create_client(chain=localnet)

    unknown_party = "0x0000000000000000000000000000000000000001"
    successes = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_successes",
        args=[unknown_party],
    )
    assert successes == 0
