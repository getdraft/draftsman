from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .catalog import build_reference_index, load_effective_catalog, object_summary, search_objects
from .config import load_config
from .paths import REPO_ROOT
from .providers import build_provider_command, detect_provider
from .sessions import DraftsmanSessionStore
from .validation import selected_framework_root, validate_workspace


DEFAULT_PROVIDER_TIMEOUT_SECONDS = 180
FRAMEWORK_MANAGED_PATH_ERROR = (
    "Draftsman proposals must not edit .draft/framework/** or .draft/framework.lock. "
    "Use an explicit framework refresh/update flow for framework changes."
)


@dataclass
class DraftsmanResponse:
    session_id: str
    answer: str
    questions: list[str]
    proposals: list[dict[str, Any]]
    grounding: list[dict[str, str]]
    provider_used: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "answer": self.answer,
            "questions": self.questions,
            "proposals": [public_proposal(proposal) for proposal in self.proposals],
            "grounding": self.grounding,
            "providerUsed": self.provider_used,
        }


class DraftsmanEngine:
    def __init__(
        self,
        config_path: Path | None = None,
        session_store: DraftsmanSessionStore | None = None,
    ) -> None:
        self.config_path = config_path
        self.session_store = session_store or DraftsmanSessionStore()

    def chat(self, message: str, session_id: str | None = None) -> DraftsmanResponse:
        config = load_config(self.config_path)
        configured_framework = Path(config.get("framework_repo_path") or REPO_ROOT).expanduser()
        workspace_value = str(config.get("content_repo_path") or "").strip()
        workspace = Path(workspace_value).expanduser() if workspace_value else None
        framework_root = selected_framework_root(workspace, configured_framework)
        session = self.session_store.load(session_id)
        session.setdefault("messages", []).append({"role": "user", "content": message})

        local = answer_locally(message, workspace, framework_root)
        if local:
            session["messages"].append({"role": "draftsman", "content": local.answer})
            self.session_store.save(session)
            return DraftsmanResponse(session["id"], local.answer, local.questions, [], local.grounding, False)

        provider_response = self.ask_provider(config, framework_root, workspace, message, session)
        session["messages"].append({"role": "draftsman", "content": provider_response.answer})
        session["proposals"] = merge_proposals(session.get("proposals", []), provider_response.proposals)
        self.session_store.save(session)
        return provider_response

    def apply_proposals(self, session_id: str, proposal_ids: list[str] | None = None) -> dict[str, Any]:
        config = load_config(self.config_path)
        workspace_value = str(config.get("content_repo_path") or "").strip()
        if not workspace_value:
            raise ValueError("No company DRAFT repo selected.")
        workspace = Path(workspace_value).expanduser()
        session = self.session_store.load(session_id)
        selected = set(proposal_ids or [])
        applied: list[dict[str, str]] = []
        for proposal in session.get("proposals", []):
            if selected and proposal.get("id") not in selected:
                continue
            relative_path = proposal.get("path")
            content = proposal.get("content")
            if not relative_path or not content:
                continue
            target = safe_workspace_path(workspace, str(relative_path))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")
            applied.append(
                {
                    "id": str(proposal.get("id", "")),
                    "artifactId": str(proposal.get("artifactId", "")),
                    "name": str(proposal.get("name", "")),
                    "artifactType": str(proposal.get("artifactType", "")),
                    "path": str(relative_path),
                }
            )
            proposal["applied"] = True
        self.session_store.save(session)
        validation = validate_workspace(workspace, Path(config.get("framework_repo_path") or REPO_ROOT).expanduser())
        return {
            "applied": applied,
            "validation": {
                "ok": validation.ok,
                "stdout": validation.stdout,
                "stderr": validation.stderr,
            },
        }

    def ask_provider(
        self,
        config: dict[str, Any],
        framework_root: Path,
        workspace: Path | None,
        message: str,
        session: dict[str, Any],
    ) -> DraftsmanResponse:
        provider = config.get("provider") or {}
        provider_type = str(provider.get("type") or "")
        executable = str(provider.get("executable") or provider.get("endpoint") or "")
        status = detect_provider(provider_type, executable or None)
        if not status.available:
            answer = (
                "I can answer framework and catalog lookup questions locally, but architecture drafting "
                f"needs a configured provider. Current provider status: {status.detail}"
            )
            return DraftsmanResponse(session["id"], answer, [], [], [], False)

        prompt = build_draftsman_prompt(framework_root, workspace, message, session)
        raw = invoke_provider(provider, prompt)
        parsed = parse_provider_response(raw)
        proposals = normalize_proposals(parsed.get("proposals", []))
        answer = str(parsed.get("answer") or raw).strip()
        questions = [str(item) for item in parsed.get("questions", []) if str(item).strip()]
        grounding = [object_summary(obj) for obj in search_objects(load_effective_catalog(workspace, framework_root), message, 5)]
        return DraftsmanResponse(session["id"], answer, questions, proposals, grounding, True)


@dataclass
class LocalAnswer:
    answer: str
    questions: list[str]
    grounding: list[dict[str, str]]


def answer_locally(message: str, workspace: Path | None, framework_root: Path) -> LocalAnswer | None:
    lowered = message.lower()
    if is_setup_mode_request(lowered):
        return setup_mode_response(workspace, framework_root)
    if is_framework_definition_question(lowered, "technology component"):
        return LocalAnswer(read_doc_section(framework_root / "docs" / "technology-components.md", "What A Technology Component Is"), [], [])
    if any(
        is_framework_definition_question(lowered, term)
        for term in (
            "host",
            "runtime service",
            "data-at-rest service",
            "edge/gateway service",
            "object type",
            "host standard",
            "service standard",
        )
    ):
        return LocalAnswer(read_doc_intro(framework_root / "docs" / "object-types.md"), [], [])
    if is_framework_definition_question(lowered, "requirement group") or is_framework_definition_question(lowered, "definition checklist"):
        return LocalAnswer(read_doc_intro(framework_root / "docs" / "requirement-groups.md"), [], [])
    if is_framework_definition_question(lowered, "software deployment pattern"):
        return LocalAnswer(read_doc_intro(framework_root / "docs" / "software-deployment-patterns.md"), [], [])
    if "where" in lowered and any(term in lowered for term in ("used", "referenced", "use")):
        return answer_usage_question(message, workspace, framework_root)
    return None


def is_setup_mode_request(lowered: str) -> bool:
    setup_phrases = (
        "setup mode",
        "set up draft",
        "setup draft",
        "start setup",
        "company setup",
        "draft setup",
        "get started",
        "getting started",
        "onboard us",
        "onboarding",
    )
    return any(phrase in lowered for phrase in setup_phrases)


def setup_mode_response(workspace: Path | None, framework_root: Path) -> LocalAnswer:
    if workspace is None:
        answer = "\n".join(
            [
                "Setup mode is the Draftsman first-run path for making a company DRAFT workspace useful.",
                "",
                "Current step: select or create the private company DRAFT repo.",
                "Next: run `draft-table onboard`, or tell me the local path or Git URL for the company DRAFT repo.",
                "Left after that: business taxonomy, active Requirement Groups, capability owners, acceptable-use technology, baseline deployable standards, and the first real drafting session.",
                "Can revisit later: every governance choice. We only need enough to make the first catalog review useful.",
            ]
        )
        return LocalAnswer(answer, ["What local path or Git URL should be used for the company DRAFT workspace?"], [])

    workspace_root = workspace.expanduser().resolve()
    if is_upstream_framework_repo(workspace_root, framework_root):
        answer = "\n".join(
            [
                "Setup mode should run against a private company DRAFT workspace, not the upstream framework repo.",
                "",
                "Current step: choose the company workspace.",
                "Next: give me the local path to the company-specific repo, or run `draft-table onboard` to create/select one.",
                "Left after that: vendor the framework, confirm workspace taxonomy and governance, seed the acceptable-use baseline, then draft one real product or system.",
            ]
        )
        return LocalAnswer(answer, ["What is the local path to the company DRAFT workspace?"], [])

    status = workspace_setup_status(workspace_root, framework_root)
    next_step = setup_next_step(status)
    answer = "\n".join(
        [
            "Setup mode is active.",
            "",
            "Current state:",
            f"- Workspace: {workspace_root}",
            f"- Framework copy: {status['frameworkCopy']}",
            f"- Business taxonomy: {status['businessTaxonomy']}",
            f"- Active Requirement Groups: {status['activeRequirementGroups']}",
            f"- Capability ownership: {status['capabilityOwnership']}",
            f"- Company catalog baseline: {status['catalogBaseline']}",
            "",
            f"Next: {next_step}",
            "",
            "Left after that: finish the acceptable-use technology baseline, draft common Host/Runtime/Data-at-Rest/Edge standards, pick one real product or system, and validate the generated catalog.",
            "Can revisit later: taxonomy names, active governance groups, lifecycle choices, and incomplete object details. We will capture uncertainty instead of forcing perfect answers up front.",
        ]
    )
    return LocalAnswer(answer, setup_questions_for_status(status), [])


def workspace_setup_status(workspace: Path, framework_root: Path) -> dict[str, str | int | dict[str, int]]:
    workspace_yaml = read_workspace_yaml(workspace / ".draft" / "workspace.yaml")
    pillars = workspace_yaml.get("businessTaxonomy", {}).get("pillars", [])
    if not isinstance(pillars, list):
        pillars = []
    requirements = workspace_yaml.get("requirements", {})
    active_groups = requirements.get("activeRequirementGroups", []) if isinstance(requirements, dict) else []
    if not isinstance(active_groups, list):
        active_groups = []
    catalog_counts = workspace_catalog_counts(workspace)
    capabilities = [
        obj
        for obj in load_effective_catalog(workspace, framework_root).values()
        if obj.get("type") == "capability" and obj.get("implementations")
    ]
    owned_capabilities = [obj for obj in capabilities if obj.get("owner")]
    deployable_count = sum(
        catalog_counts.get(object_type, 0)
        for object_type in (
            "host",
            "runtime_service",
            "data_store_service",
            "edge_gateway_service",
            "product_component",
            "software_deployment_pattern",
        )
    )
    return {
        "frameworkCopy": "present" if (workspace / ".draft" / "framework").exists() else "missing",
        "businessTaxonomy": f"{len(pillars)} pillar{'s' if len(pillars) != 1 else ''}",
        "businessPillarCount": len(pillars),
        "activeRequirementGroups": f"{len(active_groups)} active group{'s' if len(active_groups) != 1 else ''}",
        "activeRequirementGroupCount": len(active_groups),
        "capabilityOwnership": (
            f"{len(owned_capabilities)} of {len(capabilities)} mapped capabilities have owners"
            if capabilities
            else "no mapped capabilities yet"
        ),
        "mappedCapabilityCount": len(capabilities),
        "ownedCapabilityCount": len(owned_capabilities),
        "catalogBaseline": (
            f"{catalog_counts.get('technology_component', 0)} Technology Components, "
            f"{deployable_count} deployable standards or patterns"
        ),
        "technologyComponentCount": catalog_counts.get("technology_component", 0),
        "deployableCount": deployable_count,
    }


def read_workspace_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def workspace_catalog_counts(workspace: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    catalog_root = workspace / "catalog"
    if not catalog_root.exists():
        return counts
    for path in catalog_root.rglob("*.yaml"):
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(loaded, dict):
            continue
        object_type = str(loaded.get("type") or "").strip()
        if object_type:
            counts[object_type] = counts.get(object_type, 0) + 1
    return counts


def setup_next_step(status: dict[str, Any]) -> str:
    if status.get("frameworkCopy") != "present":
        return "run `draft-table onboard` or refresh the workspace so `.draft/framework/` is present."
    if int(status.get("businessPillarCount") or 0) == 0:
        return "define the initial business taxonomy in `.draft/workspace.yaml`."
    if int(status.get("activeRequirementGroupCount") or 0) == 0:
        return "choose the first active Requirement Groups for new drafting work."
    if int(status.get("mappedCapabilityCount") or 0) == 0:
        return "seed the first acceptable-use capability mappings and owners."
    if int(status.get("technologyComponentCount") or 0) == 0:
        return "add the first standard Technology Components the company already uses."
    if int(status.get("deployableCount") or 0) == 0:
        return "draft the first reusable deployable standards before modeling a full product pattern."
    return "pick one real product, diagram, repository, or source document and start the first focused Drafting Session."


def setup_questions_for_status(status: dict[str, Any]) -> list[str]:
    if status.get("frameworkCopy") != "present":
        return ["Should I help you select an existing company repo path or create a new DRAFT workspace?"]
    if int(status.get("businessPillarCount") or 0) == 0:
        return ["What are the first 3-7 business pillars or product groupings people should use to browse architecture?"]
    if int(status.get("activeRequirementGroupCount") or 0) == 0:
        return ["Which governance baseline should new objects address first: DRAFT-only, SOC 2, TX-RAMP, NIST CSF, or a company-specific group?"]
    if int(status.get("mappedCapabilityCount") or 0) == 0:
        return ["Which few enterprise standards should we seed first, such as identity, logging, monitoring, patching, backup, compute, and operating systems?"]
    if int(status.get("deployableCount") or 0) == 0:
        return ["Which common deployable standard should we draft first: Host, Runtime Service, DataStoreService, or Edge/Gateway Service?"]
    return ["Which real product, system, diagram, or repository should we use for the first guided Drafting Session?"]


def is_framework_definition_question(lowered: str, term: str) -> bool:
    return term in lowered and any(prefix in lowered for prefix in ("what is", "what's", "explain", "define"))


def answer_usage_question(message: str, workspace: Path | None, framework_root: Path) -> LocalAnswer:
    objects = load_effective_catalog(workspace, framework_root)
    matches = search_objects(objects, message, 3)
    content_matches = [
        match for match in matches
        if match.get("type") not in {"requirement_group", "capability", "domain"}
    ]
    if content_matches:
        matches = content_matches
    if not matches:
        return LocalAnswer("I could not find a matching catalog object in the loaded DRAFT model.", [], [])
    target = matches[0]
    target_uid = str(target.get("uid") or target.get("id") or "")
    referenced_by = build_reference_index(objects).get(target_uid, [])
    grounding = [object_summary(target)]
    if not referenced_by:
        answer = (
            f"I found {target.get('name')}, but it is not referenced by any "
            "other object in the currently loaded DRAFT model."
        )
        return LocalAnswer(answer, [], grounding)
    lines = [f"{target.get('name')} is referenced by:"]
    for ref in referenced_by:
        source = objects.get(ref["source"], {})
        grounding.append(object_summary(source))
        lines.append(f"- {source.get('name', ref['source'])} via {ref['path']}")
    return LocalAnswer("\n".join(lines), [], grounding)


def read_doc_section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    body = match.group("body").strip() if match else text.strip()
    return trim_markdown(body)


def read_doc_intro(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    body = re.sub(r"^# .*\n", "", text, count=1).strip()
    body = body.split("\n## ", 1)[0].strip()
    return trim_markdown(body)


def trim_markdown(text: str, limit: int = 1400) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3].rstrip() + "..."


def build_draftsman_prompt(framework_root: Path, workspace: Path | None, message: str, session: dict[str, Any]) -> str:
    objects = load_effective_catalog(workspace, framework_root)
    matches = [object_summary(obj) for obj in search_objects(objects, message, 8)]
    docs = [
        ("Draftsman Instructions", framework_root / "docs" / "draftsman.md"),
        ("Company Onboarding", framework_root / "docs" / "company-onboarding.md"),
        ("Workspace Model", framework_root / "docs" / "workspaces.md"),
        ("Schema Reference", framework_root / "docs" / "yaml-schema-reference.md"),
        ("Object Types", framework_root / "docs" / "object-types.md"),
        ("Requirement Groups", framework_root / "docs" / "requirement-groups.md"),
        ("Capabilities", framework_root / "docs" / "capabilities.md"),
    ]
    doc_context = "\n\n".join(f"## {title}\n{path.read_text(encoding='utf-8')[:5000]}" for title, path in docs if path.exists())
    uploads = session.get("uploads", [])[-6:]
    upload_context = "\n".join(
        f"- {item.get('name')} ({item.get('contentType', 'unknown')}): {item.get('path')}\n{item.get('text', '')[:3000]}"
        for item in uploads
    )
    workspace_context = draftsman_workspace_context(framework_root, workspace)
    return f"""
You are the DRAFT Draftsman. You conduct architecture interviews and produce DRAFT artifacts.

Rules:
- Never ask for API keys or secrets.
- Do not show raw YAML to the user.
- Reuse existing artifacts when possible.
- Separate observed facts from assumptions.
- Ask focused follow-up questions for missing Requirement Group facts.
- When the user asks to set up DRAFT, start setup mode: explain the current step,
  the next step, what remains, and what can be revisited later before asking questions.
- In setup mode, optimize for the minimum useful catalog: workspace repo, business
  taxonomy, active Requirement Groups, capability owners, acceptable-use technology,
  baseline deployable standards, and one real first Drafting Session.
- Keep every interview lightweight. Ask no more than three questions at a time,
  prefer one question when possible, explain why each question matters, and keep
  a visible backlog of unanswered or revisit-later items instead of forcing closure.
- Adapt wording to the audience. Architects can discuss governance and patterns;
  engineers can answer concrete runtime, dependency, and operational questions;
  product teams can identify product ownership, user-facing capabilities, and
  system boundaries without needing YAML or framework terminology.
- Use requirements.activeRequirementGroups in .draft/workspace.yaml as the source for
  which workspace-activated requirement groups to push during interviews. Do not enforce an
  available workspace-mode group just because its YAML exists.
- Preserve provider identity on workspace-activated Requirement Groups so DRAFT-provided,
  third-party-provided, and company-provided control interpretations remain distinct.
- First-class objects use generated uid values for machine identity. Do not ask
  humans to invent semantic object ids. Use names and aliases in conversation,
  and keep uid stable through renames.
- For Requirement Group entries with relatedCapability, resolve the capability object first,
  check workspace capability implementations, prefer implementations with lifecycleStatus preferred,
  and ask a multiple-choice question using those options instead of an open-ended question.
- If a requirement lacks relatedCapability but a satisfaction mechanism criteria names a capability,
  resolve that capability and ask the same catalog-grounded multiple-choice question.
- Include "something else" only as an exception path; if the user chooses it, identify or draft
  the Technology Component and state that the capability owner must approve it before it becomes
  acceptable use.
- For capability requirements, ask what mechanism satisfies the capability:
  field, internal component, Technology Component configuration, external interaction, deployment
  configuration, or architectural decision.
- For Software Deployment Pattern sessions, search candidate Reference Architectures and explain the
  closest match in plain language; do not ask the user to name a Reference Architecture UID.
- After drafting Software Deployment Pattern service groups, perform composition closure: resolve each
  deployable object, resolve ProductComponent runsOn, classify each Runtime Service, Data-at-Rest
  Service, and Edge/Gateway Service delivery model, and for every self-managed service resolve the
  Host substrate from approved Host Standards or ask a catalog-grounded multiple-choice question.
- Do not assume EKS, EC2, Lambda, VM, physical, or container placement without source evidence or
  user confirmation; record unresolved substrate choices in the Drafting Session.
- Do not turn capability requirements into team ownership questions unless the
  applicable Requirement Group explicitly asks for ownership.
- For Host Requirement Group patch management, ask what patch platform, installed component,
  Technology Component configuration, or architectural decision applies updates; do not ask which
  team owns patching as the capability answer.
- For Runtime Service, DataStoreService, or Edge/Gateway Service objects with
  deliveryModel appliance, remember that the service maps directly to a vendor-product
  identity but carries service-like operating capability answers because there
  is no Host wrapper to inherit host requirements.
- If you propose artifacts, return them as JSON proposals with YAML content for the backend only.
- The visible answer must summarize artifacts in plain language.
- If no company DRAFT repo is selected, or if the selected repo is the upstream draft-framework
  implementation repo, do not propose catalog/configuration content changes. Ask the user for the
  company-specific DRAFT repo path first.
- In a company DRAFT repo, never propose changes under .draft/framework/** or to
  .draft/framework.lock. Those files are framework-managed and change only through an explicit
  framework refresh/update flow.

User request:
{message}

Selected workspace:
{workspace_context}

Relevant existing objects:
{json.dumps(matches, indent=2)}

Uploaded source material:
{upload_context or "No uploaded source material in this session."}

Framework context:
{doc_context}

Return JSON only with this shape:
{{
  "answer": "plain-language response for the user; no YAML",
  "questions": ["focused follow-up question if needed"],
  "proposals": [
    {{
      "id": "short proposal id",
      "action": "create|update",
      "artifactType": "Technology Component|Host|Runtime Service|DataStoreService|Edge/Gateway Service|ProductComponent|Reference Architecture|Software Deployment Pattern|Capability|Requirement Group|Decision Record|Drafting Session",
      "name": "artifact name",
      "summary": "plain-language summary",
      "path": "relative file path under the company DRAFT repo",
      "content": "complete YAML content for the backend to write; never mention this content in the answer"
    }}
  ]
}}
"""


def draftsman_workspace_context(framework_root: Path, workspace: Path | None) -> str:
    if workspace is None:
        return (
            "No company DRAFT workspace is selected. For company architecture content changes, "
            "ask the user for the company-specific DRAFT repo path before proposing files."
        )
    workspace_root = workspace.expanduser().resolve()
    if is_upstream_framework_repo(workspace_root, framework_root):
        return (
            f"{workspace_root} appears to be the upstream DRAFT framework repository, not a company "
            "workspace. Use it for schemas, templates, base configurations, tools, and docs only; "
            "ask for the company-specific DRAFT repo path before proposing company content changes."
        )
    return (
        f"{workspace_root} is the selected company DRAFT workspace. Content proposals may target "
        "catalog/ and company-owned configurations/, but must not target .draft/framework/** or "
        ".draft/framework.lock."
    )


def is_upstream_framework_repo(workspace: Path, framework_root: Path) -> bool:
    framework_root = framework_root.expanduser().resolve()
    framework_repo = framework_root.parent if (framework_root.parent / "draft-framework.yaml").exists() else framework_root
    if workspace in {framework_root, framework_repo.resolve()}:
        return True
    return (workspace / "draft-framework.yaml").exists() and (workspace / "framework" / "tools" / "validate.py").exists()


def invoke_provider(provider: dict[str, Any], prompt: str) -> str:
    provider_type = str(provider.get("type") or "")
    executable = str(provider.get("executable") or "")
    model = str(provider.get("model") or "")
    timeout_seconds = provider_timeout_seconds(provider)
    if provider_type == "local-llm":
        return invoke_ollama(str(provider.get("endpoint") or "http://127.0.0.1:11434"), model, prompt, timeout_seconds)
    try:
        command = build_provider_command(provider_type, executable, prompt, model)
        process = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return (
            f"The {provider_display_name(provider_type)} provider did not return within "
            f"{timeout_seconds} seconds, so I stopped waiting. I did not create or apply any artifacts. "
            "Try the request again in smaller batches, verify the provider CLI works in a terminal, "
            "or increase the provider timeout in the DRAFT Table config."
        )
    except (OSError, ValueError) as exc:
        return f"The {provider_display_name(provider_type)} provider could not be started: {exc}"
    if process.returncode != 0:
        return process.stderr.strip() or process.stdout.strip() or f"Provider command failed with exit code {process.returncode}."
    return process.stdout.strip()


def provider_timeout_seconds(provider: dict[str, Any]) -> int:
    raw = provider.get("timeout_seconds") or provider.get("timeoutSeconds") or provider.get("timeout")
    if raw in (None, ""):
        return DEFAULT_PROVIDER_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PROVIDER_TIMEOUT_SECONDS
    return max(5, min(value, 1800))


def provider_display_name(provider_type: str) -> str:
    return {
        "codex": "Codex",
        "claude-code": "Claude Code",
        "gemini-cli": "Gemini CLI",
        "local-llm": "local LLM",
        "custom-command": "custom command",
    }.get(provider_type, provider_type or "AI")


def invoke_ollama(endpoint: str, model: str, prompt: str, timeout_seconds: int = DEFAULT_PROVIDER_TIMEOUT_SECONDS) -> str:
    if not model:
        return "Local LLM mode needs a selected model name."
    url = endpoint.rstrip("/") + "/api/generate"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"Local LLM endpoint is not reachable: {exc}"
    except json.JSONDecodeError as exc:
        return f"Local LLM endpoint returned invalid JSON: {exc}"
    return str(data.get("response", ""))


def parse_provider_response(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"answer": raw, "questions": [], "proposals": []}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {"answer": raw, "questions": [], "proposals": []}
        except json.JSONDecodeError:
            pass
    return {"answer": raw, "questions": [], "proposals": []}


def normalize_proposals(proposals: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(proposals, list):
        return normalized
    for index, proposal in enumerate(proposals, start=1):
        if not isinstance(proposal, dict):
            continue
        proposal_id = str(proposal.get("id") or f"proposal-{index}")
        identity = proposal_identity(str(proposal.get("content") or ""))
        normalized.append(
            {
                "id": proposal_id,
                "action": str(proposal.get("action") or "create"),
                "artifactType": str(proposal.get("artifactType") or "Artifact"),
                "name": str(proposal.get("name") or proposal_id),
                "summary": str(proposal.get("summary") or ""),
                "path": str(proposal.get("path") or ""),
                "artifactId": identity.get("uid", ""),
                "artifactUid": identity.get("uid", ""),
                "content": str(proposal.get("content") or ""),
                "applied": bool(proposal.get("applied", False)),
            }
        )
    return normalized


def proposal_identity(content: str) -> dict[str, str]:
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "uid": str(data.get("uid") or data.get("id") or ""),
        "type": str(data.get("type") or ""),
        "name": str(data.get("name") or ""),
    }


def public_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": proposal.get("id", ""),
        "artifactId": proposal.get("artifactId", ""),
        "artifactUid": proposal.get("artifactUid", ""),
        "action": proposal.get("action", ""),
        "artifactType": proposal.get("artifactType", ""),
        "name": proposal.get("name", ""),
        "summary": proposal.get("summary", ""),
        "path": proposal.get("path", ""),
        "applied": proposal.get("applied", False),
    }


def merge_proposals(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item.get("id")): item for item in existing if item.get("id")}
    for proposal in incoming:
        by_id[str(proposal.get("id"))] = proposal
    return list(by_id.values())


def safe_workspace_path(workspace: Path, relative_path: str) -> Path:
    target = (workspace / relative_path).resolve()
    root = workspace.resolve()
    try:
        relative = target.relative_to(root)
    except ValueError:
        raise ValueError("Proposal path escapes the company DRAFT repo.")
    if is_framework_managed_path(relative):
        raise ValueError(FRAMEWORK_MANAGED_PATH_ERROR)
    return target


def is_framework_managed_path(relative: Path) -> bool:
    parts = relative.parts
    return parts[:2] == (".draft", "framework") or parts == (".draft", "framework.lock")
