"""
Integration tests for DeliverableEscrow.

These tests connect to the already-deployed contract instance on
GenLayer Studio (localnet) and exercise the full agreement lifecycle:
create -> submit -> evaluate -> read status.
"""

from genlayer_py import create_client
from genlayer_py.chains import localnet

CONTRACT_ADDRESS = "0xE380ADc9FD2da4bC1991d02F82D2E9E3748a6b00"


def test_full_agreement_lifecycle():
    client = create_client(chain=localnet)

    worker_address = "0x69d353B9178e357Ce28FD1678486A7BcCf2d65C8"
    spec = "Build a landing page with a working contact form and responsive design."

    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="create_agreement",
        args=[worker_address, spec],
        value=10,
    )
    receipt = client.wait_for_transaction_receipt(hash=tx_hash)
    assert receipt is not None

    agreement_id = 0  # returned by create_agreement in this test run

    evidence = (
        "Landing page deployed at example.com with a working contact form "
        "that sends emails via SMTP, and fully responsive layout tested on "
        "mobile and desktop."
    )
    tx_hash = client.write_contract(
        address=CONTRACT_ADDRESS,
        function_name="submit_deliverable",
        args=[agreement_id, evidence],
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


def test_status_not_found_for_unknown_agreement():
    client = create_client(chain=localnet)

    status = client.read_contract(
        address=CONTRACT_ADDRESS,
        function_name="get_agreement_status",
        args=[999999],
    )
    assert status == "NOT_FOUND"
