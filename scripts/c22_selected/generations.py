"""Atomic, content-addressed renewal snapshots; no trading authority is created.

The sender does not import this module. The future integration supplies semantic
validation, independently checked authority and a fresh single-sender exposure
observation. Staging a REVIEW_CANDIDATE never installs it. Readers resolve one
pointer and retain one complete immutable snapshot; no financial journal, owned
manager, approval timestamp or incident checkpoint is rewritten here.

A SQLite writer guard works on both POSIX and the Windows/Wine runtime. Files
are fsynced before rename; POSIX directory entries are also fsynced. Python's
portable Windows interface does not expose directory fsync, so the power-loss
claim there is limited to the filesystem's replace/durability guarantees.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import MappingProxyType
from typing import Callable, Mapping
import uuid

from scripts.c22_selected.renewal import (
    CALENDAR_FORMULA, RenewalPlan, RenewalState, _grant_error, economic_scope,
)
from scripts.c22_selected.trial_costs import build_trial_policy
from scripts.demo_runtime.costs import validate_policy

DOCUMENTS = frozenset({"policy", "broker", "sources", "review", "grant", "context", "cost_audit"})
_MAX_DOCUMENT = 64 * 1024 * 1024
_BINDING_KEYS = frozenset({"account_type", "account_fingerprint", "contract_id", "source_sha256",
                           "config_sha256", "economics_sha256", "calendar_formula"})


def _utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("generation_aware_utc_required")
    return stamp


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def _hex(value, length=64):
    return isinstance(value, str) and len(value) == length and all(char in "0123456789abcdef" for char in value)


def _object(raw, *, limit=_MAX_DOCUMENT):
    if not isinstance(raw, bytes) or len(raw) > limit:
        raise ValueError("generation_document_invalid")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("generation_duplicate_json_key")
            value[key] = item
        return value

    def nonfinite(_value):
        raise ValueError("generation_nonfinite_json")

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("generation_document_invalid") from error
    if not isinstance(value, dict):
        raise ValueError("generation_document_invalid")
    return value


def _sync_directory(path):
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


@dataclass(frozen=True)
class FreshState:
    """Real observation supplied by the existing sender, not a cached flat flag."""

    state: RenewalState
    observed_utc: datetime


@dataclass(frozen=True)
class GenerationSnapshot:
    generation_id: str
    binding: Mapping[str, str]
    documents: Mapping[str, bytes]


Validator = Callable[[GenerationSnapshot, datetime], bool]


class GenerationStore:
    """Stage, load and explicitly authorize a single local generation pointer.

    ``binding`` and ``trusted_grant_sha256`` must come from independently reviewed
    running configuration. The store never derives the trusted pin from a new
    untrusted grant. ``validate`` must check dated source evidence, the original
    review and applicable incident coverage; ``authorize`` additionally checks
    current external revocation/installer permission. Both must return exactly
    True. No default callback permits installation. The caller must atomically
    adopt the returned snapshot as its running entry context, while retaining any
    existing owned manager and financial journal unchanged.
    """

    def __init__(self, root, *, binding, trusted_grant_sha256):
        if (not isinstance(binding, dict) or set(binding) != _BINDING_KEYS
                or binding.get("account_type") != "Standard Demo"
                or binding.get("contract_id") != "26b8bcd69e043653"
                or binding.get("calendar_formula") != CALENDAR_FORMULA
                or not _hex(binding.get("account_fingerprint"), 16)
                or any(not _hex(binding.get(key)) for key in
                       ("source_sha256", "config_sha256", "economics_sha256"))
                or not _hex(trusted_grant_sha256)):
            raise ValueError("generation_trusted_binding_required")
        self.root = Path(root)
        self.binding = MappingProxyType(dict(binding))
        self.pin = trusted_grant_sha256

    def _safe_root(self, *, create=False):
        if self.root.is_symlink():
            raise ValueError("generation_symlink_rejected")
        if create:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.exists() and not self.root.is_dir():
            raise ValueError("generation_store_invalid")

    @contextmanager
    def _writer(self):
        self._safe_root(create=True)
        lock = self.root / ".writer.sqlite3"
        if lock.is_symlink():
            raise ValueError("generation_symlink_rejected")
        connection = sqlite3.connect(lock, timeout=0, isolation_level=None)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS writer (id INTEGER PRIMARY KEY)")
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as error:
                raise ValueError("generation_writer_busy") from error
            yield
            connection.execute("COMMIT")
        finally:
            connection.close()

    def _pointer(self):
        self._safe_root()
        pointer = self.root / "current.json"
        if pointer.is_symlink():
            raise ValueError("generation_symlink_rejected")
        if not pointer.exists():
            return None
        value = _object(pointer.read_bytes(), limit=512)
        if (set(value) != {"schema", "generation_id"} or type(value["schema"]) is not int
                or value["schema"] != 1 or not _hex(value["generation_id"])):
            raise ValueError("generation_pointer_invalid")
        return value["generation_id"]

    def _validate(self, snapshot, *, now, validate):
        now = _utc(now)
        if not callable(validate):
            raise ValueError("generation_validator_required")
        parsed = {name: _object(raw) for name, raw in snapshot.documents.items()}
        context, grant, policy = parsed["context"], parsed["grant"], parsed["policy"]
        if (context.get("binding") != self.binding or grant.get("binding") != self.binding
                or context.get("grant_sha256") != self.pin
                or _hash(_canonical(grant)) != self.pin
                or context.get("original_review_sha256") != _hash(snapshot.documents["review"])
                or context.get("cost_audit_sha256") != _hash(snapshot.documents["cost_audit"])
                or (context.get("parent_generation_id") is not None
                    and not _hex(context["parent_generation_id"]))):
            raise ValueError("generation_context_binding_mismatch")
        # Exactly the planner's grant predicate, including unchanged limits.
        # A pinned document is necessary but not sufficient authorization.
        if _grant_error(grant, self.pin, self.binding, now) is not None:
            raise ValueError("generation_authority_invalid")
        valid, _ = validate_policy(policy, fingerprint=self.binding["account_fingerprint"], now=now, strategy="c22h4")
        if not valid or _hash(_canonical(economic_scope(policy))) != self.binding["economics_sha256"]:
            raise ValueError("generation_policy_invalid")
        # Reuse the existing evidence builder and exact candidate math, not a
        # second tariff/swap interpretation. Review time is never advanced here.
        rebuilt = build_trial_policy(snapshot.documents["broker"], now=_utc(policy["reviewed_utc"]),
                                     sources=parsed["sources"])
        if rebuilt != policy:
            raise ValueError("generation_policy_evidence_mismatch")
        audit = parsed["cost_audit"]
        claimed = audit.get("receipt_sha256")
        material = {key: value for key, value in audit.items() if key != "receipt_sha256"}
        if (type(audit.get("schema_version")) is not int or audit.get("schema_version") != 1
                or audit.get("magic") != 22261025
                or audit.get("account_fingerprint") != self.binding["account_fingerprint"]
                or audit.get("original_review_sha256") != context["original_review_sha256"]
                or audit.get("status") != "CLEAR" or audit.get("execution_authorized") is not False
                or audit.get("unresolved_incidents") != [] or claimed != _hash(_canonical(material))):
            raise ValueError("generation_cost_audit_invalid")
        if validate(snapshot, now) is not True:
            raise ValueError("generation_semantic_validation_failed")
        return snapshot

    def _fresh_for_install(self, snapshot, now):
        broker = _object(snapshot.documents["broker"])
        audit = _object(snapshot.documents["cost_audit"])
        sources = _object(snapshot.documents["sources"])
        if (not timedelta(0) <= now - _utc(broker["captured_utc"]) <= timedelta(minutes=5)
                or not timedelta(0) <= now - _utc(audit["checkpoint"]["observed_utc"]) <= timedelta(minutes=5)
                or any(not timedelta(0) <= now - _utc(sources[key]["checked_utc"]) <= timedelta(hours=24)
                       for key in ("tariff", "swap", "calendar"))):
            raise ValueError("generation_fresh_evidence_required")

    def _load(self, generation_id, *, now, validate):
        if not _hex(generation_id):
            raise ValueError("generation_id_invalid")
        folder = self.root / "objects" / generation_id
        if folder.is_symlink() or folder.parent.is_symlink():
            raise ValueError("generation_symlink_rejected")
        manifest_path = folder / "manifest.json"
        if manifest_path.is_symlink():
            raise ValueError("generation_symlink_rejected")
        manifest = _object(manifest_path.read_bytes(), limit=65536)
        if (set(manifest) != {"schema", "binding", "files"} or type(manifest["schema"]) is not int
                or manifest["schema"] != 1 or not isinstance(manifest["files"], dict)
                or manifest["binding"] != self.binding
                or set(manifest["files"]) != DOCUMENTS
                or _hash(_canonical(manifest)) != generation_id):
            raise ValueError("generation_manifest_invalid")
        if {path.name for path in folder.iterdir()} != {"manifest.json"} | {name + ".json" for name in DOCUMENTS}:
            raise ValueError("generation_files_incomplete")
        documents = {}
        for name in sorted(DOCUMENTS):
            path = folder / (name + ".json")
            if path.is_symlink():
                raise ValueError("generation_symlink_rejected")
            content = path.read_bytes()
            if _hash(content) != manifest["files"][name]:
                raise ValueError("generation_document_hash_mismatch")
            documents[name] = content
        snapshot = GenerationSnapshot(generation_id, MappingProxyType(dict(self.binding)), MappingProxyType(documents))
        return self._validate(snapshot, now=now, validate=validate)

    def stage(self, plan, documents, *, now, validate):
        """Seal a candidate without changing the current generation or context."""
        if (not isinstance(plan, RenewalPlan) or plan.candidate_policy is None
                or plan.installation_authorized is not False
                or not (plan.action == "REVIEW_CANDIDATE" or (plan.action == "DEFER"
                    and plan.reason == "flat_no_orders_no_active_no_unknown_required"))
                or not isinstance(documents, dict) or set(documents) != DOCUMENTS
                or _object(documents["policy"]) != plan.candidate_policy):
            raise ValueError("generation_review_candidate_required")
        for content in documents.values():
            _object(content)
        manifest = {"schema": 1, "binding": dict(self.binding),
                    "files": {name: _hash(documents[name]) for name in sorted(DOCUMENTS)}}
        ident = _hash(_canonical(manifest))
        snapshot = GenerationSnapshot(ident, MappingProxyType(dict(self.binding)),
                                      MappingProxyType(dict(documents)))
        self._validate(snapshot, now=now, validate=validate)
        with self._writer():
            objects = self.root / "objects"
            if objects.is_symlink():
                raise ValueError("generation_symlink_rejected")
            objects.mkdir(mode=0o700, exist_ok=True)
            target = objects / ident
            if target.exists():
                return self._load(ident, now=now, validate=validate)
            temporary = Path(tempfile.mkdtemp(prefix=".stage-", dir=self.root))
            for name, content in sorted(documents.items()):
                _write(temporary / (name + ".json"), content)
            _write(temporary / "manifest.json", _canonical(manifest))
            _sync_directory(temporary)
            os.rename(temporary, target)
            _sync_directory(objects)
        return self._load(ident, now=now, validate=validate)

    def load_current(self, *, now, validate):
        """Resolve the pointer once; never combine documents from two versions."""
        ident = self._pointer()
        return None if ident is None else self._load(ident, now=now, validate=validate)

    def load_current_historical(self, *, now, validate):
        """Prove one sealed historical context for planning or owned management.

        Validation uses its actual construction time, never a rewritten time.
        This does NOT assert present policy/grant validity or authorize entry.
        Callers must independently enforce current authority and audit lineage.
        """
        now = _utc(now)
        ident = self._pointer()
        if ident is None:
            return None
        path = self.root / "objects" / ident / "policy.json"
        if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
            raise ValueError("generation_symlink_rejected")
        if path.stat().st_size > _MAX_DOCUMENT:
            raise ValueError("generation_document_invalid")
        reviewed = _utc(_object(path.read_bytes())["reviewed_utc"])
        if reviewed > now:
            raise ValueError("generation_historical_clock_invalid")
        return self._load(ident, now=reviewed, validate=validate)

    def install(self, generation_id, *, expected_current, clock, observe_state, validate, authorize,
                before_replace=None):
        """Switch only after separate current authorization and fresh flat proof.

        This changes the storage pointer only. The returned complete snapshot is
        the sole adoption value; callers must not reload its files separately.
        Callback failures leave the previous pointer, owned manager and journal.
        A crash after replace may expose the new *complete* generation on restart.
        """
        if expected_current is not None and not _hex(expected_current):
            raise ValueError("generation_expected_pointer_invalid")
        if (not all(callable(callback) for callback in (clock, observe_state, validate, authorize))
                or (before_replace is not None and not callable(before_replace))):
            raise ValueError("generation_explicit_authorization_required")
        with self._writer():
            if self._pointer() != expected_current:
                raise ValueError("generation_current_changed")
            now = _utc(clock())
            snapshot = self._load(generation_id, now=now, validate=validate)
            self._fresh_for_install(snapshot, now)
            context = _object(snapshot.documents["context"])
            if context.get("parent_generation_id") != expected_current:
                raise ValueError("generation_parent_mismatch")
            if authorize(snapshot, now) is not True:
                raise ValueError("generation_explicit_authorization_required")
            observation = observe_state()
            now = _utc(clock())
            if (not isinstance(observation, FreshState) or not isinstance(observation.state, RenewalState)
                    or not observation.state.install_window()
                    or not timedelta(0) <= now - _utc(observation.observed_utc) <= timedelta(seconds=5)):
                raise ValueError("generation_fresh_flat_window_required")
            self._validate(snapshot, now=now, validate=validate)
            temporary = self.root / (".next-" + uuid.uuid4().hex)
            _write(temporary, _canonical({"schema": 1, "generation_id": generation_id}))
            # Validation, authorization and fsync may be slow. The original
            # observation cannot silently age into installation permission.
            final_now = _utc(clock())
            if not timedelta(0) <= final_now - _utc(observation.observed_utc) <= timedelta(seconds=5):
                raise ValueError("generation_fresh_flat_window_required")
            self._fresh_for_install(snapshot, final_now)
            grant = _object(snapshot.documents["grant"])
            policy = _object(snapshot.documents["policy"])
            valid, _ = validate_policy(policy, fingerprint=self.binding["account_fingerprint"],
                                       now=final_now, strategy="c22h4")
            if not valid or not _utc(grant["approved_utc"]) <= final_now < _utc(grant["expires_utc"]):
                raise ValueError("generation_authority_invalid")
            if before_replace is not None:
                # The coordinator durably records the exact transition after
                # our final evidence/flat checks. SQLite and the pointer file
                # cannot form one transaction; restart must reconcile intent.
                before_replace(snapshot, final_now, observation)
                final_now = _utc(clock())
                if not timedelta(0) <= final_now - _utc(observation.observed_utc) <= timedelta(seconds=5):
                    raise ValueError("generation_fresh_flat_window_required")
                self._fresh_for_install(snapshot, final_now)
                valid, _ = validate_policy(policy, fingerprint=self.binding["account_fingerprint"],
                                           now=final_now, strategy="c22h4")
                if not valid or not _utc(grant["approved_utc"]) <= final_now < _utc(grant["expires_utc"]):
                    raise ValueError("generation_authority_invalid")
            os.replace(temporary, self.root / "current.json")
            try:
                _sync_directory(self.root)
            except OSError as error:
                # Replace already committed a whole generation. Callers must
                # block entry and load/validate the pointer before adopting a
                # context, never assume every raised exception means old data.
                raise RuntimeError("generation_switch_durability_unknown") from error
            return snapshot
