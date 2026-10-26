"""Build a before/after Markdown table from run_benchmark.py JSON results.

    python benchmarks/compare.py results/baseline.json results/after.json [results/after-log-warning.json]
"""

import csv
import json
import statistics
import sys
from pathlib import Path

MIB = 1024 * 1024


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def snapshot(run: dict, point: str) -> dict | None:
    return next((item for item in run["snapshots"] if item["point"] == point), None)


def per_run(result: dict, pick) -> list[float]:
    values = []
    for run in result["runs"]:
        value = pick(run)
        if value is not None:
            values.append(value)
    return values


def fmt(values: list[float], unit: str = "", scale: float = 1, digits: int = 1) -> str:
    if not values:
        return "n/a"
    mean = statistics.fmean(values) / scale
    if len(values) == 1:
        return f"{mean:.{digits}f}{unit}"
    return f"{mean:.{digits}f}{unit} ± {statistics.stdev(values) / scale:.{digits}f}"


def change(before: list[float], after: list[float]) -> str:
    if not before or not after or statistics.fmean(before) == 0:
        return "n/a"
    ratio = (statistics.fmean(after) - statistics.fmean(before)) / statistics.fmean(before)
    return f"{ratio:+.1%}"


def memory_rows(results: list[dict]) -> list[tuple[str, list[list[float]], str, float, int]]:
    def rss(point):
        return lambda run: (snapshot(run, point) or {}).get("process", {}).get("rss_bytes")

    def store(point, field):
        return lambda run: (snapshot(run, point) or {}).get("store", {}).get(field)

    def peak(run):
        peaks = [item["process"].get("peak_rss_bytes") for item in run["snapshots"] if item["process"].get("peak_rss_bytes")]
        return max(peaks) if peaks else None

    rows = [
        ("초기 RSS", rss("initial"), " MiB", MIB, 1),
        ("10회 후 RSS", rss("after_10"), " MiB", MIB, 1),
        ("50회 후 RSS", rss("after_50"), " MiB", MIB, 1),
        ("100회 후 RSS", rss("after_100"), " MiB", MIB, 1),
        ("100회 후 3초 유휴 RSS", rss("idle_after_sequential"), " MiB", MIB, 1),
        ("동시 100회 추가 후 RSS (누적 200회)", rss("after_concurrent"), " MiB", MIB, 1),
        ("Peak RSS", peak, " MiB", MIB, 1),
        ("100회 후 저장 이미지 수", store("after_100", "items"), "", 1, 0),
        ("100회 후 저장 바이트", store("after_100", "bytes"), " MiB", MIB, 1),
        ("200회 후 저장 이미지 수", store("after_concurrent", "items"), "", 1, 0),
        ("200회 후 저장 바이트", store("after_concurrent", "bytes"), " MiB", MIB, 1),
    ]
    return [(label, [per_run(result, pick) for result in results], unit, scale, digits) for label, pick, unit, scale, digits in rows]


def latency_rows(results: list[dict]) -> list[tuple[str, list[list[float]], str, float, int]]:
    def per_repeat(phase: str, endpoint: str | None, field: str):
        values_by_result = []
        for result in results:
            values = []
            rows_path = Path(result["_path"]).with_suffix(".csv")
            with open(rows_path, encoding="utf-8") as handle:
                rows = [row for row in csv.DictReader(handle) if row["phase"] == phase and row["status"] == "200" and (endpoint is None or row["endpoint"] == endpoint)]
            for repeat in sorted({row["repeat"] for row in rows}):
                latencies = sorted(float(row["latency_ms"]) for row in rows if row["repeat"] == repeat)
                if field == "p95":
                    values.append(latencies[max(1, -(-95 * len(latencies) // 100)) - 1])
                else:
                    values.append(statistics.fmean(latencies))
            values_by_result.append(values)
        return values_by_result

    def throughput(phase: str):
        values_by_result = []
        for result in results:
            values = []
            rows_path = Path(result["_path"]).with_suffix(".csv")
            with open(rows_path, encoding="utf-8") as handle:
                rows = [row for row in csv.DictReader(handle) if row["phase"] == phase]
            for run in result["runs"]:
                wall = run["phases"].get(phase, {}).get("wall_seconds")
                count = sum(1 for row in rows if row["repeat"] == str(run["repeat"]))
                if wall:
                    values.append(count / wall)
            values_by_result.append(values)
        return values_by_result

    def error_rate(phase: str):
        values_by_result = []
        for result in results:
            summary = result["latency"].get(phase)
            values_by_result.append([summary["error_rate"] * 100] if summary else [])
        return values_by_result

    generate = "POST /api/generate"
    result_get = "GET /api/results/{id}"
    return [
        ("순차 POST /api/generate 평균", per_repeat("sequential", generate, "mean"), " ms", 1, 2),
        ("순차 POST /api/generate P95", per_repeat("sequential", generate, "p95"), " ms", 1, 2),
        ("순차 GET result P95", per_repeat("sequential", result_get, "p95"), " ms", 1, 2),
        ("동시성 8 POST /api/generate 평균", per_repeat("concurrent", generate, "mean"), " ms", 1, 2),
        ("동시성 8 POST /api/generate P95", per_repeat("concurrent", generate, "p95"), " ms", 1, 2),
        ("동시성 8 전체 요청 P95", per_repeat("concurrent", None, "p95"), " ms", 1, 2),
        ("순차 처리량", throughput("sequential"), " req/s", 1, 1),
        ("동시성 8 처리량", throughput("concurrent"), " req/s", 1, 1),
        ("순차 오류율", error_rate("sequential"), "%", 1, 2),
        ("동시성 8 오류율", error_rate("concurrent"), "%", 1, 2),
    ]


def table(title: str, labels: list[str], rows) -> str:
    header = "| Metric | " + " | ".join(labels) + " | Change (" + labels[1] + " vs " + labels[0] + ") |"
    lines = [f"### {title}", "", header, "|" + "---|" * (len(labels) + 2)]
    for label, values, unit, scale, digits in rows:
        cells = [fmt(item, unit, scale, digits) for item in values]
        lines.append(f"| {label} | " + " | ".join(cells) + f" | {change(values[0], values[1])} |")
    return "\n".join(lines)


def main() -> None:
    paths = sys.argv[1:]
    results = []
    for path in paths:
        result = load(path)
        result["_path"] = path
        results.append(result)
    labels = [result["label"] for result in results]
    crashes = "\n".join(f"- {result['label']}: " + ", ".join(f"repeat {run['repeat']} crashed_at={run['crashed_at']}" for run in result["runs"]) for result in results)
    output = "\n\n".join([
        "<!-- generated by benchmarks/compare.py; values are mean ± sample stdev across repeats -->",
        table("메모리", labels, memory_rows(results)),
        table("응답시간·처리량", labels, latency_rows(results)),
        "### 실행 상태\n\n" + crashes,
    ])
    print(output)
    Path(paths[0]).with_name("comparison.md").write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
