from __future__ import annotations

import collections
import collections.abc
import math
import subprocess
import tempfile
from itertools import combinations
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
THIRD_PARTY = Path(__file__).resolve().parent / "third_party"

MZOOM_JAR = THIRD_PARTY / "mzoom" / "MZoom-2.0.jar"
DCUBE_JAR = THIRD_PARTY / "dcube" / "DCube-2.0.jar"
CATCHCORE_DIR = THIRD_PARTY / "catchcore"
CATCHCORE_DEPS = THIRD_PARTY / "catchcore_deps"


def _iter_entries(cell_items: dict[tuple, frozenset]) -> list[tuple]:
    return [
        tuple(list(cell) + [int(item)])
        for cell, items in sorted(cell_items.items())
        for item in sorted(items)
    ]


def _write_tensor_csv(entries: list[tuple], out_path: Path) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(",".join(map(str, entry)) + ",1\n")


def _count_mass(tuple_path: Path, total_dims: int) -> int:
    if not tuple_path.exists():
        return 0
    mass = 0
    with open(tuple_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            toks = line.split(",")
            if len(toks) < total_dims + 1:
                continue
            mass += int(float(toks[total_dims]))
    return mass


def _compute_block_density(
    dims_sets: list[set[int]],
    entries: list[tuple],
) -> tuple[int, float]:
    mass = 0
    for entry in entries:
        if all(entry[d] in dims_sets[d] for d in range(len(dims_sets))):
            mass += 1
    vol = math.prod(max(1, len(s)) for s in dims_sets)
    density = mass / (vol ** (1.0 / len(dims_sets))) if vol > 0 else 0.0
    return mass, density


def _parse_block_attributes_dir(
    output_dir: Path,
    n_dims: int,
    entries: list[tuple],
) -> list[dict]:
    total_dims = n_dims + 1

    def block_idx(path: Path) -> int:
        return int(path.stem.split("_")[1])

    blocks = []
    for attr_path in sorted(output_dir.glob("block_*.attributes"), key=block_idx):
        dims_sets = [set() for _ in range(total_dims)]
        with open(attr_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                dim_str, val_str = line.split(",", 1)
                dim = int(dim_str)
                dims_sets[dim].add(int(float(val_str)))

        tuple_path = attr_path.with_suffix(".tuples")
        mass = _count_mass(tuple_path, total_dims)
        vol = math.prod(max(1, len(s)) for s in dims_sets)
        density = mass / (vol ** (1.0 / total_dims)) if vol > 0 else 0.0
        item_set = set(sorted(dims_sets[n_dims]))

        blocks.append({
            "spatial_sets": [set(dims_sets[d]) for d in range(n_dims)],
            "c_set": item_set,
            "density": density,
            "n_entries": mass,
            "pairs": set(combinations(sorted(item_set), 2)),
        })

    return blocks


def _run_java_block_detector(
    class_name: str,
    jar_path: Path,
    entries: list[tuple],
    n_dims: int,
    *extra_args: str,
) -> list[dict]:
    total_dims = n_dims + 1
    with tempfile.TemporaryDirectory(prefix=f"{class_name.replace('.', '_')}_") as td:
        td_path = Path(td)
        tensor_path = td_path / "tensor.csv"
        out_dir = td_path / "output"
        out_dir.mkdir()
        _write_tensor_csv(entries, tensor_path)
        cmd = [
            "java",
            "-cp",
            str(jar_path),
            class_name,
            str(tensor_path),
            str(out_dir),
            str(total_dims),
            *map(str, extra_args),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"{class_name} failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        return _parse_block_attributes_dir(out_dir, n_dims, entries)


def collect_mzoom_blocks_official(
    cell_items: dict[tuple, frozenset],
    n_dims: int,
    top_k: int,
    density_measure: str = "geo",
) -> list[dict]:
    entries = _iter_entries(cell_items)
    return _run_java_block_detector(
        "mzoom.MZoom",
        MZOOM_JAR,
        entries,
        n_dims,
        density_measure,
        str(top_k),
    )


def collect_mbiz_blocks_official(
    cell_items: dict[tuple, frozenset],
    n_dims: int,
    top_k: int,
    density_measure: str = "geo",
) -> list[dict]:
    entries = _iter_entries(cell_items)
    return _run_java_block_detector(
        "mzoom.MBiz",
        MZOOM_JAR,
        entries,
        n_dims,
        density_measure,
        str(top_k),
    )


def collect_dcube_blocks_official(
    cell_items: dict[tuple, frozenset],
    n_dims: int,
    top_k: int,
    density_measure: str = "geo",
    policy: str = "density",
    mass_threshold: float = 1.0,
) -> list[dict]:
    entries = _iter_entries(cell_items)
    return _run_java_block_detector(
        "dcube.Proposed",
        DCUBE_JAR,
        entries,
        n_dims,
        density_measure,
        policy,
        str(mass_threshold),
        str(top_k),
    )


def _parse_catchcore_hierways(path: Path, n_dims: int, entries: list[tuple]) -> list[dict]:
    total_dims = n_dims + 1
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip()
        if not header.startswith("%"):
            raise RuntimeError(f"unexpected CatchCore output header: {header}")
        n_hiers, ndim = map(int, header[1:].split(","))
        if ndim != total_dims:
            raise RuntimeError(
                f"CatchCore output dimension mismatch: expected {total_dims}, got {ndim}"
            )
        f.readline()  # shapes
        dims_by_h = [[set() for _ in range(total_dims)] for _ in range(n_hiers)]
        for line in f:
            line = line.strip()
            if not line:
                continue
            head, values = line.split(":", 1)
            h, dm = map(int, head.split("_"))
            vals = [int(v) for v in values.split(",") if v != ""]
            dims_by_h[h][dm] = set(vals)

    blocks = []
    for dims_sets in dims_by_h:
        mass, density = _compute_block_density(dims_sets, entries)
        item_set = set(sorted(dims_sets[n_dims]))
        blocks.append({
            "spatial_sets": [set(dims_sets[d]) for d in range(n_dims)],
            "c_set": item_set,
            "density": density,
            "n_entries": mass,
            "pairs": set(combinations(sorted(item_set), 2)),
        })
    return blocks


def collect_catchcore_blocks_official(
    cell_items: dict[tuple, frozenset],
    n_dims: int,
    hs: int,
    p: float,
    cons: float,
    etas: float,
    eps: float = 1e-6,
) -> list[dict]:
    entries = _iter_entries(cell_items)
    total_dims = n_dims + 1
    with tempfile.TemporaryDirectory(prefix="catchcore_") as td:
        td_path = Path(td)
        tensor_path = td_path / "tensor.csv"
        out_dir = td_path / "output"
        out_dir.mkdir()
        _write_tensor_csv(entries, tensor_path)

        shim = """
import collections
import collections.abc
import runpy
import sys
import numpy as np

np.float = float
np.int = int
np.complex = complex
np.in1d = np.isin
collections.Iterable = collections.abc.Iterable

deps, root, script = sys.argv[1:4]
sys.path.insert(0, deps)
sys.path.insert(0, root)
sys.argv = [script] + sys.argv[4:]
runpy.run_path(script, run_name='__main__')
"""
        script_path = CATCHCORE_DIR / "run_catchcore.py"
        cmd = [
            "python3",
            "-c",
            shim,
            str(CATCHCORE_DEPS),
            str(CATCHCORE_DIR),
            str(script_path),
            str(tensor_path),
            str(out_dir) + "/",
            str(total_dims),
            "-1",
            str(hs),
            str(p),
            str(cons),
            str(etas),
            str(eps),
            ",",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=CATCHCORE_DIR)
        if proc.returncode != 0:
            raise RuntimeError(
                f"CatchCore failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )

        return _parse_catchcore_hierways(out_dir / "hierways.out", n_dims, entries)
