# Design Decisions

This document explains the reasoning behind the major design choices
in the Deliverable Arbitration Suite, and the tradeoffs we considered.

## Why four separate contracts instead of one

Each contract is a standalone, reusable primitive that solves one
problem on its own: escrow, web-grounded fact-checking, dispute
escalation, and reputation tracking. Any one of them could be used on
its own in a completely different project. Bundling all four into a
single monolithic contract would make each piece harder to reuse,
audit, and test independently, and would hide the fact that each one
uses a genuinely different consensus mechanism.

## Why four different consensus patterns

A single validation pattern reused across every contract does not
demonstrate an understanding of GenLayer's Equivalence Principle, it
just demonstrates one working example copied four times. This suite
deliberately uses:

- Partial field matching on a semantic decision (DeliverableEscrow).
- Partial field matching combined with live, independently-fetched
  web data (EvidenceCorroboration).
- Partial field matching against explicit, written criteria rather
  than open-ended judgment (DisputeEscalation).
- No consensus mechanism at all, because none is needed
  (ReputationLedger).

The last point matters as much as the first three. Knowing when *not*
to reach for an LLM or for validator consensus is itself part of using
GenLayer correctly, not a gap in the design.

## Why the contracts are not directly wired together on-chain

DisputeEscalation does not make a cross-contract call into
DeliverableEscrow, and ReputationLedger's `record_outcome` is called
by an admin address rather than automatically from the other
contracts. This was a deliberate scope decision: wiring contracts
together with live cross-contract calls is a meaningfully larger and
riskier piece of work than building and thoroughly testing four
correct standalone contracts. Conceptually, the intended flow is
that a real deployment would have DeliverableEscrow call into
DisputeEscalation when a decision is challenged, and call into
ReputationLedger once an agreement is finalized. This suite documents
that intended relationship rather than implementing it, so that the
scope stayed realistic for the time available while still keeping
each contract genuinely correct and independently tested.

## Why GEN (the native token) instead of an external ERC20

`DeliverableEscrow.create_agreement` is `payable` and locks the
network's native GEN token directly, rather than requiring an
external ERC20 token and an approve/transferFrom flow. This keeps the
entire lifecycle of an agreement, from locking funds to releasing
them, fully native to GenLayer with no external token contract to
trust or depend on, and made the contract simpler to deploy and test
end to end on Studio.

## Why timestamps were removed from DeliverableEscrow

An earlier version of DeliverableEscrow tracked `created_at`,
`submitted_at`, and `evaluated_at` using `gl.block.timestamp`. This
does not exist in the current GenLayer SDK
(`AttributeError: module 'genlayer.gl' has no attribute 'block'`), so
all three fields were removed. None of the contract's actual logic
depended on timestamps, so removing them did not change any behavior.

## Why terminal settlement and a cancellation path were added

The first submitted version of DeliverableEscrow could lock funds via
`create_agreement` but had no method to actually pay the worker,
refund the client, or recover funds from an agreement that never
completes. A steward review correctly flagged this as a real gap:
every deposit would stay locked forever. `release_funds` closes this
gap by paying out according to the already-agreed decision, and
`cancel_agreement` gives the client a way to reclaim funds if a
worker never submits anything, without allowing cancellation after
work has already been submitted for evaluation. Because
`gl.block.timestamp` is unavailable in this SDK, cancellation is a
state-based recovery path (available while an agreement is PENDING
with no submitted evidence) rather than a time-based timeout.

## Why release_funds validates the decision/percentage combination

A steward review also asked that validators bind the payout percentage
to the decision, rather than trusting whatever a leader proposes.
`evaluate_deliverable` now enforces this inside the leader function
itself, before a result can ever reach validator comparison or state:
ACCEPTED must carry percent 100, REJECTED must carry percent 0, and
PARTIAL must carry a percent strictly between 1 and 99. A second,
identical check runs again immediately before state is mutated, as
defense in depth against any future code path that might bypass the
leader function.

## Why value transfers use gl.get_contract_at(...).emit(value=...).__receive__()

Sending native GEN out of a contract turned out to need a very
specific, documented call shape. Several plausible-looking
alternatives, including `gl.emit_transfer(address, amount)`, a bare
`emit_transfer(address, amount)`, and `gl.ContractAt(address).emit_transfer(value=amount)`,
all failed against the deployed SDK with AttributeError or NameError.
The pattern that actually works, confirmed against GenLayer's official
SDK API reference, is to obtain a proxy for the target address with
`gl.get_contract_at(address)`, attach the value with `.emit(value=amount)`,
and invoke `.__receive__()`, which is the documented handler for a
plain value transfer with no specific method call attached. This was
verified end to end on GenLayer Studio: `release_funds` and
`cancel_agreement` both now move real GEN between the contract and the
client or worker address.

## Why DisputeEscalation caps escalation at three stages

An unbounded escalation process could be dragged out indefinitely by
a party unwilling to accept a final answer. A fixed maximum of three
stages guarantees that every dispute reaches a final, deterministic
end state (UPHELD or OVERTURNED) in a bounded number of steps, while
still giving a challenger more than one opportunity to present a
stronger case.
