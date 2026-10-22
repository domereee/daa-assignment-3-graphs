"""Independent reference solutions and semantic checkers for Assignment 3.

Author: Tuleubayev Damir.

Nothing here imports the Java solution or tools/public_validate.py. The
reference solutions deliberately use *different* algorithms from the graded
implementation where that is practical, so that an error in one is unlikely
to be repeated in the other:

    dsu      -> smaller-into-larger merging of explicit member lists
    kruskal/prim optimum -> exhaustive subset search (tiny graphs) or a
                plain Python Kruskal (large graphs)
    scc      -> pairwise reachability (tiny graphs) or iterative Tarjan
    topo     -> Kahn's in-degree algorithm (cycle detection)
    dag      -> Bellman-Ford (tiny graphs) or Kahn order + relaxation

Checkers verify answers *semantically*, so every valid non-unique answer
(another optimal forest, other SCC labels, another topological order,
another shortest-path parent) is accepted and every invalid witness rejected.
"""
from collections import deque
from itertools import combinations

INT64_MIN, INT64_MAX = -(1 << 63), (1 << 63) - 1


def is_int(value):
    return type(value) is int and INT64_MIN <= value <= INT64_MAX


# ---------------------------------------------------------------------------
# Reference solutions
# ---------------------------------------------------------------------------

def ref_dsu(n, operations):
    """Explicit member lists; the smaller list is moved into the larger one."""
    owner = list(range(n))
    members = [[v] for v in range(n)]
    components, largest, states = n, (1 if n else 0), []
    for u, v in operations:
        a, b = owner[u], owner[v]
        if a != b:
            if len(members[a]) < len(members[b]):
                a, b = b, a
            for x in members[b]:
                owner[x] = a
            members[a].extend(members[b])
            members[b] = []
            components -= 1
            largest = max(largest, len(members[a]))
        states.append([components, largest])
    return states


def _components_count(n, pairs):
    parent = list(range(n))

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    count = n
    for u, v in pairs:
        a, b = root(u), root(v)
        if a != b:
            parent[a] = b
            count -= 1
    return count


def ref_msf_bruteforce(n, edges):
    """Exhaustive search over all (n-c)-edge subsets. Only for tiny graphs."""
    c = _components_count(n, [(u, v) for u, v, _ in edges])
    need = n - c
    best = None
    for subset in combinations(range(len(edges)), need):
        chosen = [edges[i] for i in subset]
        if any(u == v for u, v, _ in chosen):
            continue
        if _components_count(n, [(u, v) for u, v, _ in chosen]) != c:
            continue  # Contains a cycle, so it does not span every component.
        cost = sum(w for _, _, w in chosen)
        best = cost if best is None else min(best, cost)
    return (0 if best is None else best), c


def ref_msf_kruskal(n, edges):
    """Plain Python Kruskal (used only as a reference for large graphs)."""
    parent = list(range(n))

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    cost, used = 0, 0
    for i in sorted(range(len(edges)), key=lambda i: edges[i][2]):
        u, v, w = edges[i]
        a, b = root(u), root(v)
        if a != b:
            parent[a] = b
            cost += w
            used += 1
    return cost, n - used


def ref_scc_bruteforce(n, edges):
    """u and v share an SCC iff each reaches the other (BFS from every vertex)."""
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    reach = []
    for s in range(n):
        seen = {s}
        queue = deque([s])
        while queue:
            x = queue.popleft()
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    queue.append(y)
        reach.append(seen)
    group = [-1] * n
    for v in range(n):
        if group[v] == -1:
            for u in range(n):
                if u in reach[v] and v in reach[u]:
                    group[u] = v
    return group


def ref_scc_tarjan(n, edges):
    """Iterative Tarjan; returns one representative id per vertex."""
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    index = [-1] * n
    low = [0] * n
    on_stack = [False] * n
    stack, group, counter = [], [-1] * n, 0
    for root in range(n):
        if index[root] != -1:
            continue
        work = [(root, 0)]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack[root] = True
        while work:
            v, i = work[-1]
            if i < len(adj[v]):
                work[-1] = (v, i + 1)
                w = adj[v][i]
                if index[w] == -1:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack[w] = True
                    work.append((w, 0))
                elif on_stack[w]:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[v])
                if low[v] == index[v]:
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        group[w] = v
                        if w == v:
                            break
    return group


def ref_is_acyclic(n, edges):
    """Kahn's algorithm: acyclic iff every vertex is eventually removed."""
    indegree = [0] * n
    adj = [[] for _ in range(n)]
    for e in edges:
        adj[e[0]].append(e[1])
        indegree[e[1]] += 1
    queue = deque(v for v in range(n) if indegree[v] == 0)
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    return len(order) == n, order


def ref_dag_bellman_ford(n, edges, source):
    acyclic, _ = ref_is_acyclic(n, edges)
    if not acyclic:
        return False, None
    dist = [None] * n
    dist[source] = 0
    for _ in range(max(0, n - 1)):
        for u, v, w in edges:
            if dist[u] is not None and (dist[v] is None or dist[u] + w < dist[v]):
                dist[v] = dist[u] + w
    return True, dist


def ref_dag_kahn(n, edges, source):
    acyclic, order = ref_is_acyclic(n, edges)
    if not acyclic:
        return False, None
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w))
    dist = [None] * n
    dist[source] = 0
    for u in order:
        if dist[u] is None:
            continue
        for v, w in adj[u]:
            if dist[v] is None or dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    return True, dist


# ---------------------------------------------------------------------------
# Semantic checkers: return None when valid, otherwise a reason string.
# ---------------------------------------------------------------------------

def check_dsu(request, answer, expected_states):
    states = answer.get("states")
    if not isinstance(states, list) or len(states) != len(request["operations"]):
        return "states has the wrong length"
    if any(not (isinstance(s, list) and len(s) == 2 and all(is_int(x) for x in s)) for s in states):
        return "every state must be [components, largest]"
    if states != expected_states:
        first = next(i for i, (a, b) in enumerate(zip(states, expected_states)) if a != b)
        return f"state {first}: got {states[first]}, expected {expected_states[first]}"
    return None


def check_forest(request, answer, expected_cost, expected_components):
    n, edges = request["n"], request["edges"]
    cost, ids, comps = answer.get("cost"), answer.get("edge_ids"), answer.get("components")
    if not (is_int(cost) and is_int(comps) and isinstance(ids, list) and all(is_int(i) for i in ids)):
        return "cost/components must be integers and edge_ids an integer list"
    if comps != expected_components:
        return f"components {comps} != {expected_components}"
    if cost != expected_cost:
        return f"cost {cost} != optimum {expected_cost}"
    if len(set(ids)) != len(ids):
        return "repeated edge id"
    if len(ids) != n - comps:
        return f"forest has {len(ids)} edges, expected n - c = {n - comps}"
    parent = list(range(n))

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    total = 0
    for i in ids:
        if not 0 <= i < len(edges):
            return f"edge id {i} out of range"
        u, v, w = edges[i]
        a, b = root(u), root(v)
        if a == b:
            return f"edge id {i} closes a cycle (or is a self-loop)"
        parent[a] = b
        total += w
    if total != cost:
        return f"selected weights sum to {total}, reported cost {cost}"
    if any(root(u) != root(v) for u, v, _ in edges):
        return "forest does not span a connected component of the input"
    return None


def check_scc(request, answer, reference_group):
    n, edges = request["n"], request["edges"]
    labels, pairs = answer.get("component"), answer.get("condensation")
    if not (isinstance(labels, list) and len(labels) == n and all(is_int(x) and x >= 0 for x in labels)):
        return "component must hold one non-negative integer label per vertex"
    forward, backward = {}, {}
    for v in range(n):
        a, b = labels[v], reference_group[v]
        if forward.setdefault(a, b) != b or backward.setdefault(b, a) != a:
            return f"vertex {v}: label partition differs from the true SCCs"
    if not (isinstance(pairs, list) and all(isinstance(p, list) and len(p) == 2 and all(is_int(x) for x in p)
                                            for p in pairs)):
        return "condensation must be a list of [from,to] pairs"
    got = [tuple(p) for p in pairs]
    if len(got) != len(set(got)):
        return "duplicate condensation pair"
    want = {(labels[u], labels[v]) for u, v in edges if labels[u] != labels[v]}
    if set(got) != want:
        missing, extra = want - set(got), set(got) - want
        return f"condensation mismatch: missing {sorted(missing)[:3]}, extra {sorted(extra)[:3]}"
    return None


def check_topo(request, answer, expected_acyclic):
    n, edges = request["n"], request["edges"]
    if type(answer.get("acyclic")) is not bool or answer["acyclic"] != expected_acyclic:
        return f"acyclic should be {expected_acyclic}"
    order = answer.get("order")
    if not expected_acyclic:
        return None if order == [] else "cyclic graph must return an empty order"
    if not (isinstance(order, list) and len(order) == n and all(is_int(v) for v in order)):
        return "order must list n integers"
    position = [-1] * n
    for i, v in enumerate(order):
        if not 0 <= v < n or position[v] != -1:
            return f"vertex {v} missing or repeated"
        position[v] = i
    for u, v in edges:
        if position[u] >= position[v]:
            return f"edge {u}->{v} goes backwards in the order"
    return None


def check_dag(request, answer, expected_acyclic, expected_distance):
    n, edges, source = request["n"], request["edges"], request["source"]
    if type(answer.get("acyclic")) is not bool or answer["acyclic"] != expected_acyclic:
        return f"acyclic should be {expected_acyclic}"
    dist, parent = answer.get("distance"), answer.get("parent_edge")
    if not expected_acyclic:
        return None if dist == [] and parent == [] else "cyclic graph must return two empty arrays"
    if not (isinstance(dist, list) and len(dist) == n and isinstance(parent, list) and len(parent) == n):
        return "distance and parent_edge must have length n"
    if any(d is not None and not is_int(d) for d in dist) or any(not is_int(p) for p in parent):
        return "bad value types"
    if dist != expected_distance:
        v = next(i for i in range(n) if dist[i] != expected_distance[i])
        return f"distance[{v}] = {dist[v]}, expected {expected_distance[v]}"
    for v in range(n):
        if v == source or dist[v] is None:
            if parent[v] != -1:
                return f"parent_edge[{v}] must be -1"
            continue
        e = parent[v]
        if not 0 <= e < len(edges):
            return f"parent_edge[{v}] = {e} out of range"
        a, b, w = edges[e]
        if b != v:
            return f"parent edge {e} of vertex {v} ends at {b}"
        if dist[a] is None or dist[a] + w != dist[v]:
            return f"parent edge {e} is not tight for vertex {v}"
    # Tight parent edges strictly follow a topological order of a DAG, so every chain
    # is finite; it must also end at the source.
    done = [False] * n
    done[source] = True
    for v in range(n):
        if dist[v] is None:
            continue
        chain, x = [], v
        while not done[x]:
            chain.append(x)
            e = parent[x]
            if e < 0:
                return f"parent chain from {v} stops at {x} before the source"
            x = edges[e][0]
            if len(chain) > n:
                return "parent chain loops"
        for y in chain:
            done[y] = True
    return None


def check(request, answer, expected):
    """Dispatch with an expected-value dict (as stored in tests/cases)."""
    task = request["task"]
    if task == "dsu":
        return check_dsu(request, answer, expected["states"])
    if task in ("kruskal", "prim"):
        return check_forest(request, answer, expected["cost"], expected["components"])
    if task == "scc":
        return check_scc(request, answer, expected["group"])
    if task == "topo":
        return check_topo(request, answer, expected["acyclic"])
    if task == "dag":
        return check_dag(request, answer, expected["acyclic"], expected.get("distance"))
    if task == "ping":
        return None if answer == {"status": "ready"} else "ping must answer ready"
    return f"unknown task {task}"


def reference(request, tiny=False):
    """Expected-value dict computed by an independent reference algorithm."""
    task, n = request["task"], request["n"]
    if task == "dsu":
        return {"states": ref_dsu(n, request["operations"])}
    if task in ("kruskal", "prim"):
        cost, comps = (ref_msf_bruteforce if tiny else ref_msf_kruskal)(n, request["edges"])
        return {"cost": cost, "components": comps}
    if task == "scc":
        return {"group": (ref_scc_bruteforce if tiny else ref_scc_tarjan)(n, request["edges"])}
    if task == "topo":
        return {"acyclic": ref_is_acyclic(n, request["edges"])[0]}
    if task == "dag":
        acyclic, dist = (ref_dag_bellman_ford if tiny else ref_dag_kahn)(n, request["edges"], request["source"])
        return {"acyclic": acyclic, "distance": dist}
    raise ValueError(task)
