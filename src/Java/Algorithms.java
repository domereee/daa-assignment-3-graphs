import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Assignment 3 - Graph Algorithms for a Campus Festival.
 * Author: Tuleubayev Damir.
 *
 * <p>Every public method builds all of its state from the current request only
 * (no static mutable fields), so a persistent process can answer any number of
 * requests independently. Every depth-first search is iterative with an explicit
 * stack and a per-vertex adjacency cursor, so deep graphs (chains of 100000
 * vertices) never overflow the Java call stack and no adjacency entry is scanned
 * twice.
 */
public final class Algorithms {
    private Algorithms() {
    }

    /** Offset that turns any weight in [-1e9, 1e9] into a non-negative 31-bit value. */
    private static final long WEIGHT_SHIFT = 1_000_000_000L;

    // =====================================================================
    // Shared helpers
    // =====================================================================

    /**
     * Compressed adjacency lists (CSR). Outgoing slots of vertex v are
     * {@code start[v] .. start[v+1]-1}; slot i leads to {@code to[i]} through the
     * original edge {@code id[i]}.
     */
    static final class Graph {
        final int n;
        final int[] start;
        final int[] to;
        final int[] id;

        private Graph(int n, int slots) {
            this.n = n;
            this.start = new int[n + 1];
            this.to = new int[slots];
            this.id = new int[slots];
        }

        /** Directed graph u -> v (or its transpose v -> u when {@code reverse}). */
        static Graph directed(int n, int[][] edges, boolean reverse) {
            Graph g = new Graph(n, edges.length);
            for (int[] e : edges) {
                g.start[(reverse ? e[1] : e[0]) + 1]++;
            }
            for (int v = 0; v < n; v++) {
                g.start[v + 1] += g.start[v];
            }
            int[] fill = Arrays.copyOf(g.start, n);
            for (int i = 0; i < edges.length; i++) {
                int from = reverse ? edges[i][1] : edges[i][0];
                int target = reverse ? edges[i][0] : edges[i][1];
                int slot = fill[from]++;
                g.to[slot] = target;
                g.id[slot] = i;
            }
            return g;
        }

        /** Undirected graph: each non-loop edge appears in both endpoint lists. */
        static Graph undirectedWithoutLoops(int n, int[][] edges) {
            int slots = 0;
            for (int[] e : edges) {
                if (e[0] != e[1]) {
                    slots += 2;
                }
            }
            Graph g = new Graph(n, slots);
            for (int[] e : edges) {
                if (e[0] != e[1]) {
                    g.start[e[0] + 1]++;
                    g.start[e[1] + 1]++;
                }
            }
            for (int v = 0; v < n; v++) {
                g.start[v + 1] += g.start[v];
            }
            int[] fill = Arrays.copyOf(g.start, n);
            for (int i = 0; i < edges.length; i++) {
                int u = edges[i][0];
                int v = edges[i][1];
                if (u == v) {
                    continue; // A self-loop can never join two components.
                }
                int a = fill[u]++;
                g.to[a] = v;
                g.id[a] = i;
                int b = fill[v]++;
                g.to[b] = u;
                g.id[b] = i;
            }
            return g;
        }
    }

    /** Disjoint-set union with iterative path compression and union by size. */
    static final class DisjointSet {
        private final int[] parent;
        private final int[] size;
        private int components;
        private int largest;

        DisjointSet(int n) {
            parent = new int[n];
            size = new int[n];
            for (int v = 0; v < n; v++) {
                parent[v] = v;
                size[v] = 1;
            }
            components = n;
            largest = n > 0 ? 1 : 0;
        }

        int find(int v) {
            int root = v;
            while (parent[root] != root) {
                root = parent[root];
            }
            while (parent[v] != root) { // Second pass: point the whole path at the root.
                int next = parent[v];
                parent[v] = root;
                v = next;
            }
            return root;
        }

        /** Returns true when u and v were in different sets and have been merged. */
        boolean union(int u, int v) {
            int a = find(u);
            int b = find(v);
            if (a == b) {
                return false;
            }
            if (size[a] < size[b]) { // Attach the smaller tree below the larger one.
                int t = a;
                a = b;
                b = t;
            }
            parent[b] = a;
            size[a] += size[b];
            components--;
            if (size[a] > largest) {
                largest = size[a];
            }
            return true;
        }

        int components() {
            return components;
        }

        int largest() {
            return largest;
        }
    }

    /** Minimal binary min-heap of primitive longs (avoids boxing in Prim). */
    static final class LongMinHeap {
        private long[] heap = new long[16];
        private int size;

        boolean isEmpty() {
            return size == 0;
        }

        void push(long value) {
            if (size == heap.length) {
                heap = Arrays.copyOf(heap, size * 2);
            }
            int i = size++;
            while (i > 0) {
                int p = (i - 1) >>> 1;
                if (heap[p] <= value) {
                    break;
                }
                heap[i] = heap[p];
                i = p;
            }
            heap[i] = value;
        }

        long pop() {
            long top = heap[0];
            long last = heap[--size];
            int i = 0;
            int half = size >>> 1;
            while (i < half) {
                int c = 2 * i + 1;
                if (c + 1 < size && heap[c + 1] < heap[c]) {
                    c++;
                }
                if (heap[c] >= last) {
                    break;
                }
                heap[i] = heap[c];
                i = c;
            }
            if (size > 0) {
                heap[i] = last;
            }
            return top;
        }
    }

    /**
     * Three-state iterative DFS (0 = unvisited, 1 = active, 2 = finished).
     * Returns the reverse finish order, or {@code null} as soon as an edge to an
     * active vertex (a directed cycle, including a self-loop) is found. Every
     * vertex is used as a root, so cycles in any component are detected.
     */
    static int[] topologicalOrderOrNull(Graph g) {
        int n = g.n;
        byte[] state = new byte[n];
        int[] cursor = new int[n]; // Next adjacency slot to examine for each vertex.
        int[] stack = new int[n];
        int[] order = new int[n];
        int filled = n; // Finished vertices are written from the back.

        for (int root = 0; root < n; root++) {
            if (state[root] != 0) {
                continue;
            }
            int top = 0;
            stack[top++] = root;
            state[root] = 1;
            cursor[root] = g.start[root];
            while (top > 0) {
                int u = stack[top - 1];
                if (cursor[u] < g.start[u + 1]) {
                    int v = g.to[cursor[u]++];
                    if (state[v] == 1) {
                        return null; // Back edge: directed cycle.
                    }
                    if (state[v] == 0) {
                        state[v] = 1;
                        cursor[v] = g.start[v];
                        stack[top++] = v;
                    }
                    // state 2: cross/forward edge to a finished vertex, not a cycle.
                } else {
                    state[u] = 2;
                    order[--filled] = u;
                    top--;
                }
            }
        }
        return order;
    }

    private static Map<String, Object> result() {
        return new LinkedHashMap<>();
    }

    // =====================================================================
    // 1. DSU
    // =====================================================================

    /** DSU with path compression and union by size; return states. */
    static Map<String, Object> dsu(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] operations = Input.operations(input);

        DisjointSet sets = new DisjointSet(n);
        int[][] states = new int[operations.length][];
        for (int i = 0; i < operations.length; i++) {
            sets.union(operations[i][0], operations[i][1]);
            states[i] = new int[] {sets.components(), sets.largest()};
        }

        Map<String, Object> result = result();
        result.put("states", states);
        return result;
    }

    // =====================================================================
    // 2. Kruskal
    // =====================================================================

    /** Separate Kruskal implementation; return cost, edge_ids, components. */
    static Map<String, Object> kruskal(Map<String, Object> input) {
        return kruskal(Input.vertexCount(input), Input.edges(input));
    }

    /** Kruskal on already extracted input (also called directly by tests/Benchmark.java). */
    static Map<String, Object> kruskal(int n, int[][] edges) {
        int m = edges.length;

        // Sort key = (weight + 1e9) << 18 | id: a primitive sort by weight that
        // keeps the original edge ID (m <= 250000 < 2^18) attached to every edge.
        long[] keys = new long[m];
        for (int i = 0; i < m; i++) {
            keys[i] = ((edges[i][2] + WEIGHT_SHIFT) << 18) | i;
        }
        Arrays.sort(keys);

        DisjointSet sets = new DisjointSet(n);
        int[] chosen = new int[Math.max(0, n - 1)];
        int count = 0;
        long cost = 0;
        for (int k = 0; k < m && count < n - 1; k++) {
            int i = (int) (keys[k] & ((1 << 18) - 1));
            if (sets.union(edges[i][0], edges[i][1])) { // find(u) != find(v)
                chosen[count++] = i;
                cost += edges[i][2];
            }
        }

        Map<String, Object> result = result();
        result.put("cost", cost);
        result.put("edge_ids", Arrays.copyOf(chosen, count));
        result.put("components", n - count);
        return result;
    }

    // =====================================================================
    // 3. Prim
    // =====================================================================

    /** Separate Prim implementation (lazy heap); restart for every unvisited component. */
    static Map<String, Object> prim(Map<String, Object> input) {
        return prim(Input.vertexCount(input), Input.edges(input));
    }

    /** Prim on already extracted input (also called directly by tests/Benchmark.java). */
    static Map<String, Object> prim(int n, int[][] edges) {
        Graph g = Graph.undirectedWithoutLoops(n, edges);

        // Heap key = (weight + 1e9) << 19 | adjacency slot (slots < 500000 < 2^19).
        boolean[] inTree = new boolean[n];
        LongMinHeap heap = new LongMinHeap();
        int[] chosen = new int[Math.max(0, n - 1)];
        int count = 0;
        int components = 0;
        long cost = 0;

        for (int root = 0; root < n; root++) {
            if (inTree[root]) {
                continue;
            }
            components++; // Restart: a new component begins at an unvisited vertex.
            inTree[root] = true;
            pushFrontier(g, edges, heap, inTree, root);
            while (!heap.isEmpty()) {
                int slot = (int) (heap.pop() & ((1 << 19) - 1));
                int v = g.to[slot];
                if (inTree[v]) {
                    continue; // Stale entry: both endpoints are already in the tree.
                }
                inTree[v] = true;
                int id = g.id[slot];
                chosen[count++] = id;
                cost += edges[id][2];
                pushFrontier(g, edges, heap, inTree, v);
            }
        }

        Map<String, Object> result = result();
        result.put("cost", cost);
        result.put("edge_ids", Arrays.copyOf(chosen, count));
        result.put("components", components);
        return result;
    }

    private static void pushFrontier(Graph g, int[][] edges, LongMinHeap heap,
                                     boolean[] inTree, int u) {
        for (int slot = g.start[u]; slot < g.start[u + 1]; slot++) {
            if (!inTree[g.to[slot]]) {
                heap.push(((edges[g.id[slot]][2] + WEIGHT_SHIFT) << 19) | slot);
            }
        }
    }

    // =====================================================================
    // 4. Kosaraju SCC
    // =====================================================================

    /** Kosaraju's two DFS passes; return component and exact condensation. */
    static Map<String, Object> scc(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);
        Graph forward = Graph.directed(n, edges, false);
        Graph transpose = Graph.directed(n, edges, true);

        // Pass 1: iterative DFS on G, record vertices by increasing finish time.
        int[] finishOrder = new int[n];
        int finished = 0;
        boolean[] seen = new boolean[n];
        int[] cursor = new int[n];
        int[] stack = new int[n];
        for (int root = 0; root < n; root++) {
            if (seen[root]) {
                continue;
            }
            int top = 0;
            stack[top++] = root;
            seen[root] = true;
            cursor[root] = forward.start[root];
            while (top > 0) {
                int u = stack[top - 1];
                if (cursor[u] < forward.start[u + 1]) {
                    int v = forward.to[cursor[u]++];
                    if (!seen[v]) {
                        seen[v] = true;
                        cursor[v] = forward.start[v];
                        stack[top++] = v;
                    }
                } else {
                    finishOrder[finished++] = u;
                    top--;
                }
            }
        }

        // Pass 2: DFS on the transpose in decreasing finish time; each tree is one SCC.
        int[] component = new int[n];
        Arrays.fill(component, -1);
        int labels = 0;
        for (int k = n - 1; k >= 0; k--) {
            int root = finishOrder[k];
            if (component[root] != -1) {
                continue;
            }
            int label = labels++;
            int top = 0;
            stack[top++] = root;
            component[root] = label;
            while (top > 0) {
                int u = stack[--top];
                for (int s = transpose.start[u]; s < transpose.start[u + 1]; s++) {
                    int v = transpose.to[s];
                    if (component[v] == -1) {
                        component[v] = label;
                        stack[top++] = v;
                    }
                }
            }
        }

        Map<String, Object> result = result();
        result.put("component", component);
        result.put("condensation", condensation(edges, component, labels));
        return result;
    }

    /**
     * Distinct cross-component pairs in O(n + m) worst case, without hashing:
     * group cross edges by source label (counting sort), then for each source label
     * keep a "last seen" stamp per target label to drop duplicates.
     */
    private static int[][] condensation(int[][] edges, int[] component, int labels) {
        int[] start = new int[labels + 1];
        int cross = 0;
        for (int[] e : edges) {
            int a = component[e[0]];
            if (a != component[e[1]]) {
                start[a + 1]++;
                cross++;
            }
        }
        for (int c = 0; c < labels; c++) {
            start[c + 1] += start[c];
        }
        int[] targets = new int[cross];
        int[] fill = Arrays.copyOf(start, labels);
        for (int[] e : edges) {
            int a = component[e[0]];
            int b = component[e[1]];
            if (a != b) {
                targets[fill[a]++] = b;
            }
        }

        int[] stamp = new int[labels];
        Arrays.fill(stamp, -1);
        int[][] pairs = new int[cross][];
        int count = 0;
        for (int a = 0; a < labels; a++) {
            for (int i = start[a]; i < start[a + 1]; i++) {
                int b = targets[i];
                if (stamp[b] != a) {
                    stamp[b] = a;
                    pairs[count++] = new int[] {a, b};
                }
            }
        }
        return Arrays.copyOf(pairs, count);
    }

    // =====================================================================
    // 5. Topological ordering
    // =====================================================================

    /** Three-state DFS and reverse finish order; return acyclic and order. */
    static Map<String, Object> topo(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);

        int[] order = topologicalOrderOrNull(Graph.directed(n, edges, false));

        Map<String, Object> result = result();
        result.put("acyclic", order != null);
        result.put("order", order != null ? order : new int[0]);
        return result;
    }

    // =====================================================================
    // 6. DAG shortest paths + route reconstruction
    // =====================================================================

    /** Whole-graph cycle check and DAG relaxation; return acyclic, distance, parent_edge. */
    static Map<String, Object> dag(Map<String, Object> input) {
        return dag(Input.vertexCount(input), Input.source(input), Input.edges(input));
    }

    /** DAG shortest paths on already extracted input (used by tests/RouteHelperTest.java). */
    static Map<String, Object> dag(int n, int source, int[][] edges) {
        Graph g = Graph.directed(n, edges, false);
        int[] order = topologicalOrderOrNull(g); // Checks every component, not only the source's.

        Map<String, Object> result = result();
        if (order == null) {
            result.put("acyclic", false);
            result.put("distance", new Long[0]);
            result.put("parent_edge", new int[0]);
            return result;
        }

        long[] dist = new long[n];
        boolean[] reached = new boolean[n];
        int[] parentEdge = new int[n];
        Arrays.fill(parentEdge, -1);
        reached[source] = true;
        dist[source] = 0;

        for (int u : order) {
            if (!reached[u]) {
                continue; // Never relax from an unreachable vertex.
            }
            for (int s = g.start[u]; s < g.start[u + 1]; s++) {
                int v = g.to[s];
                long candidate = dist[u] + edges[g.id[s]][2];
                if (!reached[v] || candidate < dist[v]) {
                    reached[v] = true;
                    dist[v] = candidate;
                    parentEdge[v] = g.id[s];
                }
            }
        }

        Long[] distance = new Long[n];
        for (int v = 0; v < n; v++) {
            distance[v] = reached[v] ? Long.valueOf(dist[v]) : null;
        }
        result.put("acyclic", true);
        result.put("distance", distance);
        result.put("parent_edge", parentEdge);
        return result;
    }

    /**
     * Route-reconstruction helper for the {@code dag} result.
     *
     * <p>Follows {@code parentEdge} IDs backwards from {@code target}: the parent
     * edge of v is {@code edges[parentEdge[v]] = [u, v, w]}, so the walk moves to u.
     * The collected vertices are reversed, giving a route that starts at
     * {@code source} and ends at {@code target}.
     *
     * <ul>
     *   <li>target == source: returns {@code [source]};</li>
     *   <li>reachable target: returns {@code [source, ..., target]};</li>
     *   <li>unreachable target ({@code parentEdge[target] == -1}): returns an
     *       <b>empty list</b> (the documented no-route result).</li>
     * </ul>
     * Runs in O(L) time and O(L) output space for a route with L vertices.
     */
    static List<Integer> reconstructRoute(int[][] edges, int[] parentEdge, int source, int target) {
        List<Integer> route = new ArrayList<>();
        if (target == source) {
            route.add(source);
            return route;
        }
        if (target < 0 || target >= parentEdge.length || parentEdge[target] == -1) {
            return route; // No route: empty list.
        }
        int v = target;
        while (v != source) {
            int e = parentEdge[v];
            if (e < 0) {
                return new ArrayList<>(); // Defensive: a broken chain is reported as no route.
            }
            route.add(v);
            v = edges[e][0];
        }
        route.add(source);
        Collections.reverse(route);
        return route;
    }

    /** Edge IDs used by a reconstructed route, in route order (for tests and analysis). */
    static List<Integer> routeEdgeIds(int[] parentEdge, List<Integer> route) {
        List<Integer> ids = new ArrayList<>();
        for (int i = 1; i < route.size(); i++) {
            ids.add(parentEdge[route.get(i)]);
        }
        return ids;
    }
}
