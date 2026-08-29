# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json

from genlayer import *
from dataclasses import dataclass


MAX_STAGES = 3


@allow_storage
@dataclass
class Dispute:
    initiator: Address
    original_decision: str
    justification: str
    stage: u32
    status: str


class DisputeEscalation(gl.Contract):
    disputes: TreeMap[u256, Dispute]
    next_id: u256

    def __init__(self):
        self.next_id = u256(0)

    # ================= PUBLIC WRITE METHODS =================

    @gl.public.write
    def open_dispute(self, original_decision: str, justification: str) -> u256:
        assert original_decision.strip() != "", "original_decision cannot be empty"
        assert justification.strip() != "", "justification cannot be empty"

        dispute_id = self.next_id
        self.next_id += u256(1)

        self.disputes[dispute_id] = Dispute(
            initiator=gl.message.sender_address,
            original_decision=original_decision,
            justification=justification,
            stage=u32(1),
            status="OPEN",
        )

        return dispute_id

    @gl.public.write
    def escalate_dispute(self, dispute_id: u256):
        assert dispute_id in self.disputes
        dispute = self.disputes[dispute_id]

        assert dispute.status == "OPEN", "Dispute is not open for escalation"

        original_decision = dispute.original_decision
        justification = dispute.justification
        stage = dispute.stage

        def leader_fn():
            prompt = f"""
            You are reviewing a dispute at escalation stage {stage} of
            {MAX_STAGES}.

            Original decision being challenged:
            {original_decision}

            Challenger's justification:
            {justification}

            Explicit criteria for overturning the original decision:
            - The justification must point to specific, concrete evidence
              that directly contradicts the original decision.
            - Mere disagreement, dissatisfaction, or a request for a
              second opinion is NOT sufficient grounds to overturn.
            - The evidence must be strong enough that a reasonable neutral
              party would consider the original decision clearly wrong.

            Respond with ONLY a JSON object in exactly this format,
            and nothing else:
            {{"verdict": "UPHELD" or "OVERTURNED"}}
            """
            response = gl.nondet.exec_prompt(prompt)
            try:
                data = json.loads(response)
            except Exception:
                raise gl.vm.UserError("[LLM_ERROR] validator returned invalid JSON")

            verdict = str(data.get("verdict", "")).upper()
            if verdict not in ("UPHELD", "OVERTURNED"):
                raise gl.vm.UserError("[LLM_ERROR] validator returned an invalid verdict")
            return {"verdict": verdict}

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False

            leader_data = leader_result.calldata
            if leader_data.get("verdict") not in ("UPHELD", "OVERTURNED"):
                return False

            validator_data = leader_fn()

            # Non-comparative pattern: each validator independently applies
            # the same explicit criteria; only the objective "verdict"
            # field must match, not the reasoning text.
            return leader_data["verdict"] == validator_data["verdict"]

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        verdict = result["verdict"]

        if verdict == "OVERTURNED":
            dispute.status = "OVERTURNED"
        else:
            if dispute.stage >= u32(MAX_STAGES):
                dispute.status = "UPHELD"
            else:
                dispute.stage = dispute.stage + u32(1)

        self.disputes[dispute_id] = dispute

    # ================= PUBLIC VIEW METHODS =================

    @gl.public.view
    def get_dispute_status(self, dispute_id: u256) -> str:
        if dispute_id not in self.disputes:
            return "NOT_FOUND"
        return self.disputes[dispute_id].status

    @gl.public.view
    def get_dispute_stage(self, dispute_id: u256) -> u32:
        if dispute_id not in self.disputes:
            return u32(0)
        return self.disputes[dispute_id].stage
