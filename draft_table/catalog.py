from __future__ import annotations

import re
import secrets
import time
from pathlib import Path
from typing import Any

import yaml

from .paths import REPO_ROOT, resolve_framework_root, workspace_framework_root


CATALOG_FOLDERS = (
    "technology-components",
    "network-services",
    "hosts",
    "runtime-services",
    "data-at-rest-services",
    "product-services",
    "decision-records",
    "capabilities",
    "requirement-groups",
    "domains",
    "object-patches",
    "reference-architectures",
    "software-deployment-patterns",
    "sessions",
    # Nested catalog folders by content role
    "engineering/product-components",
    "engineering/data-components",
    "engineering/software-deployment-patterns",
    "shared-services/hosts",
    "shared-services/runtime-services",
    "shared-services/data-store-services",
    "shared-services/network-services",
    "shared-services/technology-components",
    "governance/decision-records",
    "governance/sessions",
    "governance/relationships",
    "governance/systems",
    "governance/reference-architectures",
)

REFERENCE_KEYS = {
    "ref",
    "runsOn",
    "followsReferenceArchitecture",
    "host",
    "primaryTechnologyComponent",
    "operatingSystemComponent",
    "computePlatformComponent",
    "inherits",
    "platformDependency",
    "linkedObject",
    "primaryObjectUid",
    "riskRef",
    "domain",
    "relatedCapability",
    "requirementGroup",
    "target",
}

UID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{10}-[0-9A-HJKMNP-TV-Z]{4}$")


def load_effective_catalog(workspace: Path | None, framework_repo: Path = REPO_ROOT) -> dict[str, dict[str, Any]]:
    framework_root = selected_framework_root(workspace, framework_repo)
    objects: dict[str, dict[str, Any]] = {}
    roots = [framework_root / "configurations"]
    if workspace and workspace.exists():
        provider_root = workspace / ".draft" / "providers"
        if provider_root.exists():
            roots.extend(
                provider_config
                for provider_config in sorted(provider_root.glob("*/configurations"))
                if provider_config.exists()
            )
        workspace_config = workspace / "configurations"
        workspace_catalog = workspace / "catalog"
        if workspace_config.exists():
            roots.append(workspace_config)
        if workspace_catalog.exists():
            roots.append(workspace_catalog)
        elif workspace.name == "catalog":
            roots.append(workspace)
    else:
        examples_catalog = framework_root / "examples" / "catalog"
        if not examples_catalog.exists():
            examples_catalog = framework_root.parent / "examples" / "catalog"
        roots.append(examples_catalog)

    for root in roots:
        for path in discover_yaml_files(root):
            data = read_yaml(path)
            object_id = data.get("uid") or data.get("id")
            if object_id:
                data["_source"] = display_path(path, framework_root)
                objects[str(object_id)] = data
    return apply_object_patches(objects)


def selected_framework_root(workspace: Path | None, framework_repo: Path = REPO_ROOT) -> Path:
    if workspace:
        vendored = workspace_framework_root(workspace)
        if (vendored / "configurations").exists():
            return vendored.resolve()
    return resolve_framework_root(framework_repo)


def discover_yaml_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    for folder in CATALOG_FOLDERS:
        folder_path = root / folder
        if folder_path.exists():
            files.extend(sorted(folder_path.rglob("*.yaml")))
    if root.name in {"catalog", "configurations"}:
        files.extend(path for path in sorted(root.glob("*.yaml")) if path.is_file())
    return sorted(set(files))


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def display_path(path: Path, framework_root: Path) -> str:
    for root in (framework_root, framework_root.parent, Path.cwd()):
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def apply_object_patches(objects: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    patched = dict(objects)
    for obj in objects.values():
        if obj.get("type") != "object_patch":
            continue
        target = str(obj.get("target") or "")
        patch = obj.get("patch")
        if target in patched and isinstance(patch, dict):
            patched[target] = deep_merge(patched[target], patch)
    return patched


def deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = dict(base)
        for key, value in patch.items():
            if key in {"uid", "id", "type"}:
                continue
            merged[key] = deep_merge(merged.get(key), value)
        return merged
    return patch


def build_reference_index(objects: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    referenced_by: dict[str, list[dict[str, str]]] = {}
    known_uids = set(objects)
    for object_id, obj in objects.items():
        for target, ref_path in extract_refs(obj, known_uids):
            referenced_by.setdefault(target, []).append({"source": object_id, "path": ref_path})
    return referenced_by


def is_probable_reference_key(path: str) -> bool:
    key = path.rsplit(".", 1)[-1]
    return key in REFERENCE_KEYS or key.endswith("Refs")


def is_object_ref(value: Any, path: str, known_uids: set[str] | None) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if known_uids and value in known_uids:
        return True
    return is_probable_reference_key(path) and bool(UID_PATTERN.match(value))


def extract_refs(node: Any, known_uids: set[str] | None = None, path: str = "") -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else key
            if key in REFERENCE_KEYS and is_object_ref(value, child_path, known_uids):
                refs.append((value, child_path))
            elif key.endswith("Refs") and isinstance(value, list):
                for index, item in enumerate(value):
                    if is_object_ref(item, f"{child_path}[{index}]", known_uids):
                        refs.append((item, f"{child_path}[{index}]"))
            else:
                refs.extend(extract_refs(value, known_uids, child_path))
    elif isinstance(node, list):
        if path.endswith(".appliesTo"):
            return refs
        for index, item in enumerate(node):
            item_path = f"{path}[{index}]"
            if is_object_ref(item, item_path, known_uids):
                refs.append((item, f"{path}[{index}]"))
            else:
                refs.extend(extract_refs(item, known_uids, item_path))
    return refs


def search_objects(objects: dict[str, dict[str, Any]], query: str, limit: int = 8) -> list[dict[str, Any]]:
    tokens = tokenize(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for obj in objects.values():
        haystack = " ".join(
            str(value)
            for value in (
                obj.get("id", ""),
                obj.get("uid", ""),
                obj.get("name", ""),
                " ".join(str(alias) for alias in obj.get("aliases", []) if isinstance(obj.get("aliases"), list)),
                obj.get("type", ""),
                obj.get("description", ""),
                " ".join(str(tag) for tag in obj.get("tags", []) if isinstance(obj.get("tags"), list)),
            )
        ).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score:
            scored.append((score, obj))
    return [obj for _score, obj in sorted(scored, key=lambda item: (-item[0], item[1].get("name", "")))[:limit]]


def tokenize(text: str) -> list[str]:
    return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if len(token) > 2]


def object_summary(obj: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(obj.get("uid") or obj.get("id") or ""),
        "uid": str(obj.get("uid") or obj.get("id") or ""),
        "name": str(obj.get("name") or obj.get("uid") or obj.get("id") or ""),
        "type": str(obj.get("type", "")),
        "status": str(obj.get("catalogStatus", "")),
        "source": str(obj.get("_source", "")),
        "description": str(obj.get("description", "")).strip(),
    }


LISTENER_DEFAULT_PORTS = {"http": 80, "https": 443}
LISTENER_EXTERNAL_OWNER = "external_system"
LISTENER_INTERNAL_OWNER_TYPES = ("product_component", "data_component")
VENDOR_STUB_REASON = (
    "A vendor-owned stub listener needs a company-internal relationship owner "
    "(a product or data component that calls it)."
)
_LISTENER_PATH_PARAM = re.compile(r"\{[^{}/]+\}|:[A-Za-z_][A-Za-z0-9_]*(?=/|$)")
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def normalize_listener_endpoint(endpoint: Any) -> str:
    """Path only: no scheme, host, query or fragment; templated parameters become {}."""
    text = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://[^/]*", "", str(endpoint or "").strip())
    text = text.split("?", 1)[0].split("#", 1)[0]
    if not text.startswith("/"):
        text = "/" + text
    return _LISTENER_PATH_PARAM.sub("{}", text).rstrip("/") or "/"


def listener_identity_key(listener: dict[str, Any]) -> tuple[str, str, str, int | None, str]:
    """Exact identity: owner kind + owner ref + protocol + port (default when omitted) + normalized endpoint."""
    owner = listener.get("owner") if isinstance(listener.get("owner"), dict) else {}
    protocol = str(listener.get("protocol") or "").strip().lower()
    port = listener.get("port")
    if port in (None, ""):
        port = LISTENER_DEFAULT_PORTS.get(protocol)
    try:
        port_number = int(port) if port not in (None, "") else None
    except (TypeError, ValueError):
        port_number = None
    return (
        str(owner.get("kind") or ""),
        str(owner.get("ref") or "").strip(),
        protocol,
        port_number,
        normalize_listener_endpoint(listener.get("endpoint")),
    )


def _names_of(obj: dict[str, Any]) -> set[str]:
    aliases = obj.get("aliases") if isinstance(obj.get("aliases"), list) else []
    values = [obj.get("name", ""), *aliases]
    return {str(value).strip().lower() for value in values if str(value).strip()}


# owner.kind -> the catalog object types it names. An external_system owner is a `system` object (validate.py
# OWNER_KIND_TYPES); the literal kind is accepted too for callers that pass bare owner records.
LISTENER_OWNER_OBJECT_TYPES = {LISTENER_EXTERNAL_OWNER: ("system", LISTENER_EXTERNAL_OWNER)}


def resolve_listener_owner(objects: dict[str, dict[str, Any]], owner_kind: str, owner_ref: str) -> dict[str, Any]:
    """Resolve an owner by uid, or by exact name or alias. Several name matches are returned, never guessed."""
    wanted = str(owner_ref or "").strip()
    lowered = wanted.lower()
    types = LISTENER_OWNER_OBJECT_TYPES.get(owner_kind, (owner_kind,))
    candidates: list[dict[str, str]] = []
    for key, obj in objects.items():
        if obj.get("type") not in types:
            continue
        uid = str(obj.get("uid") or key)
        if uid == wanted:
            return {"status": "linked", "uid": uid}
        if lowered and lowered in _names_of(obj):
            candidates.append({"uid": uid, "name": str(obj.get("name") or uid)})
    if len(candidates) == 1:
        return {"status": "linked", "uid": candidates[0]["uid"]}
    if candidates:
        return {"status": "ambiguous", "candidates": candidates}
    return {"status": "owner_not_found"}


def lookup_listener(
    objects: dict[str, dict[str, Any]],
    owner_kind: str,
    owner_ref: str,
    protocol: Any,
    port: Any,
    endpoint: Any,
) -> dict[str, Any]:
    owner = resolve_listener_owner(objects, owner_kind, owner_ref)
    if owner["status"] != "linked":
        return owner
    owner_uid = owner["uid"]
    key = listener_identity_key(
        {"owner": {"kind": owner_kind, "ref": owner_uid}, "protocol": protocol, "port": port, "endpoint": endpoint}
    )
    matches = [
        str(obj.get("uid") or uid)
        for uid, obj in objects.items()
        if obj.get("type") == "listener" and listener_identity_key(obj) == key
    ]
    if not matches:
        return {"status": "not_found", "ownerUid": owner_uid}
    if len(matches) > 1:
        return {"status": "ambiguous", "candidates": [{"uid": match} for match in matches]}
    return {"status": "linked", "uid": matches[0], "ownerUid": owner_uid}


_VERSION_SEGMENT = re.compile(r"^(v\d+(\.\d+)*|\d{4}-\d{2}(-\d{2})?)$", re.IGNORECASE)


def _unversioned_segments(endpoint: Any) -> tuple[str, ...]:
    return tuple(part for part in normalize_listener_endpoint(endpoint).split("/") if part and not _VERSION_SEGMENT.match(part))


def listener_near_match(key: tuple[str, str, str, int | None, str], other: tuple[str, str, str, int | None, str]) -> list[str]:
    """How two listener identity keys nearly match, or [] when they do not (or match exactly).

    A near match has the same owner and protocol, and differs only by an API version segment in the path
    (``/v1/orders`` and ``/v2/orders``), by a path one of them extends (``/`` and ``/orders``, same port), or by
    the port (same path). It is a question for the user, never a link.
    """
    if key == other or key[:3] != other[:3] or not key[1]:
        return []
    base, other_base = _unversioned_segments(key[4]), _unversioned_segments(other[4])
    same_port = key[3] == other[3]
    differs: list[str] = []
    if base == other_base:
        if key[4] != other[4]:
            differs.append("version")
        if not same_port:
            differs.append("port")
    elif same_port and (base[: len(other_base)] == other_base or other_base[: len(base)] == base):
        differs.append("path")
    return differs


def near_match_listeners(
    objects: dict[str, dict[str, Any]],
    owner_kind: str,
    owner_ref: str,
    protocol: Any,
    port: Any,
    endpoint: Any,
) -> list[dict[str, Any]]:
    """Listeners that look like the one described but do not match it exactly. Ask the user about each."""
    owner = resolve_listener_owner(objects, owner_kind, owner_ref)
    if owner["status"] != "linked":
        return []
    key = listener_identity_key({"owner": {"kind": owner_kind, "ref": owner["uid"]}, "protocol": protocol, "port": port, "endpoint": endpoint})
    found = []
    for uid, obj in objects.items():
        if obj.get("type") != "listener":
            continue
        other = listener_identity_key(obj)
        differs = listener_near_match(key, other)
        if differs:
            found.append({"uid": str(obj.get("uid") or uid), "name": str(obj.get("name") or uid), "protocol": other[2],
                          "port": other[3], "endpoint": other[4], "differs": differs})
    return sorted(found, key=lambda item: item["uid"])


def new_listener_uid(existing: Any) -> str:
    taken = set(existing)
    stamp = int(time.time() * 1000) & ((1 << 48) - 1)
    chars = []
    for _ in range(10):
        chars.append(_CROCKFORD[stamp & 31])
        stamp >>= 5
    prefix = "".join(reversed(chars))
    while True:
        uid = f"{prefix}-" + "".join(secrets.choice(_CROCKFORD) for _ in range(4))
        if uid not in taken:
            return uid


def create_listener_stub(
    objects: dict[str, dict[str, Any]],
    owner_uid: str,
    owner_kind: str,
    protocol: Any,
    port: Any,
    endpoint: Any,
    name: str = "",
) -> dict[str, Any]:
    proto = str(protocol or "").strip()
    number = port if port not in (None, "") else LISTENER_DEFAULT_PORTS.get(proto.lower())
    if number is None:
        raise ValueError("A listener needs a port, or a protocol with a default port.")
    path = normalize_listener_endpoint(endpoint)
    return {
        "schemaVersion": "1.0",
        "uid": new_listener_uid(objects),
        "type": "listener",
        "name": name or f"{proto} {path} stub",
        "owner": {"kind": owner_kind, "ref": owner_uid},
        "protocol": proto,
        "port": int(number),
        "endpoint": path,
        "authenticationModel": "TBD",
        "catalogStatus": "stub",
    }


def _is_internal_source(objects: dict[str, dict[str, Any]], uid: str | None) -> bool:
    return bool(uid) and str(objects.get(str(uid), {}).get("type") or "") in LISTENER_INTERNAL_OWNER_TYPES


def link_or_stub_listener(
    objects: dict[str, dict[str, Any]],
    owner_kind: str,
    owner_ref: str,
    protocol: Any,
    port: Any,
    endpoint: Any,
    *,
    name: str = "",
    source_uid: str | None = None,
    confirmed_new: bool = False,
) -> dict[str, Any]:
    """Lookup-before-create: link an existing listener, or create one stub. Never guesses an owner.

    When no listener matches exactly but some nearly match, the result is ``near_match`` with those candidates:
    ask whether one of them is the same listener. Pass ``confirmed_new=True`` once the user says it is not.
    """
    found = lookup_listener(objects, owner_kind, owner_ref, protocol, port, endpoint)
    status = found["status"]
    if status == "linked":
        return {"action": "linked", "uid": found["uid"]}
    if status != "not_found":
        return {"action": status, "candidates": found.get("candidates", [])}
    if not confirmed_new:
        near = near_match_listeners(objects, owner_kind, found["ownerUid"], protocol, port, endpoint)
        if near:
            return {"action": "near_match", "candidates": near}
    if owner_kind == LISTENER_EXTERNAL_OWNER and not _is_internal_source(objects, source_uid):
        return {"action": "rejected", "reason": VENDOR_STUB_REASON}
    stub = create_listener_stub(objects, found["ownerUid"], owner_kind, protocol, port, endpoint, name)
    return {"action": "created", "uid": stub["uid"], "stub": stub}


def upgrade_listener_stub(stub: dict[str, Any], authored: dict[str, Any]) -> dict[str, Any]:
    if stub.get("catalogStatus") != "stub":
        raise ValueError("Only a stub listener can be upgraded.")
    upgraded = {**stub, **{key: value for key, value in authored.items() if key not in ("uid", "type")}}
    upgraded["uid"] = stub["uid"]
    upgraded["type"] = "listener"
    if "catalogStatus" not in authored:
        upgraded["catalogStatus"] = "incomplete"
    if "authenticationModel" not in authored and upgraded.get("authenticationModel") == "TBD":
        upgraded.pop("authenticationModel")
    return upgraded


def record_authored_listener(
    objects: dict[str, dict[str, Any]], authored: dict[str, Any], *, confirmed_new: bool = False
) -> dict[str, Any]:
    """An authored listener links to an existing one, upgrades a matching stub, or is created. Never duplicates a UID.

    A new listener that nearly matches existing ones returns ``near_match`` until ``confirmed_new=True``.
    """
    owner = authored.get("owner") if isinstance(authored.get("owner"), dict) else {}
    kind = str(owner.get("kind") or "")
    found = lookup_listener(objects, kind, str(owner.get("ref") or ""), authored.get("protocol"), authored.get("port"), authored.get("endpoint"))
    if found["status"] not in ("linked", "not_found"):
        return {"action": found["status"], "candidates": found.get("candidates", [])}
    if found["status"] == "not_found" and not confirmed_new:
        near = near_match_listeners(objects, kind, found["ownerUid"], authored.get("protocol"), authored.get("port"), authored.get("endpoint"))
        if near:
            return {"action": "near_match", "candidates": near}
    owner_ref = {"kind": kind, "ref": found["ownerUid"]}
    normalized = {**authored, "owner": owner_ref, "endpoint": normalize_listener_endpoint(authored.get("endpoint"))}
    if found["status"] == "not_found":
        listener = {**normalized, "uid": new_listener_uid(objects), "type": "listener"}
        problem = vendor_stub_problem(objects, listener)
        if problem:
            return {"action": "rejected", "reason": problem}
        return {"action": "created", "uid": listener["uid"], "listener": listener}
    existing = objects[found["uid"]]
    if existing.get("catalogStatus") != "stub":
        return {"action": "linked", "uid": found["uid"], "listener": existing}
    merged = upgrade_listener_stub(existing, normalized)
    problem = vendor_stub_problem(objects, merged)
    if problem:
        return {"action": "rejected", "reason": problem}
    return {"action": "upgraded", "uid": found["uid"], "listener": merged}


def vendor_stub_problem(objects: dict[str, dict[str, Any]], listener: dict[str, Any]) -> str | None:
    """A vendor-owned stub may stay a stub only while a company-internal object's relationship targets it."""
    owner = listener.get("owner") if isinstance(listener.get("owner"), dict) else {}
    if listener.get("catalogStatus") != "stub" or owner.get("kind") != LISTENER_EXTERNAL_OWNER:
        return None
    uid = str(listener.get("uid") or "")
    for obj in objects.values():
        if (
            obj.get("type") == "relationship"
            and obj.get("targetListener") == uid
            and _is_internal_source(objects, str(obj.get("source") or ""))
        ):
            return None
    return VENDOR_STUB_REASON
