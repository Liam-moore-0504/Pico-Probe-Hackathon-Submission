from __future__ import annotations

import re
import time

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

from .base import Plugin, PluginManifest


class SymPyPlugin(Plugin):
    manifest: PluginManifest = PluginManifest(
        plugin_id="core.sympy",
        name="SymPy",
        version=sp.__version__,
        category="symbolic",
        capabilities=["simplify", "solve", "factor", "expand", "integrate", "differentiate", "limit", "series", "symbolic_verification"],
        input_schema={"type": "object", "required": ["operation", "expression"], "properties": {"operation": {"type": "string", "enum": ["simplify", "solve", "factor", "expand", "integrate", "differentiate", "limit", "series", "verify_identity"]}, "expression": {"type": "string", "default": "1"}, "equation": {"type": "object"}, "variables": {"type": "array", "items": {"type": "string"}}, "assumptions": {"type": "object"}, "target_claim_id": {"type": "string"}}},
        output_schema={"type": "object", "required": ["status", "exact_result", "engine_version"], "properties": {"status": {"type": "string"}, "exact_result": {"type": "string"}, "latex": {"type": "string"}, "warnings": {"type": "array"}, "assumptions": {"type": "object"}, "target_claim_id": {"type": "string"}, "evidence_stance": {"type": "string"}, "engine_version": {"type": "string"}, "duration_ms": {"type": "number"}}},
        reliability=0.99,
        dependencies=["sympy"],
        timeout_seconds=15,
    )

    def execute(self, payload: dict) -> dict:
        started = time.perf_counter()
        equation = payload.get("equation") or {}
        text = str(payload.get("expression") or (f"({equation.get('lhs')})-({equation.get('rhs')})" if equation else "")).strip()
        operation = payload.get("operation") or payload.get("action", "simplify")
        if operation == "verify_identity":
            operation = "simplify"
        if not text or len(text) > 20_000:
            raise ValueError("Expression must contain 1 to 20,000 characters")
        allowed = {"simplify", "solve", "factor", "expand", "integrate", "differentiate", "limit", "series"}
        if operation not in allowed:
            raise ValueError("Unsupported symbolic operation")
        declarations = payload.get("variables") or payload.get("symbols", [])
        names = set(re.findall(r"[A-Za-z][A-Za-z0-9_]*", text))
        builtins = {"sin", "cos", "tan", "exp", "log", "sqrt", "pi", "E", "I"}
        forbidden = names - set(declarations) - builtins
        if forbidden:
            raise ValueError("Declare all symbols explicitly: " + ", ".join(sorted(forbidden)))
        local = {name: sp.Symbol(name, **payload.get("assumptions", {}).get(name, {})) for name in declarations}
        local.update({"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "log": sp.log, "sqrt": sp.sqrt, "pi": sp.pi, "E": sp.E, "I": sp.I})
        expression = parse_expr(text, local_dict=local, global_dict={**sp.__dict__, "__builtins__": {}}, transformations=standard_transformations, evaluate=False)
        variable_name = payload.get("variable") or (declarations[0] if declarations else None)
        variable = local.get(variable_name) if variable_name else None
        if operation == "solve":
            result = sp.solve(expression, variable) if variable else sp.solve(expression)
        elif operation == "factor":
            result = sp.factor(expression)
        elif operation == "expand":
            result = sp.expand(expression)
        elif operation == "integrate":
            result = sp.integrate(expression, variable) if variable else sp.integrate(expression)
        elif operation == "differentiate":
            result = sp.diff(expression, variable) if variable else sp.diff(expression)
        elif operation == "limit":
            result = sp.limit(expression, variable, payload.get("point", 0))
        elif operation == "series":
            result = sp.series(expression, variable, payload.get("point", 0), int(payload.get("order", 6)))
        else:
            result = sp.simplify(expression)
        return {
            "status": "success",
            "execution_mode": "local",
            "normalized_input": str(expression),
            "operation": operation,
            "result": str(result),
            "latex": sp.latex(result),
            "warnings": [],
            "verification_status": "symbolically_computed",
            "engine": "sympy",
            "engine_version": sp.__version__,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "exact_result": str(result),
            "assumptions": payload.get("assumptions", {}),
            "target_claim_id": payload.get("target_claim_id", ""),
            "evidence_stance": "supports" if str(result) in {"0", "True"} else "tests",
        }
