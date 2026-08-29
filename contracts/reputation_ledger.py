# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass


@allow_storage
@dataclass
class Score:
    successes: u32
    failures: u32
    partials: u32


class ReputationLedger(gl.Contract):
    admin: Address
    scores: TreeMap[Address, Score]

    def __init__(self):
        self.admin = gl.message.sender_address

    # ================= PUBLIC WRITE METHODS =================

    @gl.public.write
    def record_outcome(self, party: str, outcome: str):
        # Only the admin may record outcomes. In a production deployment,
        # this would be restricted to a trusted upstream contract (e.g.
        # DeliverableEscrow) rather than a single admin address, but that
        # requires cross-contract calls which are out of scope here.
        assert gl.message.sender_address == self.admin, \
            "Only the admin can record outcomes"

        party_address = Address(party)
        outcome_upper = outcome.upper()
        assert outcome_upper in ("SUCCESS", "FAILURE", "PARTIAL"), \
            "outcome must be SUCCESS, FAILURE, or PARTIAL"

        if party_address in self.scores:
            score = self.scores[party_address]
        else:
            score = Score(successes=u32(0), failures=u32(0), partials=u32(0))

        if outcome_upper == "SUCCESS":
            score.successes = score.successes + u32(1)
        elif outcome_upper == "FAILURE":
            score.failures = score.failures + u32(1)
        else:
            score.partials = score.partials + u32(1)

        self.scores[party_address] = score

    # ================= PUBLIC VIEW METHODS =================

    @gl.public.view
    def get_successes(self, party: str) -> u32:
        party_address = Address(party)
        if party_address not in self.scores:
            return u32(0)
        return self.scores[party_address].successes

    @gl.public.view
    def get_failures(self, party: str) -> u32:
        party_address = Address(party)
        if party_address not in self.scores:
            return u32(0)
        return self.scores[party_address].failures

    @gl.public.view
    def get_partials(self, party: str) -> u32:
        party_address = Address(party)
        if party_address not in self.scores:
            return u32(0)
        return self.scores[party_address].partials
