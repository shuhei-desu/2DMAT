import typing
from typing import List, Set
from os import PathLike

import sys
import itertools

import numpy as np

try:
    from tqdm import tqdm

    has_tqdm = True
except:
    has_tqdm = False


class Cells:
    cells: List[Set[int]]
    dimension: int
    mins: np.ndarray
    maxs: np.ndarray
    Ns: np.ndarray
    ncell: int
    cellsize: float

    def __init__(self, mins: np.ndarray, maxs: np.ndarray, cellsize: float):
        self.dimension = len(mins)
        self.mins = mins
        Ls = (maxs - mins) * 1.001
        self.Ns = np.ceil(Ls / cellsize).astype(np.int64)
        self.maxs = self.mins + cellsize * self.Ns
        self.cellsize = cellsize
        self.ncell = typing.cast(int, np.prod(self.Ns))
        self.cells = [set() for _ in range(self.ncell)]

    def coord2cellindex(self, x: np.ndarray) -> int:
        return self.cellcoord2cellindex(self.coord2cellcoord(x))

    def coord2cellcoord(self, x: np.ndarray) -> np.ndarray:
        return np.floor((x - self.mins) / self.cellsize).astype(np.int64)

    def cellcoord2cellindex(self, ns: np.ndarray) -> int:
        index = 0
        oldN = 1
        for n, N in zip(ns, self.Ns):
            index *= oldN
            index += n
            oldN = N
        return index

    def cellindex2cellcoord(self, index: int) -> np.ndarray:
        ns = np.zeros(self.dimension, dtype=np.int64)
        for d in range(self.dimension):
            d = self.dimension - d - 1
            N = self.Ns[d]
            ns[d] = index % N
            index = index // N
        return ns

    def out_of_bound(self, ns: np.ndarray) -> bool:
        if np.any(ns < 0):
            return True
        if np.any(ns >= self.Ns):
            return True
        return False

    def neighborcells(self, index: int) -> List[int]:
        neighbors: List[int] = []
        center_coord = self.cellindex2cellcoord(index)
        for diff in itertools.product([-1, 0, 1], repeat=self.dimension):
            other_coord = center_coord + np.array(diff)
            if self.out_of_bound(other_coord):
                continue
            other_coord_index = self.cellcoord2cellindex(other_coord)
            neighbors.append(other_coord_index)
        return neighbors


def make_neighbor_list_cell(
    X: np.ndarray, radius: float, show_progress: bool
) -> List[List[int]]:
    mins = typing.cast(np.ndarray, X.min(axis=0))
    maxs = typing.cast(np.ndarray, X.max(axis=0))
    cells = Cells(mins, maxs, radius * 1.001)
    npoints = X.shape[0]
    nnlist: List[List[int]] = [[] for _ in range(npoints)]
    for n in range(npoints):
        xs = X[n, :]
        index = cells.coord2cellindex(xs)
        cells.cells[index].add(n)
    if show_progress:
        if has_tqdm:
            ns = tqdm(range(npoints))
        else:
            print("WARNING: cannot show progress because tqdm package is not available")
            ns = range(npoints)
    else:
        ns = range(npoints)
    for n in ns:
        xs = X[n, :]
        cellindex = cells.coord2cellindex(xs)
        for neighborcell in cells.neighborcells(cellindex):
            for other in cells.cells[neighborcell]:
                if other <= n:
                    continue
                ys = X[other, :]
                r = np.linalg.norm(xs - ys)
                if r <= radius:
                    nnlist[n].append(other)
                    nnlist[other].append(n)
    return nnlist


def make_neighbor_list_naive(
    X: np.ndarray, radius: float, show_progress: bool
) -> List[List[int]]:
    npoints = X.shape[0]
    nnlist: List[List[int]] = [[] for _ in range(npoints)]
    if show_progress:
        if has_tqdm:
            ns = tqdm(range(npoints))
        else:
            print("WARNING: cannot show progress because tqdm package is not available")
            ns = range(npoints)
    else:
        ns = range(npoints)
    for n in ns:
        xs = X[n, :]
        for m in range(n + 1, npoints):
            ys = X[m, :]
            r = np.linalg.norm(xs - ys)
            if r <= radius:
                nnlist[n].append(m)
                nnlist[m].append(n)
    return nnlist


def make_neighbor_list(
    X: np.ndarray,
    radius: float,
    check_allpairs: bool = False,
    show_progress: bool = False,
) -> List[List[int]]:
    if check_allpairs:
        return make_neighbor_list_naive(X, radius, show_progress=show_progress)
    else:
        return make_neighbor_list_cell(X, radius, show_progress=show_progress)


def load_neighbor_list(filename: PathLike, nnodes: int = None) -> List[List[int]]:
    if nnodes is None:
        nnodes = 0
        with open(filename) as f:
            for line in f:
                line = line.split("#")[0].strip()
                if len(line) == 0:
                    continue
                nnodes += 1
    neighbor_list: List[List[int]] = [[] for _ in range(nnodes)]
    with open(filename) as f:
        for line in f:
            line = line.strip().split("#")[0]
            if len(line) == 0:
                continue
            words = line.split()
            i = int(words[0])
            nn = [int(w) for w in words[1:]]
            neighbor_list[i] = nn
    return neighbor_list


def write_neighbor_list(
    filename: str,
    nnlist: List[List[int]],
    radius: float = None,
    unit: np.ndarray = None,
):
    with open(filename, "w") as f:
        if radius is not None:
            f.write(f"# radius = {radius}\n")
        if unit is not None:
            f.write(f"# unit =")
            for u in unit:
                f.write(f" {u}")
            f.write("\n")
        for i, nn in enumerate(nnlist):
            f.write(str(i))
            for o in sorted(nn):
                f.write(f" {o}")
            f.write("\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Make neighbor-list file from mesh-data file",
        epilog="""
Note:
  - The first column of an input file will be ignored.
  - UNIT is used for changing aspect ratio (a kind of normalization)
    - Each coodinate will be divided by the corresponding unit
    - UNIT is given as a string separated with white space
      - For example, -u "1.0 0.5 1.0" for 3D case
  - tqdm python package is required to show progress bar
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=str, help="input file")
    parser.add_argument(
        "-o", "--output", type=str, default="neighborlist.txt", help="output file"
    )
    parser.add_argument(
        "-r", "--radius", type=float, default=1.0, help="neighborhood radius"
    )
    parser.add_argument(
        "-u",
        "--unit",
        default=None,
        help='length unit for each coordinate (see Note)',
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Do not show progress bar"
    )
    parser.add_argument(
        "--check_allpairs",
        action="store_true",
        help="check all pairs (bruteforce algorithm)",
    )

    args = parser.parse_args()

    inputfile = args.input
    outputfile = args.output
    radius = args.radius

    X = np.loadtxt(inputfile)
    D = X.shape[1] - 1

    if args.unit is None:
        unit = np.ones(D, dtype=float)
    else:
        unit = np.array([float(w) for w in args.unit.split()])
        if len(unit) != D:
            print(f"--unit option expects {D} floats as a string but {len(unit)} given")
            sys.exit(1)
    X = X[:, 1:] / unit

    nnlist = make_neighbor_list(
        X, radius, check_allpairs=args.check_allpairs, show_progress=(not args.quiet)
    )
    write_neighbor_list(outputfile, nnlist, radius=radius, unit=unit)


if __name__ == "__main__":
    main()
