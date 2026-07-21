# Build Week submission checklist

## Automated gates

- [x] Backend pytest suite, including Epistemic Contract and Claim Passport
- [x] Ruff
- [x] Frontend ESLint and production build
- [x] npm production audit
- [x] Bandit high-severity scan
- [x] Python dependency audit
- [x] Secret scan
- [x] Clean Docker demo build and health check

The repository's configured MyPy CI profile passes. Fully strict MyPy remains a future hardening target and is not represented as complete.

## Experience gates

- [ ] First-login tutorial works from beginning to end
- [ ] Guided investigation is idempotent
- [ ] Epistemic Contract persists and appears in the passport
- [ ] Rehearsal run reaches its human checkpoint
- [ ] Valid Lean proof succeeds and invalid proof fails
- [ ] SymPy check succeeds
- [ ] Claim Passport accurately summarizes graph objects
- [ ] Replay contains the complete mutation trail
- [ ] Light and dark themes pass desktop and mobile review

## Submission gates

- [x] One live GPT‑5.6 run with a user-provided key completed by the project owner
- [x] Fresh-clone setup verified
- [x] Private GitHub repository created
- [ ] Reviewer access confirmed
- [ ] Demo video recorded
- [ ] Screenshots exported
- [ ] Devpost copy finalized
- [ ] Submission completed before the official deadline

Public deployment activation is tracked only in the preserved public-launch edition and is not part of this private competition release.
