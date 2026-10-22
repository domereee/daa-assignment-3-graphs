# Own tests — Assignment 3 (Tuleubayev Damir)

Language: **Java 17** (`submission.json` → `"Java"`). All commands run from the repository root.

```sh
python tools/run.py --setup                      # build + ping
python tools/run.py --check                      # 36 public cases + state-reset batch
python tests/run_tests.py                        # own JSON-Lines suite (≈ 30 s)
python tests/run_java_tests.py                   # route-helper tests + Kruskal/Prim benchmark
python tools/run.py --input tests/my_cases.jsonl # print raw actual results for the hand-made inputs
```

On Windows use `py -3` instead of `python`.

## Files

| File | What it is |
|---|---|
| `cases/handmade.json` | 34 hand-made inputs, each with an **expected** answer and a written **justification** (`why`). |
| `my_cases.jsonl` | The same 34 inputs as JSON Lines, for `tools/run.py --input`. |
| `checker.py` | Independent reference solutions + semantic checkers (no code shared with the Java solution or with `tools/public_validate.py`). |
| `run_tests.py` | Runs the program through the same build/launch command as `tools/run.py` and checks every answer. |
| `RouteHelperTest.java` | Calls the route helper `Algorithms.reconstructRoute` directly. |
| `Benchmark.java` | Kruskal vs Prim on identical seeded graphs at three sizes. |
| `run_java_tests.py` | Compiles and runs the two Java files above. |
| `results/handmade_actual.jsonl` | Actual output for each hand-made case (name line + result line). |
| `results/my_cases_output.jsonl` | Raw output of `tools/run.py --input tests/my_cases.jsonl`. |
| `results/test_report.txt` | Output of the last full `run_tests.py` run (with timings). |
| `results/route_helper_output.txt` | Output of `RouteHelperTest`. |
| `results/benchmark.md` | Output of `Benchmark` (table used in `ANALYSIS.md`). |

## Test groups (`run_tests.py`)

1. **handmade** (34) — every hand value is additionally re-derived by the brute-force
   reference, so each expected answer is justified twice (by hand and by a different
   algorithm). Covers: ping; DSU self-unions, repeated unions, zero operations, `n=1`;
   MSF isolates, negative self-loops, all-negative weights, parallel/tied edges, several
   components, ±64-bit totals; SCC with duplicate cross pairs, one big cycle, DAG with
   duplicate edge, self-loops; topo diamond, cycle in another component, cross edge to a
   finished vertex (must **not** be a cycle), self-cycle; DAG negative edges, source in the
   middle with unreachable predecessors, cycle/self-loop unreachable from the source,
   parallel tied edges, distances `-1` and `0`, −3·10⁹.
2. **random-small** (1500) — 250 seeded random graphs per task with `n ≤ 7`, loops and
   duplicates allowed. Expected answers: explicit member-list merging (DSU), exhaustive
   subset search (MSF optimum), pairwise BFS reachability (SCC), Kahn's algorithm (cycle
   detection), Bellman–Ford (DAG distances).
3. **checker** (25) — proves the checking is semantic: it **accepts** 9 alternative valid
   answers (another optimal forest, edge IDs in another order, other SCC label names,
   another topological order, tied/parallel DAG parent edges) and **rejects** 16 invalid
   witnesses (forest with a cycle, repeated ID, non-optimal forest, wrong cost, split SCC,
   duplicate/missing/internal condensation pair, negative label, order breaking an edge,
   repeated vertex, parent edge ending elsewhere, wrong distance, parent on the source,
   `-1` used as "unreachable").
4. **full-limits** (19) — `n = 100000`, `m`/`q = 250000`, each input in a fresh process and
   timed (all well under the 20 s limit): random DSU, Kruskal and Prim on the *same*
   random graph, deep path with cost 99 999·10⁹, 250 000 parallel/tied edges with 99 000
   isolates, random SCC, deep chain closed into one SCC, deep chain of 100 000 singleton
   SCCs, random DAG topo, deep chain topo, deep chain + one back edge, DAG shortest paths
   (random, with backbone so all 100 000 vertices are reachable, random source), deep
   chain of −10⁹ (distance −99 999·10⁹), source in the middle of the chain, large graph with
   a cycle away from the source. References: Python Kruskal, iterative Tarjan, Kahn.
5. **state-reset** (105) — one process answers the hand-made batch three times, interleaved
   with three full-limit requests; every answer is checked again.

Inputs of groups 2, 4, 5 are generated from the fixed seed `20261019` inside
`run_tests.py`, so they are reproducible without storing ~40 MB of JSON.

## Route helper (`RouteHelperTest.java`)

No-route result: **empty list**. Checked calls: reachable target (`[0,1,2,3]`, cost 0),
the source (`[0]`), unreachable target (`[]`), tied routes + parallel edges, pure parallel
edges, source in the middle with unreachable predecessors, and a 100 000-vertex chain.
Each route is verified for start/end vertex, edge direction and total weight. See
`results/route_helper_output.txt` and `ANALYSIS.md` §8.
