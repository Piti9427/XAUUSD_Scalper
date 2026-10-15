"""Atomic, hash-bound campaign artifacts. Caller holds campaign OS lock."""

from pathlib import Path

from scripts.research.c22_context_campaign import (
    read,
    require,
    digest,
    checkpoint_digest,
    write_checkpoint,
)
from scripts.research.reward156_tuning import atomic_json


class Store:
    def __init__(self, root, protocol):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.root / "checkpoint.json"
        path = self.root / "protocol.json"
        if path.exists():
            require(read(path) == protocol, "resume protocol drift")
        else:
            require(
                all(p.name in (".campaign.lock", "protocol.pending") for p in self.root.iterdir()),
                "unrecognized campaign artifacts",
            )
            atomic_json(path, protocol)
        if self.checkpoint.exists():
            self.state = read(self.checkpoint)
            require(
                self.state.get("self_sha256") == checkpoint_digest(self.state),
                "checkpoint digest mismatch",
            )
            require(
                self.state.get("protocol_sha256") == digest(path), "checkpoint protocol mismatch"
            )
        else:
            self.state = dict(protocol_sha256=digest(path), artifacts={}, pending=None)
            write_checkpoint(self.checkpoint, self.state)
        for name, expected in self.state["artifacts"].items():
            self.target(name)
            require(digest(self.root / name) == expected, "resume artifact drift: " + name)
        if self.state["pending"] is not None:
            pending = self.state["pending"]
            target = self.target(pending["name"])
            require(pending["name"] not in self.state["artifacts"], "pending overwrites artifact")
            if target.exists():
                require(read(target) == pending["value"], "pending artifact drift")
            self.finish(pending["name"], pending["value"])
        allowed = {"protocol.json", "checkpoint.json", ".campaign.lock", *self.state["artifacts"]}
        # Atomic writes can leave owned temporary bytes at interruption.
        for pending in self.root.rglob("*.pending"):
            relative = str(pending.with_suffix(".json").relative_to(self.root))
            require(relative in allowed, "unrecognized pending artifact")
            pending.unlink()
        require(
            all(
                str(p.relative_to(self.root)) in allowed
                for p in self.root.rglob("*")
                if p.is_file()
            ),
            "unrecognized campaign artifacts",
        )

    def target(self, name):
        target = self.root / name
        require(
            not Path(name).is_absolute()
            and ".." not in Path(name).parts
            and target.resolve().is_relative_to(self.root.resolve())
            and name.endswith(".json")
            and name not in ("protocol.json", "checkpoint.json"),
            "invalid artifact name",
        )
        return target

    def get(self, name):
        if name not in self.state["artifacts"]:
            return None
        target = self.target(name)
        require(digest(target) == self.state["artifacts"][name], "artifact drift: " + name)
        return read(target)

    def finish(self, name, value):
        target = self.target(name)
        atomic_json(target, value)
        self.state["artifacts"][name] = digest(target)
        self.state["pending"] = None
        write_checkpoint(self.checkpoint, self.state)

    def put(self, name, value):
        self.target(name)
        if name in self.state["artifacts"]:
            require(self.get(name) == value, "attempted artifact overwrite: " + name)
            return
        self.state["pending"] = dict(name=name, value=value)
        write_checkpoint(self.checkpoint, self.state)
        self.finish(name, value)
