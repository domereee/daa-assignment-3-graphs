# Assignment 3 — Graph Algorithms: Analysis

**Student:** Tuleubayev Damir
**Course:** Design and Analysis of Algorithms
**Language:** Java 17 (`submission.json`: `{"language": "Java"}`)
**Implementation:** `src/Java/Algorithms.java` (all six methods + route helper). The supplied
`Main.java`, `Input.java` and `Json.java` adapters are unchanged.

---

## 0. Build, run and test commands

Run from the repository root (Python 3.12+ and JDK 17+ required; on Windows use `py -3`).

| Purpose | Command |
|---|---|
| Build + launch check (`ping`) | `python tools/run.py --setup` |
| 36 public cases + state-reset batch | `python tools/run.py --check` |
| Own JSON-Lines test-suite (5 groups, ≈ 30 s) | `python tests/run_tests.py` (`--quick` skips full-limit inputs) |
| Route-helper tests + Kruskal/Prim benchmark | `python tests/run_java_tests.py` (`--no-bench` = helper only) |
| Raw results for own inputs | `python tools/run.py --input tests/my_cases.jsonl` |
| Manual build (what `run.py` does) | `javac --release 17 -encoding UTF-8 -d .build/Java src/Java/*.java` |
| Manual run | `java -Xmx384m -cp .build/Java Main < tests/my_cases.jsonl` |
| Manual helper/benchmark build | `javac --release 17 -encoding UTF-8 -d .build/tests src/Java/*.java tests/RouteHelperTest.java tests/Benchmark.java` |
| Manual helper/benchmark run | `java -cp .build/tests RouteHelperTest` and `java -Xmx384m -cp .build/tests Benchmark` |

Results of the last runs (all passing) are stored in `tests/results/`:
`--check` → 36/36 PASS + state reset PASS; `run_tests.py` → 34 + 1500 + 25 + 19 + 105 checks
passed; `RouteHelperTest` → 11/11 checks passed.

---

## 1. Common design decisions

**Graph representation.** Every directed or undirected graph is stored in compressed
adjacency form (CSR): `start[v] .. start[v+1]-1` are the outgoing slots of `v`, and slot `i`
stores the target `to[i]` and the **original edge ID** `id[i]`. Building it is two counting
passes, `O(n + m)` time and `O(n + m)` memory, with no per-edge objects. Because the slot keeps
the original ID, sorting or traversal never loses the input numbering required in the output.

**State reset.** `Algorithms` has no static mutable fields. Each request allocates its own
arrays (DSU, CSR, heap, `state`, `cursor`, `dist`, ...) from the `n` and `edges` of *that*
request, and they become garbage when the method returns. A persistent process therefore
answers any sequence of requests independently. This is checked by the public
"two complete batches in one process" check and by my own `state-reset` group (105 mixed
requests, including three full-limit ones, answered by one process).

**Deep DFS.** All three depth-first searches (Kosaraju pass 1, topological DFS used by `topo`
and `dag`) are **iterative**: an explicit `int[] stack` of size `n` plus an `int[] cursor`
that remembers, for each suspended vertex, the next adjacency slot to examine. When the
search returns to a vertex it resumes from `cursor[v]`, so every adjacency entry is examined
exactly once (`O(n + m)` total), and the depth of the search is limited only by the array
size, not by the Java call stack (a recursive DFS on a 100 000-vertex chain needs 100 000
nested frames and risks `StackOverflowError` with default thread stack sizes). Kosaraju's second pass only needs to *collect* a
component, so it uses a plain stack where a vertex is labelled when pushed. Tested on chains
of 100 000 vertices for `scc`, `topo` and `dag`.

**64-bit arithmetic.** Weights fit `int` (`|w| ≤ 10⁹`), but every sum (`cost`, `dist`) is a
`long`. The largest possible magnitude is `(n−1)·10⁹ < 10¹⁴`, far inside the signed 64-bit
range. Tested with totals of ±4·10⁹, −3·10⁹ and ±99 999·10⁹.

**Packed keys.** For sorting (Kruskal) and the heap (Prim) a weight and an index are packed
into one `long`: `key = (w + 10⁹) << k | index`. Since `w + 10⁹ ∈ [0, 2·10⁹] < 2³¹` and the
index is below `2^k` (`k = 18` for edge IDs < 250 000, `k = 19` for adjacency slots < 500 000),
the key is non-negative, below 2⁵⁰, and orders first by weight and then by index. This lets
Java sort a primitive `long[]` and lets the heap store primitives (no boxing).

---

## 2. DSU (`dsu`)

**Steps.** `parent[v] = v`, `size[v] = 1`, `components = n`, `largest = (n > 0 ? 1 : 0)`.
For each operation `[u, v]`: `a = find(u)`, `b = find(v)`; if `a ≠ b`, attach the root of the
smaller tree to the root of the larger one, add the sizes, decrement `components` and update
`largest = max(largest, size[new root])`. Append `[components, largest]` after every operation.
`find` is iterative with full path compression (first pass finds the root, second pass points
every vertex on the path directly at it).

**Invariant.** (1) Every set is a rooted tree; `parent[r] = r` exactly for roots. (2) For every
root, `size[r]` is the number of vertices in its tree (union by **size**, so size is stored
explicitly — no rank/size confusion). (3) `components` = number of roots; `largest` = max
`size` over roots. (`largest` only needs to be updated on a merge, because sets never shrink.)

**Correctness.** Two vertices are in the same component iff they have the same root; path
compression only changes `parent` pointers *inside* one tree, so it never changes any root.
A self-union or a repeated union finds `a = b` and changes nothing, exactly as required.

**Boundary cases.** `n = 0` → `states = []`; no operations → `[]` (no initial state);
self-union `[v, v]`; repeated and reversed unions; `n = 1`.

**Complexity.** Union by size + path compression: `O(n + q·α(n))` amortised time;
memory `O(n)` for the forest plus `O(q)` for the returned states → `O(n + q)`.
Tested with `n = 100 000`, `q = 250 000` (0.6–0.8 s including JVM start and JSON I/O).

---

## 3. Kruskal (`kruskal`)

**Steps.** Pack every edge as `(w + 10⁹) << 18 | id`, sort the `long[]`, create a DSU over
the `n` vertices, and scan the edges in ascending weight. Accept an edge exactly when
`find(u) ≠ find(v)` (`union` returns `true`): record its original ID and add its weight.
Stop early once `n − 1` edges have been accepted. `components = n − accepted`.

**Invariant.** After processing a prefix of the sorted list, the accepted edges are a subset
of some minimum spanning forest (MSF), and the DSU sets are exactly the connected components
of the accepted edges.

**Correctness.** When edge `e = (u, v)` with `find(u) ≠ find(v)` is examined, consider the cut
between `u`'s current DSU set and the rest. No earlier (lighter or equal) edge crosses that
cut, otherwise it would already have merged the sets; so `e` is a minimum edge crossing the cut
and, by the **cut property**, can be added to an MSF that contains the accepted edges (an
exchange argument handles equal weights). Edges with `find(u) = find(v)` (including self-loops)
would close a cycle and are rejected. At the end, every input edge has both endpoints in one
set, so the accepted edges span every component; an acyclic spanning forest of a graph with
`c` components has exactly `n − c` edges, hence `components = n − accepted`.

**Boundary cases.** `n = 0` → `cost 0, [], 0`; isolates count as components; self-loops are
never chosen (even negative ones); parallel edges — the lightest is chosen, equal ones are
tie-broken by ID; negative weights need no special handling (sorting works for any sign).

**Complexity.** Packing `O(m)`, sort `O(m log m)`, DSU scan `O(m·α(n))` →
`O(n + m log(m+1))` time; memory `O(n + m)` (key array, DSU, chosen IDs).

---

## 4. Prim (`prim`)

**Steps.** Build an undirected CSR in which every non-loop edge appears in both endpoint
lists (self-loops are skipped because they never join two components). For every vertex
`root = 0..n−1` that is not yet in a tree, **restart**: `components++`, mark `root`, and push
all its frontier slots into a min-heap with key `(w + 10⁹) << 19 | slot`. Repeatedly pop the
minimum; if the slot's target is already in the tree the entry is stale and is skipped (lazy
deletion); otherwise mark the target, record the slot's original edge ID and weight, and push
the new vertex's frontier slots whose other endpoint is still outside the tree. When the heap
is empty the component is complete and the outer loop restarts at the next unvisited vertex.

**Invariant.** The marked vertices of the current component and the recorded edges form a tree
that is a subset of some MSF; the heap contains (possibly with stale entries) every edge from
the tree to a non-tree vertex.

**Correctness.** The popped non-stale entry is a minimum-weight edge crossing the cut
(current tree, rest of its component) — every crossing edge was pushed when its tree endpoint
was marked. By the cut property it belongs to an MSF together with the tree. The heap empties
exactly when no edge leaves the tree, i.e. the tree spans a whole connected component; the
restart then begins the next component, so `components` equals the number of restarts
(isolated vertices are one-vertex restarts) and `n − components` edges are recorded.

**Boundary cases.** `n = 0` → no restart, `cost 0, [], 0`; isolates; disconnected graphs (the
restart is the requirement "Prim must restart in each component"); self-loops skipped;
parallel and tied edges (tie broken by slot); negative weights (the shift makes keys
non-negative while preserving order).

**Complexity.** Each non-loop edge is pushed at most twice (once from each endpoint), so the
heap holds ≤ 2m entries: `O(n + m log(m+1))` time with a lazy heap; memory `O(n + m)`
(CSR of `2m` slots, heap ≤ `2m` longs, flags). Kruskal and Prim agree on cost and component
count on every test; their edge IDs may differ when optima tie, which the checker accepts.

---

## 5. Kosaraju SCC (`scc`)

**Steps.** Build the CSR of `G` and of its transpose `Gᵀ`.
*Pass 1:* iterative DFS on `G` from every unvisited vertex; when a vertex has no remaining
slots it is appended to `finishOrder` (increasing finish time).
*Pass 2:* scan `finishOrder` from the end (decreasing finish time); each still-unlabelled
vertex starts a DFS on `Gᵀ` that labels every unlabelled vertex it reaches with a new label
`0, 1, 2, ...` — one DFS tree = one SCC.
*Condensation:* for every edge `u → v` with `label(u) ≠ label(v)`, group the target label by
source label (counting sort over labels), then for each source label `a` keep `stamp[b] = a`
for targets already emitted; a pair `[a, b]` is output only the first time. This removes
internal edges and duplicates in `O(n + m)` worst case without hashing.

**Invariant.** In pass 2, when a root `r` is taken in decreasing finish order, every SCC whose
maximum finish time is larger than `f(r)` has already been labelled completely.

**Correctness.** Standard lemma: if there is an edge from SCC `C` to SCC `C'` in `G`, then
`max f(C) > max f(C')`. Hence the unlabelled vertex with the largest finish time belongs to an
SCC `C` with no incoming edges from unlabelled SCCs in `G` — i.e. no *outgoing* edges to
unlabelled SCCs in `Gᵀ`. The DFS on `Gᵀ` from `r` therefore reaches all of `C` (it is strongly
connected in `Gᵀ` too) and nothing outside `C` except already-labelled vertices, which it
skips. By induction every DFS tree of pass 2 is exactly one SCC. The condensation contains
`(label(u), label(v))` for every cross edge, each once by the stamp test, and no internal pair.

**Boundary cases.** `n = 0` → `[]`, `[]`; isolated vertices are singleton SCCs; self-loops and
duplicate edges (internal → ignored, duplicate cross pairs → one pair); one huge SCC
(deep chain closed into a cycle, 100 000 vertices); 100 000 singleton SCCs with 99 999
condensation pairs.

**Complexity.** Two CSRs, two DFS passes and the condensation are all `O(n + m)` time and
`O(n + m)` memory (the deduplication is deterministic linear, better than the expected-linear
hash bound in the specification).

---

## 6. DFS topological ordering (`topo`)

**Steps.** `state[v] ∈ {0 = unvisited, 1 = active, 2 = finished}`. For every root `0..n−1`
with state 0, run the iterative DFS: on reaching vertex `u` set it active; take the next slot
`u → v` from `cursor[u]`: if `v` is **active** → a directed cycle was found, return
`acyclic = false, order = []`; if `v` is unvisited → push it; if `v` is finished → ignore
(cross/forward edge, not a cycle). When `u` has no remaining slots, mark it finished and write
it into `order` from the back — the array is thus the **reverse finish order**.

**Invariant.** The active vertices are exactly the vertices on the current DFS stack, i.e. a
directed path from the root to the top vertex.

**Correctness.** *Cycle detection:* an edge to an active vertex closes a path on the stack into
a cycle (a self-loop `v → v` is the shortest case). Conversely, if a cycle exists, let `x` be
its first discovered vertex; by the white-path theorem every cycle vertex is finished before
`x` finishes, so the cycle edge entering `x` is examined while `x` is active. Because every
vertex is used as a root, cycles in any component are found. *Order:* in an acyclic graph,
when the edge `u → v` is examined, `v` is either unvisited (then it finishes before `u`) or
already finished, so `finish(v) < finish(u)`; reversing finish order puts `u` before `v` for
every edge.

**Boundary cases.** `n = 0` → `true, []`; isolated vertices and parallel edges; self-loop;
a cycle in a component other than vertex 0's; an edge to a finished vertex (must not be
reported as a cycle); 100 000-vertex chains with and without one back edge.

**Complexity.** `O(n + m)` time (each slot examined once thanks to `cursor`), `O(n + m)`
memory.

---

## 7. DAG shortest paths (`dag`)

**Steps.** Build the directed CSR and run the same whole-graph three-state DFS as `topo`. If
any cycle exists (also one unreachable from `source`) return `acyclic = false`, `distance = []`,
`parent_edge = []`. Otherwise set `dist[source] = 0`, mark it reached, `parent_edge[·] = −1`,
and process vertices in topological order: **skip unreached vertices**; for a reached `u`
relax every outgoing edge `e = u → v`: if `v` is unreached or `dist[u] + w < dist[v]`, set
`dist[v]`, mark it reached, `parent_edge[v] = e` (original edge ID). Output `distance` as
`Long[]` with `null` for unreached vertices — never `−1`, which can be a real cost.

**Invariant.** When vertex `u` is taken from the topological order, `dist[u]` (or "unreached")
is final: every edge into `u` starts at an earlier vertex, which has already been processed.

**Correctness.** By induction over the topological order: let `s = v₀ → … → v_k = v` be a
shortest path; all `v_i` appear in increasing topological order, and when `v_{i−1}` is
processed with its final distance, relaxing the edge into `v_i` gives `dist[v_i] ≤ δ(v_i)`,
while every assigned value is the length of a real path, so `dist = δ`. Negative weights are
fine because a DAG has no negative cycles. Vertices before the source in the order are
unreachable and never relaxed, so an edge from an unreachable vertex can never create a
finite distance. The final `parent_edge[v]` is the edge that last improved `dist[v]`, so it
ends at `v` and is tight (`dist[u] + w = dist[v]`); following parents moves strictly backwards
in topological order and therefore ends at the source.

**Boundary cases.** `n = 1` with no edges; unreachable vertices → `null` and `−1`; distances
`−1` and `0` that are real; cycle or self-loop unreachable from the source; tied paths and
parallel edges (strict `<` keeps the first optimal edge; any tight edge is valid); 64-bit
distances down to −99 999·10⁹.

**Complexity.** DFS `O(n + m)` + one relaxation per edge `O(n + m)` → `O(n + m)` time and
memory.

---

## 8. Route-reconstruction helper

```java
static List<Integer> reconstructRoute(int[][] edges, int[] parentEdge, int source, int target)
```

* `target == source` → `[source]`.
* Reachable target → walk `v = target`, `v = edges[parentEdge[v]][0]` until `source`, then
  reverse: `[source, …, target]`.
* **No route** (`parentEdge[target] == −1` and `target ≠ source`) → **empty list `[]`**
  (this is the documented choice; the JSON `distance` still uses `null`).
* `O(L)` time and `O(L)` output space for a route of `L` vertices.

`routeEdgeIds(parentEdge, route)` lists the parent edge IDs along a route (used for reporting).

Actual calls from `tests/RouteHelperTest.java` (`tests/results/route_helper_output.txt`). For
every call the test verifies that the route starts at the source and ends at the target, that
each selected edge `edges[id]` goes **from** `route[i−1]` **to** `route[i]` (direction), and that
the weights add up to `distance[target]`.

| Graph (edges as `[u,v,w]`, ID = position) | Source | Target | Route | Selected edge IDs | Weight check |
|---|---:|---:|---|---|---|
| published: `[0,1,3] [0,2,8] [1,2,-7] [2,3,4]`, n=5 | 0 | 3 (reachable) | `[0, 1, 2, 3]` | `[0, 2, 3]` | 3 − 7 + 4 = **0** = distance |
| same | 0 | 0 (source) | `[0]` | `[]` | 0 |
| same | 0 | 4 (unreachable) | `[]` | `[]` | distance `null` |
| same | 0 | 2 | `[0, 1, 2]` | `[0, 2]` | 3 − 7 = **−4** (beats direct edge 1 of weight 8) |
| tied + parallel: `[0,1,1] [0,2,1] [1,3,1] [2,3,1] [1,3,1]` | 0 | 3 | `[0, 2, 3]` | `[1, 3]` | 1 + 1 = **2**; `[0,1,3]` via 2 or 4 would be equally valid |
| parallel: `[0,1,5] [0,1,-3] [0,1,-3]` | 0 | 1 | `[0, 1]` | `[1]` | **−3** (edge 2 ties; edge 0 is not optimal) |
| source in the middle: `[0,1,5] [1,2,1] [2,3,-2] [0,3,1]` | 2 | 3 | `[2, 3]` | `[2]` | **−2**; edge 3 from unreachable 0 never relaxed |
| same | 2 | 2 (source) | `[2]` | `[]` | 0 |
| same | 2 | 0 and 1 (unreachable) | `[]` | `[]` | distance `null` |
| chain `i → i+1`, weight −10⁹, n = 100 000 | 0 | 99 999 | `[0, …, 99999]` (100 000 vertices) | 99 999 IDs | **−99 999·10⁹** (≈ 14 ms) |

In the tied case the DFS from 0 finishes 3, then 1, then 2, so the topological order is
`[0, 2, 1, 3]`: vertex 2 is processed before vertex 1 and relaxes 3 via edge 3 first; the later
equal candidates via edges 2 and 4 are not strictly better and do not replace it. The other
optimal witnesses are accepted by the semantic checker
(`run_tests.py`, group *checker*: parent via edge 2 or parallel edge 4 → accepted; parent edge
ending at another vertex → rejected).

---

## 9. Own tests (summary)

Details: `tests/README.md`; outputs: `tests/results/`.

| Group | Checks | Expected answers come from |
|---|---:|---|
| handmade | 34 | hand computation with written justification (`tests/cases/handmade.json`), re-derived by brute force |
| random-small (seed 20261019) | 1500 | exhaustive MSF search, pairwise reachability, Kahn, Bellman–Ford, member-list DSU |
| checker accept/reject | 25 | 9 alternative valid answers accepted, 16 invalid witnesses rejected |
| full limits + deep chains | 19 | Python Kruskal, iterative Tarjan, Kahn + relaxation (n = 100 000, m/q = 250 000) |
| state reset (one process) | 105 | same references; handmade ×3 interleaved with 3 full-limit requests |
| route helper (Java) | 11 | hand values + direction/weight verification |

All full-limit inputs finish in 0.3–0.8 s per process (including JVM start-up and JSON I/O),
far below the 20 s batch limit; the 384 MB heap limit used by `tools/run.py` is respected.

---

## 10. Benchmark: Kruskal vs Prim on identical graphs

**Inputs.** `tests/Benchmark.java`, generator seeded with `SplittableRandom(20261019 + k)` for
size index `k = 0, 1, 2`: a random spanning tree (vertex `i` joins a random earlier vertex,
so the graph is connected) plus `m − (n − 1)` uniformly random extra edges (self-loops and
parallel edges allowed), weights uniform in `[−10⁹, 10⁹]`. Both methods receive the **same**
`int[][]` array.

**Correctness first.** Before timing, both results are validated: `n − c` distinct edges, no
cycle (DSU), spanning every component, reported cost = sum of selected weights, and equal
costs and component counts for Kruskal and Prim.

**Command.** `python tests/run_java_tests.py` (or `java -Xmx384m -cp .build/tests Benchmark`
after the manual build in §0). Compilation is done beforehand and is **excluded**.

**Timer and boundary.** `System.nanoTime()` around one call of
`Algorithms.kruskal(n, edges)` / `Algorithms.prim(n, edges)`. **Included:** sort-key packing
and sorting / CSR construction, the DSU or heap work, building the result map. **Excluded**
(identically for both): JVM start-up, JSON parsing and serialisation, graph generation,
validation. **Warm-up:** 5 untimed runs of each method per size (JIT compilation); then 7 timed
runs per method, alternating Kruskal, Prim, Kruskal, …, with `System.gc()` before each run.

**Environment.** OpenJDK 21.0.12 running bytecode compiled with `--release 17`, flags
`-Xmx384m`; Ubuntu 24.04.5 LTS (Linux cloud container), Intel Xeon @ 2.10 GHz, 2 logical
CPUs, 7 GB RAM. Measured on 2026-10-19.

| n | m | method | cost | components | 7 timings (ms) | median (ms) |
|---:|---:|---|---:|---:|---|---:|
| 1 000 | 5 000 | Kruskal | −765 764 241 311 | 1 | 1.25, 1.19, 1.00, 0.73, 0.93, 0.95, 0.96 | **0.96** |
| 1 000 | 5 000 | Prim | −765 764 241 311 | 1 | 1.64, 1.47, 1.47, 1.11, 1.40, 1.15, 1.06 | **1.40** |
| 10 000 | 50 000 | Kruskal | −7 612 561 839 603 | 1 | 7.21, 7.49, 6.01, 6.91, 6.51, 4.75, 9.10 | **6.91** |
| 10 000 | 50 000 | Prim | −7 612 561 839 603 | 1 | 10.97, 9.79, 9.56, 10.37, 10.70, 9.89, 18.58 | **10.37** |
| 100 000 | 250 000 | Kruskal | −53 473 302 076 823 | 1 | 35.90, 36.07, 35.95, 34.30, 33.41, 38.45, 42.28 | **35.95** |
| 100 000 | 250 000 | Prim | −53 473 302 076 823 | 1 | 89.11, 87.11, 81.36, 76.79, 81.24, 80.98, 93.20 | **81.36** |

Median ratio Prim / Kruskal: 1.46× (n = 10³), 1.50× (n = 10⁴), 2.26× (n = 10⁵).

**Observations.** Both methods return the same optimal cost at every size, confirming the
implementations against each other. Kruskal was faster at all three sizes and the gap grew
with size. Plausible reasons (not proven by this experiment): Kruskal sorts one contiguous
`long[]` of `m` primitives (cache-friendly dual-pivot quicksort) and then performs nearly
constant-time DSU operations; Prim first builds a CSR with `2m` slots and then performs up
to `2m` heap pushes and pops whose memory accesses jump between distant vertices and heap
positions, which costs more cache misses as the graph outgrows the CPU caches. Timings grow
roughly in proportion to `m` (×10 edges → ×7.2 and ×7.4 time from 10³ to 10⁴; ×5 edges →
×5.2 and ×7.8 from 10⁴ to 10⁵), consistent with `O(m log m)` plus memory effects.

**Asymptotic argument (separate from the measurements).** Both are `O(n + m log m)` with the
chosen implementations (Kruskal: sort; lazy Prim: ≤ 2m heap operations). Neither dominates
asymptotically for sparse graphs like these; Prim with an indexed heap would be
`O((n + m) log n)`, and on dense graphs an array-based `O(n²)` Prim would win, which this
benchmark does not test.

**Limitations.** One machine (a shared cloud vCPU, so background load is possible — see the
outliers 9.10 ms and 18.58 ms); one seed per size; sparse random graphs only (`m/n` = 5, 5,
2.5); JIT and garbage-collection effects are reduced (warm-up, `System.gc()`, medians of 7)
but not eliminated; sub-millisecond timings at n = 1 000 are close to timer and scheduling
noise. Absolute numbers will differ on other hardware; rerunning
`python tests/run_java_tests.py` regenerates `tests/results/benchmark.md`.

---

## 11. Sources and AI assistance

**Sources.** T. H. Cormen, C. E. Leiserson, R. L. Rivest, C. Stein, *Introduction to
Algorithms* (3rd ed.), chapters 21 (disjoint sets), 22 (DFS, topological sort, strongly
connected components — Kosaraju's two-pass method), 23 (Kruskal, Prim, cut property),
24.2 (single-source shortest paths in DAGs). R. Sedgewick, K. Wayne, *Algorithms* (4th ed.),
§4.3 (lazy Prim). The assignment README and the supplied adapters/tools of this repository.
No code was copied from external sources.

**AI assistance.** An AI assistant (Claude, Anthropic) was used to help draft the Java
implementation, the test harness (`tests/`), the benchmark program and the text of this
analysis. Verification: every number and output reported here comes from runs that were
actually executed (public checks, own test-suite, route-helper tests and benchmark; raw
outputs in `tests/results/`). I am responsible for the correctness, originality and quality
of the submitted work, have reviewed it, and can explain every method.
