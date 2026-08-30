# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json

from genlayer import *
from dataclasses import dataclass


@allow_storage
@dataclass
class Agreement:
    client: Address
    worker: Address
    amount: u256
    spec: str
    deliverable_evidence: str
    status: str
    partial_percent: u256
    settled: bool


class DeliverableEscrow(gl.Contract):
    agreements: TreeMap[u256, Agreement]
    next_id: u256

    def __init__(self):
        self.next_id = u256(0)

    # ================= PUBLIC WRITE METHODS =================

    @gl.public.write.payable
    def create_agreement(self, worker: str, spec: str) -> u256:
        worker_address = Address(worker)
        amount = gl.message.value

        assert amount > 0, "Amount must be greater than zero"
        assert spec.strip() != "", "Spec cannot be empty"

        agreement_id = self.next_id
        self.next_id += u256(1)

        self.agreements[agreement_id] = Agreement(
            client=gl.message.sender_address,
            worker=worker_address,
            amount=u256(amount),
            spec=spec,
            deliverable_evidence="",
            status="PENDING",
            partial_percent=u256(0),
            settled=False,
        )

        return agreement_id

    @gl.public.write
    def cancel_agreement(self, agreement_id: u256):
        # Recovery path: as long as the worker has not submitted anything
        # yet, the client can cancel and reclaim the full deposit. This
        # avoids funds being locked forever if a worker never engages.
        # Note: GenLayer's SDK in this environment has no block timestamp
        # primitive available, so this is a state-based recovery path
        # rather than a time-based timeout. See DECISIONS.md.
        assert agreement_id in self.agreements
        agreement = self.agreements[agreement_id]

        assert gl.message.sender_address == agreement.client, \
            "Only the client can cancel this agreement"
        assert agreement.status == "PENDING", \
            "Agreement can only be cancelled while pending"
        assert agreement.deliverable_evidence.strip() == "", \
            "Cannot cancel after a deliverable has been submitted"
        assert not agreement.settled, "Agreement already settled"

        agreement.status = "CANCELLED"
        agreement.settled = True
        self.agreements[agreement_id] = agreement

        gl.emit_transfer(agreement.client, agreement.amount)

    @gl.public.write
    def submit_deliverable(self, agreement_id: u256, evidence: str):
        assert agreement_id in self.agreements
        agreement = self.agreements[agreement_id]

        assert gl.message.sender_address == agreement.worker, \
            "Only the assigned worker can submit the deliverable"
        assert agreement.status == "PENDING", \
            "Agreement is not in a submittable state"
        assert evidence.strip() != "", "Evidence cannot be empty"

        agreement.deliverable_evidence = evidence
        self.agreements[agreement_id] = agreement

    @gl.public.write
    def evaluate_deliverable(self, agreement_id: u256):
        assert agreement_id in self.agreements
        agreement = self.agreements[agreement_id]

        assert agreement.status == "PENDING", \
            "Agreement already evaluated or not ready"
        assert agreement.deliverable_evidence.strip() != "", \
            "No deliverable submitted yet"

        spec = agreement.spec
        evidence = agreement.deliverable_evidence

        def leader_fn():
            prompt = f"""
            You are an impartial evaluator comparing delivered work
            against an agreed specification.

            Specification:
            {spec}

            Submitted evidence:
            {evidence}

            Respond with ONLY a JSON object in exactly this format,
            and nothing else:
            {{"decision": "ACCEPTED" or "REJECTED" or "PARTIAL", "percent": <integer 0-100>}}

            Rules:
            - ACCEPTED: evidence fully satisfies the spec. percent must be 100.
            - REJECTED: evidence does not meaningfully satisfy the spec. percent must be 0.
            - PARTIAL: evidence satisfies part of the spec. percent is your
              honest estimate (1-99) of how much of the spec was fulfilled.
            """
            response = gl.nondet.exec_prompt(prompt)
            try:
                data = json.loads(response)
            except Exception:
                raise gl.vm.UserError("[LLM_ERROR] validator returned invalid JSON")

            decision = str(data.get("decision", "")).upper()
            if decision not in ("ACCEPTED", "REJECTED", "PARTIAL"):
                raise gl.vm.UserError("[LLM_ERROR] validator returned an invalid decision")
            percent = int(data.get("percent", 0))

            if decision == "ACCEPTED" and percent != 100:
                raise gl.vm.UserError("[LLM_ERROR] ACCEPTED must carry percent 100")
            if decision == "REJECTED" and percent != 0:
                raise gl.vm.UserError("[LLM_ERROR] REJECTED must carry percent 0")
            if decision == "PARTIAL" and not (1 <= percent <= 99):
                raise gl.vm.UserError("[LLM_ERROR] PARTIAL must carry percent between 1 and 99")

            return {
                "decision": decision,
                "percent": percent,
            }

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False

            leader_data = leader_result.calldata
            if leader_data.get("decision") not in ("ACCEPTED", "REJECTED", "PARTIAL"):
                return False

            validator_data = leader_fn()

            return leader_data["decision"] == validator_data["decision"]

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        decision = result["decision"]
        percent = result["percent"]

        if decision == "ACCEPTED":
            assert percent == 100, "Invalid ACCEPTED percent"
        elif decision == "REJECTED":
            assert percent == 0, "Invalid REJECTED percent"
        else:
            assert 1 <= percent <= 99, "Invalid PARTIAL percent"

        agreement.status = decision
        agreement.partial_percent = u256(percent)
        self.agreements[agreement_id] = agreement

    @gl.public.write
    def release_funds(self, agreement_id: u256):
        assert agreement_id in self.agreements
        agreement = self.agreements[agreement_id]

        assert agreement.status in ("ACCEPTED", "REJECTED", "PARTIAL"), \
            "Agreement has not been evaluated yet"
        assert not agreement.settled, "Funds already released for this agreement"

        if agreement.status == "ACCEPTED":
            gl.emit_transfer(agreement.worker, agreement.amount)
        elif agreement.status == "REJECTED":
            gl.emit_transfer(agreement.client, agreement.amount)
        else:
            worker_share = (agreement.amount * agreement.partial_percent) // u256(100)
            client_share = agreement.amount - worker_share
            if worker_share > 0:
                gl.emit_transfer(agreement.worker, worker_share)
            if client_share > 0:
                gl.emit_transfer(agreement.client, client_share)

        agreement.settled = True
        self.agreements[agreement_id] = agreement

    # ================= PUBLIC VIEW METHODS =================

    @gl.public.view
    def get_agreement_status(self, agreement_id: u256) -> str:
        if agreement_id not in self.agreements:
            return "NOT_FOUND"
        return self.agreements[agreement_id].status

    @gl.public.view
    def get_agreement_evidence(self, agreement_id: u256) -> str:
        if agreement_id not in self.agreements:
            return "NOT_FOUND"
        return self.agreements[agreement_id].deliverable_evidence

    @gl.public.view
    def is_settled(self, agreement_id: u256) -> bool:
        if agreement_id not in self.agreements:
            return False
        return self.agreements[agreement_id].settled
