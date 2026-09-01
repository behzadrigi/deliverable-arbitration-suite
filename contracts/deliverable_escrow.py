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
    client_proposal: str
    worker_proposal: str


def _validate_decision_percent(decision: str, percent: int):
    if decision == "ACCEPTED":
        assert percent == 100, "ACCEPTED must carry percent 100"
    elif decision == "REJECTED":
        assert percent == 0, "REJECTED must carry percent 0"
    elif decision == "PARTIAL":
        assert percent in (25, 50, 75), "PARTIAL percent must be exactly 25, 50, or 75"
    else:
        assert False, "invalid decision: " + decision


class DeliverableEscrow(gl.Contract):
    agreements: TreeMap[u256, Agreement]
    next_id: u256

    def __init__(self):
        self.next_id = u256(0)

    # ================= CREATION / SUBMISSION / PRE-SUBMISSION CANCEL =================

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
            client_proposal="",
            worker_proposal="",
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
        agreement.status = "SUBMITTED"
        self.agreements[agreement_id] = agreement

    @gl.public.write
    def cancel_agreement(self, agreement_id: u256):
        assert agreement_id in self.agreements
        agreement = self.agreements[agreement_id]

        assert gl.message.sender_address == agreement.client, \
            "Only the client can cancel this agreement"
        assert agreement.status == "PENDING", \
            "Agreement can only be cancelled while pending"
        assert not agreement.settled, "Agreement already settled"

        agreement.status = "REJECTED"
        agreement.partial_percent = u256(0)
        self.agreements[agreement_id] = agreement

        self.release_funds(agreement_id)

    # ================= POST-SUBMISSION RECOVERY (MUTUAL RESOLUTION) =================

    @gl.public.write
    def propose_resolution(self, agreement_id: u256, decision: str, percent: u256):
        assert agreement_id in self.agreements
        agreement = self.agreements[agreement_id]

        assert agreement.status == "SUBMITTED", \
            "Agreement is not awaiting resolution"

        decision_upper = decision.upper()
        _validate_decision_percent(decision_upper, int(percent))

        sender = gl.message.sender_address
        is_client = sender == agreement.client
        is_worker = sender == agreement.worker
        assert is_client or is_worker, \
            "Only the client or worker on this agreement can propose a resolution"

        proposal = decision_upper + ":" + str(int(percent))

        if is_client:
            agreement.client_proposal = proposal
        else:
            agreement.worker_proposal = proposal

        self.agreements[agreement_id] = agreement

        if (
            agreement.client_proposal != ""
            and agreement.client_proposal == agreement.worker_proposal
        ):
            agreement.status = decision_upper
            agreement.partial_percent = percent
            self.agreements[agreement_id] = agreement
            self.release_funds(agreement_id)

    # ================= LLM-JUDGED EVALUATION (PRIMARY PATH) =================

    @gl.public.write
    def evaluate_deliverable(self, agreement_id: u256):
        assert agreement_id in self.agreements
        agreement = self.agreements[agreement_id]

        assert agreement.status == "SUBMITTED", \
            "Agreement is not awaiting evaluation"

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
            {{"decision": "ACCEPTED" or "REJECTED" or "PARTIAL", "percent": <integer>}}

            Rules:
            - ACCEPTED: evidence fully satisfies the spec. percent must be exactly 100.
            - REJECTED: evidence does not meaningfully satisfy the spec. percent must be exactly 0.
            - PARTIAL: evidence satisfies part of the spec. percent must be
              exactly one of 25, 50, or 75 (pick the closest match). Do not
              use any other percent value for PARTIAL.
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

            try:
                _validate_decision_percent(decision, percent)
            except AssertionError:
                raise gl.vm.UserError("[LLM_ERROR] invalid decision/percent combination")

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

            return (
                leader_data.get("decision") == validator_data.get("decision")
                and leader_data.get("percent") == validator_data.get("percent")
            )

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        decision = result["decision"]
        percent = u256(result["percent"])

        _validate_decision_percent(decision, int(percent))

        agreement.status = decision
        agreement.partial_percent = percent
        self.agreements[agreement_id] = agreement

        self.release_funds(agreement_id)

    # ================= SETTLEMENT =================

    @gl.public.write
    def release_funds(self, agreement_id: u256):
        assert agreement_id in self.agreements
        agreement = self.agreements[agreement_id]

        assert agreement.status in ("ACCEPTED", "REJECTED", "PARTIAL"), \
            "Agreement has not reached a final decision yet"

        if agreement.settled:
            return

        agreement.settled = True
        self.agreements[agreement_id] = agreement

        payment = int(agreement.amount)
        percent = int(agreement.partial_percent)
        worker_amount = payment * percent // 100
        client_amount = payment - worker_amount

        if worker_amount > 0:
            gl.get_contract_at(agreement.worker).emit(value=u256(worker_amount)).__receive__()
        if client_amount > 0:
            gl.get_contract_at(agreement.client).emit(value=u256(client_amount)).__receive__()

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

    @gl.public.view
    def get_proposals(self, agreement_id: u256) -> str:
        if agreement_id not in self.agreements:
            return "NOT_FOUND"
        agreement = self.agreements[agreement_id]
        return "client:" + agreement.client_proposal + " worker:" + agreement.worker_proposal
