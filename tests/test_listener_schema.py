from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "framework" / "schemas" / "listener.schema.yaml"

SCHEMA = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
UID_RE = re.compile(SCHEMA["uidPattern"].lstrip("^").rstrip("$"))
OWNER_SCHEMA = SCHEMA["listenerOwner"]

VALID_UID = "01KS7ZZ1C5-1PFR"
OWNER_UID = "01KS7ZZ1C6-2QGS"


def validate_listener(obj: object) -> list[str]:
    """Return a list of validation errors for a listener object (empty when valid)."""
    if not isinstance(obj, dict):
        return ["listener must be a mapping"]
    errors: list[str] = []
    for field in SCHEMA["requiredFields"]:
        if field not in obj:
            errors.append(f"missing required field: {field}")
    if obj.get("type") != "listener":
        errors.append("type must be listener")
    uid = obj.get("uid")
    if "uid" in obj and not (isinstance(uid, str) and UID_RE.match(uid)):
        errors.append("uid does not match uidPattern")
    if "name" in obj and (not isinstance(obj["name"], str) or not obj["name"].strip()):
        errors.append("name must be a non-empty string")
    for field, allowed in SCHEMA["enumFields"].items():
        if field in obj and obj[field] not in allowed:
            errors.append(f"{field} must be one of {allowed}")
    if "port" in obj:
        port = obj["port"]
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            errors.append("port must be an integer from 1 to 65535")
    if "endpoint" in obj and (not isinstance(obj["endpoint"], str) or not obj["endpoint"].strip()):
        errors.append("endpoint must be a non-empty string")
    if "methods" in obj:
        methods = obj["methods"]
        if not isinstance(methods, list) or not all(isinstance(m, str) and m.strip() for m in methods):
            errors.append("methods must be a list of non-empty strings")
    if "owner" in obj:
        errors.extend(_validate_owner(obj["owner"]))
    return errors


def _validate_owner(owner: object) -> list[str]:
    if not isinstance(owner, dict):
        return ["owner must be a mapping with ref and kind"]
    errors: list[str] = []
    for field in OWNER_SCHEMA["requiredFields"]:
        if field not in owner:
            errors.append(f"owner missing required field: {field}")
    ref = owner.get("ref")
    if "ref" in owner and not (isinstance(ref, str) and UID_RE.match(ref)):
        errors.append("owner.ref must be a UID")
    kind = owner.get("kind")
    if "kind" in owner and kind not in OWNER_SCHEMA["enumFields"]["kind"]:
        errors.append("owner.kind must be product_component, data_component or external_system")
    return errors


def _listener(**overrides: object) -> dict:
    base: dict = {
        "schemaVersion": "1.0",
        "uid": VALID_UID,
        "type": "listener",
        "name": "Orders API",
        "owner": {"ref": OWNER_UID, "kind": "product_component"},
        "protocol": "REST",
        "port": 443,
        "endpoint": "/orders",
        "authenticationModel": "oauth",
        "catalogStatus": "complete",
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def test_schema_declares_listener_fields_and_enums():
    assert SCHEMA["type"] == "listener"
    for field in ("owner", "protocol", "port", "endpoint", "authenticationModel", "catalogStatus"):
        assert field in SCHEMA["requiredFields"] or field in SCHEMA["optionalFields"]
    assert SCHEMA["enumFields"]["catalogStatus"] == ["stub", "incomplete", "complete"]
    assert "none" in SCHEMA["enumFields"]["authenticationModel"]
    assert "TBD" in SCHEMA["enumFields"]["authenticationModel"]
    assert OWNER_SCHEMA["enumFields"]["kind"] == [
        "product_component",
        "data_component",
        "external_system",
    ]


def test_valid_listener_has_no_errors():
    assert validate_listener(_listener()) == []


def test_valid_stub_with_optional_fields_has_no_errors():
    stub = _listener(
        catalogStatus="stub",
        authenticationModel="TBD",
        methods=["GET", "POST"],
        description="Endpoint named by a caller, details pending.",
    )
    assert validate_listener(stub) == []


def test_none_authentication_is_accepted_by_schema():
    assert validate_listener(_listener(authenticationModel="none")) == []


@pytest_owner_kinds := None  # placeholder removed below
