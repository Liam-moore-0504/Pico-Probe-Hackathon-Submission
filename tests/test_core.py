import pytest

from orchestra.core.enums import ClaimStatus, EdgeType, NodeKind
from orchestra.core.graph import GraphCycleError, ResearchGraph
from orchestra.core.lifecycle import InvalidClaimTransition, transition
from orchestra.core.models import ResearchEdge, ResearchNode


def test_lifecycle():
    assert transition(ClaimStatus.PROPOSED, ClaimStatus.UNDER_TEST) == ClaimStatus.UNDER_TEST
    with pytest.raises(InvalidClaimTransition):
        transition(ClaimStatus.PROPOSED, ClaimStatus.FORMALLY_VERIFIED)


def test_cycle():
    g = ResearchGraph()
    a = ResearchNode(kind=NodeKind.QUESTION, title="a")
    b = ResearchNode(kind=NodeKind.CLAIM, title="b")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(ResearchEdge(source_id=a.id, target_id=b.id, edge_type=EdgeType.DEPENDS_ON))
    with pytest.raises(GraphCycleError):
        g.add_edge(ResearchEdge(source_id=b.id, target_id=a.id, edge_type=EdgeType.REFINES))
