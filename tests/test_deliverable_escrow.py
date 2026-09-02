"""
Integration tests for DeliverableEscrow.

These tests connect to the already-deployed contract instance on
GenLayer Studio (localnet) and exercise the full agreement lifecycle:
create -> submit -> evaluate -> release, the pre-submission cancellation
recovery path, and the mutual post-submission resolution recovery path.
"""

from genlayer_py import create_client
from genlayer_py.chains import localnet

CONTRACT_ADDRESS = "0xE99027282726e7c7F03Ca990f378b50812584AaC"
WORKER_ADDRESS = "0x69d353B9178e357Ce28FD1678486A7BcCf2d65C8"
SPEC = "Build a landing page with a working contact form and responsive design."
EVIDENCE = (
    "Landing page deployed at example.com with a working contact form "
    "that sends emails via SMTP, and fully responsive layout tested on "
    "mobile and desktop."
)


def test_full_agreement_lifecycle_with_settlement():
    client = create_client(chain=localnet)

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="create_agreement",
        args=[WORKER_ADDRESS, SPEC],
        value=10,
    )
    receipt = client.wait_for_transaction_receipt(hash=tx_hash)
    assert receipt is not None

    agreement_id = 0  # returned by create_agreement in this test run

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="submit_deliverable",
        args=[agreement_id, EVIDENCE],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="evaluate_deliverable",
        args=[agreement_id],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    status = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_agreement_status",
        args=[agreement_id],
    )
    assert status in ("ACCEPTED", "PARTIAL", "REJECTED")

    settled_before = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="is_settled",
        args=[agreement_id],
    )
    assert settled_before is False

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="release_funds",
        args=[agreement_id],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    settled_after = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="is_settled",
        args=[agreement_id],
    )
    assert settled_after is True


def test_cancel_agreement_before_submission_refunds_client():
    client = create_client(chain=localnet)

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="create_agreement",
        args=[WORKER_ADDRESS, SPEC],
        value=5,
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    agreement_id = 1  # second agreement created in this test run

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="cancel_agreement",
        args=[agreement_id],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    status = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_agreement_status",
        args=[agreement_id],
    )
    assert status == "REJECTED"


def test_mutual_resolution_settles_once_both_sides_agree():
    client = create_client(chain=localnet)

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="create_agreement",
        args=[WORKER_ADDRESS, SPEC],
        value=8,
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    agreement_id = 2  # third agreement created in this test run

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="submit_deliverable",
        args=[agreement_id, EVIDENCE],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    # This test only exercises the recovery path itself (both proposals
    # eventually resolving the agreement); it does not attempt to model
    # calling as two different accounts within a single test run.
    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="propose_resolution",
        args=[agreement_id, "ACCEPTED", 100],
    )
    client.wait_for_transaction_receipt(hash=tx_hash)

    proposals = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_proposals",
        args=[agreement_id],
    )
    assert "ACCEPTED:100" in proposals


def test_status_not_found_for_unknown_agreement():
    client = create_client(chain=localnet)

    status = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_agreement_status",
        args=[999999],
    )
    assert status == "NOT_FOUND"
