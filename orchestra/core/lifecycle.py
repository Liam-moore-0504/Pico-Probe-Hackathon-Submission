from orchestra.core.enums import ClaimStatus

_ALLOWED = {
    ClaimStatus.UNVERIFIED: {ClaimStatus.PROPOSED},
    ClaimStatus.PROPOSED: {ClaimStatus.UNDER_TEST, ClaimStatus.DISPROVEN, ClaimStatus.INCONCLUSIVE},
    ClaimStatus.UNDER_TEST: {ClaimStatus.TESTED, ClaimStatus.COUNTEREXAMPLE_FOUND, ClaimStatus.INCONCLUSIVE},
    ClaimStatus.TESTED: {ClaimStatus.SUPPORTED, ClaimStatus.COUNTEREXAMPLE_FOUND, ClaimStatus.INCONCLUSIVE},
    ClaimStatus.SUPPORTED: {ClaimStatus.INDEPENDENTLY_CONFIRMED, ClaimStatus.FORMALLY_VERIFIED, ClaimStatus.COUNTEREXAMPLE_FOUND},
    ClaimStatus.INDEPENDENTLY_CONFIRMED: {ClaimStatus.FORMALLY_VERIFIED, ClaimStatus.COUNTEREXAMPLE_FOUND},
    ClaimStatus.COUNTEREXAMPLE_FOUND: {ClaimStatus.DISPROVEN, ClaimStatus.INCONCLUSIVE},
    ClaimStatus.FORMALLY_VERIFIED: {ClaimStatus.INVALIDATED, ClaimStatus.COUNTEREXAMPLE_FOUND},
    ClaimStatus.DISPROVEN: set(),
    ClaimStatus.INVALIDATED: set(),
    ClaimStatus.INCONCLUSIVE: {ClaimStatus.UNDER_TEST},
}


class InvalidClaimTransition(ValueError):
    pass


def transition(current: ClaimStatus, target: ClaimStatus, facts: dict | None = None) -> ClaimStatus:
    if target not in _ALLOWED.get(current, set()):
        raise InvalidClaimTransition(f"Invalid claim transition: {current.value} -> {target.value}")
    facts = facts or {}
    guards = {
        ClaimStatus.SUPPORTED: ("supporting_evidence", "Supporting evidence is required"),
        ClaimStatus.INDEPENDENTLY_CONFIRMED: ("independent_sources", "Two independent sources are required"),
        ClaimStatus.FORMALLY_VERIFIED: ("formal_verification", "Compiler-backed formal verification is required"),
        ClaimStatus.COUNTEREXAMPLE_FOUND: ("counterexample", "A linked counterexample is required"),
        ClaimStatus.DISPROVEN: ("falsification", "A linked falsification or authorized human decision is required"),
    }
    if target in guards:
        key, message = guards[target]
        value = facts.get(key)
        if key == "independent_sources":
            if int(value or 0) < 2:
                raise InvalidClaimTransition(message)
        elif not value:
            raise InvalidClaimTransition(message)
    return target
