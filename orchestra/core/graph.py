from collections import defaultdict, deque


class GraphCycleError(ValueError):
    pass


class ResearchGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.outgoing = defaultdict(set)
        self.incoming = defaultdict(set)

    def add_node(self, n):
        if n.id in self.nodes:
            raise ValueError("Node already exists")
        self.nodes[n.id] = n

    def add_edge(self, e):
        if e.source_id not in self.nodes or e.target_id not in self.nodes:
            raise ValueError("Both endpoints must exist")
        if e.source_id == e.target_id:
            raise GraphCycleError("Self-loop")
        self.outgoing[e.source_id].add(e.target_id)
        self.incoming[e.target_id].add(e.source_id)
        if self.has_cycle():
            self.outgoing[e.source_id].remove(e.target_id)
            self.incoming[e.target_id].remove(e.source_id)
            raise GraphCycleError("Edge introduces cycle")
        self.edges[e.id] = e

    def has_cycle(self):
        state = {n: 0 for n in self.nodes}

        def visit(n):
            state[n] = 1
            for x in self.outgoing.get(n, ()):
                if state[x] == 1:
                    return True
                if state[x] == 0 and visit(x):
                    return True
            state[n] = 2
            return False

        return any(state[n] == 0 and visit(n) for n in self.nodes)

    def descendants(self, n):
        out = set()
        q = deque(self.outgoing.get(n, ()))
        while q:
            x = q.popleft()
            if x not in out:
                out.add(x)
                q.extend(self.outgoing.get(x, ()))
        return out
