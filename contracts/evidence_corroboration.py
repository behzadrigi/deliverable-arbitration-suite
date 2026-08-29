# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json

from genlayer import *
from dataclasses import dataclass


@allow_storage
@dataclass
class Claim:
    submitter: Address
    source_url: str
    claimed_fact: str
    status: str


class EvidenceCorroboration(gl.Contract):
    claims: TreeMap[u256, Claim]
    next_id: u256

    def __init__(self):
        self.next_id = u256(0)

    # ================= PUBLIC WRITE METHODS =================

    @gl.public.write
    def submit_claim(self, source_url: str, claimed_fact: str) -> u256:
        assert source_url.strip() != "", "source_url cannot be empty"
        assert claimed_fact.strip() != "", "claimed_fact cannot be empty"

        claim_id = self.next_id
        self.next_id += u256(1)

        self.claims[claim_id] = Claim(
            submitter=gl.message.sender_address,
            source_url=source_url,
            claimed_fact=claimed_fact,
            status="PENDING",
        )

        return claim_id

    @gl.public.write
    def corroborate_claim(self, claim_id: u256):
        assert claim_id in self.claims
        claim = self.claims[claim_id]

        assert claim.status == "PENDING", "Claim already corroborated"

        source_url = claim.source_url
        claimed_fact = claim.claimed_fact

        def leader_fn():
            page_html = gl.nondet.web.render(source_url, mode='html')

            prompt = f"""
            You are verifying a factual claim against the content of a
            live web page.

            Claim to verify:
            {claimed_fact}

            Web page content:
            {page_html}

            Respond with ONLY a JSON object in exactly this format,
            and nothing else:
            {{"verdict": "CORROBORATED" or "CONTRADICTED" or "INCONCLUSIVE"}}

            Rules:
            - CORROBORATED: the page content clearly supports the claim.
            - CONTRADICTED: the page content clearly contradicts the claim.
            - INCONCLUSIVE: the page does not contain enough information
              to confirm or deny the claim.
            """
            response = gl.nondet.exec_prompt(prompt)
            try:
                data = json.loads(response)
            except Exception:
                raise gl.vm.UserError("[LLM_ERROR] validator returned invalid JSON")

            verdict = str(data.get("verdict", "")).upper()
            if verdict not in ("CORROBORATED", "CONTRADICTED", "INCONCLUSIVE"):
                raise gl.vm.UserError("[LLM_ERROR] validator returned an invalid verdict")
            return {"verdict": verdict}

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False

            leader_data = leader_result.calldata
            if leader_data.get("verdict") not in ("CORROBORATED", "CONTRADICTED", "INCONCLUSIVE"):
                return False

            validator_data = leader_fn()

            # Partial field matching: only the objective "verdict" field
            # must match. Independent web fetches and LLM phrasing may
            # otherwise vary slightly between validators.
            return leader_data["verdict"] == validator_data["verdict"]

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        claim.status = result["verdict"]
        self.claims[claim_id] = claim

    # ================= PUBLIC VIEW METHODS =================

    @gl.public.view
    def get_claim_status(self, claim_id: u256) -> str:
        if claim_id not in self.claims:
            return "NOT_FOUND"
        return self.claims[claim_id].status
