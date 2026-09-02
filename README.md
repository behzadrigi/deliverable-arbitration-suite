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
| [DeliverableEscrow](contracts/deliverable_escrow.py) | Holds funds, releases them based on an agreed ACCEPTED / REJECTED / PARTIAL verdict, supports client-initiated cancellation before submission, and a mutual client-worker resolution path if evaluation never happens after submission | Custom leader/validator, partial field matching on both decision and percent |
| [EvidenceCorroboration](contracts/evidence_corroboration.py) | Fetches a live web page and verifies a submitted claim against its actual content | Custom leader/validator with live web data |
| [DisputeEscalation](contracts/dispute_escalation.py) | Multi-stage challenge process that can uphold or overturn a prior decision against explicit criteria | Custom leader/validator, non-comparative with explicit criteria |
| [ReputationLedger](contracts/reputation_ledger.py) | Tracks each party's history of successful, failed, and partial outcomes | Fully deterministic, no LLM or consensus involved |

See [CONTRACTS.md](CONTRACTS.md) for a detailed explanation of each
contract, and [DECISIONS.md](DECISIONS.md) for the design rationale
and tradeoffs behind the suite.

## Deployed and tested on GenLayer Studio

Every method in every contract was deployed and called end to end on
GenLayer Studio, with transaction hashes collected as evidence.

- DeliverableEscrow deploy: `0xb97c0482ec85f98340c12f69344d2eab7c29cdb33c144d83e20a15a0968feac8`
- DeliverableEscrow create_agreement: `0x88b4cba916edcb9a88b458b4bb0e122e32be3802bcd5ce07af31a20a3f82197a`
- DeliverableEscrow submit_deliverable: `0xfcf80e5594627b995ae5503fb1596e6808657313df2bf5369b900dfaef2eb4e0`
- DeliverableEscrow evaluate_deliverable: `0x32bd08d7cdae2c9961ee952b2ecd4f35bb881db1a485eefadfef483c4b934c73`
- DeliverableEscrow release_funds: `0xcd53891198b0a3536ddfc5bac9d72834ddcdb2e8083350dbb188a837be7bfce9`
- DeliverableEscrow cancel_agreement (second agreement): `0xcd1dc3aa2ee48b7bd0bb05498ca6c02ef61b8234fb6c62bff69c45922521a503`
- DeliverableEscrow propose_resolution, client side (third agreement): `0x207a82a644430a051531ea27e0eb47c987f50b5f28ad6dffc01d7e255e803751`
- DeliverableEscrow propose_resolution, worker side, triggers settlement: `0x5271163d48c65f43b104c97ca33bc7a3bdd6e1b735b5b2593d12c425d715158f`
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
