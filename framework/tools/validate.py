#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import os
import sys
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from uid_utils import UID_PATTERN_TEXT, generate_uid


FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = FRAMEWORK_ROOT.parent
SCHEMA_ROOT = FRAMEWORK_ROOT / "schemas"
BASE_CONFIGURATION_ROOT = FRAMEWORK_ROOT / "configurations"
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "examples"
SKIP_DIRS = {"tools", "schemas", "docs", "adrs", ".github", ".git", ".draft"}
VALID_DIAGRAM_TIERS = {"presentation", "application", "data", "utility"}
VALID_TECHNOLOGY_COMPONENT_CLASSIFICATIONS = {"operating-system", "compute-platform", "software", "agent"}
VALID_DEPLOYMENT_QUALITIES = {"availability", "scalability", "recoverability"}
DECISION_ENUMS = {
    "autoscaling": {"required", "optional", "none"},
    "loadBalancer": {"required", "optional", "none"},
}

TYPE_CHECKERS = {
    "bool": bool,
    "list": list,
    "dict": dict,
    "str": str,
    "int": int,
}

VALID_REQUIREMENT_SCOPES = {
    "host",
    "runtime_service",
    "data_at_rest_service",
    "edge_gateway_service",
    "product_service",
    "product_component",
    "data_component",
    "reference_architecture",
    "software_deployment_pattern",
}

VALID_REQUIREMENT_ANSWER_TYPES = {
    "technologyComponent",
    "technologyComponentConfiguration",
    "deploymentConfiguration",
    "externalInteraction",
    "internalComponent",
    "architecturalDecision",
    "field",
}
VALID_REQUIREMENT_MODES = {"mandatory", "conditional"}
VALID_REQUIREMENT_ACTIVATIONS = {"always", "workspace"}
VALID_IMPLEMENTATION_STATUSES = {"candidate", "preferred", "existing-only", "deprecated", "retired"}
STANDARD_TYPES = {
    "host",
    "runtime_service",
    "data_at_rest_service",
    "edge_gateway_service",
    "product_service",
    "product_component",
    "data_component",
}
SERVICE_TYPES = {"runtime_service", "data_at_rest_service", "edge_gateway_service"}
BUSINESS_PILLAR_ID_PATTERN = re.compile(r"^business-pillar\.[a-z0-9-]+$")
UID_PATTERN = re.compile(UID_PATTERN_TEXT)
WORKSPACE_DOCUMENT_TYPES = {"vocabulary", "vocabulary_proposal"}
VALID_VOCABULARY_MODES = {"advisory", "gated"}
VALID_VOCABULARY_VALUE_STATUSES = {"approved", "proposed", "deprecated", "retired"}
DRAFTING_INTERVIEW_REQUIRED = "drafting-interview-required"
VOCABULARY_DEFINITIONS = {
    "deploymentTargets": {
        "label": "deployment target",
        "default_file": "deployment-targets.yaml",
        "sentinels": {"owner-interview-required", DRAFTING_INTERVIEW_REQUIRED},
    },
    "dataClassificationLevels": {
        "label": "data classification",
        "default_file": "data-classification-levels.yaml",
        "sentinels": {DRAFTING_INTERVIEW_REQUIRED},
    },
    "teams": {
        "label": "team",
        "default_file": "teams.yaml",
        "sentinels": {DRAFTING_INTERVIEW_REQUIRED},
    },
    "availabilityTiers": {
        "label": "availability tier",
        "default_file": "availability-tiers.yaml",
        "sentinels": {DRAFTING_INTERVIEW_REQUIRED},
    },
    "failureDomains": {
        "label": "failure domain",
        "default_file": "failure-domains.yaml",
        "sentinels": {DRAFTING_INTERVIEW_REQUIRED},
    },
    "connectionProtocols": {
        "label": "connection protocol",
        "default_file": "connection-protocols.yaml",
        "sentinels": {DRAFTING_INTERVIEW_REQUIRED},
    },
    "networkZones": {
        "label": "network zone",
        "default_file": "network-zones.yaml",
        "sentinels": {DRAFTING_INTERVIEW_REQUIRED},
    },
    "networkZonePatterns": {
        "label": "network zone pattern",
        "default_file": "network-zone-patterns.yaml",
    },
}


def discover_yaml_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.yaml")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def workspace_yaml_roots(workspace_root: Path) -> list[Path]:
    roots = [BASE_CONFIGURATION_ROOT]
    provider_root = workspace_root / ".draft" / "providers"
    if provider_root.exists():
        roots.extend(
            provider_config
            for provider_config in sorted(provider_root.glob("*/configurations"))
            if provider_config.exists()
        )
    workspace_config = workspace_root / "configurations"
    workspace_catalog = workspace_root / "catalog"
    if workspace_config.exists():
        roots.append(workspace_config)
    if workspace_catalog.exists():
        roots.append(workspace_catalog)
    elif workspace_root.exists() and workspace_root.name == "catalog":
        roots.append(workspace_root)
    return roots


def discover_workspace_yaml_files(workspace_root: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for root in workspace_yaml_roots(workspace_root):
        for path in discover_yaml_files(root):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    return sorted(files)


def display_path(path: Path) -> str:
    for root in (REPO_ROOT, Path.cwd()):
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DRAFT framework and workspace YAML.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE_ROOT,
        help="Workspace root containing catalog/ and configurations/. Defaults to examples/.",
    )
    return parser.parse_args(argv)


def load_workspace_requirements(workspace_root: Path, failures: list[str]) -> dict[str, Any]:
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if not config_path.exists():
        return {"active_groups": set(), "require_active_group_disposition": False}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{config_path}: Fix workspace configuration YAML; parser reported {exc}")
        return {"active_groups": set(), "require_active_group_disposition": False}
    if not isinstance(data, dict):
        failures.append(f"{config_path}: Make workspace configuration a mapping at the top level")
        return {"active_groups": set(), "require_active_group_disposition": False}

    requirements = data.get("requirements") or {}
    if not isinstance(requirements, dict):
        failures.append(f"{config_path}: Make requirements a mapping with activeRequirementGroups")
        return {"active_groups": set(), "require_active_group_disposition": False}

    active = requirements.get("activeRequirementGroups") or []
    if not isinstance(active, list):
        failures.append(f"{config_path}: Set requirements.activeRequirementGroups to a list of requirement_group UIDs")
        active = []
    active_groups = {str(group_id) for group_id in active if is_non_empty(group_id)}
    return {
        "active_groups": active_groups,
        "require_active_group_disposition": requirements.get("requireActiveRequirementGroupDisposition") is True,
    }


def load_workspace_business_taxonomy(workspace_root: Path, failures: list[str]) -> dict[str, Any]:
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if not config_path.exists():
        return {"pillars": {}, "require_sdp_pillar": False}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{config_path}: Fix workspace configuration YAML; parser reported {exc}")
        return {"pillars": {}, "require_sdp_pillar": False}
    if not isinstance(data, dict):
        failures.append(f"{config_path}: Make workspace configuration a mapping at the top level")
        return {"pillars": {}, "require_sdp_pillar": False}

    taxonomy = data.get("businessTaxonomy") or {}
    if not taxonomy:
        return {"pillars": {}, "require_sdp_pillar": False}
    if not isinstance(taxonomy, dict):
        failures.append(f"{config_path}: Make businessTaxonomy a mapping with pillars")
        return {"pillars": {}, "require_sdp_pillar": False}

    pillars = taxonomy.get("pillars") or []
    if not isinstance(pillars, list):
        failures.append(f"{config_path}: Set businessTaxonomy.pillars to a list of company pillar mappings")
        pillars = []

    pillar_by_id: dict[str, dict[str, Any]] = {}
    for index, pillar in enumerate(pillars):
        context = f"{config_path}: businessTaxonomy.pillars[{index}]"
        if not isinstance(pillar, dict):
            failures.append(f"{context}: Change pillar entry to a mapping with id and name")
            continue
        pillar_id = str(pillar.get("id") or "").strip()
        if not pillar_id:
            failures.append(f"{context}: Add id using business-pillar.<slug>")
            continue
        if not BUSINESS_PILLAR_ID_PATTERN.match(pillar_id):
            failures.append(f"{context}: Rename id '{pillar_id}' so it matches business-pillar.<slug>")
        if pillar_id in pillar_by_id:
            failures.append(f"{context}: Remove duplicate business pillar id '{pillar_id}'")
        if not is_non_empty(pillar.get("name")):
            failures.append(f"{context}: Add name so the browser can show the business pillar clearly")
        owner = pillar.get("owner")
        if owner is not None and not isinstance(owner, dict):
            failures.append(f"{context}: Change owner to a mapping with team and optional contact")
        pillar_by_id[pillar_id] = pillar

    return {
        "pillars": pillar_by_id,
        "require_sdp_pillar": taxonomy.get("requireSoftwareDeploymentPatternPillar") is True,
    }


def load_workspace_config(workspace_root: Path, failures: list[str]) -> dict[str, Any]:
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if not config_path.exists():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{config_path}: Fix workspace configuration YAML; parser reported {exc}")
        return {}
    if not isinstance(data, dict):
        failures.append(f"{config_path}: Make workspace configuration a mapping at the top level")
        return {}
    return data


def vocabulary_source_paths(workspace_root: Path, config: dict[str, Any], definition: dict[str, Any]) -> list[Path]:
    sources: list[Path] = []
    raw_sources = config.get("sources")
    raw_source = config.get("source")
    if is_non_empty(raw_source):
        raw_sources = [raw_source, *(raw_sources if isinstance(raw_sources, list) else [])]
    if isinstance(raw_sources, list):
        for source in raw_sources:
            if not is_non_empty(source):
                continue
            path = Path(str(source))
            sources.append(path if path.is_absolute() else workspace_root / path)

    default_path = workspace_root / "configurations" / "vocabulary" / str(definition["default_file"])
    if default_path.exists() and default_path not in sources:
        sources.append(default_path)
    return sources


def collect_vocabulary_values(
    values: Any,
    context: str,
    vocabulary_key: str,
    values_by_id: dict[str, dict[str, Any]],
    failures: list[str],
    warnings: list[str],
) -> None:
    if values is None:
        return
    if not isinstance(values, list):
        failures.append(f"{context}: Change values to a list of {vocabulary_key} mappings")
        return

    for index, entry in enumerate(values):
        entry_context = f"{context}.values[{index}]"
        if not isinstance(entry, dict):
            failures.append(f"{entry_context}: Change vocabulary entry to a mapping")
            continue
        entry_id = str(entry.get("id") or "").strip()
        if not entry_id:
            failures.append(f"{entry_context}: Add id for this vocabulary value")
            continue
        if entry_id in values_by_id:
            failures.append(f"{entry_context}: Remove duplicate vocabulary id '{entry_id}'")
            continue
        if not is_non_empty(entry.get("name")):
            warnings.append(f"{entry_context}: Add name so the vocabulary value is clear in interviews and browser views")
        status = str(entry.get("status") or "approved").strip()
        if status not in VALID_VOCABULARY_VALUE_STATUSES:
            failures.append(
                f"{entry_context}: Set status to one of {sorted(VALID_VOCABULARY_VALUE_STATUSES)}; '{status}' is not valid"
            )
        values_by_id[entry_id] = {**entry, "id": entry_id, "status": status}


def load_vocabulary_source(
    path: Path,
    vocabulary_key: str,
    values_by_id: dict[str, dict[str, Any]],
    failures: list[str],
    warnings: list[str],
) -> None:
    if not path.exists():
        failures.append(f"{path}: Vocabulary source file does not exist")
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{path}: Fix vocabulary source YAML; parser reported {exc}")
        return
    if not isinstance(data, dict):
        failures.append(f"{path}: Make vocabulary source a mapping at the top level")
        return
    declared_key = data.get("vocabulary")
    if is_non_empty(declared_key) and str(declared_key) != vocabulary_key:
        failures.append(f"{path}: Set vocabulary to '{vocabulary_key}' or remove this source from workspace.yaml")
    collect_vocabulary_values(data.get("values"), f"{path}", vocabulary_key, values_by_id, failures, warnings)


def load_workspace_vocabulary(
    workspace_root: Path,
    failures: list[str],
    warnings: list[str],
) -> dict[str, dict[str, Any]]:
    workspace_config = load_workspace_config(workspace_root, failures)
    raw_vocabulary = workspace_config.get("vocabulary")
    if raw_vocabulary is None:
        return {}
    config_path = workspace_root / ".draft" / "workspace.yaml"
    if not isinstance(raw_vocabulary, dict):
        failures.append(f"{config_path}: Change vocabulary to a mapping of declared company vocabulary lists")
        return {}
    if not raw_vocabulary:
        return {}

    loaded: dict[str, dict[str, Any]] = {}
    for vocabulary_key, definition in VOCABULARY_DEFINITIONS.items():
        raw_config = raw_vocabulary.get(vocabulary_key)
        if raw_config is None:
            continue
        context = f"{config_path}: vocabulary.{vocabulary_key}"
        if isinstance(raw_config, list):
            config = {"values": raw_config}
        elif isinstance(raw_config, dict):
            config = raw_config
        else:
            failures.append(f"{context}: Change vocabulary list declaration to a mapping with mode, source, and values")
            continue

        mode = str(config.get("mode") or "advisory").strip()
        if mode not in VALID_VOCABULARY_MODES:
            failures.append(f"{context}: Set mode to advisory or gated; '{mode}' is not valid")
            mode = "advisory"

        review_by = config.get("reviewBy")
        review_date = parse_lifecycle_date(review_by) if review_by else None
        if review_date and review_date < validation_date():
            warnings.append(
                f"{context}: reviewBy {review_date.isoformat()} has passed; review advisory vocabulary before it becomes permanent"
            )

        values_by_id: dict[str, dict[str, Any]] = {}
        collect_vocabulary_values(config.get("values"), context, vocabulary_key, values_by_id, failures, warnings)
        for source_path in vocabulary_source_paths(workspace_root, config, definition):
            load_vocabulary_source(source_path, vocabulary_key, values_by_id, failures, warnings)

        approved_ids = {
            value_id
            for value_id, value in values_by_id.items()
            if str(value.get("status") or "approved") == "approved"
        }
        loaded[vocabulary_key] = {
            "key": vocabulary_key,
            "label": definition["label"],
            "mode": mode,
            "values": values_by_id,
            "approved_ids": approved_ids,
            "sentinels": set(definition.get("sentinels", set())),
        }
    return loaded


def validate_workspace_requirements(
    workspace_root: Path,
    active_group_ids: set[str],
    catalog_by_id: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    config_path = workspace_root / ".draft" / "workspace.yaml"
    for group_id in sorted(active_group_ids):
        group = catalog_by_id.get(group_id)
        if not group or group.get("type") != "requirement_group":
            failures.append(
                f"{config_path}: Activate only existing workspace-mode requirement groups; '{group_id}' was not found"
            )
        elif group.get("activation") != "workspace":
            failures.append(
                f"{config_path}: Remove '{group_id}' from requirements.activeRequirementGroups; always-on requirement groups do not need workspace activation"
            )


def validate_software_deployment_business_context(
    obj: dict[str, Any],
    path: Path,
    business_taxonomy: dict[str, Any],
    failures: list[str],
) -> None:
    pillars = business_taxonomy.get("pillars", {})
    require_pillar = business_taxonomy.get("require_sdp_pillar") is True
    context = obj.get("businessContext")
    if context is None:
        if require_pillar:
            failures.append(
                f"{path}: Add businessContext.pillar because .draft/workspace.yaml requires Software Deployment Patterns to declare a business pillar"
            )
        return
    if not isinstance(context, dict):
        failures.append(f"{path}: Change businessContext to a mapping with pillar, optional additionalPillars, productFamily, and notes")
        return

    pillar = str(context.get("pillar") or "").strip()
    if not pillar:
        failures.append(f"{path}: Add businessContext.pillar using a businessTaxonomy.pillars id from .draft/workspace.yaml")
    elif pillars and pillar not in pillars:
        failures.append(f"{path}: Replace businessContext.pillar '{pillar}' with a declared businessTaxonomy.pillars id")
    elif not pillars:
        failures.append(f"{path}: Declare businessTaxonomy.pillars in .draft/workspace.yaml before using businessContext.pillar '{pillar}'")

    additional = context.get("additionalPillars") or []
    if additional and not isinstance(additional, list):
        failures.append(f"{path}: Change businessContext.additionalPillars to a list of business pillar IDs")
        return
    if isinstance(additional, list):
        for index, additional_pillar in enumerate(additional):
            additional_id = str(additional_pillar or "").strip()
            if not additional_id:
                failures.append(f"{path}: Remove empty businessContext.additionalPillars[{index}]")
            elif pillars and additional_id not in pillars:
                failures.append(
                    f"{path}: Replace businessContext.additionalPillars[{index}] '{additional_id}' with a declared businessTaxonomy.pillars id"
                )


def deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = copy.deepcopy(base)
        for key, value in patch.items():
            if key in {"uid", "id", "type"}:
                continue
            merged[key] = deep_merge(merged.get(key), value)
        return merged
    return copy.deepcopy(patch)


def apply_object_patches(objects: dict[Path, dict[str, Any]], failures: list[str]) -> dict[Path, dict[str, Any]]:
    objects_by_uid = {
        str(obj["uid"]): obj
        for obj in objects.values()
        if isinstance(obj, dict) and is_non_empty(obj.get("uid"))
    }
    patched_by_uid: dict[str, dict[str, Any]] = {}
    for path, obj in objects.items():
        if obj.get("type") != "object_patch":
            continue
        target_uid = obj.get("target")
        patch = obj.get("patch")
        if not is_non_empty(target_uid):
            failures.append(f"{path}: object_patch must declare target uid")
            continue
        if not isinstance(patch, dict):
            failures.append(f"{path}: object_patch patch must be a mapping")
            continue
        target = patched_by_uid.get(str(target_uid)) or objects_by_uid.get(str(target_uid))
        if not target:
            failures.append(f"{path}: object_patch target uid '{target_uid}' does not exist")
            continue
        patched_by_uid[str(target_uid)] = deep_merge(target, patch)

    if not patched_by_uid:
        return objects

    patched_objects = dict(objects)
    for path, obj in objects.items():
        uid = obj.get("uid")
        if uid in patched_by_uid:
            patched_objects[path] = patched_by_uid[str(uid)]
    return patched_objects


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("top-level YAML document must be a mapping")
    return data


def load_schemas(root: Path) -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.yaml")):
        data = load_yaml(path)
        data["_schema_path"] = path
        schemas.append(data)
    return schemas


def is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def has_required_value(node: dict[str, Any], field: str) -> bool:
    if field not in node or node.get(field) is None:
        return False
    value = node.get(field)
    if isinstance(value, str):
        return bool(value.strip())
    return True


def object_uid(obj: dict[str, Any]) -> str:
    return str(obj.get("uid") or "")


def object_label(obj: dict[str, Any]) -> str:
    return str(obj.get("name") or obj.get("uid") or obj.get("id") or "unknown")


def requirement_group_name(group: dict[str, Any], fallback: str = "Requirement Group") -> str:
    name = str(group.get("name") or fallback)
    return re.sub(r"\s+Requirement Group$", "", name).strip() or fallback


def requirement_authority_prefix(group: dict[str, Any]) -> str:
    authority = group.get("authority")
    if isinstance(authority, dict):
        for key in ("shortName", "name"):
            value = authority.get(key)
            if is_non_empty(value):
                return str(value).strip()
    provider = group.get("provider")
    if isinstance(provider, dict):
        for key in ("shortName", "name", "id"):
            value = provider.get(key)
            if is_non_empty(value):
                return str(value).strip()
    return ""


def requirement_display_label(group: dict[str, Any], requirement: dict[str, Any]) -> str:
    requirement_id = str(requirement.get("id") or requirement.get("externalControlId") or "unknown")
    if requirement.get("externalControlId"):
        prefix = requirement_authority_prefix(group)
        return f"{prefix}.{requirement_id}" if prefix else requirement_id
    prefix = requirement_authority_prefix(group)
    group_name = requirement_group_name(group)
    return f"{prefix} {group_name} / {requirement_id}" if prefix else f"{group_name} / {requirement_id}"


def uid_repair_command(workspace_root: Path, path: Path, suggested_uid: str) -> str:
    try:
        file_arg = path.resolve().relative_to(workspace_root).as_posix()
    except ValueError:
        file_arg = display_path(path)
    repair_script = display_path(Path(__file__).with_name("repair_uids.py"))
    return f"python3 {repair_script} --workspace {workspace_root.as_posix()} --file {file_arg} --uid {suggested_uid}"


def repair_file_command(workspace_root: Path, path: Path) -> str:
    try:
        file_arg = path.resolve().relative_to(workspace_root).as_posix()
    except ValueError:
        file_arg = display_path(path)
    repair_script = display_path(Path(__file__).with_name("repair_uids.py"))
    return f"python3 {repair_script} --workspace {workspace_root.as_posix()} --file {file_arg}"


def validate_object_uids(
    objects: dict[Path, dict[str, Any]],
    workspace_root: Path,
    failures: list[str],
) -> None:
    seen: dict[str, Path] = {}
    existing = {
        str(obj.get("uid"))
        for obj in objects.values()
        if isinstance(obj, dict) and is_non_empty(obj.get("uid"))
    }
    for path, obj in objects.items():
        if not isinstance(obj, dict) or not is_non_empty(obj.get("type")):
            continue
        if obj.get("type") in WORKSPACE_DOCUMENT_TYPES:
            continue
        if "id" in obj:
            suggested = generate_uid(existing)
            existing.add(suggested)
            command = uid_repair_command(workspace_root, path, suggested)
            failures.append(
                f"{path}: Remove legacy field 'id' and use generated uid '{suggested}' for object identity. "
                f"Repair command: {command}"
            )
        uid = object_uid(obj)
        if not uid:
            suggested = generate_uid(existing)
            existing.add(suggested)
            command = uid_repair_command(workspace_root, path, suggested)
            failures.append(
                f"{path}: Add required field 'uid' with generated value '{suggested}'. "
                f"Repair command: {command}"
            )
            continue
        if not UID_PATTERN.match(uid):
            suggested = generate_uid(existing)
            existing.add(suggested)
            command = uid_repair_command(workspace_root, path, suggested)
            failures.append(
                f"{path}: Replace malformed uid '{uid}' with generated value '{suggested}'. "
                f"Repair command: {command}"
            )
        if uid in seen:
            suggested = generate_uid(existing)
            existing.add(suggested)
            command = uid_repair_command(workspace_root, path, suggested)
            failures.append(
                f"{path}: Replace duplicate uid '{uid}' with generated value '{suggested}' because it already appears in {seen[uid]}. "
                f"Repair command: {command}"
            )
        else:
            seen[uid] = path


def get_nested_value(node: Any, dotted_key: str) -> Any:
    current = node
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def schema_specificity(schema: dict[str, Any]) -> int:
    return sum(1 for key in ("subtype", "category", "serviceCategory") if is_non_empty(schema.get(key)))


def select_schema(obj: dict[str, Any], schemas: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for schema in schemas:
        if schema.get("type") != obj.get("type"):
            continue
        if is_non_empty(schema.get("subtype")) and schema.get("subtype") != obj.get("subtype"):
            continue
        if is_non_empty(schema.get("category")) and schema.get("category") != obj.get("category"):
            continue
        if is_non_empty(schema.get("serviceCategory")) and schema.get("serviceCategory") != obj.get("serviceCategory"):
            continue
        candidates.append(schema)
    if not candidates:
        return None
    return sorted(candidates, key=schema_specificity, reverse=True)[0]


def matches_conditions(obj: dict[str, Any], conditions: dict[str, Any]) -> bool:
    for key, expected in conditions.items():
        if obj.get(key) != expected:
            return False
    return True


def validate_schema_section(
    node: dict[str, Any],
    schema: dict[str, Any],
    context: str,
    failures: list[str],
    root_schema: dict[str, Any] | None = None,
) -> None:
    root_schema = root_schema or schema
    field_descriptions = schema.get("fieldDescriptions") if isinstance(schema.get("fieldDescriptions"), dict) else {}
    for field in schema.get("requiredFields", []):
        if not has_required_value(node, field):
            hint = field_descriptions.get(field, "Populate this field with a valid value for the selected schema.")
            failures.append(f"{context}: Add required field '{field}' — {hint}")

    uid_pattern = schema.get("uidPattern")
    if uid_pattern and is_non_empty(node.get("uid")) and not re.match(str(uid_pattern), str(node.get("uid"))):
        failures.append(f"{context}: Replace uid '{node.get('uid')}' so it matches pattern {uid_pattern}")

    for field, allowed_values in (schema.get("enumFields") or {}).items():
        value = node.get(field)
        if value is None or value == "":
            continue
        if value not in allowed_values:
            failures.append(f"{context}: Set {field} to one of {allowed_values}; '{value}' is not valid")

    for field, expected_type in (schema.get("fieldTypes") or {}).items():
        if field not in node or node.get(field) is None:
            continue
        checker = TYPE_CHECKERS.get(str(expected_type))
        if checker and not isinstance(node.get(field), checker):
            failures.append(f"{context}: Change field '{field}' to type {expected_type}")

    for field, allowed_values in (schema.get("enumListFields") or {}).items():
        value = node.get(field)
        if value is None:
            continue
        if not isinstance(value, list):
            failures.append(f"{context}: Change field '{field}' to a list")
            continue
        invalid = [item for item in value if item not in allowed_values]
        if invalid:
            failures.append(f"{context}: Replace invalid {field} values {invalid} with one of {allowed_values}")

    for conditional in schema.get("conditionalRequired", []) or []:
        when = conditional.get("when", {})
        required = conditional.get("require", [])
        if isinstance(when, dict) and matches_conditions(node, when):
            for field in required:
                if not has_required_value(node, field):
                    hint = field_descriptions.get(field, "Populate this conditional field because the matching condition is present.")
                    failures.append(f"{context}: Add required field '{field}' — {hint}")

    for field, section_name in (schema.get("collectionSchemas") or {}).items():
        if field not in node or node.get(field) is None:
            continue
        value = node.get(field)
        if not isinstance(value, list):
            failures.append(f"{context}: Change field '{field}' to a list")
            continue
        child_schema = schema.get(section_name) or root_schema.get(section_name)
        if not isinstance(child_schema, dict):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                failures.append(f"{context}: Change '{field}[{index}]' to a mapping")
                continue
            validate_schema_section(item, child_schema, f"{context}: {field}[{index}]", failures, root_schema)


def resolve_requirement_group_requirements(
    group_id: str,
    requirement_groups: dict[str, dict[str, Any]],
    stack: set[str] | None = None,
) -> list[dict[str, Any]]:
    if group_id not in requirement_groups:
        raise KeyError(f"unknown Requirement Group '{group_id}'")
    stack = stack or set()
    if group_id in stack:
        raise ValueError(f"cyclic Requirement Group inheritance detected at '{group_id}'")
    stack.add(group_id)
    group = requirement_groups[group_id]
    requirements: list[dict[str, Any]] = []
    parent_id = group.get("inherits")
    if parent_id:
        requirements.extend(resolve_requirement_group_requirements(parent_id, requirement_groups, stack))
    requirements.extend(group.get("requirements", []))
    stack.remove(group_id)
    return requirements


def requirement_group_applies_to_object(group: dict[str, Any], obj: dict[str, Any]) -> bool:
    object_type = str(obj.get("type") or "")
    applies_to = group.get("appliesTo") or []
    if not isinstance(applies_to, list) or object_type not in applies_to:
        return False
    qualifiers = group.get("appliesToQualifiers") or {}
    if isinstance(qualifiers, dict):
        for key, expected in qualifiers.items():
            if obj.get(key) != expected:
                return False
    if object_type == "host" and group.get("name") == "Host Requirement Group":
        tags = obj.get("tags") or []
        if isinstance(tags, list) and any(tag in {"serverless", "container"} for tag in tags):
            return False
    return True


def requirement_applies_to_object(requirement: dict[str, Any], obj: dict[str, Any]) -> bool:
    scoped_to = requirement.get("appliesTo")
    if isinstance(scoped_to, list) and scoped_to and obj.get("type") not in scoped_to:
        return False
    applicability = requirement.get("applicability")
    if isinstance(applicability, dict) and applicability:
        if "allOf" in applicability:
            clauses = applicability.get("allOf")
            return isinstance(clauses, list) and all(applicability_clause_matches(obj, clause) for clause in clauses)
        if "anyOf" in applicability:
            clauses = applicability.get("anyOf")
            return isinstance(clauses, list) and any(applicability_clause_matches(obj, clause) for clause in clauses)
    return True


def applicability_clause_matches(obj: dict[str, Any], clause: Any) -> bool:
    if not isinstance(clause, dict) or not is_non_empty(clause.get("field")):
        return False
    value = get_nested_value(obj, str(clause["field"]))
    if "equals" in clause:
        return value == clause.get("equals")
    if "in" in clause and isinstance(clause.get("in"), list):
        return value in clause.get("in")
    if "contains" in clause:
        return isinstance(value, list) and clause.get("contains") in value
    if "truthy" in clause:
        return bool(value) is bool(clause.get("truthy"))
    return False


def applicable_requirement_group_ids(
    obj: dict[str, Any],
    requirement_groups: dict[str, dict[str, Any]],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> list[str]:
    active_group_ids = active_group_ids or set()
    declared = obj.get("requirementGroups", [])
    declared_ids = {str(group_id) for group_id in declared} if isinstance(declared, list) else set()
    applicable: set[str] = set()
    for group_id, group in requirement_groups.items():
        if not requirement_group_applies_to_object(group, obj):
            continue
        if group.get("activation") == "always":
            applicable.add(group_id)
        elif group_id in declared_ids:
            applicable.add(group_id)
        elif require_active_group_disposition and group_id in active_group_ids:
            applicable.add(group_id)
    return sorted(applicable)


def mechanism_description(mechanism: dict[str, Any]) -> str:
    mechanism_type = mechanism.get("mechanism")
    if mechanism_type == "field":
        field = mechanism.get("key", "unknown")
        equals = mechanism.get("equals")
        return f"field({field}={equals})" if equals is not None else f"field({field})"
    if mechanism_type == "externalInteraction":
        capability = mechanism.get("criteria", {}).get("capability", "unknown")
        return f"externalInteraction(capability={capability})"
    if mechanism_type == "internalComponent":
        criteria = mechanism.get("criteria", {})
        concern = criteria.get("concern")
        role = criteria.get("role")
        if concern:
            return f"internalComponent(concern={concern})"
        return f"internalComponent(role={role or 'unknown'})"
    if mechanism_type == "technologyComponentConfiguration":
        capability = mechanism.get("criteria", {}).get("capability") or mechanism.get("criteria", {}).get("concern", "unknown")
        return f"technologyComponentConfiguration(capability={capability})"
    if mechanism_type == "deploymentConfiguration":
        quality = mechanism.get("criteria", {}).get("quality", "unknown")
        return f"deploymentConfiguration(quality={quality})"
    if mechanism_type == "architecturalDecision":
        return f"architecturalDecision({mechanism.get('key', 'unknown')})"
    return str(mechanism_type)


def referenced_technology_components(obj: dict[str, Any], catalog_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[str] = []
    for field in ("operatingSystemComponent", "computePlatformComponent", "primaryTechnologyComponent"):
        ref = obj.get(field)
        if is_non_empty(ref):
            refs.append(str(ref))
    for component in obj.get("internalComponents", []) or []:
        if isinstance(component, dict) and is_non_empty(component.get("ref")):
            refs.append(str(component["ref"]))

    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    if obj.get("type") == "technology_component" and is_non_empty(obj.get("uid")):
        resolved.append(obj)
        seen.add(str(obj["uid"]))
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        target = catalog_by_id.get(ref)
        if target and target.get("type") == "technology_component":
            resolved.append(target)
    return resolved


def parse_lifecycle_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def validation_date() -> date:
    configured = os.environ.get("DRAFT_VALIDATION_DATE")
    if configured:
        parsed = parse_lifecycle_date(configured)
        if parsed:
            return parsed
    return date.today()


def collect_technology_component_refs(
    ref: str,
    catalog_by_id: dict[str, dict[str, Any]],
    seen: set[str] | None = None,
) -> set[str]:
    if seen is None:
        seen = set()
    if ref in seen:
        return set()
    seen.add(ref)

    target = catalog_by_id.get(ref)
    if not isinstance(target, dict):
        return set()
    if target.get("type") == "technology_component":
        return {ref}

    refs: list[str] = []
    for field in ("operatingSystemComponent", "computePlatformComponent", "primaryTechnologyComponent", "host", "runsOn"):
        value = target.get(field)
        if is_non_empty(value):
            refs.append(str(value))
    for component in target.get("internalComponents", []) or []:
        if isinstance(component, dict) and is_non_empty(component.get("ref")):
            refs.append(str(component["ref"]))

    technology_refs: set[str] = set()
    for nested_ref in refs:
        technology_refs.update(collect_technology_component_refs(nested_ref, catalog_by_id, seen))
    return technology_refs


def reference_architecture_technology_refs(
    obj: dict[str, Any],
    catalog_by_id: dict[str, dict[str, Any]],
) -> set[str]:
    technology_refs: set[str] = set()
    for group in obj.get("serviceGroups", []) or []:
        if not isinstance(group, dict):
            continue
        for entry in group.get("deployableObjects", []) or []:
            if isinstance(entry, dict) and is_non_empty(entry.get("ref")):
                technology_refs.update(collect_technology_component_refs(str(entry["ref"]), catalog_by_id))
    return technology_refs


def vendor_lifecycle_risk_technologies(
    obj: dict[str, Any],
    catalog_by_id: dict[str, dict[str, Any]],
) -> tuple[list[tuple[str, date]], list[tuple[str, date, date | None]]]:
    today = validation_date()
    expired: list[tuple[str, date]] = []
    extended_support: list[tuple[str, date, date | None]] = []
    for ref in sorted(reference_architecture_technology_refs(obj, catalog_by_id)):
        target = catalog_by_id.get(ref)
        if not isinstance(target, dict):
            continue
        vendor_lifecycle = target.get("vendorLifecycle") or {}
        if not isinstance(vendor_lifecycle, dict):
            continue
        mainstream_end = parse_lifecycle_date(vendor_lifecycle.get("mainstreamSupportEnd"))
        support_end = parse_lifecycle_date(vendor_lifecycle.get("extendedSupportEnd"))
        if support_end and support_end <= today:
            expired.append((ref, support_end))
        elif mainstream_end and mainstream_end <= today:
            extended_support.append((ref, mainstream_end, support_end))
    return expired, extended_support


def mechanism_satisfied(obj: dict[str, Any], mechanism: dict[str, Any], catalog_by_id: dict[str, dict[str, Any]]) -> bool:
    mechanism_type = mechanism.get("mechanism")
    if mechanism_type == "field":
        key = mechanism.get("key", "")
        if key not in obj:
            return False
        value = obj.get(key)
        if "equals" in mechanism:
            return value == mechanism.get("equals")
        if mechanism.get("allowEmpty") is True:
            return value is not None
        return is_non_empty(value)
    if mechanism_type == "externalInteraction":
        capability = mechanism.get("criteria", {}).get("capability")
        interactions = list(obj.get("externalInteractions", []) or [])
        for service_group in obj.get("serviceGroups", []) or []:
            if isinstance(service_group, dict):
                interactions.extend(service_group.get("externalInteractions", []) or [])
        if capability == "any":
            return bool(interactions)
        # Check if any interaction has the required capability in its capabilities list
        for interaction in interactions:
            if not isinstance(interaction, dict):
                continue
            caps = interaction.get("capabilities", [])
            if isinstance(caps, list) and capability in caps:
                return True
        return False
    if mechanism_type == "technologyComponent":
        criteria = mechanism.get("criteria", {})
        capability = criteria.get("capability") or criteria.get("concern")
        classification = criteria.get("classification")
        ref = mechanism.get("ref")
        for component in referenced_technology_components(obj, catalog_by_id):
            if ref and component.get("uid") != ref:
                continue
            if classification and component.get("classification") != classification:
                continue
            caps = component.get("capabilities", [])
            if not capability or (isinstance(caps, list) and capability in caps):
                return True
        return False
    if mechanism_type == "internalComponent":
        criteria = mechanism.get("criteria", {})
        capability = criteria.get("capability") or criteria.get("concern")
        role = criteria.get("role")
        classification = criteria.get("classification")
        if capability:
            for abb in referenced_technology_components(obj, catalog_by_id):
                if classification and abb.get("classification") != classification:
                    continue
                caps = abb.get("capabilities", [])
                if isinstance(caps, list) and capability in caps:
                    return True
            return False
        return any(
            isinstance(component, dict) and component.get("role") == role
            for component in obj.get("internalComponents", [])
        )
    if mechanism_type == "technologyComponentConfiguration":
        capability = mechanism.get("criteria", {}).get("capability") or mechanism.get("criteria", {}).get("concern")
        classification = mechanism.get("criteria", {}).get("classification")
        for abb in referenced_technology_components(obj, catalog_by_id):
            if classification and abb.get("classification") != classification:
                continue
            configurations = abb.get("configurations", [])
            if not isinstance(configurations, list):
                continue
            for configuration in configurations:
                if not isinstance(configuration, dict):
                    continue
                caps = configuration.get("capabilities", [])
                if isinstance(caps, list) and capability in caps:
                    return True
        return False
    if mechanism_type == "architecturalDecision":
        key = mechanism.get("key", "")
        decisions = obj.get("architecturalDecisions", {})
        if isinstance(decisions, dict):
            value = get_nested_value(decisions, key)
            if is_non_empty(value):
                return True
        return False
    if mechanism_type == "deploymentConfiguration":
        quality = mechanism.get("criteria", {}).get("quality")
        configurations = obj.get("deploymentConfigurations", [])
        if not isinstance(configurations, list):
            return False
        for configuration in configurations:
            if not isinstance(configuration, dict):
                continue
            qualities = configuration.get("addressesQualities", [])
            if isinstance(qualities, list) and quality in qualities:
                return True
        return False
    return False


def validate_requirement(
    obj: dict[str, Any],
    requirement: dict[str, Any],
    group_id: str,
    catalog_by_id: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    requirement_id = requirement.get("id", "unknown")
    valid_answer_types = requirement.get("validAnswerTypes", [])
    for implementation in obj.get("requirementImplementations", []) or []:
        if not isinstance(implementation, dict):
            continue
        if implementation.get("requirementGroup") != group_id or implementation.get("requirementId") != requirement_id:
            continue
        status = implementation.get("status")
        if status == "not-applicable" and requirement.get("naAllowed") is True:
            return True, ""
        mechanism = implementation.get("mechanism")
        if (
            status == "satisfied"
            and mechanism in valid_answer_types
            and implementation_resolves(obj, implementation, catalog_by_id)
        ):
            return True, ""

    mechanisms = requirement.get("canBeSatisfiedBy", [])
    minimum = int(requirement.get("minimumSatisfactions", 1))
    satisfied = [mechanism for mechanism in mechanisms if mechanism_satisfied(obj, mechanism, catalog_by_id)]
    if len(satisfied) >= minimum:
        return True, ""

    related = requirement.get("relatedCapability")
    mechanism_text = " or ".join(mechanism_description(mechanism) for mechanism in mechanisms)
    if minimum > 1:
        mechanism_text = f"at least {minimum} of {mechanism_text}"
    related_text = f" — see capability {related} for approved implementations" if related else ""
    group = catalog_by_id.get(group_id, {})
    label = requirement_display_label(group, requirement)
    source = str(group.get("name") or group_id)
    return (
        False,
        f"[{object_label(obj)}] Satisfy {label} from {source} using {mechanism_text}{related_text}",
    )


def applicable_requirements_for_object(
    obj: dict[str, Any],
    requirement_groups: dict[str, dict[str, Any]],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    requirements: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for group_id in applicable_requirement_group_ids(
        obj,
        requirement_groups,
        active_group_ids,
        require_active_group_disposition,
    ):
        group = requirement_groups[group_id]
        try:
            resolved_requirements = resolve_requirement_group_requirements(group_id, requirement_groups)
        except (KeyError, ValueError):
            continue
        for requirement in resolved_requirements:
            if isinstance(requirement, dict) and requirement_applies_to_object(requirement, obj):
                requirements.append((group_id, group, requirement))
    return requirements


def interaction_capabilities(interaction: dict[str, Any]) -> list[str]:
    capabilities = interaction.get("capabilities", [])
    return [str(capability) for capability in capabilities] if isinstance(capabilities, list) else []


def technology_ref_satisfies_criteria(
    ref: str,
    criteria: dict[str, Any],
    catalog_by_id: dict[str, dict[str, Any]],
) -> bool:
    target = catalog_by_id.get(ref)
    if not target or target.get("type") != "technology_component":
        return False
    classification = criteria.get("classification")
    if classification and target.get("classification") != classification:
        return False
    capability = criteria.get("capability") or criteria.get("concern")
    if capability:
        caps = target.get("capabilities", [])
        return isinstance(caps, list) and capability in caps
    return True


def technology_ref_configuration_satisfies_criteria(
    ref: str,
    criteria: dict[str, Any],
    catalog_by_id: dict[str, dict[str, Any]],
) -> bool:
    target = catalog_by_id.get(ref)
    if not target or target.get("type") != "technology_component":
        return False
    classification = criteria.get("classification")
    if classification and target.get("classification") != classification:
        return False
    capability = criteria.get("capability") or criteria.get("concern")
    configurations = target.get("configurations", [])
    if not isinstance(configurations, list):
        return False
    for configuration in configurations:
        if not isinstance(configuration, dict):
            continue
        caps = configuration.get("capabilities", [])
        if isinstance(caps, list) and capability in caps:
            return True
    return False


def external_interaction_satisfies_mechanism(interaction: dict[str, Any], mechanism: dict[str, Any]) -> bool:
    if mechanism.get("mechanism") != "externalInteraction":
        return False
    capability = mechanism.get("criteria", {}).get("capability")
    if capability == "any":
        return True
    return bool(capability and capability in interaction_capabilities(interaction))


def internal_component_satisfies_mechanism(
    obj: dict[str, Any],
    component: dict[str, Any],
    mechanism: dict[str, Any],
    catalog_by_id: dict[str, dict[str, Any]],
) -> bool:
    ref = component.get("ref")
    if not is_non_empty(ref):
        return False
    ref = str(ref)
    mechanism_type = mechanism.get("mechanism")
    if mechanism_type == "field":
        key = mechanism.get("key")
        return is_non_empty(key) and obj.get(str(key)) == ref
    if mechanism_type == "technologyComponent":
        expected_ref = mechanism.get("ref")
        if expected_ref and expected_ref != ref:
            return False
        criteria = mechanism.get("criteria", {}) if isinstance(mechanism.get("criteria"), dict) else {}
        return technology_ref_satisfies_criteria(ref, criteria, catalog_by_id)
    if mechanism_type == "internalComponent":
        criteria = mechanism.get("criteria", {}) if isinstance(mechanism.get("criteria"), dict) else {}
        role = criteria.get("role")
        if role and component.get("role") == role:
            return True
        return technology_ref_satisfies_criteria(ref, criteria, catalog_by_id)
    if mechanism_type == "technologyComponentConfiguration":
        criteria = mechanism.get("criteria", {}) if isinstance(mechanism.get("criteria"), dict) else {}
        return technology_ref_configuration_satisfies_criteria(ref, criteria, catalog_by_id)
    if mechanism_type == "externalInteraction":
        interactions = obj.get("externalInteractions", [])
        if not isinstance(interactions, list):
            return False
        return any(
            isinstance(interaction, dict)
            and interaction.get("enabledBy") == ref
            and external_interaction_satisfies_mechanism(interaction, mechanism)
            for interaction in interactions
        )
    return False


def external_interaction_satisfies_implementation(interaction: dict[str, Any], implementation: dict[str, Any]) -> bool:
    if implementation.get("status") != "satisfied" or implementation.get("mechanism") != "externalInteraction":
        return False
    ref = implementation.get("ref")
    caps = interaction_capabilities(interaction)
    if ref and ref in {interaction.get("ref"), interaction.get("name"), *caps}:
        return True
    criteria = implementation.get("criteria", {}) if isinstance(implementation.get("criteria"), dict) else {}
    capabilities = criteria.get("capabilities") or ([criteria.get("capability")] if criteria.get("capability") else [])
    return bool(capabilities and any(capability in caps for capability in capabilities))


def internal_component_satisfies_implementation(
    obj: dict[str, Any],
    component: dict[str, Any],
    implementation: dict[str, Any],
    catalog_by_id: dict[str, dict[str, Any]],
) -> bool:
    if implementation.get("status") != "satisfied":
        return False
    ref = component.get("ref")
    if not is_non_empty(ref):
        return False
    ref = str(ref)
    mechanism = implementation.get("mechanism")
    if mechanism == "field":
        key = implementation.get("key")
        return is_non_empty(key) and obj.get(str(key)) == ref
    if mechanism in {"technologyComponent", "internalComponent"}:
        if implementation.get("ref") == ref:
            return True
        criteria = implementation.get("criteria", {}) if isinstance(implementation.get("criteria"), dict) else {}
        return technology_ref_satisfies_criteria(ref, criteria, catalog_by_id)
    if mechanism == "technologyComponentConfiguration":
        if implementation.get("ref") and implementation.get("ref") != ref:
            return False
        criteria = implementation.get("criteria", {}) if isinstance(implementation.get("criteria"), dict) else {}
        return technology_ref_configuration_satisfies_criteria(ref, criteria, catalog_by_id)
    if mechanism == "externalInteraction":
        interactions = obj.get("externalInteractions", [])
        if not isinstance(interactions, list):
            return False
        return any(
            isinstance(interaction, dict)
            and interaction.get("enabledBy") == ref
            and external_interaction_satisfies_implementation(interaction, implementation)
            for interaction in interactions
        )
    return False


def entry_rationale_candidates(entry: dict[str, Any], context: str, kind: str) -> list[str]:
    candidates = [context]
    for key in ("id", "name", "ref", "enabledBy", "role"):
        value = entry.get(key)
        if is_non_empty(value):
            candidates.append(str(value))
    if kind == "external":
        candidates.extend(interaction_capabilities(entry))
    return list(dict.fromkeys(candidates))


def rationale_bucket_matches(value: Any, candidates: list[str]) -> bool:
    if isinstance(value, dict):
        for candidate in candidates:
            entry = value.get(candidate)
            if entry is True or is_non_empty(entry):
                return True
        return False
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            reason = item.get("reason") or item.get("rationale") or item.get("decision") or item.get("notes")
            if not is_non_empty(reason):
                continue
            item_candidates = {
                str(item_value)
                for item_value in (
                    item.get("id"),
                    item.get("name"),
                    item.get("ref"),
                    item.get("enabledBy"),
                    item.get("role"),
                    item.get("capability"),
                )
                if is_non_empty(item_value)
            }
            capabilities = item.get("capabilities")
            if isinstance(capabilities, list):
                item_candidates.update(str(capability) for capability in capabilities if is_non_empty(capability))
            if item_candidates & set(candidates):
                return True
        return False
    return False


def dependency_rationale_present(obj: dict[str, Any], kind: str, entry: dict[str, Any], context: str) -> bool:
    decisions = obj.get("architecturalDecisions", {})
    if not isinstance(decisions, dict):
        return False
    candidates = entry_rationale_candidates(entry, context, kind)
    bucket_names = (
        ("externalInteractionRationales", "dependencyRationales")
        if kind == "external"
        else ("internalComponentRationales", "dependencyRationales")
    )
    return any(rationale_bucket_matches(decisions.get(bucket_name), candidates) for bucket_name in bucket_names)


def dependency_rationale_guidance(kind: str, entry: dict[str, Any], context: str) -> str:
    bucket = "externalInteractionRationales" if kind == "external" else "internalComponentRationales"
    key = entry.get("name") or entry.get("ref") or entry.get("enabledBy") or entry.get("role") or context
    return f"architecturalDecisions.{bucket}[{key!r}]"


def validate_unrequired_dependency_rationales(
    obj: dict[str, Any],
    path: Path,
    requirement_groups: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, dict[str, Any]],
    failures: list[str],
    warnings: list[str],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> None:
    applicable_requirements = applicable_requirements_for_object(
        obj,
        requirement_groups,
        active_group_ids,
        require_active_group_disposition,
    )
    implementations = [
        implementation
        for implementation in obj.get("requirementImplementations", []) or []
        if isinstance(implementation, dict)
    ]

    interactions = obj.get("externalInteractions", [])
    if isinstance(interactions, list):
        for index, interaction in enumerate(interactions):
            if not isinstance(interaction, dict):
                continue
            context = f"externalInteractions[{index}]"
            satisfies_requirement = any(
                external_interaction_satisfies_mechanism(interaction, mechanism)
                for _, _, requirement in applicable_requirements
                for mechanism in requirement.get("canBeSatisfiedBy", []) or []
                if isinstance(mechanism, dict)
            ) or any(external_interaction_satisfies_implementation(interaction, implementation) for implementation in implementations)
            if satisfies_requirement or dependency_rationale_present(obj, "external", interaction, context):
                continue
            record_requirement_gap(
                obj,
                path,
                f"[{object_label(obj)}] Add {dependency_rationale_guidance('external', interaction, context)} "
                f"to explain why {context} is modeled, or update it to satisfy a specific applicable requirement; "
                "it does not directly satisfy any applicable requirement",
                failures,
                warnings,
            )

    components = obj.get("internalComponents", [])
    if isinstance(components, list):
        for index, component in enumerate(components):
            if not isinstance(component, dict):
                continue
            context = f"internalComponents[{index}]"
            satisfies_requirement = any(
                internal_component_satisfies_mechanism(obj, component, mechanism, catalog_by_id)
                for _, _, requirement in applicable_requirements
                for mechanism in requirement.get("canBeSatisfiedBy", []) or []
                if isinstance(mechanism, dict)
            ) or any(internal_component_satisfies_implementation(obj, component, implementation, catalog_by_id) for implementation in implementations)
            if satisfies_requirement or dependency_rationale_present(obj, "internal", component, context):
                continue
            ref = component.get("ref")
            enabled_interaction_has_rationale = (
                is_non_empty(ref)
                and isinstance(interactions, list)
                and any(
                    isinstance(interaction, dict)
                    and interaction.get("enabledBy") == ref
                    and dependency_rationale_present(obj, "external", interaction, f"externalInteractions[{interaction_index}]")
                    for interaction_index, interaction in enumerate(interactions)
                )
            )
            if enabled_interaction_has_rationale:
                continue
            record_requirement_gap(
                obj,
                path,
                f"[{object_label(obj)}] Add {dependency_rationale_guidance('internal', component, context)} "
                f"to explain why {context} is modeled, or update it to satisfy a specific applicable requirement; "
                "it does not directly satisfy any applicable requirement",
                failures,
                warnings,
            )


def validate_against_schema(obj: dict[str, Any], path: Path, schemas: list[dict[str, Any]], failures: list[str]) -> None:
    schema = select_schema(obj, schemas)
    if schema is None:
        failures.append(f"{path}: no schema found for type '{obj.get('type')}'")
        return
    validate_schema_section(obj, schema, str(path), failures)


def record_requirement_gap(
    obj: dict[str, Any],
    path: Path,
    message: str,
    failures: list[str],
    warnings: list[str],
) -> None:
    entry = f"{path}: {message}"
    if obj.get("catalogStatus") == "approved":
        failures.append(entry)
    else:
        warnings.append(entry)


def approved_or_preferred_object(obj: dict[str, Any]) -> bool:
    return obj.get("catalogStatus") == "approved" or obj.get("lifecycleStatus") == "preferred"


def valid_values_text(vocabulary: dict[str, Any]) -> str:
    approved_ids = sorted(vocabulary.get("approved_ids") or [])
    if not approved_ids:
        return "no approved values are declared"
    return ", ".join(approved_ids)


def record_vocabulary_issue(
    vocabulary: dict[str, Any],
    obj: dict[str, Any],
    path: Path,
    field_path: str,
    value: str,
    message: str,
    failures: list[str],
    warnings: list[str],
    fail_when_gated: bool = True,
) -> None:
    entry = f"{path}: [{object_label(obj)}] {field_path} {message}; found '{value}'. Approved values: {valid_values_text(vocabulary)}"
    if vocabulary.get("mode") == "gated" and fail_when_gated:
        failures.append(entry)
    else:
        warnings.append(entry)


def validate_vocabulary_value(
    obj: dict[str, Any],
    path: Path,
    field_path: str,
    raw_value: Any,
    vocabulary: dict[str, Any] | None,
    failures: list[str],
    warnings: list[str],
) -> None:
    if not vocabulary or raw_value is None:
        return
    value = str(raw_value).strip()
    if not value:
        return
    if value in vocabulary.get("sentinels", set()):
        record_vocabulary_issue(
            vocabulary,
            obj,
            path,
            field_path,
            value,
            "is an interview-required value that must be revisited before approval",
            failures,
            warnings,
            fail_when_gated=approved_or_preferred_object(obj),
        )
        return

    values = vocabulary.get("values") or {}
    if value in vocabulary.get("approved_ids", set()):
        return
    if value in values:
        status = str(values[value].get("status") or "approved")
        record_vocabulary_issue(
            vocabulary,
            obj,
            path,
            field_path,
            value,
            f"uses a {status} standard value, not an approved standard value",
            failures,
            warnings,
        )
        return

    record_vocabulary_issue(
        vocabulary,
        obj,
        path,
        field_path,
        value,
        "uses a non-standard value",
        failures,
        warnings,
    )


def validate_workspace_vocabulary_references(
    objects: dict[Path, dict[str, Any]],
    workspace_vocabulary: dict[str, dict[str, Any]],
    failures: list[str],
    warnings: list[str],
) -> None:
    team_vocabulary = workspace_vocabulary.get("teams")
    deployment_vocabulary = workspace_vocabulary.get("deploymentTargets")
    data_vocabulary = workspace_vocabulary.get("dataClassificationLevels")
    availability_vocabulary = workspace_vocabulary.get("availabilityTiers")
    failure_vocabulary = workspace_vocabulary.get("failureDomains")
    connection_protocol_vocabulary = workspace_vocabulary.get("connectionProtocols")
    network_zone_vocabulary = workspace_vocabulary.get("networkZones")
    deployable_or_pattern_types = STANDARD_TYPES | {"software_deployment_pattern"}

    for path, obj in objects.items():
        if not isinstance(obj, dict) or obj.get("type") in WORKSPACE_DOCUMENT_TYPES:
            continue

        owner = obj.get("owner")
        if isinstance(owner, dict):
            validate_vocabulary_value(
                obj,
                path,
                "owner.team",
                owner.get("team"),
                team_vocabulary,
                failures,
                warnings,
            )

        if obj.get("type") == "software_deployment_pattern":
            network_zones = obj.get("networkZones") or []
            if isinstance(network_zones, list):
                for index, network_zone in enumerate(network_zones):
                    if not isinstance(network_zone, dict):
                        continue
                    validate_vocabulary_value(
                        obj,
                        path,
                        f"networkZones[{index}].id",
                        network_zone.get("id"),
                        network_zone_vocabulary,
                        failures,
                        warnings,
                    )
            service_groups = obj.get("serviceGroups") or []
            if isinstance(service_groups, list):
                for index, service_group in enumerate(service_groups):
                    if not isinstance(service_group, dict):
                        continue
                    validate_vocabulary_value(
                        obj,
                        path,
                        f"serviceGroups[{index}].deploymentTarget",
                        service_group.get("deploymentTarget"),
                        deployment_vocabulary,
                        failures,
                        warnings,
                    )
                    deployable_objects = service_group.get("deployableObjects") or []
                    if isinstance(deployable_objects, list):
                        for object_index, deployable_object in enumerate(deployable_objects):
                            if not isinstance(deployable_object, dict):
                                continue
                            validate_vocabulary_value(
                                obj,
                                path,
                                f"serviceGroups[{index}].deployableObjects[{object_index}].networkZone",
                                deployable_object.get("networkZone"),
                                network_zone_vocabulary,
                                failures,
                                warnings,
                            )
                    connections = service_group.get("connections") or []
                    if isinstance(connections, list):
                        for connection_index, connection in enumerate(connections):
                            if not isinstance(connection, dict):
                                continue
                            validate_vocabulary_value(
                                obj,
                                path,
                                f"serviceGroups[{index}].connections[{connection_index}].protocol",
                                connection.get("protocol"),
                                connection_protocol_vocabulary,
                                failures,
                                warnings,
                            )

        if obj.get("type") not in deployable_or_pattern_types:
            continue
        decisions = obj.get("architecturalDecisions") or {}
        if not isinstance(decisions, dict):
            continue
        validate_vocabulary_value(
            obj,
            path,
            "architecturalDecisions.dataClassification",
            decisions.get("dataClassification"),
            data_vocabulary,
            failures,
            warnings,
        )
        validate_vocabulary_value(
            obj,
            path,
            "architecturalDecisions.availabilityRequirement",
            decisions.get("availabilityRequirement"),
            availability_vocabulary,
            failures,
            warnings,
        )
        validate_vocabulary_value(
            obj,
            path,
            "architecturalDecisions.failureDomain",
            decisions.get("failureDomain"),
            failure_vocabulary,
            failures,
            warnings,
        )


def validate_vocabulary_document(obj: dict[str, Any], path: Path, failures: list[str], warnings: list[str]) -> None:
    vocabulary_key = str(obj.get("vocabulary") or "").strip()
    if vocabulary_key not in VOCABULARY_DEFINITIONS:
        failures.append(f"{path}: Set vocabulary to one of {sorted(VOCABULARY_DEFINITIONS)}")
        return
    values_by_id: dict[str, dict[str, Any]] = {}
    collect_vocabulary_values(obj.get("values"), f"{path}", vocabulary_key, values_by_id, failures, warnings)


def validate_vocabulary_proposal(
    obj: dict[str, Any],
    path: Path,
    workspace_vocabulary: dict[str, dict[str, Any]],
    failures: list[str],
    warnings: list[str],
) -> None:
    vocabulary_key = str(obj.get("vocabulary") or "").strip()
    if vocabulary_key not in VOCABULARY_DEFINITIONS:
        failures.append(f"{path}: Set vocabulary to one of {sorted(VOCABULARY_DEFINITIONS)}")
        return
    proposed_id = str(obj.get("proposedId") or "").strip()
    if not proposed_id:
        failures.append(f"{path}: Add proposedId for the proposed standard value")
    if not is_non_empty(obj.get("proposedName")):
        failures.append(f"{path}: Add proposedName for the proposed standard value")
    status = str(obj.get("status") or "proposed").strip()
    if status not in {"draft", "proposed", "submitted", "accepted", "rejected"}:
        failures.append(f"{path}: Set status to draft, proposed, submitted, accepted, or rejected")
    field_refs = obj.get("fieldRefs") or []
    if field_refs and not isinstance(field_refs, list):
        failures.append(f"{path}: Change fieldRefs to a list")
    if proposed_id:
        vocabulary = workspace_vocabulary.get(vocabulary_key)
        values = vocabulary.get("values", {}) if vocabulary else {}
        if proposed_id in values and str(values[proposed_id].get("status") or "approved") == "approved":
            warnings.append(f"{path}: proposedId '{proposed_id}' is already an approved {vocabulary_key} value")


def validate_architectural_decisions(obj: dict[str, Any], path: Path, failures: list[str]) -> None:
    decision_sets: list[dict[str, Any]] = []
    direct_decisions = obj.get("architecturalDecisions", {})
    if isinstance(direct_decisions, dict) and direct_decisions:
        decision_sets.append(direct_decisions)

    for decisions in decision_sets:
        for key, allowed_values in DECISION_ENUMS.items():
            if key in decisions and decisions[key] not in allowed_values:
                allowed_text = ", ".join(sorted(allowed_values))
                failures.append(
                    f'{path}: [{object_label(obj)}] architecturalDecisions.{key} must be one of: '
                    f'{allowed_text} — got "{decisions[key]}"'
                )

        if "minNodes" in decisions and not isinstance(decisions["minNodes"], int):
            failures.append(
                f'{path}: [{object_label(obj)}] architecturalDecisions.minNodes must be an integer — '
                f'got "{decisions["minNodes"]}"'
            )


def validate_external_interaction_refs(
    obj: dict[str, Any],
    path: Path,
    catalog_by_id: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    interactions = obj.get("externalInteractions", [])
    if not isinstance(interactions, list):
        return
    for index, interaction in enumerate(interactions):
        if not isinstance(interaction, dict):
            continue
        ref = interaction.get("ref")
        if ref and ref not in catalog_by_id:
            failures.append(
                f"{path}: externalInteractions[{index}].ref references unknown object '{ref}' — "
                "model the interacted platform as a Host, Runtime Service, Data-at-Rest Service, Edge/Gateway Service, Product Service, or Technology Component, "
                "or remove ref until the target object exists"
            )


def technology_configuration_ids(obj: dict[str, Any]) -> set[str]:
    configurations = obj.get("configurations", [])
    if not isinstance(configurations, list):
        return set()
    return {
        str(configuration.get("id"))
        for configuration in configurations
        if isinstance(configuration, dict) and is_non_empty(configuration.get("id"))
    }


def validate_internal_component_configuration_refs(
    obj: dict[str, Any],
    path: Path,
    catalog_by_id: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    components = obj.get("internalComponents", [])
    if not isinstance(components, list):
        return
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            continue
        configuration = component.get("configuration")
        if not is_non_empty(configuration):
            continue
        ref = component.get("ref")
        target = catalog_by_id.get(str(ref)) if is_non_empty(ref) else None
        if not target or target.get("type") != "technology_component":
            failures.append(
                f"{path}: internalComponents[{index}].configuration requires ref to an existing Technology Component; "
                f"'{ref or 'missing'}' was not found as a Technology Component"
            )
            continue
        if str(configuration) not in technology_configuration_ids(target):
            failures.append(
                f"{path}: internalComponents[{index}].configuration references unknown configuration "
                f"'{configuration}' on Technology Component '{ref}'"
            )


def validate_product_service_architecture_refs(
    obj: dict[str, Any],
    path: Path,
    failures: list[str],
) -> None:
    if obj.get("type") != "product_service":
        return
    processes = obj.get("internalProcesses", [])
    process_names: set[str] = set()
    duplicate_names: set[str] = set()
    if isinstance(processes, list):
        for process in processes:
            if not isinstance(process, dict) or not is_non_empty(process.get("name")):
                continue
            name = str(process["name"])
            if name in process_names:
                duplicate_names.add(name)
            process_names.add(name)
    for name in sorted(duplicate_names):
        failures.append(f"{path}: internalProcesses contains duplicate process name '{name}'")

    endpoints = obj.get("apiEndpoints", [])
    if not isinstance(endpoints, list):
        return
    for index, endpoint in enumerate(endpoints):
        if not isinstance(endpoint, dict):
            continue
        exposed_by = endpoint.get("exposedBy")
        if is_non_empty(exposed_by) and str(exposed_by) not in process_names:
            failures.append(
                f"{path}: apiEndpoints[{index}].exposedBy references unknown internal process '{exposed_by}'"
            )


def validate_component(
    obj: dict[str, Any],
    path: Path,
    requirement_groups: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, dict[str, Any]],
    capability_ids: set[str],
    failures: list[str],
    warnings: list[str],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> None:
    classification = obj.get("classification")
    if classification not in VALID_TECHNOLOGY_COMPONENT_CLASSIFICATIONS:
        failures.append(
            f"{path}: Set Technology Component classification to one of {sorted(VALID_TECHNOLOGY_COMPONENT_CLASSIFICATIONS)}"
        )
    capabilities = obj.get("capabilities", [])
    if capabilities is not None:
        if not isinstance(capabilities, list):
            failures.append(f"{path}: Change capabilities to a list of capability IDs")
        else:
            invalid = [cap for cap in capabilities if cap not in capability_ids]
            if invalid:
                failures.append(
                    f"{path}: Replace invalid capability references {invalid} with capability object UIDs from configurations/capabilities"
                )
    configurations = obj.get("configurations", [])
    if configurations is not None:
        if not isinstance(configurations, list):
            failures.append(f"{path}: Change configurations to a list")
        else:
            for index, configuration in enumerate(configurations):
                if not isinstance(configuration, dict):
                    failures.append(f"{path}: Change configurations[{index}] to a mapping")
                    continue
                config_caps = configuration.get("capabilities", [])
                if not isinstance(config_caps, list):
                    failures.append(f"{path}: Change configurations[{index}].capabilities to a list of capability IDs")
                    continue
                invalid = [cap for cap in config_caps if cap not in capability_ids]
                if invalid:
                    failures.append(
                        f"{path}: Replace invalid configuration capability references {invalid} with capability object UIDs from configurations/capabilities"
                    )

    validate_applicable_requirements(
        obj,
        path,
        requirement_groups,
        catalog_by_id,
        capability_ids,
        failures,
        warnings,
        active_group_ids,
        require_active_group_disposition,
    )


def agent_interaction_exception(obj: dict[str, Any], abb_id: str) -> bool:
    decisions = obj.get("architecturalDecisions", {})
    if not isinstance(decisions, dict):
        return False
    exceptions = decisions.get("agentInteractionExceptions")
    if isinstance(exceptions, list):
        return abb_id in exceptions
    if isinstance(exceptions, dict):
        value = exceptions.get(abb_id)
        return is_non_empty(value) or value is True
    return False


def has_enabled_external_interaction(obj: dict[str, Any], abb_id: str) -> bool:
    interactions = obj.get("externalInteractions", [])
    if not isinstance(interactions, list):
        return False
    return any(
        isinstance(interaction, dict) and interaction.get("enabledBy") == abb_id
        for interaction in interactions
    )


def validate_classified_component_refs(
    obj: dict[str, Any],
    path: Path,
    catalog_by_id: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    def validate_ref(field: str, expected_classification: str | None = None) -> None:
        ref = obj.get(field)
        if not ref:
            return
        target = catalog_by_id.get(ref)
        if not target or target.get("type") != "technology_component":
            return
        target_classification = target.get("classification")
        if expected_classification and target_classification != expected_classification:
            failures.append(
                f"{path}: {field} must reference a Technology Component classified as '{expected_classification}' — got '{target_classification or 'unknown'}'"
            )

    validate_ref("operatingSystemComponent", "operating-system")
    validate_ref("computePlatformComponent", "compute-platform")

    function_ref = obj.get("primaryTechnologyComponent")
    if function_ref:
        target = catalog_by_id.get(function_ref)
        if target and target.get("type") == "technology_component":
            classification = target.get("classification")
            if classification not in {"software", "agent"}:
                failures.append(
                    f"{path}: primaryTechnologyComponent must reference a Technology Component classified as 'software' or 'agent' — got '{classification or 'unknown'}'"
                )

    components = obj.get("internalComponents", [])
    if not isinstance(components, list):
        return
    for component in components:
        if not isinstance(component, dict):
            continue
        ref = component.get("ref")
        if not ref:
            continue
        target = catalog_by_id.get(ref)
        if not target or target.get("type") != "technology_component":
            continue
        if target.get("classification") == "agent":
            if not has_enabled_external_interaction(obj, ref) and not agent_interaction_exception(obj, ref):
                failures.append(
                    f"{path}: agent Technology Component '{ref}' requires an externalInteraction enabledBy that Technology Component or architecturalDecisions.agentInteractionExceptions"
                )


def validate_standard(
    obj: dict[str, Any],
    path: Path,
    requirement_groups: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, dict[str, Any]],
    catalog_ids: set[str],
    capability_ids: set[str],
    failures: list[str],
    warnings: list[str],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> None:
    validate_applicable_requirements(
        obj,
        path,
        requirement_groups,
        catalog_by_id,
        capability_ids,
        failures,
        warnings,
        active_group_ids,
        require_active_group_disposition,
    )

    object_type = obj.get("type")
    if object_type == "host":
        tags = obj.get("tags") or []
        is_managed_host = isinstance(tags, list) and any(tag in {"serverless", "container"} for tag in tags)
        required_host_fields = () if is_managed_host else ("operatingSystemComponent", "computePlatformComponent")
        for field in required_host_fields:
            ref = obj.get(field)
            if ref and ref not in catalog_ids:
                failures.append(f"{path}: {field} references unknown object '{ref}'")
    if object_type in SERVICE_TYPES:
        if obj.get("deliveryModel") == "self-managed":
            for field in ("host", "primaryTechnologyComponent"):
                if not is_non_empty(obj.get(field)):
                    failures.append(f"{path}: {object_type} with deliveryModel self-managed must declare {field}")
        for field in ("host", "primaryTechnologyComponent"):
            ref = obj.get(field)
            if ref and ref not in catalog_ids:
                failures.append(f"{path}: {field} references unknown object '{ref}'")
        host_ref = obj.get("host")
        host_target = catalog_by_id.get(str(host_ref)) if is_non_empty(host_ref) else None
        if host_ref and (not host_target or host_target.get("type") != "host"):
            failures.append(f"{path}: host references unknown Host '{host_ref}'")
    if object_type == "product_service":
        runs_on = obj.get("runsOn")
        target = catalog_by_id.get(runs_on) if runs_on else None
        if runs_on and (not target or target.get("type") not in STANDARD_TYPES):
            failures.append(f"{path}: runsOn references unknown deployable object '{runs_on}'")
    if object_type == "product_component":
        runs_on = obj.get("runsOn")
        target = catalog_by_id.get(runs_on) if runs_on else None
        allowed = {"host", "runtime_service", "edge_gateway_service"}
        if runs_on and (not target or target.get("type") not in allowed):
            failures.append(f"{path}: runsOn must reference a Host, RuntimeService, or EdgeGatewayService (got '{runs_on}')")
    if object_type == "data_component":
        runs_on = obj.get("runsOn")
        target = catalog_by_id.get(runs_on) if runs_on else None
        if runs_on and (not target or target.get("type") != "data_at_rest_service"):
            failures.append(f"{path}: runsOn must reference a DataStoreService (got '{runs_on}')")
    if object_type in SERVICE_TYPES and obj.get("deliveryModel") == "saas":
        if "dataLeavesInfrastructure" in obj and not isinstance(obj.get("dataLeavesInfrastructure"), bool):
            failures.append(f"{path}: dataLeavesInfrastructure must be true or false")
        if obj.get("dataLeavesInfrastructure") is True and not is_non_empty(obj.get("dpaNotes")):
            warnings.append(f"{path}: SaaS-delivered services with dataLeavesInfrastructure=true should document dpaNotes")

    validate_classified_component_refs(obj, path, catalog_by_id, failures)
    deployment_configurations = obj.get("deploymentConfigurations", [])
    if deployment_configurations is not None:
        if not isinstance(deployment_configurations, list):
            failures.append(f"{path}: deploymentConfigurations must be a list")
        else:
            for index, configuration in enumerate(deployment_configurations):
                if not isinstance(configuration, dict):
                    failures.append(f"{path}: deploymentConfigurations[{index}] must be a mapping")
                    continue
                qualities = configuration.get("addressesQualities", [])
                if qualities is not None:
                    if not isinstance(qualities, list):
                        failures.append(f"{path}: deploymentConfigurations[{index}].addressesQualities must be a list")
                    else:
                        invalid = [quality for quality in qualities if quality not in VALID_DEPLOYMENT_QUALITIES]
                        if invalid:
                            failures.append(
                                f"{path}: deploymentConfigurations[{index}].addressesQualities contains invalid values {invalid}"
                            )
    validate_architectural_decisions(obj, path, failures)


def validate_ra(
    obj: dict[str, Any],
    path: Path,
    requirement_groups: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, dict[str, Any]],
    capability_ids: set[str],
    failures: list[str],
    warnings: list[str],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> None:
    validate_applicable_requirements(
        obj,
        path,
        requirement_groups,
        catalog_by_id,
        capability_ids,
        failures,
        warnings,
        active_group_ids,
        require_active_group_disposition,
    )

    object_id = object_label(obj)
    expired_technologies, extended_support_technologies = vendor_lifecycle_risk_technologies(obj, catalog_by_id)
    if expired_technologies and obj.get("lifecycleStatus") != "deprecated":
        details = ", ".join(f"{ref} extendedSupportEnd {support_end.isoformat()}" for ref, support_end in expired_technologies)
        failures.append(
            f"{path}: Set lifecycleStatus: deprecated on Reference Architecture '{object_id}' because it includes end-of-support Technology Components: {details}"
        )
    if extended_support_technologies and obj.get("lifecycleStatus") == "preferred":
        details = ", ".join(
            f"{ref} mainstreamSupportEnd {mainstream_end.isoformat()}"
            + (f", extendedSupportEnd {support_end.isoformat()}" if support_end else ", extendedSupportEnd not declared")
            for ref, mainstream_end, support_end in extended_support_technologies
        )
        failures.append(
            f"{path}: Set lifecycleStatus: deprecated by default, or existing-only with architecturalDecisions.lifecycleRationale, on Reference Architecture '{object_id}' because it includes Technology Components in extended support: {details}"
        )
    if extended_support_technologies and obj.get("lifecycleStatus") == "existing-only":
        decisions = obj.get("architecturalDecisions") or {}
        if not isinstance(decisions, dict) or not is_non_empty(decisions.get("lifecycleRationale")):
            details = ", ".join(f"{ref} mainstreamSupportEnd {mainstream_end.isoformat()}" for ref, mainstream_end, _ in extended_support_technologies)
            failures.append(
                f"{path}: Add architecturalDecisions.lifecycleRationale to explain why Reference Architecture '{object_id}' remains existing-only while these Technology Components are in extended support: {details}"
            )

    if not is_non_empty(obj.get("patternType")):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add patternType to satisfy requirement-group.reference-architecture requirement 'pattern-type'",
            failures,
            warnings,
        )

    service_groups = obj.get("serviceGroups", [])
    if not isinstance(service_groups, list) or not service_groups:
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add serviceGroups with tiered deployableObjects entries to satisfy requirement-group.reference-architecture requirement 'service-groups'",
            failures,
            warnings,
        )
    else:
        groups_without_deployables = [
            group.get("name", "unknown")
            for group in service_groups
            if isinstance(group, dict) and not isinstance(group.get("deployableObjects"), list)
        ]
        if groups_without_deployables:
            record_requirement_gap(
                obj,
                path,
                f"[{object_id}] Add deployableObjects to every service group to satisfy requirement-group.reference-architecture requirement 'service-groups' (missing on: {', '.join(groups_without_deployables)})",
                failures,
                warnings,
            )

    if not is_non_empty(obj.get("architecturalDecisions")):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add architecturalDecisions to satisfy requirement-group.reference-architecture requirement 'deployment-qualities'",
            failures,
            warnings,
        )


def validate_software_deployment_pattern(
    obj: dict[str, Any],
    path: Path,
    requirement_groups: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, dict[str, Any]],
    capability_ids: set[str],
    business_taxonomy: dict[str, Any],
    failures: list[str],
    warnings: list[str],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> None:
    validate_applicable_requirements(
        obj,
        path,
        requirement_groups,
        catalog_by_id,
        capability_ids,
        failures,
        warnings,
        active_group_ids,
        require_active_group_disposition,
    )
    validate_software_deployment_business_context(obj, path, business_taxonomy, failures)

    object_id = object_label(obj)
    if not is_non_empty(obj.get("followsReferenceArchitecture")) and not is_non_empty(obj.get("architecturalDecisions", {}).get("noApplicablePattern") if isinstance(obj.get("architecturalDecisions"), dict) else None):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add followsReferenceArchitecture or architecturalDecisions.noApplicablePattern to satisfy requirement-group.software-deployment-pattern requirement 'reference-architecture-conformance'",
            failures,
            warnings,
        )

    service_groups = obj.get("serviceGroups", [])
    if not isinstance(service_groups, list):
        service_groups = []

    if not service_groups:
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add serviceGroups to satisfy requirement-group.software-deployment-pattern requirement 'service-groups'",
            failures,
            warnings,
        )

    architectural_decisions = obj.get("architecturalDecisions", {})
    if not isinstance(architectural_decisions, dict):
        architectural_decisions = {}

    if not is_non_empty(architectural_decisions.get("deploymentTargets")):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Describe deployment boundary or execution context in architecturalDecisions.deploymentTargets to satisfy DRAFT Software Deployment Pattern / deployment-targets",
            failures,
            warnings,
        )

    if not is_non_empty(architectural_decisions.get("availabilityRequirement")):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add architecturalDecisions.availabilityRequirement to satisfy requirement-group.software-deployment-pattern requirement 'availability-requirement'",
            failures,
            warnings,
        )

    has_additional_interactions = any(
        isinstance(group, dict)
        and isinstance(group.get("externalInteractions"), list)
        and len(group.get("externalInteractions", [])) > 0
        for group in service_groups
    ) or (isinstance(obj.get("externalInteractions"), list) and len(obj.get("externalInteractions", [])) > 0)
    if not has_additional_interactions and not is_non_empty(architectural_decisions.get("noAdditionalInteractions")):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add an external interaction or architecturalDecisions.noAdditionalInteractions to satisfy requirement-group.software-deployment-pattern requirement 'additional-interactions'",
            failures,
            warnings,
        )

    if not is_non_empty(architectural_decisions.get("dataClassification")):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add architecturalDecisions.dataClassification to satisfy requirement-group.software-deployment-pattern requirement 'data-classification'",
            failures,
            warnings,
        )

    if not is_non_empty(architectural_decisions.get("failureDomain")):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add architecturalDecisions.failureDomain to satisfy requirement-group.software-deployment-pattern requirement 'failure-domain'",
            failures,
            warnings,
        )

    if not is_non_empty(architectural_decisions.get("patternDeviations")) and not is_non_empty(architectural_decisions.get("noPatternDeviations")):
        record_requirement_gap(
            obj,
            path,
            f"[{object_id}] Add architecturalDecisions.patternDeviations or noPatternDeviations to satisfy requirement-group.software-deployment-pattern requirement 'pattern-deviations'",
            failures,
            warnings,
        )


def validate_decision_record(obj: dict[str, Any], path: Path, failures: list[str], warnings: list[str]) -> None:
    if obj.get("category") == "decision" and not is_non_empty(obj.get("decisionRationale")):
        warnings.append(f"{path}: decision Decision Records should include decisionRationale")


def validate_drafting_session(
    obj: dict[str, Any],
    path: Path,
    workspace_root: Path,
    requirement_groups: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, dict[str, Any]],
    capability_ids: set[str],
    failures: list[str],
    warnings: list[str],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> None:
    if "primaryObjectId" in obj:
        failures.append(
            f"{path}: Rename legacy field primaryObjectId to primaryObjectUid. Repair command: {repair_file_command(workspace_root, path)}"
        )
    validate_applicable_requirements(
        obj,
        path,
        requirement_groups,
        catalog_by_id,
        capability_ids,
        failures,
        warnings,
        active_group_ids,
        require_active_group_disposition,
    )

    primary_object_uid = obj.get("primaryObjectUid")
    if primary_object_uid and primary_object_uid not in catalog_by_id:
        failures.append(f"{path}: primaryObjectUid references unknown object '{primary_object_uid}'")

    generated_objects = obj.get("generatedObjects", [])
    if isinstance(generated_objects, list):
        for index, entry in enumerate(generated_objects):
            if not isinstance(entry, dict):
                continue
            if "proposedId" in entry:
                failures.append(
                    f"{path}: Rename generatedObjects[{index}].proposedId to proposedUid. Repair command: {repair_file_command(workspace_root, path)}"
                )
            ref = entry.get("ref")
            proposed_uid = entry.get("proposedUid")
            if not is_non_empty(ref) and not is_non_empty(proposed_uid):
                failures.append(f"{path}: generatedObjects[{index}] must declare either ref or proposedUid")
            if ref and ref not in catalog_by_id:
                failures.append(f"{path}: generatedObjects[{index}] references unknown object '{ref}'")

    for field_name in ("unresolvedQuestions", "assumptions", "nextSteps"):
        entries = obj.get(field_name, [])
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            related_objects = entry.get("relatedObjects", [])
            if not isinstance(related_objects, list):
                continue
            for ref_index, ref_entry in enumerate(related_objects):
                if not isinstance(ref_entry, dict):
                    continue
                ref = ref_entry.get("ref")
                if ref and ref not in catalog_by_id:
                    failures.append(
                        f"{path}: {field_name}[{index}].relatedObjects[{ref_index}] references unknown object '{ref}'"
                    )


def object_scope(obj: dict[str, Any]) -> str | None:
    object_type = obj.get("type")
    if object_type in VALID_REQUIREMENT_SCOPES:
        return str(object_type)
    return None


def find_external_interaction(obj: dict[str, Any], implementation: dict[str, Any]) -> bool:
    interactions = obj.get("externalInteractions", [])
    if not isinstance(interactions, list):
        return False
    ref = implementation.get("ref")
    criteria = implementation.get("criteria", {}) if isinstance(implementation.get("criteria"), dict) else {}
    capabilities = criteria.get("capabilities") or ([criteria.get("capability")] if criteria.get("capability") else [])
    for interaction in interactions:
        if not isinstance(interaction, dict):
            continue
        interaction_caps = interaction.get("capabilities", [])
        if ref and ref in {interaction.get("ref"), interaction.get("name")} | set(interaction_caps):
            return True
        if capabilities and any(cap in interaction_caps for cap in capabilities):
            return True
    return False


def find_deployment_configuration(obj: dict[str, Any], implementation: dict[str, Any]) -> bool:
    configurations = obj.get("deploymentConfigurations", [])
    if not isinstance(configurations, list):
        return False
    key = implementation.get("key")
    ref = implementation.get("ref")
    criteria = implementation.get("criteria", {}) if isinstance(implementation.get("criteria"), dict) else {}
    quality = criteria.get("quality")
    for configuration in configurations:
        if not isinstance(configuration, dict):
            continue
        if key and key in {configuration.get("id"), configuration.get("name")}:
            return True
        if ref and ref in {configuration.get("id"), configuration.get("name")}:
            return True
        qualities = configuration.get("addressesQualities", [])
        if quality and isinstance(qualities, list) and quality in qualities:
            return True
    return False


def find_technology_component_reference(obj: dict[str, Any], implementation: dict[str, Any], catalog_by_id: dict[str, dict[str, Any]]) -> bool:
    ref = implementation.get("ref")
    if not is_non_empty(ref):
        return False
    if obj.get("operatingSystemComponent") == ref or obj.get("computePlatformComponent") == ref or obj.get("primaryTechnologyComponent") == ref:
        return True
    for component in obj.get("internalComponents", []) or []:
        if isinstance(component, dict) and component.get("ref") == ref:
            return True
    target = catalog_by_id.get(str(ref))
    return bool(target and target.get("type") == "technology_component")


def find_technology_component_configuration(obj: dict[str, Any], implementation: dict[str, Any], catalog_by_id: dict[str, dict[str, Any]]) -> bool:
    ref = implementation.get("ref")
    key = implementation.get("key")
    criteria = implementation.get("criteria", {}) if isinstance(implementation.get("criteria"), dict) else {}
    capability = criteria.get("capability") or criteria.get("concern")
    for abb in referenced_technology_components(obj, catalog_by_id):
        if ref and abb.get("uid") != ref:
            continue
        configurations = abb.get("configurations", [])
        if not isinstance(configurations, list):
            continue
        for configuration in configurations:
            if not isinstance(configuration, dict):
                continue
            if key and key in {configuration.get("id"), configuration.get("name")}:
                return True
            caps = configuration.get("capabilities", [])
            if capability and isinstance(caps, list) and capability in caps:
                return True
    return False


def implementation_resolves(
    obj: dict[str, Any],
    implementation: dict[str, Any],
    catalog_by_id: dict[str, dict[str, Any]],
) -> bool:
    mechanism = implementation.get("mechanism")
    if mechanism == "field":
        key = implementation.get("key")
        return is_non_empty(key) and is_non_empty(get_nested_value(obj, str(key)))
    if mechanism == "architecturalDecision":
        key = implementation.get("key")
        decisions = obj.get("architecturalDecisions", {})
        return is_non_empty(key) and isinstance(decisions, dict) and is_non_empty(get_nested_value(decisions, str(key)))
    if mechanism == "externalInteraction":
        return find_external_interaction(obj, implementation)
    if mechanism == "deploymentConfiguration":
        return find_deployment_configuration(obj, implementation)
    if mechanism == "technologyComponent":
        return find_technology_component_reference(obj, implementation, catalog_by_id)
    if mechanism == "technologyComponentConfiguration":
        return find_technology_component_configuration(obj, implementation, catalog_by_id)
    return False


def collect_requirement_capability_refs(requirement_groups: dict[str, dict[str, Any]]) -> set[str]:
    refs: set[str] = set()
    for group in requirement_groups.values():
        for requirement in group.get("requirements", []) or []:
            if not isinstance(requirement, dict):
                continue
            related_capability = requirement.get("relatedCapability")
            if is_non_empty(related_capability):
                refs.add(str(related_capability))
            for mechanism in requirement.get("canBeSatisfiedBy", []) or []:
                if not isinstance(mechanism, dict):
                    continue
                criteria = mechanism.get("criteria")
                if not isinstance(criteria, dict):
                    continue
                capability = criteria.get("capability") or criteria.get("concern")
                if capability and capability != "any":
                    refs.add(str(capability))
    return refs



def validate_capability(
    obj: dict[str, Any],
    path: Path,
    catalog_by_id: dict[str, dict[str, Any]],
    domain_ids: set[str],
    requirement_capability_refs: set[str],
    failures: list[str],
    warnings: list[str],
) -> None:
    domain_id = obj.get("domain")
    if domain_id not in domain_ids:
        failures.append(f"{path}: Set domain to an existing domain object UID; '{domain_id}' was not found")
    capability_id = obj.get("uid")
    if is_non_empty(capability_id) and capability_id not in requirement_capability_refs:
        message = (
            f"{path}: Add this Capability to at least one Requirement Group before approving it; "
            "approved capabilities must be traceable to a requirement demand signal"
        )
        if obj.get("catalogStatus") == "approved":
            failures.append(message)
        else:
            warnings.append(message)
    implementations = obj.get("implementations", [])
    if not isinstance(implementations, list):
        failures.append(f"{path}: Change implementations to a list of Technology Component mappings")
        return
    owner = obj.get("owner")
    if implementations and not (isinstance(owner, dict) and is_non_empty(owner.get("team"))):
        failures.append(
            f"{path}: Add owner.team before assigning capability implementations; "
            "the company capability owner approves Technology Component lifecycle decisions"
        )
    for index, implementation in enumerate(implementations):
        context = f"{path}: implementations[{index}]"
        if not isinstance(implementation, dict):
            failures.append(f"{context}: Change implementation entry to a mapping")
            continue
        ref = implementation.get("ref")
        target = catalog_by_id.get(str(ref)) if is_non_empty(ref) else None
        if not target or target.get("type") != "technology_component":
            failures.append(f"{context}: Set ref to an existing Technology Component UID; capability lifecycle applies only to discrete vendor product versions")
        lifecycle_status = implementation.get("lifecycleStatus")
        if lifecycle_status not in VALID_IMPLEMENTATION_STATUSES:
            failures.append(
                f"{context}: Set lifecycleStatus to one of {sorted(VALID_IMPLEMENTATION_STATUSES)}"
            )
        configuration = implementation.get("configuration")
        if configuration and target:
            configs = target.get("configurations", [])
            if not any(isinstance(config, dict) and config.get("id") == configuration for config in configs):
                failures.append(
                    f"{context}: Set configuration to a configuration id that exists on Technology Component '{ref}'"
                )


def validate_requirement_group(
    obj: dict[str, Any],
    path: Path,
    capability_ids: set[str],
    failures: list[str],
) -> None:
    activation = obj.get("activation")
    if activation not in VALID_REQUIREMENT_ACTIVATIONS:
        failures.append(f"{path}: Set activation to 'always' or 'workspace'")
    applies_to = obj.get("appliesTo")
    if not isinstance(applies_to, list) or not applies_to:
        failures.append(f"{path}: Add appliesTo with at least one governed object type")
        applies_to = []
    invalid_scopes = [scope for scope in applies_to if scope not in VALID_REQUIREMENT_SCOPES and scope != "drafting_session"]
    if invalid_scopes:
        failures.append(f"{path}: Replace invalid appliesTo values {invalid_scopes} with supported object types")
    requirements = obj.get("requirements")
    if not isinstance(requirements, list):
        failures.append(f"{path}: Change requirements to a list")
        return
    seen: set[str] = set()
    for index, requirement in enumerate(requirements):
        context = f"{path}: requirements[{index}]"
        if not isinstance(requirement, dict):
            failures.append(f"{context}: Change requirement entry to a mapping")
            continue
        requirement_id = requirement.get("id")
        if is_non_empty(requirement_id):
            if str(requirement_id) in seen:
                failures.append(f"{context}: Rename duplicate requirement id '{requirement_id}' so it is unique in this group")
            seen.add(str(requirement_id))
        mode = requirement.get("requirementMode")
        if mode not in VALID_REQUIREMENT_MODES:
            failures.append(f"{context}: Set requirementMode to mandatory or conditional")
        if not isinstance(requirement.get("naAllowed"), bool):
            failures.append(f"{context}: Set naAllowed to true or false")
        related_capability = requirement.get("relatedCapability")
        if is_non_empty(related_capability) and related_capability not in capability_ids:
            failures.append(
                f"{context}: Set relatedCapability to an existing capability object UID; '{related_capability}' was not found"
            )
        requirement_scopes = requirement.get("appliesTo")
        if requirement_scopes is not None:
            if not isinstance(requirement_scopes, list):
                failures.append(f"{context}: Change appliesTo to a list when present")
            else:
                invalid_requirement_scopes = [
                    scope for scope in requirement_scopes if scope not in VALID_REQUIREMENT_SCOPES and scope != "drafting_session"
                ]
                if invalid_requirement_scopes:
                    failures.append(
                        f"{context}: Replace invalid requirement appliesTo values {invalid_requirement_scopes} with supported object types"
                    )
        valid_answer_types = requirement.get("validAnswerTypes")
        if not isinstance(valid_answer_types, list) or not valid_answer_types:
            failures.append(f"{context}: Add validAnswerTypes with at least one satisfaction mechanism")
        else:
            invalid_answer_types = [value for value in valid_answer_types if value not in VALID_REQUIREMENT_ANSWER_TYPES]
            if invalid_answer_types:
                failures.append(
                    f"{context}: Replace invalid validAnswerTypes {invalid_answer_types} with supported mechanisms"
                )
        mechanisms = requirement.get("canBeSatisfiedBy")
        if not isinstance(mechanisms, list) or not mechanisms:
            failures.append(f"{context}: Add canBeSatisfiedBy with at least one satisfaction mechanism")
        else:
            for mechanism_index, mechanism in enumerate(mechanisms):
                mechanism_context = f"{context}: canBeSatisfiedBy[{mechanism_index}]"
                if not isinstance(mechanism, dict):
                    failures.append(f"{mechanism_context}: Change mechanism entry to a mapping")
                    continue
                mechanism_type = mechanism.get("mechanism")
                if mechanism_type not in VALID_REQUIREMENT_ANSWER_TYPES:
                    failures.append(
                        f"{mechanism_context}: Set mechanism to one of {sorted(VALID_REQUIREMENT_ANSWER_TYPES)}"
                    )
                criteria = mechanism.get("criteria")
                if isinstance(criteria, dict):
                    capability = criteria.get("capability") or criteria.get("concern")
                    if capability and capability != "any" and capability not in capability_ids:
                        failures.append(
                            f"{mechanism_context}: Set criteria capability '{capability}' to an existing capability ID"
                        )
        applicability = requirement.get("applicability")
        if applicability is not None:
            validate_applicability_shape(applicability, context, failures)
        elif mode == "conditional":
            failures.append(f"{context}: Add applicability rules for conditional requirements")
        if mode == "conditional" and requirement.get("naAllowed") is not True:
            failures.append(f"{context}: Set naAllowed: true for conditional requirements")


def validate_applicability_shape(applicability: Any, context: str, failures: list[str]) -> None:
    if not isinstance(applicability, dict):
        failures.append(f"{context}: Change applicability to a mapping with anyOf or allOf")
        return
    groups = [key for key in ("anyOf", "allOf") if key in applicability]
    if not groups:
        failures.append(f"{context}: Add applicability.anyOf or applicability.allOf")
        return
    for group in groups:
        clauses = applicability.get(group)
        if not isinstance(clauses, list) or not clauses:
            failures.append(f"{context}: Add at least one applicability.{group} clause")
            continue
        for clause_index, clause in enumerate(clauses):
            clause_context = f"{context}: applicability.{group}[{clause_index}]"
            if not isinstance(clause, dict):
                failures.append(f"{clause_context}: Change clause to a mapping")
                continue
            if not is_non_empty(clause.get("field")):
                failures.append(f"{clause_context}: Add field")
            predicates = [key for key in ("equals", "in", "contains", "truthy") if key in clause]
            if not predicates:
                failures.append(f"{clause_context}: Add equals, in, contains, or truthy")
            if "truthy" in clause and not isinstance(clause.get("truthy"), bool):
                failures.append(f"{clause_context}: Set truthy to true or false")
            if "in" in clause and not isinstance(clause.get("in"), list):
                failures.append(f"{clause_context}: Change in to a list")


def validate_applicable_requirements(
    obj: dict[str, Any],
    path: Path,
    requirement_groups: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, dict[str, Any]],
    capability_ids: set[str],
    failures: list[str],
    warnings: list[str],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> None:
    declared = obj.get("requirementGroups", [])
    if declared is None:
        declared = []
    if not isinstance(declared, list):
        failures.append(f"{path}: Change requirementGroups to a list of requirement_group UIDs")
        declared = []
    declared_group_ids = {str(group_id) for group_id in declared if is_non_empty(group_id)}
    for group_id in sorted(declared_group_ids):
        group = requirement_groups.get(group_id)
        if not group:
            failures.append(f"{path}: Replace unknown requirement group '{group_id}' with an existing requirement_group UID")
        elif group.get("activation") == "workspace" and group_id not in active_group_ids:
            failures.append(
                f"{path}: Activate requirement group '{group_id}' in .draft/workspace.yaml or remove the object claim"
            )

    applicable_group_ids = applicable_requirement_group_ids(
        obj,
        requirement_groups,
        active_group_ids,
        require_active_group_disposition,
    )
    for group_id in applicable_group_ids:
        group = requirement_groups[group_id]
        try:
            requirements = resolve_requirement_group_requirements(group_id, requirement_groups)
        except (KeyError, ValueError) as exc:
            failures.append(f"{path}: Fix requirement group inheritance for '{group_id}' ({exc})")
            continue
        for requirement in requirements:
            if not isinstance(requirement, dict) or not requirement_applies_to_object(requirement, obj):
                continue
            valid, message = validate_requirement(obj, requirement, group_id, catalog_by_id)
            if not valid:
                record_requirement_gap(obj, path, message, failures, warnings)
    validate_requirement_implementations(
        obj,
        path,
        requirement_groups,
        catalog_by_id,
        failures,
        warnings,
        active_group_ids,
        require_active_group_disposition,
    )
    validate_unrequired_dependency_rationales(
        obj,
        path,
        requirement_groups,
        catalog_by_id,
        failures,
        warnings,
        active_group_ids,
        require_active_group_disposition,
    )


def validate_requirement_implementations(
    obj: dict[str, Any],
    path: Path,
    requirement_groups: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, dict[str, Any]],
    failures: list[str],
    warnings: list[str],
    active_group_ids: set[str] | None = None,
    require_active_group_disposition: bool = False,
) -> None:
    scope = object_scope(obj)
    if not scope:
        return
    active_group_ids = active_group_ids or set()
    requirement_groups_field = obj.get("requirementGroups", []) or []
    declared_group_ids = {str(group_id) for group_id in requirement_groups_field} if isinstance(requirement_groups_field, list) else set()

    if require_active_group_disposition:
        missing_active = sorted(
            group_id
            for group_id in active_group_ids
            if group_id not in declared_group_ids
            and requirement_group_applies_to_object(requirement_groups.get(group_id, {}), obj)
        )
        if missing_active:
            record_requirement_gap(
                obj,
                path,
                f"[{object_label(obj)}] Add requirementGroups entries for active requirement groups {missing_active} or record not-applicable dispositions",
                failures,
                warnings,
            )

    implementations = obj.get("requirementImplementations", [])
    if implementations is None:
        implementations = []
    if not isinstance(implementations, list):
        failures.append(f"{path}: Change requirementImplementations to a list")
        return

    implementations_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for index, implementation in enumerate(implementations):
        context = f"{path}: requirementImplementations[{index}]"
        if not isinstance(implementation, dict):
            failures.append(f"{context}: Change requirement implementation to a mapping")
            continue
        group_id = implementation.get("requirementGroup")
        requirement_id = implementation.get("requirementId")
        if not is_non_empty(group_id) or not is_non_empty(requirement_id):
            failures.append(f"{context}: Add requirementGroup and requirementId")
            continue
        group = requirement_groups.get(str(group_id))
        if not group:
            failures.append(f"{context}: Set requirementGroup to an existing requirement_group UID")
            continue
        if group.get("activation") == "workspace" and str(group_id) not in declared_group_ids:
            failures.append(f"{context}: Add '{group_id}' to requirementGroups before recording evidence")
            continue
        requirement = find_requirement(group, str(requirement_id), requirement_groups)
        if not requirement or not requirement_applies_to_object(requirement, obj):
            failures.append(f"{context}: Set requirementId to an applicable requirement in '{group_id}'")
            continue
        status = implementation.get("status")
        if status == "not-compliant":
            label = requirement_display_label(group, requirement)
            record_requirement_gap(
                obj,
                path,
                f"[{object_label(obj)}] Resolve not-compliant {label} from {group.get('name') or group_id} before approving this object",
                failures,
                warnings,
            )
            implementations_by_key[(str(group_id), str(requirement_id))] = implementation
            continue
        if status == "not-applicable":
            if requirement.get("naAllowed") is not True:
                failures.append(f"{context}: Use not-applicable only when the requirement sets naAllowed: true")
            implementations_by_key[(str(group_id), str(requirement_id))] = implementation
            continue
        if status != "satisfied":
            failures.append(f"{context}: Set status to satisfied, not-applicable, or not-compliant")
            continue
        mechanism = implementation.get("mechanism")
        valid_answer_types = requirement.get("validAnswerTypes", [])
        label = requirement_display_label(group, requirement)
        if mechanism and mechanism not in valid_answer_types:
            failures.append(
                f"{context}: Set mechanism to one of {valid_answer_types} for {label}"
            )
        elif mechanism and not implementation_resolves(obj, implementation, catalog_by_id):
            record_requirement_gap(
                obj,
                path,
                f"[{object_label(obj)}] Update requirementImplementation for {label} because mechanism '{mechanism}' does not resolve against the object",
                failures,
                warnings,
            )
        implementations_by_key[(str(group_id), str(requirement_id))] = implementation

    for group_id in sorted(declared_group_ids & active_group_ids):
        group = requirement_groups.get(group_id)
        if not group or group.get("activation") != "workspace" or not requirement_group_applies_to_object(group, obj):
            continue
        for requirement in resolve_requirement_group_requirements(group_id, requirement_groups):
            if not isinstance(requirement, dict) or not requirement_applies_to_object(requirement, obj):
                continue
            key = (group_id, str(requirement.get("id")))
            if key not in implementations_by_key:
                label = requirement_display_label(group, requirement)
                record_requirement_gap(
                    obj,
                    path,
                    f"[{object_label(obj)}] Add requirementImplementation for active requirement {label} from {group.get('name') or group_id}",
                    failures,
                    warnings,
                )


def find_requirement(
    group: dict[str, Any],
    requirement_id: str,
    requirement_groups: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    group_id = str(group.get("uid") or "")
    for requirement in resolve_requirement_group_requirements(group_id, requirement_groups):
        if isinstance(requirement, dict) and requirement.get("id") == requirement_id:
            return requirement
    return None


def validate_service_group_structure(
    obj: dict[str, Any],
    path: Path,
    decision_record_ids: set[str],
    catalog_by_id: dict[str, dict[str, Any]],
    failures: list[str],
    require_deployment_target: bool = True,
) -> None:
    scaling_units = obj.get("scalingUnits", [])
    service_groups = obj.get("serviceGroups", [])
    scaling_unit_names: set[str] = set()

    if scaling_units and not isinstance(scaling_units, list):
        failures.append(f"{path}: scalingUnits must be a list")
        scaling_units = []
    if service_groups and not isinstance(service_groups, list):
        failures.append(f"{path}: serviceGroups must be a list")
        service_groups = []

    for scaling_unit in scaling_units:
        if not isinstance(scaling_unit, dict):
            failures.append(f"{path}: each scalingUnits entry must be a mapping")
            continue
        name = scaling_unit.get("name")
        if not is_non_empty(name):
            failures.append(f"{path}: scalingUnits entries must include name")
            continue
        scaling_unit_names.add(str(name))
        unit_type = scaling_unit.get("type")
        if unit_type == "replicable" and not isinstance(scaling_unit.get("instanceCount"), int):
            failures.append(f"{path}: scalingUnit '{name}' type replicable requires integer instanceCount")

    service_group_names: set[str] = set()
    for group in service_groups:
        if not isinstance(group, dict):
            failures.append(f"{path}: each serviceGroups entry must be a mapping")
            continue
        name = group.get("name")
        deployment_target = group.get("deploymentTarget")
        if not is_non_empty(name):
            failures.append(f"{path}: serviceGroups entries must include name")
            continue
        service_group_names.add(str(name))
        if require_deployment_target and not is_non_empty(deployment_target):
            failures.append(f"{path}: serviceGroup '{name}' missing deploymentTarget")

    for group in service_groups:
        if not isinstance(group, dict) or not is_non_empty(group.get("name")):
            continue
        group_name = str(group["name"])
        scaling_unit_name = group.get("scalingUnit")
        if scaling_unit_name and scaling_unit_name not in scaling_unit_names:
            failures.append(f"{path}: serviceGroup '{group_name}' references unknown scalingUnit '{scaling_unit_name}'")

        for entry in group.get("deployableObjects", []) or []:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("ref")
            target = catalog_by_id.get(ref) if ref else None
            target_type = target.get("type") if target else None
            if ref and not target:
                failures.append(f"{path}: serviceGroup '{group_name}' references unknown deployable object '{ref}'")
            elif (
                ref
                and obj.get("type") == "software_deployment_pattern"
                and target_type in {"host", "technology_component"}
            ):
                failures.append(
                    f"{path}: software deployment pattern serviceGroup '{group_name}' references {target_type} "
                    f"'{ref}' directly; serviceGroups must reference service-level deployable objects, "
                    "and the Host or Technology Component must be modeled on that service object"
                )
            elif ref and target_type not in STANDARD_TYPES:
                failures.append(f"{path}: serviceGroup '{group_name}' references unknown deployable object '{ref}'")
            diagram_tier = entry.get("diagramTier")
            if diagram_tier not in VALID_DIAGRAM_TIERS:
                failures.append(
                    f"{path}: serviceGroup '{group_name}' deployable object '{ref}' must set diagramTier to one of {sorted(VALID_DIAGRAM_TIERS)}"
                )
            risk_ref = entry.get("riskRef")
            if risk_ref and risk_ref not in decision_record_ids:
                failures.append(f"{path}: serviceGroup '{group_name}' deployable object '{ref}' references unknown Decision Record '{risk_ref}'")
            intent = entry.get("intent")
            if intent and intent not in {"ha", "sa"}:
                failures.append(f"{path}: serviceGroup '{group_name}' deployable object '{ref}' has invalid intent '{intent}'")

        for interaction in group.get("externalInteractions", []) or []:
            if not isinstance(interaction, dict):
                continue
            if interaction.get("type", "external") == "internal":
                ref = interaction.get("ref")
                if not ref or ref not in service_group_names:
                    failures.append(
                        f"{path}: serviceGroup '{group_name}' internal interaction '{interaction.get('name', 'unnamed')}' must reference a valid service group name"
                    )


def validate_service_group_refs(
    obj: dict[str, Any],
    path: Path,
    decision_record_ids: set[str],
    catalog_by_id: dict[str, dict[str, Any]],
    failures: list[str],
    require_deployment_target: bool = True,
) -> None:
    for risk in obj.get("decisionRecords", []):
        if not isinstance(risk, dict):
            continue
        ref = risk.get("ref")
        if ref and ref not in decision_record_ids:
            failures.append(f"{path}: decisionRecords references unknown Decision Record '{ref}'")

    validate_service_group_structure(
        obj,
        path,
        decision_record_ids,
        catalog_by_id,
        failures,
        require_deployment_target=require_deployment_target,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    workspace_root = args.workspace.resolve()

    files = discover_workspace_yaml_files(workspace_root)
    schemas = load_schemas(SCHEMA_ROOT)
    objects: dict[Path, dict[str, Any]] = {}
    failures: list[str] = []
    warnings: list[str] = []
    workspace_requirements = load_workspace_requirements(workspace_root, failures)
    business_taxonomy = load_workspace_business_taxonomy(workspace_root, failures)
    workspace_vocabulary = load_workspace_vocabulary(workspace_root, failures, warnings)

    for path in files:
        try:
            objects[path] = load_yaml(path)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{path}: failed to parse YAML ({exc})")

    validate_object_uids(objects, workspace_root, failures)
    objects = apply_object_patches(objects, failures)

    catalog_by_id = {
        obj["uid"]: obj
        for obj in objects.values()
        if isinstance(obj, dict) and is_non_empty(obj.get("uid"))
    }
    requirement_groups = {
        object_id: obj for object_id, obj in catalog_by_id.items() if obj.get("type") == "requirement_group"
    }
    requirement_capability_refs = collect_requirement_capability_refs(requirement_groups)
    capability_ids = {object_id for object_id, obj in catalog_by_id.items() if obj.get("type") == "capability"}
    domain_ids = {object_id for object_id, obj in catalog_by_id.items() if obj.get("type") == "domain"}
    decision_record_ids = {object_id for object_id, obj in catalog_by_id.items() if obj.get("type") == "decision_record"}
    catalog_ids = set(catalog_by_id.keys())
    active_group_ids = workspace_requirements["active_groups"]
    require_active_group_disposition = workspace_requirements["require_active_group_disposition"]
    validate_workspace_requirements(workspace_root, active_group_ids, catalog_by_id, failures)
    validate_workspace_vocabulary_references(objects, workspace_vocabulary, failures, warnings)

    for path, obj in objects.items():
        if obj.get("type") is None:
            continue
        if obj.get("type") == "vocabulary":
            validate_vocabulary_document(obj, path, failures, warnings)
            continue
        if obj.get("type") == "vocabulary_proposal":
            validate_vocabulary_proposal(obj, path, workspace_vocabulary, failures, warnings)
            continue
        validate_against_schema(obj, path, schemas, failures)
        validate_external_interaction_refs(obj, path, catalog_by_id, failures)
        validate_internal_component_configuration_refs(obj, path, catalog_by_id, failures)
        validate_product_service_architecture_refs(obj, path, failures)
        if obj.get("type") == "capability":
            validate_capability(obj, path, catalog_by_id, domain_ids, requirement_capability_refs, failures, warnings)
        if obj.get("type") == "requirement_group":
            validate_requirement_group(obj, path, capability_ids, failures)
        if obj.get("type") == "technology_component":
            validate_component(
                obj,
                path,
                requirement_groups,
                catalog_by_id,
                capability_ids,
                failures,
                warnings,
                active_group_ids,
                require_active_group_disposition,
            )
        if obj.get("type") == "decision_record":
            validate_decision_record(obj, path, failures, warnings)
        if obj.get("type") == "drafting_session":
            validate_drafting_session(
                obj,
                path,
                workspace_root,
                requirement_groups,
                catalog_by_id,
                capability_ids,
                failures,
                warnings,
                active_group_ids,
                require_active_group_disposition,
            )
        if obj.get("type") in STANDARD_TYPES:
            validate_standard(
                obj,
                path,
                requirement_groups,
                catalog_by_id,
                catalog_ids,
                capability_ids,
                failures,
                warnings,
                active_group_ids,
                require_active_group_disposition,
            )
        if obj.get("type") == "reference_architecture":
            validate_ra(
                obj,
                path,
                requirement_groups,
                catalog_by_id,
                capability_ids,
                failures,
                warnings,
                active_group_ids,
                require_active_group_disposition,
            )
            validate_service_group_refs(
                obj,
                path,
                decision_record_ids,
                catalog_by_id,
                failures,
                require_deployment_target=False,
            )
        if obj.get("type") == "software_deployment_pattern":
            validate_software_deployment_pattern(
                obj,
                path,
                requirement_groups,
                catalog_by_id,
                capability_ids,
                business_taxonomy,
                failures,
                warnings,
                active_group_ids,
                require_active_group_disposition,
            )
            validate_service_group_refs(obj, path, decision_record_ids, catalog_by_id, failures)

    failing_paths = {entry.split(":", 1)[0] for entry in failures}
    for path in files:
        if str(path) in failing_paths:
            print(f"FAIL {display_path(path)}")
        else:
            print(f"PASS {display_path(path)}")

    if failures:
        print("")
        print("Validation failures:")
        for failure in failures:
            print(f"- {failure}")
        if warnings:
            print("")
            print("Validation warnings:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    if warnings:
        print("")
        print("Validation warnings:")
        for warning in warnings:
            print(f"- {warning}")

    print("")
    print(f"Validated {len(files)} catalog files successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
