"""Copy-on-write historical tape reuse; original bytes remain immutable."""

import ctypes
import os
from pathlib import Path
import shutil
import sys

import numpy as np

from scripts.research.c22_context_campaign import require


def clone_tape(source, target, total):
    source, target = Path(source), Path(target)
    require(source.resolve() != target.resolve(), "cannot overwrite source tape")
    require(
        not target.exists() and type(total) is int and total > 0,
        "new target and positive size required",
    )
    with source.open("rb") as handle:
        version = np.lib.format.read_magic(handle)
        require(version in ((1, 0), (2, 0)), "unsupported NPY version")
        reader = (
            np.lib.format.read_array_header_1_0
            if version == (1, 0)
            else np.lib.format.read_array_header_2_0
        )
        shape, fortran, dtype = reader(handle)
        offset = handle.tell()
    require(
        len(shape) == 1 and not fortran and dtype in (np.dtype("int64"), np.dtype("float64")),
        "one-dimensional numeric tape required",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    cloned = False
    if sys.platform == "darwin":
        library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        clone = library.clonefile
        clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        clone.restype = ctypes.c_int
        cloned = clone(os.fsencode(source), os.fsencode(target), 0) == 0
    if not cloned:
        require(
            shutil.disk_usage(target.parent).free >= source.stat().st_size + 8 * 1024**2,
            "insufficient disk for non-COW tape copy",
        )
        shutil.copyfile(source, target)
    with target.open("r+b") as handle:
        writer = (
            np.lib.format.write_array_header_1_0
            if version == (1, 0)
            else np.lib.format.write_array_header_2_0
        )
        writer(
            handle,
            dict(descr=np.lib.format.dtype_to_descr(dtype), fortran_order=False, shape=(total,)),
        )
        require(handle.tell() == offset, "resized NPY header changes data offset")
        handle.truncate(offset + total * dtype.itemsize)
    return np.load(target, mmap_mode="r+")
