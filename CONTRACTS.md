# Contracts

Detailed explanation of each contract in the Deliverable Arbitration
Suite: what it does, why consensus is used the way it is, and what
state can or cannot change under which outcomes.

## DeliverableEscrow

**Purpose**

Holds a client's funds in escrow for a piece of work and releases them
only once GenLayer validators independently agree on whether the
delivered evidence satisfies the agreed specification. Provides two
separate recovery paths so funds are never permanently locked, no
matter which stage an agreement gets stuck at.

**How consensus is used**

`evaluate_deliverable` runs a custom leader/validator function. The
leader asks an LLM to compare the specification against the submitted
evidence and return one of ACCEPTED, REJECTED, or PARTIAL. For
ACCEPTED the percent must be exactly 100, for REJECTED exactly 0, and
for PARTIAL the LLM must pick one of a small fixed set (25, 50, or
75). Every validator independently re-runs the same comparison, and
`validator_fn` requires BOTH the decision field AND the percent field
to match exactly across the leader's run and each validator's run.
Restricting PARTIAL to three discrete buckets, rather than an open
0-100 range, is what makes genuine agreement on the payout-relevant
number realistic; an open range would rarely produce identical values
across independent LLM calls.

`release_funds`, `cancel_agreement`, and `propose_resolution` are
fully deterministic and do not use the Equivalence Principle, since
moving already-agreed-upon funds, or checking whether two parties
independently proposed the same outcome, are mechanical operations,
not judgment calls.

**Terminal settlement and two recovery paths**

- `release_funds` can only be called once an agreement has reached
  ACCEPTED, REJECTED, or PARTIAL, and only pays out once per
  agreement. ACCEPTED sends the full amount to the worker, REJECTED
  returns the full amount to the client, and PARTIAL splits the
  amount according to the agreed percentage.
- `cancel_agreement` (pre-submission recovery) lets the client reclaim
  the full deposit, but only while the agreement is still PENDING,
  i.e. before the worker has submitted anything.
- `propose_resolution` (post-submission recovery) covers the case
  where evidence has been submitted but `evaluate_deliverable` is
  never successfully called. Either the client or the worker can
  propose a decision and percent; the agreement only settles once
  both sides have independently proposed the exact same outcome.
  Neither party can force a result alone, and no block timestamp is
  required, since `gl.block.timestamp` does not exist in this SDK.
- Value is sent using GenLayer's documented value-transfer pattern,
  `gl.get_contract_at(address).emit(value=amount).__receive__()`.

**Safety properties**

- Funds can only be locked through `create_agreement`, which requires
  a positive payment and a non-empty spec.
- `submit_deliverable` can only be called once, and only by the
  address registered as the worker at creation time.
- `evaluate_deliverable` can only run once per agreement (it requires
  status SUBMITTED); a decided agreement cannot be re-evaluated to
  "shop" for a different outcome.
- The decision/percent combination is enforced by every validator
  independently before it can ever be compared, and again at the
  point of state mutation, not merely trusted from the leader.
- `release_funds` can only move funds once per agreement, guarded by
  a `settled` flag.
- `cancel_agreement` can only be called by the client, only while
  PENDING, so a worker who has already submitted work cannot be cut
  out by a late cancellation.
- `propose_resolution` only accepts proposals from the registered
  client or worker on that specific agreement, only while status is
  SUBMITTED, and only settles the agreement once both proposals are
  byte-for-byte identical.

## EvidenceCorroboration

**Purpose**

Verifies a submitted factual claim against the actual content of a
live web page, rather than trusting a screenshot or a claim at face
value.

**How consensus is used**

`corroborate_claim` uses a custom leader/validator function where each
validator independently fetches the same URL with
`gl.nondet.web.render` and asks an LLM whether the page content
supports, contradicts, or is inconclusive about the claim. Because
independent web fetches and LLM phrasing can vary slightly, only the
objective `verdict` field (CORROBORATED / CONTRADICTED / INCONCLUSIVE)
is required to match, not the raw page content or reasoning text.

**Safety properties**

- A claim can only be corroborated once; its status moves from PENDING
  to a final verdict and cannot be re-run.
- The verdict is only ever set from a value that passed validator
  consensus, never from the leader's result alone.

## DisputeEscalation

**Purpose**

Provides a multi-stage challenge process so that a contested decision
is not overturned lightly, but also is not final without a chance for
review.

**How consensus is used**

`escalate_dispute` uses a custom leader/validator function where every
validator independently applies the same explicit, written criteria
for what counts as sufficient evidence to overturn a decision (not
mere disagreement). Only the objective `verdict` field (UPHELD /
OVERTURNED) must match across validators.

**Safety properties**

- A dispute can only move forward one stage at a time, up to a fixed
  maximum of three stages.
- An OVERTURNED verdict at any stage immediately finalizes the dispute
  as OVERTURNED; no further stages are needed or possible.
- Reaching the final stage without an OVERTURNED verdict finalizes the
  dispute as UPHELD.
- A dispute that is not OPEN can no longer be escalated.

## ReputationLedger

**Purpose**

Tracks each party's history of successful, failed, and partial
outcomes across past agreements.

**How consensus is used**

None. This contract deliberately does not use the Equivalence
Principle, `gl.nondet`, or any LLM call. Tallying past finalized
outcomes is a purely deterministic bookkeeping operation with no
judgment involved, so introducing non-deterministic consensus here
would add cost and complexity without adding any safety or accuracy
benefit.

**Safety properties**

- Only the admin address can record an outcome, and only with one of
  the three fixed outcome values (SUCCESS, FAILURE, PARTIAL).
- Counts are strictly additive; there is no method to decrement or
  reset a party's history.
