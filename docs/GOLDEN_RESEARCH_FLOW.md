# Golden no-key research flow

1. Start Pico Probe with `docker compose -p picoprobe-build-week -f docker-compose.demo.yml up -d --build`.
2. Open `http://127.0.0.1:8000`, create an account, and create a project.
3. Define the Assurance Contract or explicitly use the safe default for rehearsal.
4. Instantiate a template or create and save a pipeline.
5. Select **Compile pipeline** and inspect contract version, typed ports, assurance requirements, and downstream expectations.
6. Run with **Rehearsal — no paid model calls**. Rehearsal uses the same compiler, envelopes, resolver, validator, artifacts, graph, and event stream as live mode.
7. Complete researcher checkpoints with a typed contribution category.
8. Inspect Claim Graph, Claim Passport, Replay, assurance status, and Discovery.

Automated validation is `python -m pytest -q`, followed by `npm run lint && npm run build` in `frontend/`. This release currently has 31 passing backend tests.
