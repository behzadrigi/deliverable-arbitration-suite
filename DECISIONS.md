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

- Partial field matching on a semantic decision, extended to also
  cover a payout-relevant number (DeliverableEscrow).
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
This limitation later shaped how the two recovery paths below were
designed, since neither could rely on elapsed time.

## Why DeliverableEscrow has two separate recovery paths

The first submitted version of DeliverableEscrow could lock funds via
`create_agreement` but had no way to actually settle an agreement or
recover funds if it never completed. A steward review correctly
flagged this, and a first fix added `release_funds` (terminal
settlement) and `cancel_agreement` (a pre-submission recovery path
for the client). On resubmission, the steward correctly flagged that
this was still incomplete: `cancel_agreement` only covers the case
where the worker never submits anything, but does nothing for the
case where evidence has already been submitted and
`evaluate_deliverable` is simply never called again, or keeps
failing.

`propose_resolution` closes that second gap. Either the client or the
worker can propose a decision and percent once evidence has been
submitted; the agreement only settles once both sides have
independently proposed the exact same outcome. Because
`gl.block.timestamp` is unavailable in this SDK, a real timeout is not
possible, so this is a mutual-consent recovery path instead of a
time-based one: neither party can force a result alone, but the two of
them together can always resolve a stuck agreement without waiting on
a third party or a clock.

## Why release_funds validates the decision/percentage combination, and why PARTIAL uses discrete buckets

A steward review asked that validators bind the payout percentage to
the decision, rather than trusting whatever a leader proposes. The
first fix addressed this by validating the combination inside the
leader function and again before state mutation, but the steward
correctly pointed out that this still was not enough: validators were
only comparing the `decision` field with each other, not the
`percent` field, so the percentage itself was never actually agreed
upon by consensus, only individually range-checked by whichever
validator happened to run.

The fix was to restrict PARTIAL to a small, fixed set of percentages
(25, 50, or 75) instead of an open 0-100 range, and to make
`validator_fn` require both the `decision` field and the `percent`
field to match exactly between the leader's run and each validator's
run. An open numeric range would rarely produce identical values
across independent LLM calls, making genuine consensus on a specific
number impractical; a small discrete set makes it realistic for
independent validators to converge on the same bucket, so the payout
percentage is now genuinely bound by the Equivalence Principle rather
than asserted by the leader alone.

## Why value transfers use gl.get_contract_at(...).emit(value=...).__receive__()

Sending native GEN out of a contract needed a very specific, documented
call shape. Several plausible-looking alternatives, including
`gl.emit_transfer(address, amount)`, a bare `emit_transfer(address,
amount)`,
