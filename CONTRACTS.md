# Contracts

Detailed explanation of each contract in the Deliverable Arbitration
Suite: what it does, why consensus is used the way it is, and what
state can or cannot change under which outcomes.

## DeliverableEscrow

**Purpose**

Holds a client's funds in escrow for a piece of work and releases them
only once GenLayer validators independently agree on whether the
delivered evidence satisfies the agreed specification. Also provides a
recovery path so funds are never permanently locked.

**How consensus is used**

`evaluate_deliverable` runs a custom leader/validator function. The
leader asks an LLM to compare the specification against the submitted
evidence and return one of ACCEPTED, REJECTED, or PARTIAL, plus a
percentage for PARTIAL. Every validator independently re-runs the same
comparison. Only the objective `decision` field must match across
validators; the free-text reasoning and the exact percentage are
allowed to vary slightly between independent LLM calls, so only the
field the outcome actually depends on is bound by consensus. The
decision/percentage combination itself is validated inside the leader
function before it can ever reach state (ACCEPTED must carry 100,
REJECTED must carry 0, PARTIAL must carry 1-99), with a second
defense-in-depth check at the point of state mutation.

`release_funds` and `cancel_agreement` are fully deterministic and do
not use consensus, since moving already-agreed-upon funds is a
mechanical bookkeeping step, not a judgment call.

**Terminal settlement and recovery**

- `release_funds` can only be called once an agreement has reached
  ACCEPTED, REJECTED, or PARTIAL, and only once per agreement. ACCEPTED
  sends the full amount to the worker, REJECTED returns the full amount
  to the client, and PARTIAL splits the amount according to the agreed
  percentage.
- `cancel_agreement` lets the client reclaim the full deposit, but only
  while the agreement is still PENDING and the worker has not yet
  submitted anything. This prevents funds from being locked forever if
  a worker never engages, without allowing a client to cancel after
  work has already been submitted for evaluation.
- Value is sent using GenLayer's documented value-transfer pattern,
  `gl.get_contract_at(address).emit(value=amount).__receive__()`, which
  performs a real transfer to a client or worker address.

**Safety properties**

- Funds can only be locked through `create_agreement`, which requires
  a positive payment and a non-empty spec.
- `submit_deliverable` can only be called once, and only by the
  address registered as the worker at creation time.
- `evaluate_deliverable` can only run once per agreement; a rejected
  or accepted agreement cannot be re-evaluated to "shop" for a
  different outcome.
- No state transition to ACCEPTED, REJECTED, or PARTIAL happens
  without validator consensus on the decision field, and the
  decision/percentage combination is enforced rather than trusted.
- `release_funds` can only move funds once per agreement, guarded by a
  `settled` flag, so a settled agreement cannot be paid out twice.
- `cancel_agreement` can only be called by the client, only while
  PENDING, and only before any deliverable evidence has been
  submitted, so a worker who has already submitted work cannot be
  cut out by a late cancellation.

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
