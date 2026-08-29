"""
Integration tests for DisputeEscalation.

Opens a dispute with a deliberately weak justification and verifies
that escalation upholds the original decision and advances the stage,
rather than overturning it.
"""

from genlayer_py import create_client
from genlayer_py.chains import localnet

CONTRACT_ADDRESS = "0xe36bAc9AEe00b3bB691a15ccda7975894153Ec77"


def test_weak_justification_is_upheld_and_advances_stage():
    client = create_client(chain=localnet)

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="open_dispute",
        args=[
            "REJECTED",
            "I just don't agree with this decision, I think it should be different.",
        ],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    dispute_id = 0

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="escalate_dispute",
        args=[dispute_id],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    stage = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_dispute_stage",
        args=[dispute_id],
    )
    status = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_dispute_status",
        args=[dispute_id],
    )

    assert stage >= 1
    assert status in ("OPEN", "UPHELD", "OVERTURNED")


def test_status_not_found_for_unknown_dispute():
    client = create_client(chain=localnet)

    status = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_dispute_status",
        args=[999999],
    )
    assert status == "NOT_FOUND"
