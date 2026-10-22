"""Own test-suite for Assignment 3 (Java solution, JSON Lines interface).

Author: Tuleubayev Damir.

Run from the repository root:

    python tests/run_tests.py            # everything (about a minute)
    python tests/run_tests.py --quick    # skip the full-limit inputs

Groups:
  1. handmade      - tests/cases/handmade.json: hand-computed expected answers with
                     a written justification; also cross-checked by the references.
  2. random-small  - 1500 seeded random tiny graphs (n <= 7), expected answers by
                     brute force (subset search, pairwise reachability, Bellman-Ford).
  3. checker       - the semantic checker accepts alternative valid answers and
                     rejects invalid witnesses (so it is not just "equal to mine").
  4. full-limits   - n = 100000, m / q = 250000, deep chains of 100000 vertices,
                     64-bit totals, a cycle unreachable from the DAG source.
                     Each input runs in its own process and is timed.
  5. state-reset   - one process answers a mixed batch (handmade x3 interleaved
                     with full-limit requests); every answer is checked again.

Actual outputs are written to tests/results/. Inputs for groups 2, 4 and 5 are
regenerated from fixed seeds (see generators below), so they are reproducible
without storing tens of megabytes of JSON.
"""
import json
import pathlib
import random
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import checker  # noqa: E402
from run import build, select_language  # noqa: E402  (supplied launcher)

RESULTS = ROOT / "tests" / "results"
SEED = 20261019
REPORT = []


def log(line=""):
    print(line)
    REPORT.append(line)


def run_batch(command, requests, timeout=20):
    data = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in requests)
    started = time.perf_counter()
    proc = subprocess.run(command, input=data, capture_output=True, text=True,
                          encoding="utf-8", timeout=timeout)
    elapsed = time.perf_counter() - started
    if proc.returncode:
        raise RuntimeError(proc.stderr[-2000:])
    lines = proc.stdout.splitlines()
    if len(lines) != len(requests):
        raise RuntimeError(f"expected {len(requests)} lines, got {len(lines)}")
    return [json.loads(line) for line in lines], elapsed, lines


# ---------------------------------------------------------------------------
# Generators (seeded)
# ---------------------------------------------------------------------------

def random_small(rng, task):
    n = rng.randint(1 if task == "dag" else 0, 7)
    m = rng.randint(0, 9) if n else 0
    if task == "dsu":
        return {"task": "dsu", "n": n, "operations": [[rng.randrange(n), rng.randrange(n)] for _ in range(m)]}
    if task in ("kruskal", "prim"):
        return {"task": task, "n": n,
                "edges": [[rng.randrange(n), rng.randrange(n), rng.choice([-3, -1, 0, 1, 2, 2, 5, 10**9])]
                          for _ in range(m)]}
    if task in ("scc", "topo"):
        if task == "topo" and rng.random() < 0.6:  # Bias towards DAGs so orders get tested.
            perm = list(range(n))
            rng.shuffle(perm)
            edges = []
            for _ in range(m):
                a, b = sorted(rng.sample(range(n), 2)) if n > 1 else (0, 0)
                if a != b:
                    edges.append([perm[a], perm[b]])
            return {"task": task, "n": n, "edges": edges}
        return {"task": task, "n": n, "edges": [[rng.randrange(n), rng.randrange(n)] for _ in range(m)]}
    # dag
    perm = list(range(n))
    rng.shuffle(perm)
    edges = []
    for _ in range(m):
        if n > 1 and rng.random() < 0.9:
            a, b = sorted(rng.sample(range(n), 2))
            edges.append([perm[a], perm[b], rng.randint(-5, 5)])
        else:
            u = rng.randrange(n)
            edges.append([u, rng.randrange(n), rng.randint(-5, 5)])  # May create a cycle.
    return {"task": "dag", "n": n, "source": rng.randrange(n), "edges": edges}


def random_dag_edges(rng, n, m, weighted, wlo=-10**9, whi=10**9):
    perm = list(range(n))
    rng.shuffle(perm)
    edges = []
    for _ in range(m):
        a, b = rng.randrange(n), rng.randrange(n)
        while a == b:
            b = rng.randrange(n)
        if a > b:
            a, b = b, a
        e = [perm[a], perm[b]]
        if weighted:
            e.append(rng.randint(wlo, whi))
        edges.append(e)
    return edges, perm


def permuted_chain(rng, n, weight=None):
    perm = list(range(n))
    rng.shuffle(perm)
    edges = [[perm[i], perm[i + 1]] for i in range(n - 1)]
    if weight is not None:
        for e in edges:
            e.append(weight)
    return perm, edges


def full_limit_cases():
    rng = random.Random(SEED)
    N, M = 100000, 250000
    cases = []
    cases.append(("dsu random n=1e5 q=2.5e5",
                  {"task": "dsu", "n": N, "operations": [[rng.randrange(N), rng.randrange(N)] for _ in range(M)]}))
    wedges = [[rng.randrange(N), rng.randrange(N), rng.randint(-10**9, 10**9)] for _ in range(M)]
    cases.append(("kruskal random n=1e5 m=2.5e5", {"task": "kruskal", "n": N, "edges": wedges}))
    cases.append(("prim same random graph", {"task": "prim", "n": N, "edges": wedges}))
    _, path = permuted_chain(rng, N, 10**9)
    cases.append(("kruskal deep path, cost 99999e9", {"task": "kruskal", "n": N, "edges": path}))
    cases.append(("prim deep path, cost 99999e9", {"task": "prim", "n": N, "edges": path}))
    dense = [[rng.randrange(1000), rng.randrange(1000), rng.choice([-10**9, 10**9])] for _ in range(M)]
    cases.append(("prim many parallel/tied edges n=1e5 (99000 isolates)", {"task": "prim", "n": N, "edges": dense}))
    cases.append(("kruskal many parallel/tied edges n=1e5", {"task": "kruskal", "n": N, "edges": dense}))
    cases.append(("scc random n=1e5 m=2.5e5",
                  {"task": "scc", "n": N, "edges": [[rng.randrange(N), rng.randrange(N)] for _ in range(M)]}))
    perm, chain = permuted_chain(rng, N)
    cases.append(("scc deep chain closed into one cycle", {"task": "scc", "n": N, "edges": chain + [[perm[-1], perm[0]]]}))
    cases.append(("scc deep chain, 1e5 singleton SCCs", {"task": "scc", "n": N, "edges": chain}))
    cases.append(("topo random DAG n=1e5 m=2.5e5",
                  {"task": "topo", "n": N, "edges": random_dag_edges(rng, N, M, False)[0]}))
    cases.append(("topo deep chain", {"task": "topo", "n": N, "edges": chain}))
    cases.append(("topo deep chain with one back edge", {"task": "topo", "n": N, "edges": chain + [[perm[-1], perm[0]]]}))
    dag_edges, dag_rank = random_dag_edges(rng, N, M, True)
    cases.append(("dag random DAG n=1e5 m=2.5e5, source = first in rank",
                  {"task": "dag", "n": N, "source": dag_rank[0], "edges": dag_edges}))
    backbone = [[dag_rank[i], dag_rank[i + 1], rng.randint(-10**9, 10**9)] for i in range(N - 1)]
    mixed = backbone + dag_edges[: M - (N - 1)]
    rng.shuffle(mixed)
    cases.append(("dag DAG with backbone, all reachable, m=2.5e5",
                  {"task": "dag", "n": N, "source": dag_rank[0], "edges": mixed}))
    cases.append(("dag same DAG, random source",
                  {"task": "dag", "n": N, "source": rng.randrange(N), "edges": dag_edges}))
    perm2, neg_chain = permuted_chain(rng, N, -10**9)
    cases.append(("dag deep chain of -1e9 (distance -99999e9)",
                  {"task": "dag", "n": N, "source": perm2[0], "edges": neg_chain}))
    cases.append(("dag deep chain, source in the middle",
                  {"task": "dag", "n": N, "source": perm2[N // 2], "edges": neg_chain}))
    with_cycle = dag_edges[:-3] + [[0, 1, 0], [1, 2, 0], [2, 0, 0]]
    src = rng.randrange(3, N)
    cases.append(("dag large graph with a cycle (source elsewhere)",
                  {"task": "dag", "n": N, "source": src, "edges": with_cycle}))
    return cases


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

def group_handmade(command):
    cases = json.loads((ROOT / "tests" / "cases" / "handmade.json").read_text(encoding="utf-8"))
    answers, _, lines = run_batch(command, [c["input"] for c in cases])
    with open(RESULTS / "handmade_actual.jsonl", "w", encoding="utf-8") as out:
        for case, line in zip(cases, lines):
            out.write(json.dumps({"name": case["name"]}) + "\n" + line + "\n")
    failures = 0
    for case, answer in zip(cases, answers):
        request, expected = case["input"], dict(case["expected"])
        if request["task"] != "ping":
            # Independent second justification: the reference agrees with the hand value.
            ref = checker.reference(request, tiny=True)
            agree = all(ref[k] == v for k, v in expected.items() if k != "group")
            if "group" in expected:  # Same partition, whatever the representative names.
                agree = len({(a, b) for a, b in zip(expected["group"], ref["group"])}) == len(set(expected["group"])) \
                    == len(set(ref["group"]))
            if not agree:
                failures += 1
                log(f"  HAND-VALUE MISMATCH {case['name']}: reference says {ref}")
                continue
        reason = checker.check(request, answer, expected)
        if reason:
            failures += 1
            log(f"  FAIL {case['name']}: {reason}")
    log(f"[handmade]     {len(cases) - failures}/{len(cases)} passed  (actual outputs: tests/results/handmade_actual.jsonl)")
    return failures


def group_random_small(command):
    rng = random.Random(SEED)
    requests = [random_small(rng, task) for task in ("dsu", "kruskal", "prim", "scc", "topo", "dag") for _ in range(250)]
    answers, _, _ = run_batch(command, requests)
    failures = 0
    for request, answer in zip(requests, answers):
        reason = checker.check(request, answer, checker.reference(request, tiny=True))
        if reason:
            failures += 1
            if failures <= 5:
                log(f"  FAIL {json.dumps(request)} -> {answer}: {reason}")
    log(f"[random-small] {len(requests) - failures}/{len(requests)} passed  (seed {SEED}, brute-force references)")
    return failures


def group_checker():
    """The checker must accept every valid alternative and reject invalid witnesses."""
    tied = {"task": "prim", "n": 4, "edges": [[0, 1, 1], [1, 2, 1], [2, 3, 1], [3, 0, 1], [0, 2, 5]]}
    scc_req = {"task": "scc", "n": 4, "edges": [[0, 1], [1, 0], [1, 2], [0, 2], [2, 3]]}
    topo_req = {"task": "topo", "n": 4, "edges": [[0, 2], [1, 2], [2, 3]]}
    dag_req = {"task": "dag", "n": 4, "source": 0, "edges": [[0, 1, 1], [0, 2, 1], [1, 3, 1], [2, 3, 1], [1, 3, 1]]}
    dag_exp = {"acyclic": True, "distance": [0, 1, 1, 2]}
    forest_exp = {"cost": 3, "components": 1}
    scc_exp = {"group": [0, 0, 2, 3]}
    cases = [
        # (description, request, answer, expected, should_be_valid)
        ("forest A {0,1,2}", tied, {"cost": 3, "edge_ids": [0, 1, 2], "components": 1}, forest_exp, True),
        ("alternative forest {3,0,1} in another order", tied, {"cost": 3, "edge_ids": [3, 0, 1], "components": 1}, forest_exp, True),
        ("forest with a cycle 0-1-2-3-0", tied, {"cost": 4, "edge_ids": [0, 1, 2, 3], "components": 1}, forest_exp, False),
        ("too few edges, cost understated", tied, {"cost": 2, "edge_ids": [0, 1], "components": 1}, forest_exp, False),
        ("repeated edge id", tied, {"cost": 3, "edge_ids": [0, 0, 1], "components": 1}, forest_exp, False),
        ("non-optimal forest (uses weight 5)", tied, {"cost": 7, "edge_ids": [0, 4, 2], "components": 1}, forest_exp, False),
        ("reported cost differs from chosen edges", tied, {"cost": 3, "edge_ids": [0, 4, 2], "components": 1}, forest_exp, False),
        ("SCC labels 5,5,7,9", scc_req, {"component": [5, 5, 7, 9], "condensation": [[5, 7], [7, 9]]}, scc_exp, True),
        ("SCC labels 100,100,3,0 (other names)", scc_req, {"component": [100, 100, 3, 0], "condensation": [[3, 0], [100, 3]]}, scc_exp, True),
        ("SCC splits a real component", scc_req, {"component": [1, 2, 3, 4], "condensation": [[1, 2], [2, 1], [2, 3], [1, 3], [3, 4]]}, scc_exp, False),
        ("SCC duplicate condensation pair", scc_req, {"component": [5, 5, 7, 9], "condensation": [[5, 7], [5, 7], [7, 9]]}, scc_exp, False),
        ("SCC missing condensation pair", scc_req, {"component": [5, 5, 7, 9], "condensation": [[5, 7]]}, scc_exp, False),
        ("SCC internal pair listed", scc_req, {"component": [5, 5, 7, 9], "condensation": [[5, 5], [5, 7], [7, 9]]}, scc_exp, False),
        ("SCC negative label", scc_req, {"component": [-1, -1, 7, 9], "condensation": [[-1, 7], [7, 9]]}, scc_exp, False),
        ("topo order [1,0,2,3]", topo_req, {"acyclic": True, "order": [1, 0, 2, 3]}, {"acyclic": True}, True),
        ("alternative topo order [0,1,2,3]", topo_req, {"acyclic": True, "order": [0, 1, 2, 3]}, {"acyclic": True}, True),
        ("topo order breaks 2->3", topo_req, {"acyclic": True, "order": [0, 1, 3, 2]}, {"acyclic": True}, False),
        ("topo order repeats a vertex", topo_req, {"acyclic": True, "order": [0, 1, 2, 2]}, {"acyclic": True}, False),
        ("DAG parent via edge 2 then edge 3", dag_req, {"acyclic": True, "distance": [0, 1, 1, 2], "parent_edge": [-1, 0, 1, 3]}, dag_exp, True),
        ("DAG tie: parent via edge 2", dag_req, {"acyclic": True, "distance": [0, 1, 1, 2], "parent_edge": [-1, 0, 1, 2]}, dag_exp, True),
        ("DAG tie: parallel edge 4", dag_req, {"acyclic": True, "distance": [0, 1, 1, 2], "parent_edge": [-1, 0, 1, 4]}, dag_exp, True),
        ("DAG parent edge ends elsewhere", dag_req, {"acyclic": True, "distance": [0, 1, 1, 2], "parent_edge": [-1, 0, 0, 2]}, dag_exp, False),
        ("DAG wrong distance", dag_req, {"acyclic": True, "distance": [0, 1, 1, 3], "parent_edge": [-1, 0, 1, 2]}, dag_exp, False),
        ("DAG source with a parent", dag_req, {"acyclic": True, "distance": [0, 1, 1, 2], "parent_edge": [0, 0, 1, 2]}, dag_exp, False),
        ("DAG -1 used as unreachable distance",
         {"task": "dag", "n": 2, "source": 0, "edges": []}, {"acyclic": True, "distance": [0, -1], "parent_edge": [-1, -1]},
         {"acyclic": True, "distance": [0, None]}, False),
    ]
    failures = 0
    for description, request, answer, expected, valid in cases:
        verdict = checker.check(request, answer, expected) is None
        if verdict != valid:
            failures += 1
            log(f"  FAIL checker: {description} -> {'accepted' if verdict else 'rejected'}")
    log(f"[checker]      {len(cases) - failures}/{len(cases)} verdicts correct "
        f"({sum(c[4] for c in cases)} alternatives accepted, {sum(not c[4] for c in cases)} invalid witnesses rejected)")
    return failures


def group_full_limits(command):
    failures = 0
    rows = []
    for name, request in full_limit_cases():
        answers, elapsed, _ = run_batch(command, [request])
        expected = checker.reference(request, tiny=False)
        reason = checker.check(request, answers[0], expected)
        detail = ""
        if request["task"] in ("kruskal", "prim"):
            detail = f"cost={answers[0]['cost']} components={answers[0]['components']}"
        elif request["task"] == "dag":
            d = [x for x in answers[0]["distance"] if x is not None]
            detail = f"acyclic={answers[0]['acyclic']}" + (f" reachable={len(d)} min={min(d)}" if d else "")
        elif request["task"] == "topo":
            detail = f"acyclic={answers[0]['acyclic']}"
        elif request["task"] == "scc":
            detail = f"sccs={len(set(answers[0]['component']))} pairs={len(answers[0]['condensation'])}"
        elif request["task"] == "dsu":
            detail = f"final={answers[0]['states'][-1]}"
        status = "PASS" if reason is None else f"FAIL ({reason})"
        failures += reason is not None
        rows.append(f"  {status:5} {elapsed:6.2f}s  {name:52} {detail}")
    log(f"[full-limits]  {len(rows) - failures}/{len(rows)} passed (each in its own process; time includes JVM start + JSON I/O)")
    for row in rows:
        log(row)
    return failures


def group_state_reset(command):
    hand = [c["input"] for c in json.loads((ROOT / "tests" / "cases" / "handmade.json").read_text(encoding="utf-8"))]
    big = dict(full_limit_cases())
    heavy = [big["dsu random n=1e5 q=2.5e5"], big["dag deep chain of -1e9 (distance -99999e9)"],
             big["scc deep chain closed into one cycle"]]
    requests = hand + [heavy[0]] + hand + [heavy[1], heavy[2]] + hand
    answers, elapsed, _ = run_batch(command, requests)
    expected_cache = {}
    failures = 0
    for request, answer in zip(requests, answers):
        key = id(request)
        if key not in expected_cache:
            expected_cache[key] = {} if request["task"] == "ping" else checker.reference(request, tiny=request["n"] <= 8)
        reason = checker.check(request, answer, expected_cache[key])
        failures += reason is not None
    log(f"[state-reset]  {len(requests) - failures}/{len(requests)} answers valid in ONE process "
        f"(handmade x3 + 3 full-limit requests interleaved, {elapsed:.2f}s)")
    return failures


def main():
    quick = "--quick" in sys.argv
    RESULTS.mkdir(parents=True, exist_ok=True)
    language = select_language(None)
    command = build(language)
    log(f"Language: {language} (same build and 'java -Xmx384m Main' command as tools/run.py)")
    failures = group_handmade(command)
    failures += group_random_small(command)
    failures += group_checker()
    if not quick:
        failures += group_full_limits(command)
        failures += group_state_reset(command)
    log("ALL TESTS PASSED" if not failures else f"{failures} FAILURE(S)")
    if not quick:
        (RESULTS / "test_report.txt").write_text("\n".join(REPORT) + "\n", encoding="utf-8")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
