from __future__ import annotations

import secrets
import time
from typing import Iterable


CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
UID_PATTERN_TEXT = r"^[0-9A-HJKMNP-TV-Z]{10}-[0-9A-HJKMNP-TV-Z]{4}$"


def encode_base32(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(CROCKFORD_BASE32[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def generate_uid(existing: Iterable[str] | None = None) -> str:
    existing_uids = set(existing or [])
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    prefix = encode_base32(timestamp_ms, 10)
    while True:
        random_part = "".join(secrets.choice(CROCKFORD_BASE32) for _ in range(4))
        uid = f"{prefix}-{random_part}"
        if uid not in existing_uids:
            return uid


def generate_relationship_uid(source: str, target: str, suffix: str = "") -> str:
    import hashlib
    # Hash the source, target, and optional suffix to make it deterministic
    key = f"{source}:{target}"
    if suffix:
        key += f":{suffix}"
    hasher = hashlib.sha256(key.encode("utf-8"))
    digest = hasher.digest()
    
    # 14 Crockford base32 characters = 70 bits. Take first 9 bytes (72 bits)
    val = int.from_bytes(digest[:9], byteorder="big")
    
    # Encode first 10 characters (50 bits) for prefix
    prefix_val = val >> 20
    prefix = encode_base32(prefix_val, 10)
    
    # Encode last 4 characters (20 bits) for suffix
    suffix_val = val & ((1 << 20) - 1)
    suffix = encode_base32(suffix_val, 4)
    
    return f"{prefix}-{suffix}"


def derive_inline_relationships(catalog: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Scans a catalog dictionary (mapping UID -> object) and yields dynamically
    generated relationship objects for dependencies (runtimeSpec.dependencies, runsOn, host).
    Returns a dictionary of the derived relationship objects.
    """
    from typing import Any
    derived: dict[str, dict[str, Any]] = {}
    
    # Collect existing hand-authored relationships (source, target) to avoid duplicates
    existing_relationships = set()
    for obj in catalog.values():
        if isinstance(obj, dict) and obj.get("type") == "relationship" and not obj.get("_derived"):
            src = obj.get("source")
            tgt = obj.get("target")
            if isinstance(src, str) and isinstance(tgt, str):
                existing_relationships.add((src.strip(), tgt.strip()))

    for obj_uid, obj in list(catalog.items()):
        if not isinstance(obj, dict):
            continue
        
        # 1. ProductComponent
        if obj.get("type") == "product_component":
            # runsOn field
            runs_on = obj.get("runsOn")
            if isinstance(runs_on, str) and runs_on.strip():
                target_uid = runs_on.strip()
                source_uid = str(obj_uid)
                if (source_uid.strip(), target_uid.strip()) not in existing_relationships:
                    rel_uid = generate_relationship_uid(source_uid, target_uid, suffix="runsOn")
                    source_name = obj.get("name") or source_uid
                    target_name = catalog[target_uid].get("name") if target_uid in catalog else target_uid
                    rel_obj = {
                        "schemaVersion": "1.0",
                        "uid": rel_uid,
                        "type": "relationship",
                        "name": f"{source_name} → {target_name}",
                        "source": source_uid,
                        "target": target_uid,
                        "label": "runs on",
                        "notes": "Derived from runsOn field",
                        "catalogStatus": "complete",
                        "_source": f"derived from {obj.get('_source', 'product_component')} [runsOn]",
                        "_derived": True
                    }
                    derived[rel_uid] = rel_obj
                    existing_relationships.add((source_uid.strip(), target_uid.strip()))
            
            # runtimeSpec dependencies
            runtime_spec = obj.get("runtimeSpec")
            if isinstance(runtime_spec, dict):
                dependencies = runtime_spec.get("dependencies")
                if isinstance(dependencies, list):
                    for idx, dep in enumerate(dependencies):
                        if not isinstance(dep, dict) or not dep.get("ref"):
                            continue
                        target_uid = str(dep["ref"])
                        source_uid = str(obj_uid)
                        
                        if (source_uid.strip(), target_uid.strip()) not in existing_relationships:
                            # Generate deterministic UID for the relationship (no suffix for backwards compatibility/tests)
                            rel_uid = generate_relationship_uid(source_uid, target_uid)
                            
                            # Resolve human-readable names if available in catalog
                            source_name = obj.get("name") or source_uid
                            target_name = catalog[target_uid].get("name") if target_uid in catalog else target_uid
                            
                            # Build the virtual relationship object
                            rel_obj = {
                                "schemaVersion": "1.0",
                                "uid": rel_uid,
                                "type": "relationship",
                                "name": f"{source_name} → {target_name}",
                                "source": source_uid,
                                "target": target_uid,
                                "label": dep.get("interface") or dep.get("purpose") or "depends on",
                                "notes": dep.get("notes") or dep.get("purpose") or "",
                                "catalogStatus": "complete",
                                "_source": f"derived from {obj.get('_source', 'product_component')} [inline dependency]",
                                "_derived": True
                            }
                            derived[rel_uid] = rel_obj
                            existing_relationships.add((source_uid.strip(), target_uid.strip()))

        # 2. DataComponent
        elif obj.get("type") == "data_component":
            runs_on = obj.get("runsOn")
            if isinstance(runs_on, str) and runs_on.strip():
                target_uid = runs_on.strip()
                source_uid = str(obj_uid)
                if (source_uid.strip(), target_uid.strip()) not in existing_relationships:
                    rel_uid = generate_relationship_uid(source_uid, target_uid, suffix="runsOn")
                    source_name = obj.get("name") or source_uid
                    target_name = catalog[target_uid].get("name") if target_uid in catalog else target_uid
                    rel_obj = {
                        "schemaVersion": "1.0",
                        "uid": rel_uid,
                        "type": "relationship",
                        "name": f"{source_name} → {target_name}",
                        "source": source_uid,
                        "target": target_uid,
                        "label": "runs on",
                        "notes": "Derived from runsOn field",
                        "catalogStatus": "complete",
                        "_source": f"derived from {obj.get('_source', 'data_component')} [runsOn]",
                        "_derived": True
                    }
                    derived[rel_uid] = rel_obj
                    existing_relationships.add((source_uid.strip(), target_uid.strip()))

        # 3. Self-Managed Services (host field)
        elif obj.get("type") in ("ai_gateway", "data_store_service", "network_service", "runtime_service"):
            host = obj.get("host")
            if isinstance(host, str) and host.strip():
                target_uid = host.strip()
                source_uid = str(obj_uid)
                if (source_uid.strip(), target_uid.strip()) not in existing_relationships:
                    rel_uid = generate_relationship_uid(source_uid, target_uid, suffix="host")
                    source_name = obj.get("name") or source_uid
                    target_name = catalog[target_uid].get("name") if target_uid in catalog else target_uid
                    rel_obj = {
                        "schemaVersion": "1.0",
                        "uid": rel_uid,
                        "type": "relationship",
                        "name": f"{source_name} → {target_name}",
                        "source": source_uid,
                        "target": target_uid,
                        "label": "runs on",
                        "notes": "Derived from host field",
                        "catalogStatus": "complete",
                        "_source": f"derived from {obj.get('_source', obj.get('type'))} [host]",
                        "_derived": True
                    }
                    derived[rel_uid] = rel_obj
                    existing_relationships.add((source_uid.strip(), target_uid.strip()))
    return derived

