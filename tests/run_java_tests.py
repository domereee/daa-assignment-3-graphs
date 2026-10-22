"""Compile and run the Java-side tests: route helper and Kruskal/Prim benchmark.

Author: Tuleubayev Damir.

    python tests/run_java_tests.py              # route helper + benchmark
    python tests/run_java_tests.py --no-bench   # route helper only

Equivalent manual commands (repository root):
    javac --release 17 -encoding UTF-8 -d .build/tests src/Java/*.java tests/RouteHelperTest.java tests/Benchmark.java
    java -cp .build/tests RouteHelperTest
    java -Xmx384m -cp .build/tests Benchmark

Outputs are saved to tests/results/route_helper_output.txt and tests/results/benchmark.md.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / ".build" / "tests"
RESULTS = ROOT / "tests" / "results"


def run(command, save_to):
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    print(proc.stdout, end="")
    if proc.returncode:
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    (RESULTS / save_to).write_text(proc.stdout, encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    sources = sorted(str(p) for p in (ROOT / "src" / "Java").glob("*.java"))
    sources += [str(ROOT / "tests" / "RouteHelperTest.java"), str(ROOT / "tests" / "Benchmark.java")]
    subprocess.run(["javac", "--release", "17", "-encoding", "UTF-8", "-d", str(OUT), *sources], check=True)
    run(["java", "-cp", str(OUT), "RouteHelperTest"], "route_helper_output.txt")
    if "--no-bench" not in sys.argv:
        print()
        run(["java", "-Xmx384m", "-cp", str(OUT), "Benchmark"], "benchmark.md")


if __name__ == "__main__":
    main()
