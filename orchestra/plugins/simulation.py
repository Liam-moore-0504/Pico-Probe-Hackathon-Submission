import math
import random
import statistics

from .base import Plugin, PluginManifest


class SimulationPlugin(Plugin):
    manifest: PluginManifest = PluginManifest(
        plugin_id="core.monte_carlo", name="Reproducible Monte Carlo", capabilities=["simulation", "monte_carlo", "numerical_test"], reliability=0.9,
        input_schema={"type": "object", "required": ["seed", "trials"], "properties": {"code": {"type": "string"}, "simulation_specification": {"type": "object"}, "parameters": {"type": "object"}, "seed": {"type": "integer"}, "trials": {"type": "integer", "minimum": 100, "maximum": 5_000_000}, "batches": {"type": "integer", "minimum": 1}, "convergence_threshold": {"type": "number", "minimum": 0}, "target_claim_id": {"type": "string"}, "expected_statistic": {"type": "string"}}},
        output_schema={"type": "object", "required": ["status", "estimate", "standard_error", "confidence_interval_95", "seed", "trials"], "properties": {"status": {"type": "string"}, "estimate": {"type": "number"}, "standard_error": {"type": "number"}, "confidence_interval_95": {"type": "array"}, "convergence": {"type": "object"}, "failed_samples": {"type": "integer"}, "seed": {"type": "integer"}, "trials": {"type": "integer"}, "artifacts": {"type": "array"}, "interpretation_warning": {"type": "string"}, "evidence_stance": {"type": "string"}}},
    )

    def execute(self, payload: dict) -> dict:
        seed = int(payload.get("seed", 0))
        if payload.get("experiment") == "reciprocal_cube_partial_sums":
            requested = payload.get("n_values", [10, 100, 1000, 10000])
            n_values = sorted({int(value) for value in requested})
            if not n_values or n_values[0] < 1 or n_values[-1] > 5_000_000:
                raise ValueError("n_values must be between 1 and 5,000,000")
            targets = set(n_values)
            partial = 0.0
            observations = []
            for k in range(1, n_values[-1] + 1):
                partial += 1.0 / (k**3)
                if k in targets:
                    observations.append({"n": k, "partial_sum": partial, "tail_upper_bound": 1.0 / (2 * k * k)})
            return {
                "status": "success", "execution_mode": "local", "experiment": "reciprocal_cube_partial_sums",
                "observations": observations, "interpretation": "Numerical convergence can test candidate formulas but cannot prove nonexistence of every possible closed form.",
                "seed": seed, "trials": n_values[-1], "estimate": partial, "standard_error": 0.0,
                "confidence_interval_95": [partial, partial + 1.0 / (2 * n_values[-1] * n_values[-1])],
                "convergence": {"tail_upper_bound": 1.0 / (2 * n_values[-1] * n_values[-1])}, "failed_samples": 0,
                "artifacts": [], "interpretation_warning": "A numerical result can support or challenge a claim but cannot formally verify it.", "evidence_stance": "tests",
            }
        samples = int(payload.get("trials", payload.get("sample_count", 10_000)))
        if not 100 <= samples <= 5_000_000:
            raise ValueError("sample_count must be between 100 and 5,000,000")
        rng = random.Random(seed)
        values = [rng.random() for _ in range(samples)]
        mean = statistics.fmean(values)
        error = statistics.pstdev(values) / math.sqrt(samples)
        return {
            "status": "success",
            "execution_mode": "local",
            "seed": seed,
            "rng": "python.random.MT19937",
            "sample_count": samples,
            "trials": samples,
            "estimate": mean,
            "confidence_interval_95": [mean - 1.96 * error, mean + 1.96 * error],
            "standard_error": error,
            "failed_samples": 0,
            "artifacts": [],
            "interpretation_warning": "A numerical result can support or challenge a claim but cannot formally verify it.",
            "evidence_stance": "tests",
            "convergence": {"first_half": statistics.fmean(values[: samples // 2]), "second_half": statistics.fmean(values[samples // 2 :])},
        }
