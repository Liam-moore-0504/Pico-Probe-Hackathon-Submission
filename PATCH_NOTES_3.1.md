# Pico Probe 3.1 patch notes

- Local Ollama requests no longer have a fixed read deadline by default. They retain a bounded connection deadline and use streaming so cancellation can be observed between chunks.
- Cloud calls remain bounded per request; the overall durable research run has no total duration cap.
- An explicit `hard_timeout_seconds` may still be set on an Ollama node.
- New projects open the Epistemic/Assurance Contract before the Claim Graph. Existing projects still open the graph because their contract and state may already exist.
- Pipeline connection circles are larger and interactive. Drag from the right output circle and release on another node's left input circle.
- The inspector's manual Start connection button was removed.
- Merge-selection wording now describes nodes as merge inputs. A merge input is a completed branch whose result will be combined, voted on, or synthesized by a new merge node.
- Three isolated rehearsal-mode mathematical investigations completed and were published to an isolated validation database. See `VALIDATION_RESEARCH_RUNS.json`. These are not published to an internet deployment or the user's local database.

## Validation

- Backend: 38 passed, 1 optional live Ollama test skipped in this environment.
- Frontend ESLint passed.
- Frontend production build could not be rerun in this Linux runtime because the uploaded `node_modules` contains a platform-specific native Rolldown binding. Reinstall dependencies locally (`rm -rf node_modules && npm ci`) before building.
