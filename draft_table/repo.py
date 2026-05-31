from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .paths import DEFAULT_WORKSPACE_PARENT, REPO_ROOT, resolve_framework_root, workspace_framework_root


WORKSPACE_DIRS = (
    "catalog",
    "catalog/technology-components",
    "catalog/network-services",
    "catalog/hosts",
    "catalog/runtime-services",
    "catalog/data-at-rest-services",
    "catalog/product-services",
    "catalog/reference-architectures",
    "catalog/software-deployment-patterns",
    "catalog/decision-records",
    "catalog/sessions",
    "configurations",
    "configurations/browser",
    "configurations/capabilities",
    "configurations/requirement-groups",
    "configurations/object-patches",
    "configurations/vocabulary",
    "configurations/vocabulary-proposals",
    ".github",
    ".github/workflows",
    ".draft",
    ".draft/providers",
)

FRAMEWORK_VENDOR_DIRS = (
    "browser",
    "configurations",
    "docs",
    "schemas",
    "tools",
    "commands",
    "integrations",
)

FRAMEWORK_VENDOR_OPTIONAL_DIRS = (
    "templates",
    "examples",
)

FRAMEWORK_VENDOR_FILES = (
    "AGENTS.md",
    "AI_INDEX.md",
    "CLAUDE.md",
    "CHANGELOG.md",
    "README.md",
    "draft-framework.yaml",
    "draft-logo.png",
    "draftlogo.png",
    "GEMINI.md",
    "RELEASE.md",
    "VERSIONING.md",
    "llms.txt",
    "security.md",
)

DEFAULT_FRAMEWORK_SOURCE = "https://github.com/getdraft/draftsman.git"
COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".pytest_cache")
WORKSPACE_TEMPLATE_FILES = (
    ("templates/workspace/README.md.tmpl", "README.md"),
    ("templates/workspace/AGENTS.md.tmpl", "AGENTS.md"),
    ("templates/workspace/CLAUDE.md.tmpl", "CLAUDE.md"),
    ("templates/workspace/GEMINI.md.tmpl", "GEMINI.md"),
    ("templates/workspace/llms.txt.tmpl", "llms.txt"),
    ("templates/workspace/.github/copilot-instructions.md.tmpl", ".github/copilot-instructions.md"),
    ("templates/workspace/.github/workflows/draft-framework-update.yml.tmpl", ".github/workflows/draft-framework-update.yml"),
    ("templates/workspace/.github/workflows/draft-vocabulary-proposals.yml.tmpl", ".github/workflows/draft-vocabulary-proposals.yml"),
    ("templates/workspace/.windsurfrules.tmpl", ".windsurfrules"),
    ("templates/workspace/.cursor/rules/draftsman.mdc.tmpl", ".cursor/rules/draftsman.mdc"),
)

TEMPLATE_ACRONYMS = {
    "ai": "AI",
    "api": "API",
    "ci": "CI",
    "cd": "CD",
    "draft": "DRAFT",
    "github": "GitHub",
    "yaml": "YAML",
}


def repo_name_from_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    name = cleaned.rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    return name or "draft-content"


def default_clone_path(url: str) -> Path:
    return DEFAULT_WORKSPACE_PARENT / repo_name_from_url(url)


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def clone_or_pull(url: str, destination: Path) -> subprocess.CompletedProcess[str]:
    destination = destination.expanduser()
    if destination.exists() and (destination / ".git").exists():
        return run_git(["pull", "--ff-only"], destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["git", "clone", url, str(destination)],
        text=True,
        capture_output=True,
        check=False,
    )


def ensure_git_repo(repo_path: Path) -> subprocess.CompletedProcess[str]:
    root = repo_path.expanduser()
    if root.exists() and not root.is_dir():
        return subprocess.CompletedProcess(
            ["git", "init"],
            2,
            "",
            f"Path exists and is not a directory: {root}",
        )
    root.mkdir(parents=True, exist_ok=True)
    if (root / ".git").exists():
        return run_git(["status", "--short", "--branch"], root)
    return run_git(["init"], root)


def git_status(repo_path: Path) -> subprocess.CompletedProcess[str]:
    return run_git(["status", "--short", "--branch"], repo_path.expanduser())


def git_commit(repo_path: Path, message: str) -> subprocess.CompletedProcess[str]:
    run_git(["add", "-A"], repo_path.expanduser())
    return run_git(["commit", "-m", message], repo_path.expanduser())


def current_framework_commit(framework_repo: Path = REPO_ROOT) -> str:
    framework_root = resolve_framework_root(framework_repo)
    git_root = framework_root.parent if (framework_root.parent / ".git").exists() else framework_root
    result = run_git(["rev-parse", "HEAD"], git_root)
    return result.stdout.strip() if result.returncode == 0 else ""


def framework_manifest_path(framework_repo: Path = REPO_ROOT) -> Path | None:
    framework_root = resolve_framework_root(framework_repo)
    for path in (framework_root / "draft-framework.yaml", framework_root.parent / "draft-framework.yaml"):
        if path.exists():
            return path
    return None


def current_framework_version(framework_repo: Path = REPO_ROOT) -> str:
    manifest_path = framework_manifest_path(framework_repo)
    if not manifest_path:
        return ""
    try:
        loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return ""
    if not isinstance(loaded, dict):
        return ""
    return str(loaded.get("version") or "").strip()


def current_framework_tag(framework_repo: Path = REPO_ROOT) -> str:
    framework_root = resolve_framework_root(framework_repo)
    git_root = framework_root.parent if (framework_root.parent / ".git").exists() else framework_root
    result = run_git(["describe", "--tags", "--exact-match"], git_root)
    return result.stdout.strip() if result.returncode == 0 else ""


def framework_lock_data(framework_repo: Path = REPO_ROOT, source_label: str | None = None) -> dict[str, Any]:
    framework_commit = current_framework_commit(framework_repo)
    framework_version = current_framework_version(framework_repo)
    framework_tag = current_framework_tag(framework_repo)
    framework: dict[str, Any] = {
        "source": source_label or DEFAULT_FRAMEWORK_SOURCE,
        "vendoredPath": ".draft/framework",
        "updatePolicy": "explicit",
        "syncedRef": "main",
        "syncedCommit": framework_commit,
    }
    if framework_version:
        framework["version"] = framework_version
    if framework_tag:
        framework["syncedTag"] = framework_tag
    return {
        "schemaVersion": "1.0",
        "framework": framework,
    }


def copy_optional_framework_dir(source_root: Path, source_repo: Path, relative: str, destination: Path) -> bool:
    for source in (source_root / relative, source_repo / relative):
        if source.exists():
            shutil.copytree(source, destination / relative, dirs_exist_ok=True, ignore=COPY_IGNORE)
            return True
    return False


def copy_optional_framework_file(source_root: Path, source_repo: Path, filename: str, destination: Path) -> bool:
    for source in (source_root / filename, source_repo / filename):
        if source.exists():
            target = destination / filename
            if filename.endswith(".md") or filename in {"AI_INDEX.md", "CLAUDE.md", "GEMINI.md", "llms.txt"}:
                target.write_text(vendored_framework_text(source.read_text(encoding="utf-8")), encoding="utf-8")
            else:
                shutil.copy2(source, target)
            return True
    return False


def template_destination_name(template: str) -> str:
    relative = template.replace("templates/workspace/", "", 1)
    return relative.removesuffix(".tmpl")


def humanize_workspace_name(value: str) -> str:
    words = re.split(r"[^A-Za-z0-9]+", value.strip())
    rendered: list[str] = []
    for word in words:
        if not word:
            continue
        lower = word.lower()
        rendered.append(TEMPLATE_ACRONYMS.get(lower, lower.capitalize()))
    return " ".join(rendered) or "Company DRAFT Workspace"


def workspace_metadata(workspace: Path) -> dict[str, Any]:
    config_path = workspace / ".draft" / "workspace.yaml"
    if not config_path.exists():
        return {}
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def named_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "displayName", "id"):
            if value.get(key):
                return str(value[key]).strip()
        return ""
    if isinstance(value, str):
        return value.strip()
    return ""


def workspace_template_context(workspace: Path) -> dict[str, str]:
    metadata = workspace_metadata(workspace)
    workspace_data = metadata.get("workspace") if isinstance(metadata.get("workspace"), dict) else {}
    repository_data = metadata.get("repository") if isinstance(metadata.get("repository"), dict) else {}

    workspace_name = str(workspace_data.get("name") or repository_data.get("name") or workspace.name).strip()
    workspace_label = str(workspace_data.get("displayName") or "").strip() or humanize_workspace_name(workspace_name)
    company_name = (
        str(workspace_data.get("companyName") or "").strip()
        or named_value(workspace_data.get("organization"))
        or named_value(metadata.get("company"))
        or named_value(metadata.get("organization"))
        or workspace_label
    )
    repository_provider = str(repository_data.get("provider") or "").strip().lower()
    repository_owner = str(repository_data.get("owner") or "").strip()
    repository_name = str(repository_data.get("name") or workspace_name).strip()
    repository_slug = f"{repository_owner}/{repository_name}" if repository_owner and repository_name else repository_name
    repository_url = ""
    if repository_provider == "github" and repository_owner and repository_name:
        repository_url = f"https://github.com/{repository_owner}/{repository_name}"
    repository_reference = repository_url or repository_slug or str(workspace.resolve())
    return {
        "workspace_name": workspace_name,
        "workspace_label": workspace_label,
        "company_name": company_name,
        "repository_slug": repository_slug,
        "repository_url": repository_url,
        "repository_reference": repository_reference,
    }


def render_workspace_template(text: str, context: dict[str, str]) -> str:
    for key, value in context.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def copy_workspace_template_file(
    source_root: Path,
    source_repo: Path,
    template: str,
    destination: Path,
    context: dict[str, str],
    overwrite: bool = False,
) -> bool:
    for source in (source_repo / template, source_root / template):
        if not source.exists():
            continue
        target = destination / template_destination_name(template)
        if target.exists() and not overwrite:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_workspace_template(source.read_text(encoding="utf-8"), context), encoding="utf-8")
        return True
    return False


def copy_workspace_templates(workspace: Path, framework_repo: Path = REPO_ROOT, overwrite: bool = False) -> list[Path]:
    workspace = workspace.expanduser()
    source_root = resolve_framework_root(framework_repo)
    source_repo = source_root.parent
    context = workspace_template_context(workspace)
    copied: list[Path] = []
    for template, destination in WORKSPACE_TEMPLATE_FILES:
        target = workspace / destination
        if copy_workspace_template_file(source_root, source_repo, template, workspace, context, overwrite=overwrite):
            copied.append(target)
    return copied


def vendored_framework_text(text: str) -> str:
    protected_vendor_root = "__DRAFT_VENDOR_FRAMEWORK_ROOT__"
    text = text.replace(".draft/framework", protected_vendor_root)
    replacements = {
        "framework/browser/": "browser/",
        "framework/docs/": "docs/",
        "framework/schemas/": "schemas/",
        "framework/configurations/": "configurations/",
        "framework/tools/": "tools/",
        "framework/browser": "browser",
        "framework/docs": "docs",
        "framework/schemas": "schemas",
        "framework/configurations": "configurations",
        "framework/tools": "tools",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.replace(protected_vendor_root, ".draft/framework")


def vendor_framework(workspace: Path, framework_repo: Path = REPO_ROOT, overwrite: bool = False) -> list[Path]:
    workspace = workspace.expanduser()
    destination = workspace_framework_root(workspace)
    if destination.exists() and not overwrite:
        if (destination / "tools" / "validate.py").exists():
            return []
        shutil.rmtree(destination)

    source_root = resolve_framework_root(framework_repo)
    source_repo = source_root.parent
    if source_root.resolve() == destination.resolve():
        return []
    if overwrite and destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    for relative in FRAMEWORK_VENDOR_DIRS:
        source = source_root / relative
        if source.exists():
            shutil.copytree(source, destination / relative, dirs_exist_ok=True, ignore=COPY_IGNORE)
    for relative in FRAMEWORK_VENDOR_OPTIONAL_DIRS:
        copy_optional_framework_dir(source_root, source_repo, relative, destination)
    for filename in FRAMEWORK_VENDOR_FILES:
        copy_optional_framework_file(source_root, source_repo, filename, destination)
    return [destination]


def refresh_vendored_framework(
    workspace: Path,
    framework_repo: Path = REPO_ROOT,
    source_label: str | None = None,
) -> list[Path]:
    workspace = workspace.expanduser()
    copied = vendor_framework(workspace, framework_repo, overwrite=True)
    copied.extend(copy_workspace_templates(workspace, framework_repo, overwrite=False))
    lock_path = workspace / ".draft" / "framework.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        yaml.safe_dump(framework_lock_data(framework_repo, source_label), sort_keys=False),
        encoding="utf-8",
    )
    return copied + [lock_path]


def framework_status(workspace: Path, framework_repo: Path = REPO_ROOT) -> dict[str, Any]:
    workspace = workspace.expanduser()
    vendor_root = workspace_framework_root(workspace)
    lock_path = workspace / ".draft" / "framework.lock"
    lock: dict[str, Any] = {}
    if lock_path.exists():
        try:
            loaded = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
            lock = loaded if isinstance(loaded, dict) else {}
        except yaml.YAMLError:
            lock = {}
    framework = lock.get("framework") if isinstance(lock.get("framework"), dict) else {}
    return {
        "vendored": (vendor_root / "tools" / "validate.py").exists(),
        "vendoredPath": str(vendor_root),
        "lockPath": str(lock_path),
        "syncedCommit": str(framework.get("syncedCommit") or framework.get("pinnedCommit") or ""),
        "installedCommit": current_framework_commit(framework_repo),
        "updatePolicy": str(framework.get("updatePolicy") or "explicit"),
    }


def ensure_workspace_layout(workspace: Path, framework_repo: Path = REPO_ROOT) -> list[Path]:
    workspace = workspace.expanduser()
    created: list[Path] = []
    for relative in WORKSPACE_DIRS:
        path = workspace / relative
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    copied = vendor_framework(workspace, framework_repo, overwrite=False)
    created.extend(copied)
    created.extend(copy_workspace_templates(workspace, framework_repo, overwrite=False))

    workspace_yaml = workspace / ".draft" / "workspace.yaml"
    if not workspace_yaml.exists():
        workspace_yaml.write_text(
            yaml.safe_dump(
                {
                    "schemaVersion": "1.0",
                    "workspace": {"name": workspace.name, "displayName": humanize_workspace_name(workspace.name)},
                    "framework": {
                        "source": DEFAULT_FRAMEWORK_SOURCE,
                        "vendoredPath": ".draft/framework",
                        "updatePolicy": "explicit",
                        "updateWorkflow": "enabled",
                    },
                    "paths": {
                        "catalog": "catalog",
                        "configurations": "configurations",
                    },
                    "requirements": {
                        "activeRequirementGroups": [],
                        "requireActiveRequirementGroupDisposition": False,
                    },
                    "vocabulary": {},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        created.append(workspace_yaml)

    framework_lock = workspace / ".draft" / "framework.lock"
    if not framework_lock.exists():
        framework_lock.write_text(yaml.safe_dump(framework_lock_data(framework_repo), sort_keys=False), encoding="utf-8")
        created.append(framework_lock)
    return created


def is_workspace(path: Path) -> bool:
    root = path.expanduser()
    framework_root = workspace_framework_root(root)
    return (
        (root / "catalog").exists()
        and (root / "configurations").exists()
        and (framework_root / "tools" / "validate.py").exists()
    )
