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

## Why DisputeEscalation caps escalation at three stages

An unbounded escalation process could be dragged out indefinitely by
a party unwilling to accept a final answer. A fixed maximum of three
stages guarantees that every dispute reaches a final, deterministic
end state (UPHELD or OVERTURNED) in a bounded number of steps, while
still giving a challenger more than one opportunity to present a
stronger case.
