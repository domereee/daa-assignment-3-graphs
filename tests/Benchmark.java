import java.util.Arrays;
import java.util.Map;
import java.util.SplittableRandom;

/**
 * Kruskal vs Prim benchmark on the SAME graphs at three sizes.
 * Author: Tuleubayev Damir.
 *
 * <p>Build and run from the repository root (or use {@code python tests/run_java_tests.py}):
 * <pre>
 *   javac --release 17 -encoding UTF-8 -d .build/tests src/Java/*.java tests/Benchmark.java
 *   java -Xmx384m -cp .build/tests Benchmark
 * </pre>
 *
 * <p>Inputs: for size index k the generator uses {@code new SplittableRandom(SEED + k)}; it
 * first adds a random spanning tree (vertex i joins a random earlier vertex, so the graph is
 * connected) and then m-(n-1) uniformly random extra edges (self-loops and parallel edges
 * allowed). Weights are uniform in [-1e9, 1e9].
 *
 * <p>Timing boundary (identical for both methods): one call of {@code Algorithms.kruskal(n, edges)}
 * or {@code Algorithms.prim(n, edges)} on the pre-built {@code int[][]} edge array, measured with
 * {@code System.nanoTime()}. Included: sorting / adjacency-list construction, DSU or heap work,
 * building the result map. Excluded: compilation, JVM start-up, JSON parsing/serialisation,
 * graph generation and result validation. Before timing, each method runs WARMUP times per size
 * (JIT warm-up); then RUNS timed runs per method, alternating K,P,K,P,... with System.gc() before
 * every run. The median of the RUNS timings is reported.
 */
public final class Benchmark {
    private static final long SEED = 20261019L;
    private static final int WARMUP = 5;
    private static final int RUNS = 7;
    private static final int[][] SIZES = {{1_000, 5_000}, {10_000, 50_000}, {100_000, 250_000}};

    public static void main(String[] args) {
        System.out.printf("Java %s, %s %s, %d logical CPUs, max heap %d MB%n",
                System.getProperty("java.version"), System.getProperty("os.name"),
                System.getProperty("os.arch"), Runtime.getRuntime().availableProcessors(),
                Runtime.getRuntime().maxMemory() / (1024 * 1024));
        System.out.printf("seed=%d warm-up=%d runs=%d timer=System.nanoTime%n%n", SEED, WARMUP, RUNS);
        System.out.println("| n | m | method | cost | components | timings (ms) | median (ms) |");
        System.out.println("|---:|---:|---|---:|---:|---|---:|");

        for (int k = 0; k < SIZES.length; k++) {
            int n = SIZES[k][0];
            int m = SIZES[k][1];
            int[][] edges = generate(n, m, new SplittableRandom(SEED + k));

            // Correctness first: both forests valid and of equal (optimal) cost.
            Map<String, Object> kr = Algorithms.kruskal(n, edges);
            Map<String, Object> pr = Algorithms.prim(n, edges);
            long cost = validate(n, edges, kr);
            if (cost != validate(n, edges, pr) || !kr.get("components").equals(pr.get("components"))) {
                throw new AssertionError("Kruskal and Prim disagree at n=" + n);
            }

            for (int w = 0; w < WARMUP; w++) {
                Algorithms.kruskal(n, edges);
                Algorithms.prim(n, edges);
            }
            double[] tk = new double[RUNS];
            double[] tp = new double[RUNS];
            for (int r = 0; r < RUNS; r++) {
                tk[r] = time(() -> Algorithms.kruskal(n, edges));
                tp[r] = time(() -> Algorithms.prim(n, edges));
            }
            row(n, m, "Kruskal", cost, kr.get("components"), tk);
            row(n, m, "Prim", cost, pr.get("components"), tp);
        }
    }

    static int[][] generate(int n, int m, SplittableRandom random) {
        int[][] edges = new int[m][];
        int i = 0;
        for (int v = 1; v < n && i < m; v++) {
            edges[i++] = new int[] {v, random.nextInt(v), weight(random)};
        }
        while (i < m) {
            edges[i++] = new int[] {random.nextInt(n), random.nextInt(n), weight(random)};
        }
        return edges;
    }

    private static int weight(SplittableRandom random) {
        return random.nextInt(-1_000_000_000, 1_000_000_001);
    }

    private static double time(Runnable action) {
        System.gc();
        long started = System.nanoTime();
        action.run();
        return (System.nanoTime() - started) / 1e6;
    }

    /** Forest check: n-c distinct non-cycle edges, spanning every component; returns cost. */
    private static long validate(int n, int[][] edges, Map<String, Object> result) {
        int[] ids = (int[]) result.get("edge_ids");
        int components = (Integer) result.get("components");
        if (ids.length != n - components) {
            throw new AssertionError("wrong forest size");
        }
        Algorithms.DisjointSet sets = new Algorithms.DisjointSet(n);
        long cost = 0;
        for (int id : ids) {
            if (!sets.union(edges[id][0], edges[id][1])) {
                throw new AssertionError("forest contains a cycle or repeated edge");
            }
            cost += edges[id][2];
        }
        for (int[] e : edges) {
            if (sets.find(e[0]) != sets.find(e[1])) {
                throw new AssertionError("forest does not span a component");
            }
        }
        if (cost != (Long) result.get("cost")) {
            throw new AssertionError("reported cost differs from selected edges");
        }
        return cost;
    }

    private static void row(int n, int m, String method, long cost, Object components, double[] t) {
        double[] sorted = t.clone();
        Arrays.sort(sorted);
        StringBuilder all = new StringBuilder();
        for (double x : t) {
            all.append(all.length() == 0 ? "" : ", ").append(String.format("%.2f", x));
        }
        System.out.printf("| %d | %d | %s | %d | %s | %s | **%.2f** |%n",
                n, m, method, cost, components, all, sorted[sorted.length / 2]);
    }
}
