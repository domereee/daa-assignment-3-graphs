import java.util.List;
import java.util.Map;

/**
 * Direct tests of the DAG route-reconstruction helper
 * {@link Algorithms#reconstructRoute(int[][], int[], int, int)}.
 * Author: Tuleubayev Damir.
 *
 * <p>Build and run from the repository root (or use {@code python tests/run_java_tests.py}):
 * <pre>
 *   javac --release 17 -encoding UTF-8 -d .build/tests src/Java/*.java tests/RouteHelperTest.java
 *   java -cp .build/tests RouteHelperTest
 * </pre>
 *
 * <p>For every call the test prints the route, the parent edge IDs used, and verifies that
 * (1) the route starts at the source and ends at the target, (2) every selected edge goes
 * from route[i-1] to route[i] (direction), and (3) the summed weight equals distance[target].
 * The documented no-route result for an unreachable target is an empty list.
 */
public final class RouteHelperTest {
    private static int failures = 0;
    private static int checks = 0;

    public static void main(String[] args) {
        // Published example: route to 3 is [0,1,2,3] with cost 0; vertex 4 is unreachable.
        int[][] example = {{0, 1, 3}, {0, 2, 8}, {1, 2, -7}, {2, 3, 4}};
        Case published = new Case("published example", 5, 0, example);
        published.expect(3, List.of(0, 1, 2, 3), 0L);
        published.expect(0, List.of(0), 0L);
        published.expect(4, List.of(), null);
        published.expect(2, List.of(0, 1, 2), -4L);

        // Tied routes and parallel edges: 0->1->3 (edge 2 or parallel edge 4) and 0->2->3 (edge 3)
        // all cost 2. Any of them is a valid witness; we verify whichever one was selected.
        int[][] tied = {{0, 1, 1}, {0, 2, 1}, {1, 3, 1}, {2, 3, 1}, {1, 3, 1}};
        Case ties = new Case("tied routes + parallel edges", 4, 0, tied);
        ties.expectAnyValid(3, 2L);

        // Pure parallel edges: weights 5, -3, -3. The strict '<' relaxation keeps the first
        // optimal edge it sees, so edge 1 is selected (edge 2 would also be valid).
        int[][] parallel = {{0, 1, 5}, {0, 1, -3}, {0, 1, -3}};
        Case par = new Case("parallel edges", 2, 0, parallel);
        par.expect(1, List.of(0, 1), -3L);

        // Source in the middle: vertices before it are unreachable and get the empty route.
        int[][] middle = {{0, 1, 5}, {1, 2, 1}, {2, 3, -2}, {0, 3, 1}};
        Case mid = new Case("source in the middle", 4, 2, middle);
        mid.expect(3, List.of(2, 3), -2L);
        mid.expect(2, List.of(2), 0L);
        mid.expect(0, List.of(), null);
        mid.expect(1, List.of(), null);

        // Deep chain: 100000 vertices, route of length L = 100000 is rebuilt in O(L).
        int n = 100000;
        int[][] chain = new int[n - 1][];
        for (int i = 0; i + 1 < n; i++) {
            chain[i] = new int[] {i, i + 1, -1_000_000_000};
        }
        Case deep = new Case("deep chain n=100000", n, 0, chain);
        deep.expectLength(n - 1, n, -99_999L * 1_000_000_000L);

        System.out.println();
        System.out.println(failures == 0
                ? "ROUTE HELPER: all " + checks + " checks passed"
                : "ROUTE HELPER: " + failures + " of " + checks + " checks FAILED");
        System.exit(failures == 0 ? 0 : 1);
    }

    /** One DAG, solved once; several helper calls on it. */
    private static final class Case {
        final String name;
        final int source;
        final int[][] edges;
        final Long[] distance;
        final int[] parentEdge;

        Case(String name, int n, int source, int[][] edges) {
            this.name = name;
            this.source = source;
            this.edges = edges;
            Map<String, Object> result = Algorithms.dag(n, source, edges);
            this.distance = (Long[]) result.get("distance");
            this.parentEdge = (int[]) result.get("parent_edge");
            System.out.println("== " + name + " (source " + source + ", " + edges.length + " edges)");
        }

        void expect(int target, List<Integer> expectedRoute, Long expectedCost) {
            List<Integer> route = Algorithms.reconstructRoute(edges, parentEdge, source, target);
            boolean ok = route.equals(expectedRoute) && verify(target, route, expectedCost);
            report(target, route, ok, route.size() <= 12);
        }

        void expectAnyValid(int target, Long expectedCost) {
            List<Integer> route = Algorithms.reconstructRoute(edges, parentEdge, source, target);
            report(target, route, verify(target, route, expectedCost), true);
        }

        void expectLength(int target, int expectedLength, Long expectedCost) {
            long started = System.nanoTime();
            List<Integer> route = Algorithms.reconstructRoute(edges, parentEdge, source, target);
            double ms = (System.nanoTime() - started) / 1e6;
            boolean ok = route.size() == expectedLength && verify(target, route, expectedCost);
            report(target, route, ok, false);
            System.out.printf("   (reconstructed %d vertices in %.2f ms)%n", route.size(), ms);
        }

        /** Direction, endpoints and total weight of the selected parent edges. */
        private boolean verify(int target, List<Integer> route, Long expectedCost) {
            if (expectedCost == null) {
                return route.isEmpty() && distance[target] == null;
            }
            if (route.isEmpty() || route.get(0) != source || route.get(route.size() - 1) != target) {
                return false;
            }
            long total = 0;
            for (int i = 1; i < route.size(); i++) {
                int[] e = edges[parentEdge[route.get(i)]];
                if (e[0] != route.get(i - 1) || e[1] != route.get(i)) {
                    return false; // Wrong direction or not the edge between consecutive vertices.
                }
                total += e[2];
            }
            return total == expectedCost && distance[target] != null && distance[target] == total;
        }

        private void report(int target, List<Integer> route, boolean ok, boolean showRoute) {
            checks++;
            if (!ok) {
                failures++;
            }
            List<Integer> ids = Algorithms.routeEdgeIds(parentEdge, route);
            String shown = showRoute ? route.toString() : "[" + route.get(0) + ", ..., " + route.get(route.size() - 1) + "]";
            String idText = showRoute ? ids.toString() : "(" + ids.size() + " edge IDs)";
            System.out.printf("   %s target %d -> route %s, edge_ids %s, distance %s%n",
                    ok ? "PASS" : "FAIL", target, shown, idText, distance[target]);
        }
    }
}
