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


class DeliverableEscrow(gl.Contract):
    agreements: TreeMap[u256, Agreement]
    next_id: u256

    def __init__(self):
        self.next_id = u256(0)

    # ================= PUBLIC WRITE METHODS =================

    @gl.public.write.payable
    def create_agreement(self, worker: str, spec: str) -> u256:
        # worker is accepted as a plain hex string and converted to
        # Address internally, per GenLayer's documented pattern.
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
        )

        return agreement_id

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
            return {
                "decision": decision,
                "percent": int(data.get("percent", 0)),
            }

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False

            leader_data = leader_result.calldata
            if leader_data.get("decision") not in ("ACCEPTED", "REJECTED", "PARTIAL"):
                return False

            validator_data = leader_fn()

            # Partial field matching: only the objective "decision" field
            # must match. Percent may vary slightly between validators.
            return leader_data["decision"] == validator_data["decision"]

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        decision = result["decision"]
        percent = result["percent"] if decision == "PARTIAL" else (
            100 if decision == "ACCEPTED" else 0
        )

        agreement.status = decision
        agreement.partial_percent = u256(percent)
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
