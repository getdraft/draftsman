#!/usr/bin/env python3
"""Propose migrations of legacy relationships to the listener model (#368). Never edits catalog files.

Scans a workspace (or one object, SDP or folder) and proposes, for review:

- `flow: bidirectional` -> `flow: outbound` (a request/response is `direction: synchronous`).
- `flow: inbound` -> source and target swapped so the caller is the source; or, when the caller is an unknown
  outside party (free-text `externalTarget`), removal of the relationship with a note to record on the listener.
- free-text `externalTarget` -> `target` set to a `system` object (an existing one matched by exact name or alias,
  or a new stub) and `targetListener` set to a listener found or created by Listener Lookup Before Create
  (a stub when the endpoint is unknown); a needs-input item when no port can be determined.
- relationships whose text reads like a protection description, to move onto the listener.

Output is a Markdown report (default, stdout or --report) and, with --patch, a unified diff that `git apply`
applies after review. With --json the proposals are printed as JSON. Nothing in the workspace is written.

Usage:
    python3 .draft/framework/tools/migrate_relationships.py --workspace . [--object UID | --sdp UID | --folder PATH]
        [--report migration.md] [--patch migration.patch] [--json]
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import LISTENER_DEFAULT_PORTS, listener_identity  # noqa: E402

DEPRECATED_FLOWS = ("inbound", "bidirectional")
INTERNAL_CALLER_TYPES = ("product_component", "data_component")
LISTENER_PROTOCOLS = ("REST", "gRPC", "GraphQL", "WebSocket", "AMQP", "SMTP", "SQL", "Redis", "Kafka", "SQS", "SNS",
                      "S3", "DynamoDB", "HTTP", "HTTPS", "TCP", "UDP")
PROTECTION_WORDS = re.compile(
    r"\b(authenticated (at|by)|authori[sz]ed (at|by)|protected by|fronted by|behind (the |a |an )?\w+|at the edge|"
    r"waf|web application firewall|firewall|mtls|tls termination|terminates tls)\b",
    re.IGNORECASE,
)
SYSTEMS_FOLDER = Path("catalog") / "governance" / "systems"
LISTENERS_FOLDER = Path("catalog") / "engineering" / "listeners"
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


@dataclass
class Item:
    kind: str  # flow-bidirectional | flow-inbound-swap | inbound-external-remove | external-target | needs-input | protection
    uid: str
    name: str
    path: str
    summary: str
    details: list[str] = field(default_factory=list)


@dataclass
class Entry:
    path: Path  # absolute
    obj: dict[str, Any]
    single: bool  # the file holds exactly this one object as a mapping


def load_workspace(workspace: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Entry]]:
    """uid -> object, and uid -> where it was authored, for every catalog YAML file in the workspace."""
    objects: dict[str, dict[str, Any]] = {}
    entries: dict[str, Entry] = {}
    root = workspace / "catalog"
    files = sorted([*root.rglob("*.yaml"), *root.rglob("*.yml")]) if root.is_dir() else []
    for path in files:
        try:
            docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d is not None]
        except yaml.YAMLError:
            continue
        items: list[Any] = []
        for doc in docs:
            items.extend(doc if isinstance(doc, list) else [doc])
        single = len(docs) == 1 and isinstance(docs[0], dict)
        for obj in items:
            if isinstance(obj, dict) and isinstance(obj.get("uid"), str):
                objects[obj["uid"]] = obj
                entries[obj["uid"]] = Entry(path, obj, single)
    return objects, entries


def scoped_relationships(objects: dict[str, dict[str, Any]], entries: dict[str, Entry], workspace: Path,
                         obj_uid: str | None, sdp_uid: str | None, folder: str | None) -> list[str]:
    rels = sorted(uid for uid, o in objects.items() if o.get("type") == "relationship")
    if obj_uid:
        return [u for u in rels if obj_uid in (u, str(objects[u].get("source") or ""), str(objects[u].get("target") or ""))]
    if sdp_uid:
        sdp = objects.get(sdp_uid) or {}
        deployed = {sdp_uid}
        for group in sdp.get("serviceGroups") or []:
            for item in (group.get("deployableObjects") or []) if isinstance(group, dict) else []:
                if isinstance(item, dict) and item.get("ref"):
                    deployed.add(str(item["ref"]))
        return [u for u in rels if str(objects[u].get("source") or "") in deployed or str(objects[u].get("target") or "") in deployed]
    if folder:
        base = (workspace / folder).resolve()
        return [u for u in rels if base == entries[u].path.resolve() or base in entries[u].path.resolve().parents]
    return rels


def stable_uid(seed: str, taken: set[str]) -> str:
    """A UID derived from seed, so re-running the helper proposes the same objects; never one already taken."""
    counter = 0
    while True:
        digest = hashlib.sha256(f"{seed}#{counter}".encode()).digest()
        chars = "".join(_CROCKFORD[b % 32] for b in digest[:14])
        uid = f"{chars[:10]}-{chars[10:]}"
        if uid not in taken:
            taken.add(uid)
            return uid
        counter += 1


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unnamed"


def listener_protocol(technology: str) -> str:
    wanted = technology.strip().lower()
    for protocol in LISTENER_PROTOCOLS:
        if protocol.lower() == wanted:
            return protocol
    return ""


def resolve_system(objects: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    """An external party by exact name or alias among `system` objects. Several matches are returned, never guessed."""
    lowered = name.strip().lower()
    found = []
    for uid, obj in sorted(objects.items()):
        if obj.get("type") != "system":
            continue
        names = {str(obj.get("name") or "").strip().lower(), *(str(a).strip().lower() for a in obj.get("aliases") or [])}
        if lowered in names:
            found.append(uid)
    if len(found) == 1:
        return {"status": "linked", "uid": found[0]}
    return {"status": "ambiguous", "candidates": found} if found else {"status": "not_found"}


class Planner:
    def __init__(self, workspace: Path, objects: dict[str, dict[str, Any]], entries: dict[str, Entry]):
        self.workspace = workspace
        self.objects = dict(objects)
        self.entries = entries
        self.taken = set(objects)
        self.items: list[Item] = []
        self.edits: dict[Path, str | None] = {}  # absolute path -> new text (None deletes the file)
        self.new_files: dict[Path, str] = {}
        self.systems_by_name: dict[str, str] = {}  # externalTarget text (lower) -> system uid, once converted
        self.pending_systems: dict[str, tuple[Path, str]] = {}  # new system uid -> (file, text), until first used

    def rel_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.workspace.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def add(self, kind: str, rel: dict[str, Any], summary: str, *details: str) -> None:
        uid = str(rel.get("uid"))
        self.items.append(Item(kind, uid, str(rel.get("name") or uid), self.rel_path(self.entries[uid].path), summary, list(details)))

    def text_of(self, path: Path) -> str:
        if path in self.edits and self.edits[path] is not None:
            return self.edits[path]  # type: ignore[return-value]
        return path.read_text(encoding="utf-8")

    def plan(self, uids: list[str]) -> None:
        for uid in uids:
            rel = self.objects[uid]
            if rel.get("_derived"):
                continue
            self.protection(rel)
            flow = str(rel.get("flow") or "").strip().lower()
            external = str(rel.get("externalTarget") or "").strip()
            needs_change = flow in DEPRECATED_FLOWS or bool(external)
            if needs_change and not self.entries[uid].single:
                self.add("needs-input", rel, "edit by hand: the file holds several objects, so no patch is proposed",
                         f"flow: {flow or 'outbound'}" + (f", externalTarget: {external}" if external else ""))
                continue
            if flow == "inbound" and external and not str(rel.get("target") or "").strip():
                self.remove_inbound_external(rel, external)
                continue
            if flow == "bidirectional":
                self.set_line(rel, "flow", "outbound", "flow-bidirectional",
                              "flow bidirectional -> outbound (the response is direction synchronous)")
            elif flow == "inbound":
                self.swap(rel)
            if external:
                self.external_target(rel, external)

    # -- conversions -------------------------------------------------------------------------------------------
    def set_line(self, rel: dict[str, Any], key: str, value: str, kind: str, summary: str) -> bool:
        path = self.entries[str(rel["uid"])].path
        text = self.text_of(path)
        pattern = re.compile(rf"(?m)^{re.escape(key)}:[^\n]*$")
        if len(pattern.findall(text)) != 1:
            self.add("needs-input", rel, f"edit by hand: no single top-level `{key}:` line to change")
            return False
        self.edits[path] = pattern.sub(f"{key}: {value}", text)
        if kind:
            self.add(kind, rel, summary)
        return True

    def swap(self, rel: dict[str, Any]) -> None:
        uid = str(rel["uid"])
        path = self.entries[uid].path
        text = self.text_of(path)
        source, target = str(rel.get("source") or "").strip(), str(rel.get("target") or "").strip()
        lines = text.split("\n")
        src_idx = [i for i, line in enumerate(lines) if re.match(r"^source:", line)]
        tgt_idx = [i for i, line in enumerate(lines) if re.match(r"^target:", line)]
        if not source or not target or len(src_idx) != 1 or len(tgt_idx) != 1:
            self.add("needs-input", rel, "edit by hand: flow inbound needs source and target swapped, and they are not single lines")
            return
        lines[src_idx[0]], lines[tgt_idx[0]] = f"source: {target}", f"target: {source}"
        dropped = []
        for key in ("targetListener", "targetInterface"):
            idx = [i for i, line in enumerate(lines) if re.match(rf"^{key}:", line)]
            if idx:
                dropped.append(key)
                for i in reversed(idx):
                    del lines[i]
        text = "\n".join(lines)
        text = re.sub(r"(?m)^flow:[^\n]*$", "flow: outbound", text)
        self.edits[path] = text
        caller, callee = self.name(target), self.name(source)
        details = [f"caller {caller} becomes the source; {callee} becomes the target",
                   f"check that the label '{rel.get('label') or ''}' reads from the caller's side"]
        if dropped:
            details.append(f"dropped {', '.join(dropped)} (they named the old target)")
        self.add("flow-inbound-swap", rel, "flow inbound -> source and target swapped, flow outbound", *details)
        self.add("needs-input", rel, f"name the listener on {callee} this call lands on (targetListener), with Listener Lookup Before Create")

    def remove_inbound_external(self, rel: dict[str, Any], external: str) -> None:
        path = self.entries[str(rel["uid"])].path
        self.edits[path] = None
        listener_side = self.name(str(rel.get("source") or ""))
        label = str(rel.get("label") or "").strip()
        self.add("inbound-external-remove", rel, "inbound call from an unknown outside party -> remove the relationship",
                 f"record on {listener_side}'s listener instead (authenticationModel, or description): "
                 f"\"{label + ' ' if label else ''}{external}\"")

    def external_target(self, rel: dict[str, Any], external: str) -> None:
        uid = str(rel["uid"])
        system = self.systems_by_name.get(external.lower())
        details: list[str] = []
        if not system:
            found = resolve_system(self.objects, external)
            if found["status"] == "ambiguous":
                self.add("needs-input", rel, f"choose the system for externalTarget '{external}': several match",
                         *[f"{c} ({self.name(c)})" for c in found["candidates"]])
                return
            if found["status"] == "linked":
                system = found["uid"]
                details.append(f"external party: existing system {self.name(system)} ({system})")
            else:
                system = self.new_system(external)
                details.append(f"external party: new system stub '{external}' ({system})")
        else:
            details.append(f"external party: system {self.name(system)} ({system}), proposed above")
        named = str(rel.get("targetListener") or "").strip()
        listener = self.objects.get(named) if named else None
        if isinstance(listener, dict) and listener.get("type") == "listener":
            owner = (listener.get("owner") or {}).get("ref") if isinstance(listener.get("owner"), dict) else None
            if owner != system and isinstance(self.objects.get(str(owner)), dict) and self.objects[str(owner)].get("type") == "system" \
                    and system in self.pending_systems:
                self.pending_systems.pop(system)  # the listener already names its system: use that one, no new stub
                self.objects.pop(system, None)
                system = str(owner)
                details[-1] = f"external party: system {self.name(system)} ({system}), the owner of its targetListener"
            elif owner != system:
                self.add("needs-input", rel, f"targetListener {named} is owned by '{owner}', not by the system for '{external}'")
                self.drop_pending(system)
                return
            listener_uid = named
            details.append(f"listener: keeps targetListener {named}")
        else:
            listener_uid = self.find_or_stub_listener(rel, system, details)
            if not listener_uid:
                self.drop_pending(system)
                return
        path = self.entries[uid].path
        text = self.text_of(path)
        lines = text.split("\n")
        ext_idx = [i for i, line in enumerate(lines) if re.match(r"^externalTarget:", line)]
        if len(ext_idx) != 1 or any(re.match(r"^target:", line) for line in lines):
            self.add("needs-input", rel, "edit by hand: no single top-level externalTarget line to replace")
            self.drop_pending(system)
            return
        new = [f"target: {system}"]
        if not any(re.match(r"^targetListener:", line) for line in lines):
            new.append(f"targetListener: {listener_uid}")
        lines[ext_idx[0]:ext_idx[0] + 1] = new
        self.edits[path] = "\n".join(lines)
        if system in self.pending_systems:  # first successful use: the new system stub is proposed
            path_, text_ = self.pending_systems.pop(system)
            self.new_files[path_] = text_
        self.systems_by_name[external.lower()] = system
        self.add("external-target", rel, f"externalTarget '{external}' -> target {system}, targetListener {listener_uid}", *details)

    def find_or_stub_listener(self, rel: dict[str, Any], system: str, details: list[str]) -> str:
        technology = str(rel.get("technology") or "").strip()
        protocol = listener_protocol(technology)
        port = LISTENER_DEFAULT_PORTS.get(protocol.lower()) if protocol else None
        if not protocol or port is None:
            self.add("needs-input", rel, f"give the protocol and port of the listener on '{self.name(system)}' this call lands on",
                     f"technology '{technology or 'not recorded'}' does not give a listener protocol with a default port; "
                     "the relationship keeps its externalTarget until then")
            return ""
        key = ("external_system", system, protocol.lower(), port, "/")
        for uid, obj in sorted(self.objects.items()):
            if listener_identity(obj) == key:
                details.append(f"listener: existing {uid} ({protocol} {port} /)")
                return uid
        source = self.objects.get(str(rel.get("source") or ""), {})
        if source.get("type") not in INTERNAL_CALLER_TYPES:
            self.add("needs-input", rel, f"a vendor stub listener on '{self.name(system)}' needs a company-internal caller",
                     f"the source is a {source.get('type') or 'missing object'}, not a product or data component; "
                     "record the call from the component that makes it, or author the listener in full")
            return ""
        uid = stable_uid(f"listener:{system}:{protocol}:{port}", self.taken)
        listener = {
            "schemaVersion": "1.0", "uid": uid, "type": "listener", "name": f"{self.name(system)} {protocol} {port} stub",
            "owner": {"kind": "external_system", "ref": system}, "protocol": protocol, "port": port, "endpoint": "/",
            "authenticationModel": "TBD", "catalogStatus": "stub",
        }
        self.objects[uid] = listener
        self.new_files[self.workspace / LISTENERS_FOLDER / f"listener-{slug(self.name(system))}-{slug(protocol)}-{port}.yaml"] = (
            yaml.safe_dump(listener, sort_keys=False, allow_unicode=True))
        details.append(f"listener: new stub {uid} ({protocol} {port} /; endpoint and authenticationModel to confirm)")
        return uid

    def new_system(self, name: str) -> str:
        """A new system stub for an external party. It is proposed only once a relationship is converted to it."""
        uid = stable_uid(f"system:{name.lower()}", self.taken)
        system = {"schemaVersion": "1.0", "uid": uid, "type": "system", "name": name,
                  "description": f"External party proposed by migrate_relationships.py from externalTarget '{name}'. Confirm lifecycleStatus.",
                  "catalogStatus": "stub", "lifecycleStatus": "candidate"}
        self.objects[uid] = system
        self.pending_systems[uid] = (self.workspace / SYSTEMS_FOLDER / f"system-{slug(name)}.yaml",
                                     yaml.safe_dump(system, sort_keys=False, allow_unicode=True))
        return uid

    def drop_pending(self, system: str) -> None:
        if system in self.pending_systems:
            self.pending_systems.pop(system)
            self.objects.pop(system, None)
            self.taken.discard(system)

    def protection(self, rel: dict[str, Any]) -> None:
        text = " ".join(str(rel.get(k) or "") for k in ("name", "label", "description", "notes") if not isinstance(rel.get(k), dict))
        match = PROTECTION_WORDS.search(text)
        if match:
            self.add("protection", rel, f"reads like a protection description ('{match.group(0)}'): move it onto the "
                     "listener's authenticationModel or description")

    def name(self, uid: str) -> str:
        obj = self.objects.get(uid) or {}
        return str(obj.get("name") or uid)

    # -- output ------------------------------------------------------------------------------------------------
    def patch(self) -> str:
        chunks: list[str] = []
        for path in sorted(self.edits):
            rel = self.rel_path(path)
            old = path.read_text(encoding="utf-8")
            new = self.edits[path]
            if new is None:
                chunks.append(f"diff --git a/{rel} b/{rel}\ndeleted file mode 100644\n")
                chunks.extend(difflib.unified_diff(old.splitlines(True), [], f"a/{rel}", "/dev/null"))
            elif new != old:
                chunks.append(f"diff --git a/{rel} b/{rel}\n")
                chunks.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}"))
        for path in sorted(self.new_files):
            rel = self.rel_path(path)
            chunks.append(f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n")
            chunks.extend(difflib.unified_diff([], self.new_files[path].splitlines(True), "/dev/null", f"b/{rel}"))
        return "".join(chunks)

    def report(self) -> str:
        titles = [
            ("flow-bidirectional", "flow bidirectional -> outbound"),
            ("flow-inbound-swap", "flow inbound -> caller as source"),
            ("inbound-external-remove", "Inbound calls from unknown outside parties (remove; note on the listener)"),
            ("external-target", "externalTarget -> system and listener"),
            ("needs-input", "Needs your input"),
            ("protection", "Reads like a protection description"),
        ]
        out = ["# Relationship migration proposals (#368)", "",
               "Review every item. Nothing has been changed: apply the patch with `git apply <file>` on a branch, "
               "then run `validate.py`.", ""]
        for kind, title in titles:
            items = [i for i in self.items if i.kind == kind]
            if not items:
                continue
            out += [f"## {title} ({len(items)})", ""]
            for item in items:
                out.append(f"- `{item.uid}` {item.name} ({item.path}): {item.summary}")
                out += [f"  - {d}" for d in item.details]
            out.append("")
        if self.new_files:
            out += [f"## New objects ({len(self.new_files)})", ""]
            out += [f"- {self.rel_path(p)}" for p in sorted(self.new_files)]
            out.append("")
        if not self.items:
            out += ["No legacy relationships found in scope.", ""]
        return "\n".join(out)

    def as_json(self) -> dict[str, Any]:
        return {"items": [item.__dict__ for item in self.items],
                "changedFiles": [self.rel_path(p) for p in sorted(self.edits) if self.edits[p] is not None],
                "deletedFiles": [self.rel_path(p) for p in sorted(self.edits) if self.edits[p] is None],
                "newFiles": [self.rel_path(p) for p in sorted(self.new_files)]}


def propose(workspace: Path, obj_uid: str | None = None, sdp_uid: str | None = None, folder: str | None = None) -> Planner:
    objects, entries = load_workspace(workspace)
    planner = Planner(workspace, objects, entries)
    planner.plan(scoped_relationships(objects, entries, workspace, obj_uid, sdp_uid, folder))
    return planner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path("."))
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--object", dest="obj", help="only relationships of this uid, or whose source or target it is")
    scope.add_argument("--sdp", help="only relationships touching objects deployed in this software deployment pattern")
    scope.add_argument("--folder", help="only relationships in files under this folder (relative to the workspace)")
    parser.add_argument("--report", type=Path, help="write the Markdown report here instead of stdout")
    parser.add_argument("--patch", type=Path, help="write a unified diff of the proposals here (apply with git apply)")
    parser.add_argument("--json", action="store_true", help="print the proposals as JSON instead of Markdown")
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    for out in (args.report, args.patch):
        if out is not None:
            target = out.resolve()
            if (workspace / "catalog") in target.parents:
                parser.error(f"{out} is inside the catalog; write proposals outside catalog/")
    planner = propose(workspace, args.obj, args.sdp, args.folder)
    text = json.dumps(planner.as_json(), indent=2) if args.json else planner.report()
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if args.patch:
        args.patch.write_text(planner.patch(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
