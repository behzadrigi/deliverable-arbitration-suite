# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
# DeliverableEscrow — rebuilt from scratch to close two steward-flagged gaps:
#
#   1) No recovery path once evidence was submitted (only evaluate_deliverable
#      could move the agreement forward; if nobody ever called it, funds were
#      stuck forever). gl.block.timestamp does not exist in this SDK, so a
#      time-based timeout is not possible. Fix: `propose_resolution` — a
#      mutual, deterministic recovery path. Either party can propose a
#      decision + percent after submission; the agreement only settles once
#      BOTH sides have proposed the exact same outcome. No unilateral trust
#      on either side, no timestamp required.
#
#   2) PARTIAL percent was taken from the leader's LLM result alone and only
#      range-checked (1-99), never actually compared across validators. Fix:
#      the LLM must now choose percent from a small fixed set {25, 50, 75}.
#      That discrete value is part of what gl.vm.run_nondet_unsafe's
#      leader/validator Equivalence Principle check compares, exactly like
#      the `decision` field already was — so percent is now genuinely under
#      consensus, not just leader-asserted and range-validated.

from genlayer import *
import json


class DeliverableEscrow(gl.Contract):
    # Per-agreement state, keyed by agreement_id. Kept as separate TreeMaps
    # (rather than a single struct/record) to stay close to primitives whose
    # behavior is already confirmed on GenLayer Studio.
    client: TreeMap[u256, Address]
    worker: TreeMap[u256, Address]
    spec: TreeMap[u256, str]
    payment: TreeMap[u256, u256]
    evidence: TreeMap[u256, str]
    status: TreeMap[u256, str]        # PENDING / SUBMITTED / ACCEPTED / REJECTED / PARTIAL
    percent: TreeMap[u256, u256]      # meaningful once status is a terminal decision
    settled: TreeMap[u256, bool]
    next_id: u256

    # Mutual post-submission recovery proposals ("DECISION:PERCENT" strings).
    client_proposal: TreeMap[u256, str]
    worker_proposal: TreeMap[u256, str]

    def __init__(self):
        self.next_id = u256(0)

    # ------------------------------------------------------------------ #
    # Creation / submission / pre-submission cancellation
    # ------------------------------------------------------------------ #

    @gl.public.write.payable
    def create_agreement(self, worker: str, spec: str) -> u256:
        assert gl.message.value > 0, "payment must be positive"
        assert len(spec.strip()) > 0, "spec cannot be empty"

        agreement_id = self.next_id
        self.next_id = u256(int(self.next_id) + 1)

        self.client[agreement_id] = gl.message.sender_address
        self.worker[agreement_id] = Address(worker)
        self.spec[agreement_id] = spec
        self.payment[agreement_id] = u256(gl.message.value)
        self.status[agreement_id] = "PENDING"
        self.settled[agreement_id] = False
        return agreement_id

    @gl.public.write
    def submit_deliverable(self, agreement_id: u256, evidence: str) -> None:
        assert self.status[agreement_id] == "PENDING", "agreement not pending"
        assert gl.message.sender_address == self.worker[agreement_id], \
            "only the registered worker can submit"
        assert len(evidence.strip()) > 0, "evidence cannot be empty"

        self.evidence[agreement_id] = evidence
        self.status[agreement_id] = "SUBMITTED"

    @gl.public.write
    def cancel_agreement(self, agreement_id: u256) -> None:
        assert self.status[agreement_id] == "PENDING", \
            "can only cancel before any deliverable is submitted"
        assert gl.message.sender_address == self.client[agreement_id], \
            "only the client can cancel"

        self.status[agreement_id] = "REJECTED"
        self.percent[agreement_id] = u256(0)
        self._payout(agreement_id)

    # ------------------------------------------------------------------ #
    # Fix 1: mutual, deterministic recovery after submission
    # ------------------------------------------------------------------ #

    @gl.public.write
    def propose_resolution(self, agreement_id: u256, decision: str, percent: u256) -> None:
        assert self.status[agreement_id] == "SUBMITTED", \
            "agreement is not awaiting resolution"
        self._validate_decision_percent(decision, percent)

        sender = gl.message.sender_address
        proposal = f"{decision}:{int(percent)}"

        is_client = sender == self.client[agreement_id]
        is_worker = sender == self.worker[agreement_id]
        assert is_client or is_worker, "only the client or worker on this agreement can propose a resolution"

        if is_client:
            self.client_proposal[agreement_id] = proposal
        else:
            self.worker_proposal[agreement_id] = proposal

        client_p = self.client_proposal.get(agreement_id, "")
        worker_p = self.worker_proposal.get(agreement_id, "")

        # Only settle once both sides independently proposed the identical
        # outcome. Neither party can force a resolution alone.
        if client_p != "" and client_p == worker_p:
            self.status[agreement_id] = decision
            self.percent[agreement_id] = percent
            self._payout(agreement_id)

    # ------------------------------------------------------------------ #
    # LLM-judged evaluation (Equivalence Principle) — still the primary path
    # ------------------------------------------------------------------ #

    @gl.public.write
    def evaluate_deliverable(self, agreement_id: u256) -> None:
        assert self.status[agreement_id] == "SUBMITTED", \
            "agreement is not awaiting evaluation"

        spec = self.spec[agreement_id]
        evidence = self.evidence[agreement_id]

        def leader_fn():
            prompt = f"""
Compare the submitted evidence against the specification and judge whether
the delivered work satisfies it.

Specification:
{spec}

Evidence:
{evidence}

Respond with strict JSON only, no other text:
{{"decision": "ACCEPTED" | "REJECTED" | "PARTIAL", "percent": <int>, "reasoning": "<short reasoning>"}}

percent MUST be exactly 100 when decision is ACCEPTED, exactly 0 when
decision is REJECTED, and MUST be exactly one of 25, 50, or 75 when
decision is PARTIAL. Do not use any other percent value.
""".strip()

            raw = gl.nondet.exec_prompt(prompt)
            parsed = json.loads(raw)
            decision = str(parsed["decision"]).upper()
            percent = int(parsed["percent"])
            self._validate_decision_percent(decision, u256(percent))
            return {"decision": decision, "percent": percent}

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader_data = leader_result.calldata
            if leader_data.get("decision") not in ("ACCEPTED", "REJECTED", "PARTIAL"):
                return False
            validator_data = leader_fn()
            # Both decision AND percent must match across independent
            # validator runs, so percent is genuinely bound by consensus,
            # not just range-checked by each validator in isolation.
            return (
                leader_data.get("decision") == validator_data.get("decision")
                and leader_data.get("percent") == validator_data.get("percent")
            )

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        decision = result["decision"]
        percent = u256(int(result["percent"]))
        self._validate_decision_percent(decision, percent)

        self.status[agreement_id] = decision
        self.percent[agreement_id] = percent
        self._payout(agreement_id)

    # ------------------------------------------------------------------ #
    # Settlement
    # ------------------------------------------------------------------ #

    @gl.public.write
    def release_funds(self, agreement_id: u256) -> None:
        assert self.status[agreement_id] in ("ACCEPTED", "REJECTED", "PARTIAL"), \
            "agreement has not reached a final decision yet"
        self._payout(agreement_id)

    def _payout(self, agreement_id: u256) -> None:
        if self.settled[agreement_id]:
            return
        self.settled[agreement_id] = True

        payment = int(self.payment[agreement_id])
        percent = int(self.percent[agreement_id])
        worker_amount = payment * percent // 100
        client_amount = payment - worker_amount

        if worker_amount > 0:
            gl.get_contract_at(self.worker[agreement_id]).emit(value=worker_amount).__receive__()
        if client_amount > 0:
            gl.get_contract_at(self.client[agreement_id]).emit(value=client_amount).__receive__()

    def _validate_decision_percent(self, decision: str, percent: u256) -> None:
        p = int(percent)
        if decision == "ACCEPTED":
            assert p == 100, "ACCEPTED must carry percent 100"
        elif decision == "REJECTED":
            assert p == 0, "REJECTED must carry percent 0"
        elif decision == "PARTIAL":
            assert p in (25, 50, 75), "PARTIAL percent must be exactly 25, 50, or 75"
        else:
            assert False, f"invalid decision: {decision}"

    # ------------------------------------------------------------------ #
    # Views
    # ------------------------------------------------------------------ #

    @gl.public.view
    def get_agreement(self, agreement_id: u256) -> str:
        return json.dumps({
            "client": str(self.client[agreement_id]),
            "worker": str(self.worker[agreement_id]),
            "spec": self.spec[agreement_id],
            "payment": int(self.payment[agreement_id]),
            "status": self.status[agreement_id],
            "percent": int(self.percent.get(agreement_id, u256(0))),
            "settled": self.settled[agreement_id],
            "client_proposal": self.client_proposal.get(agreement_id, ""),
            "worker_proposal": self.worker_proposal.get(agreement_id, ""),
        })
