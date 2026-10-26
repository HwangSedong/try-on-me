"""Replay a fixed try-on workload against one backend version and record memory and latency.

One iteration mirrors the studio flow: prepare a garment, download its cutout,
generate a result, download the result.  The server runs in a Docker container
with the production systemd limits (MemoryMax=384M, CPUQuota=40%) on Python 3.10,
or as a local subprocess with --mode local.

Example:
    python benchmarks/run_benchmark.py --label baseline --backend-dir ../baseline/backend
"""

import argparse
import asyncio
import csv
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

BENCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = BENCH_DIR.parent
IMAGE_TAG = "try-on-me-bench:py3.10"
MIB = 1024 * 1024


class ServerGone(Exception):
    pass


def png(width: int, height: int, color: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color).save(output, format="PNG")
    return output.getvalue()


PERSON = png(64, 96, "white")
GARMENT = png(48, 48, "navy")


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    # Nearest-rank percentile: no interpolation between samples.
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def latency_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "mean_ms": round(statistics.fmean(values), 2) if values else None,
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        # P99 from fewer than 100 samples is just the maximum, so it is omitted.
        "p99_ms": percentile(values, 0.99) if len(values) >= 100 else None,
        "max_ms": max(values) if values else None,
    }


class Server:
    def __init__(self, args, label: str, repeat: int):
        self.args = args
        self.name = f"tryon-bench-{label}-{repeat}"
        self.process: subprocess.Popen | None = None
        self.base_url = f"http://127.0.0.1:{args.port}"

    def start(self) -> None:
        server_args = ["--result-bytes", str(self.args.result_bytes), "--cutout-bytes", str(self.args.cutout_bytes), "--log-level", self.args.log_level]
        if self.args.mode == "docker":
            subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)
            subprocess.run([
                "docker", "run", "-d", "--name", self.name,
                "--memory", self.args.memory, "--memory-swap", self.args.memory, "--cpus", str(self.args.cpus),
                "-p", f"127.0.0.1:{self.args.port}:8080",
                "--mount", f"type=bind,source={Path(self.args.backend_dir).resolve()},target=/srv/backend,readonly",
                "--mount", f"type=bind,source={BENCH_DIR},target=/srv/bench,readonly",
                "-w", "/tmp", IMAGE_TAG,
                "python", "/srv/bench/bench_server.py", "--backend-dir", "/srv/backend", "--port", "8080", *server_args,
            ], check=True, capture_output=True)
        else:
            self.process = subprocess.Popen(
                [sys.executable, str(BENCH_DIR / "bench_server.py"), "--backend-dir", str(Path(self.args.backend_dir).resolve()),
                 "--host", "127.0.0.1", "--port", str(self.args.port), *server_args],
                cwd=BENCH_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    def state(self) -> dict[str, object]:
        if self.args.mode == "docker":
            result = subprocess.run(["docker", "inspect", "--format", "{{json .State}}", self.name], capture_output=True, text=True)
            if result.returncode != 0:
                return {"running": False}
            state = json.loads(result.stdout)
            return {"running": state["Running"], "oom_killed": state["OOMKilled"], "exit_code": state["ExitCode"]}
        assert self.process is not None
        code = self.process.poll()
        return {"running": code is None, "exit_code": code}

    def stop(self) -> None:
        if self.args.mode == "docker":
            subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)
        elif self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=10)


async def wait_until_healthy(client: httpx.AsyncClient, server: Server) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if (await client.get("/api/health")).status_code == 200:
                return
        except httpx.TransportError:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError(f"server did not become healthy: {server.state()}")


async def snapshot(client: httpx.AsyncClient, point: str, completed: int) -> dict[str, object]:
    try:
        stats = (await client.get("/__bench/stats")).json()
    except httpx.TransportError as error:
        raise ServerGone(point) from error
    return {"point": point, "completed_iterations": completed, **stats}


async def timed(client: httpx.AsyncClient, rows: list[dict], context: dict, endpoint: str, method: str, url: str, **kwargs) -> httpx.Response | None:
    started = time.perf_counter()
    try:
        response = await client.request(method, url, **kwargs)
        status = response.status_code
    except httpx.TransportError as error:
        response, status = None, f"transport:{type(error).__name__}"
    rows.append({**context, "endpoint": endpoint, "status": status, "latency_ms": round((time.perf_counter() - started) * 1000, 3)})
    return response


async def iteration(client: httpx.AsyncClient, rows: list[dict], context: dict) -> bool:
    prepared = await timed(client, rows, context, "POST /api/garments/prepare", "POST", "/api/garments/prepare",
                           files={"image": ("top.png", GARMENT, "image/png")}, data={"requested_category": "top"})
    if prepared is None:
        return False
    if prepared.status_code == 200:
        await timed(client, rows, context, "GET /api/cutouts/{id}", "GET", prepared.json()["cutout_url"])
    generated = await timed(client, rows, context, "POST /api/generate", "POST", "/api/generate",
                            files={"person": ("person.png", PERSON, "image/png"), "top": ("top.png", GARMENT, "image/png")},
                            data={"remove_background": "true"})
    if generated is None:
        return False
    if generated.status_code == 200:
        if await timed(client, rows, context, "GET /api/results/{id}", "GET", generated.json()["result_url"]) is None:
            return False
    return True


async def run_once(args, label: str, repeat: int) -> tuple[dict, list[dict]]:
    server = Server(args, label, repeat)
    rows: list[dict] = []
    snapshots: list[dict] = []
    crashed_at: str | None = None
    phases: dict[str, dict] = {}
    server.start()
    try:
        async with httpx.AsyncClient(base_url=server.base_url, timeout=60) as client:
            await wait_until_healthy(client, server)
            snapshots.append(await snapshot(client, "initial", 0))

            checkpoints = set(args.checkpoints)
            sequential_started = time.perf_counter()
            for index in range(1, args.iterations + 1):
                if not await iteration(client, rows, {"repeat": repeat, "phase": "sequential", "iteration": index}):
                    crashed_at = f"sequential iteration {index}"
                    break
                if index in checkpoints:
                    snapshots.append(await snapshot(client, f"after_{index}", index))
            phases["sequential"] = {"iterations": index, "wall_seconds": round(time.perf_counter() - sequential_started, 3)}

            if crashed_at is None:
                await asyncio.sleep(args.idle_seconds)
                snapshots.append(await snapshot(client, "idle_after_sequential", args.iterations))

                semaphore = asyncio.Semaphore(args.concurrency)
                outcomes: list[bool] = []

                async def bounded(index: int) -> None:
                    async with semaphore:
                        outcomes.append(await iteration(client, rows, {"repeat": repeat, "phase": "concurrent", "iteration": index}))

                concurrent_started = time.perf_counter()
                await asyncio.gather(*(bounded(index) for index in range(1, args.concurrent_iterations + 1)))
                phases["concurrent"] = {
                    "iterations": args.concurrent_iterations, "concurrency": args.concurrency,
                    "wall_seconds": round(time.perf_counter() - concurrent_started, 3),
                }
                if not all(outcomes):
                    crashed_at = "concurrent phase"
                else:
                    snapshots.append(await snapshot(client, "after_concurrent", args.iterations + args.concurrent_iterations))
    except ServerGone as error:
        crashed_at = crashed_at or f"stats request at {error}"
    finally:
        await asyncio.sleep(1)
        final_state = server.state()
        server.stop()
    return {"repeat": repeat, "crashed_at": crashed_at, "final_state": final_state, "phases": phases, "snapshots": snapshots}, rows


def summarize_rows(rows: list[dict], phases: dict) -> dict[str, object]:
    summary: dict[str, object] = {}
    for phase in ("sequential", "concurrent"):
        phase_rows = [row for row in rows if row["phase"] == phase]
        if not phase_rows:
            continue
        statuses: dict[str, int] = {}
        for row in phase_rows:
            statuses[str(row["status"])] = statuses.get(str(row["status"]), 0) + 1
        ok = [row for row in phase_rows if row["status"] == 200]
        endpoints = sorted({row["endpoint"] for row in phase_rows})
        wall = sum(run[phase]["wall_seconds"] for run in phases if phase in run)
        summary[phase] = {
            "requests": len(phase_rows),
            "succeeded": len(ok),
            "failed": len(phase_rows) - len(ok),
            "error_rate": round((len(phase_rows) - len(ok)) / len(phase_rows), 4),
            "status_codes": statuses,
            "requests_per_second": round(len(phase_rows) / wall, 2) if wall else None,
            "all_requests": latency_summary([row["latency_ms"] for row in ok]),
            "by_endpoint": {endpoint: latency_summary([row["latency_ms"] for row in ok if row["endpoint"] == endpoint]) for endpoint in endpoints},
        }
    return summary


def environment(args) -> dict[str, object]:
    env: dict[str, object] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "client_python": platform.python_version(),
        "host_os": platform.platform(),
        "host_cpu": platform.processor(),
        "mode": args.mode,
    }
    if args.mode == "docker":
        info = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}|{{.KernelVersion}}|{{.NCPU}}|{{.MemTotal}}"], capture_output=True, text=True).stdout.strip().split("|")
        python = subprocess.run(["docker", "run", "--rm", IMAGE_TAG, "python", "-c", "import platform,fastapi,uvicorn;print(platform.python_version(),fastapi.__version__,uvicorn.__version__)"], capture_output=True, text=True).stdout.split()
        env.update({
            "docker_server": info[0], "docker_kernel": info[1], "docker_vm_cpus": info[2], "docker_vm_memory_bytes": info[3],
            "server_python": python[0], "server_fastapi": python[1], "server_uvicorn": python[2],
            "container_memory_limit": args.memory, "container_cpus": args.cpus,
        })
    else:
        import fastapi
        import psutil
        import uvicorn

        env.update({
            "server_python": platform.python_version(), "server_fastapi": fastapi.__version__, "server_uvicorn": uvicorn.__version__,
            "host_logical_cpus": psutil.cpu_count(), "host_memory_bytes": psutil.virtual_memory().total,
            "memory_limit_enforced": False,
        })
    return env


def build_image() -> None:
    subprocess.run(["docker", "build", "-q", "-t", IMAGE_TAG, "-f", str(BENCH_DIR / "Dockerfile"), str(REPO_ROOT / "backend")], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True)
    parser.add_argument("--backend-dir", required=True, help="backend directory of the version under test")
    parser.add_argument("--mode", choices=["docker", "local"], default="docker")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--checkpoints", type=int, nargs="+", default=[10, 50, 100])
    parser.add_argument("--concurrent-iterations", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--idle-seconds", type=float, default=3)
    parser.add_argument("--result-bytes", type=int, default=2 * MIB)
    parser.add_argument("--cutout-bytes", type=int, default=3 * MIB // 2)
    parser.add_argument("--log-level", default="INFO", help="LOG_LEVEL passed to the server")
    parser.add_argument("--memory", default="384m")
    parser.add_argument("--cpus", type=float, default=0.4)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--output-dir", default=str(BENCH_DIR / "results"))
    args = parser.parse_args()

    if args.mode == "docker":
        build_image()
    runs: list[dict] = []
    rows: list[dict] = []
    for repeat in range(1, args.repeats + 1):
        run, run_rows = asyncio.run(run_once(args, args.label, repeat))
        runs.append(run)
        rows.extend(run_rows)
        print(f"[{args.label}] repeat {repeat}: crashed_at={run['crashed_at']} state={run['final_state']}", flush=True)

    result = {
        "label": args.label,
        "environment": environment(args),
        "workload": {
            "iteration": "POST /api/garments/prepare -> GET cutout -> POST /api/generate -> GET result",
            "iterations_sequential": args.iterations, "checkpoints": args.checkpoints,
            "iterations_concurrent": args.concurrent_iterations, "concurrency": args.concurrency,
            "result_bytes": args.result_bytes, "cutout_bytes": args.cutout_bytes,
            "person_upload_bytes": len(PERSON), "garment_upload_bytes": len(GARMENT),
            "repeats": args.repeats, "idle_seconds": args.idle_seconds, "log_level": args.log_level,
        },
        "runs": runs,
        "latency": summarize_rows(rows, [run["phases"] for run in runs]),
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{args.label}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(output_dir / f"{args.label}.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["repeat", "phase", "iteration", "endpoint", "status", "latency_ms"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {output_dir / (args.label + '.json')}")


if __name__ == "__main__":
    main()
