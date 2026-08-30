# Deliverable Arbitration Suite

A collection of four standalone GenLayer Intelligent Contracts for
deliverable-based dispute arbitration. Together they cover escrow,
evidence corroboration, multi-stage dispute escalation, and reputation
tracking, each built as an independent, reusable contract.

## Why this exists

Freelance and gig work regularly runs into the same unresolved problem:
was the delivered work good enough to be paid for? Standard smart
contracts cannot judge quality or compare a deliverable against a
written specification. This suite uses GenLayer's Equivalence Principle
to let decentralized validators make that judgment call, with real
funds and real consequences tied to the outcome.

## Contracts

| Contract | Purpose | Consensus pattern |
|---|---|---|
| [DeliverableEscrow](contracts/deliverable_escrow.py) | Holds funds, releases them based on an agreed ACCEPTED / REJECTED / PARTIAL verdict comparing delivered work to a spec, and supports a client-initiated cancellation path before a deliverable is submitted | Custom leader/validator, partial field matching |
| [EvidenceCorroboration](contracts/evidence_corroboration.py) | Fetches a live web page and verifies a submitted claim against its actual content | Custom leader/validator with live web data |
| [DisputeEscalation](contracts/dispute_escalation.py) | Multi-stage challenge process that can uphold or overturn a prior decision against explicit criteria | Custom leader/validator, non-comparative with explicit criteria |
| [ReputationLedger](contracts/reputation_ledger.py) | Tracks each party's history of successful, failed, and partial outcomes | Fully deterministic, no LLM or consensus involved |

See [CONTRACTS.md](CONTRACTS.md) for a detailed explanation of each
contract, and [DECISIONS.md](DECISIONS.md) for the design rationale
and tradeoffs behind the suite.

## Deployed and tested on GenLayer Studio

Every method in every contract was deployed and called end to end on
GenLayer Studio, with transaction hashes collected as evidence.

- DeliverableEscrow deploy: `0xfecb235138e3bd8359b7341b94697deaa22f3c76f8db4428d7b9aa4621f536a9`
- DeliverableEscrow create_agreement: `0x06482085d7689139a8dc02484559537efa435e8d4f67c4dde7e759a00119f90c`
- DeliverableEscrow submit_deliverable: `0x03e40b10465f8b5f28f1c1ca39bb73517ac3247c3521b3ea8fd2b961fcb6fdf2`
- DeliverableEscrow evaluate_deliverable: `0x862addf0bc44ee3a314788525cd51bac6fd4f68d67f83864dad634ece91e5ff3`
- DeliverableEscrow release_funds: `0xbeb98f904a3618d78d5e99ddab050aae360613fa335ff2a8f65103212009eebd`
- DeliverableEscrow cancel_agreement: `0xee4adf0b766457fae7616db43daf7c707540f20ce6d7a74dd3649dcf123a7305`
- EvidenceCorroboration deploy: `0x00ca953baaeeb6bb227711f95d4d020443929ce7fd9f7753d69b8247b7689ec2`
- EvidenceCorroboration submit_claim: `0x37108d77358ea1f5288ebd1df477d940db6bce9cd712dbeb13e3e0dfd8da8584`
- EvidenceCorroboration corroborate_claim: `0xac404f88b73fadb70d0b39d95132fbeb0376be11a1fa39eaddba847e784c8a01`
- DisputeEscalation deploy: `0xafac516b6887fd856ba04364f5c894f1fc2b7f6de0b51c11eadfbae5f3f21d3f`
- DisputeEscalation open_dispute: `0x00bd14ce967fd328495f50c998e5cbc7175dd8d604132f442b9ce71c608da28b`
- DisputeEscalation escalate_dispute: `0x89dcc590bd6de1716917d67c1256136d21a9dd569a01bf9fcd78258e1c548fee`
- ReputationLedger deploy: `0x0a7f263bb7d21ba6dc20279a3ffb9635ca74ba39e0c65fd9c82f3994849175ad`
- ReputationLedger record_outcome: `0x32e326e29b64b4663e74ea3d881233303d97c3523d67240dc4e6423225a02353`

## License

MIT
