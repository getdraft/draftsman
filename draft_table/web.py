from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .catalog import build_reference_index, extract_refs, load_effective_catalog
from .config import load_config, save_config
from .draftsman import DraftsmanEngine
from .github import github_status
from .paths import REPO_ROOT
from .providers import detect_provider
from .repo import ensure_workspace_layout, framework_status, git_status, is_workspace
from .validation import validate_workspace


def create_app(config_path: Path | None = None) -> Any:
    try:
        from fastapi import Body, FastAPI, File, HTTPException, UploadFile
        from fastapi.responses import FileResponse, HTMLResponse
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "FastAPI runtime dependencies are missing. Install with: python3 -m pip install -e ."
        ) from exc

    app = FastAPI(title="DRAFT Table", version="0.1.0")
    draftsman = DraftsmanEngine(config_path)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/assets/draftlogo.png")
    def draft_logo() -> Any:
        logo_path = REPO_ROOT / "draftlogo.png"
        if not logo_path.exists():
            raise HTTPException(status_code=404, detail="DRAFT logo asset not found.")
        return FileResponse(logo_path, media_type="image/png")

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return status_payload(config_path)

    @app.get("/api/catalog")
    def catalog() -> dict[str, Any]:
        config = load_config(config_path)
        repo_value = str(config.get("content_repo_path") or "").strip()
        repo_path = Path(repo_value).expanduser() if repo_value else None
        framework_repo = Path(config.get("framework_repo_path") or REPO_ROOT).expanduser()
        objects = load_effective_catalog(repo_path, framework_repo)
        referenced_by = build_reference_index(objects)
        summaries = [
            catalog_object_payload(object_id, obj, referenced_by.get(object_id, []))
            for object_id, obj in sorted(objects.items(), key=lambda item: str(item[1].get("name") or item[0]).lower())
        ]
        return {"objects": summaries, "counts": catalog_counts(summaries)}

    @app.post("/api/repo/select")
    def select_repo(selection: dict[str, Any] = Body(...)) -> dict[str, Any]:
        repo_path = Path(str(selection.get("path") or "")).expanduser()
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail=f"Repository path does not exist: {repo_path}")
        created = ensure_workspace_layout(repo_path)
        config = load_config(config_path)
        config["content_repo_path"] = str(repo_path)
        save_config(config, config_path)
        return {"ok": True, "path": str(repo_path), "created": [str(path) for path in created]}

    @app.post("/api/draftsman/chat")
    def draftsman_chat(request: dict[str, Any] = Body(...)) -> dict[str, Any]:
        message = str(request.get("message") or "")
        session_id = str(request.get("sessionId") or "") or None
        if not message.strip():
            raise HTTPException(status_code=400, detail="Message is required.")
        return draftsman.chat(message, session_id).public_dict()

    @app.post("/api/draftsman/apply")
    def draftsman_apply(request: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            session_id = str(request.get("sessionId") or "")
            proposal_ids = request.get("proposalIds")
            if proposal_ids is not None and not isinstance(proposal_ids, list):
                raise ValueError("proposalIds must be a list when provided.")
            return draftsman.apply_proposals(session_id, proposal_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/draftsman/upload")
    async def draftsman_upload(sessionId: Optional[str] = None, file: UploadFile = File(...)) -> dict[str, Any]:
        session = draftsman.session_store.load(sessionId)
        upload_dir = draftsman.session_store.upload_dir(str(session["id"]))
        safe_name = safe_upload_name(file.filename or "upload")
        target = upload_dir / safe_name
        content = await file.read()
        target.write_bytes(content)
        item = {
            "name": safe_name,
            "path": str(target),
            "contentType": file.content_type or "application/octet-stream",
            "text": extract_upload_text(safe_name, file.content_type or "", content),
        }
        session.setdefault("uploads", []).append(item)
        draftsman.session_store.save(session)
        return {
            "sessionId": session["id"],
            "name": safe_name,
            "contentType": item["contentType"],
            "textAvailable": bool(item["text"]),
        }

    return app


def status_payload(config_path: Path | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    repo_value = str(config.get("content_repo_path") or "").strip()
    repo_path = Path(repo_value).expanduser() if repo_value else None
    framework_repo = Path(config.get("framework_repo_path") or REPO_ROOT).expanduser()
    provider = config.get("provider") or {}
    provider_status = detect_provider(
        str(provider.get("type") or ""),
        str(provider.get("executable") or provider.get("endpoint") or "") or None,
    )
    git = {"returncode": None, "stdout": "", "stderr": "No company DRAFT repo selected."}
    validation = {"returncode": None, "stdout": "", "stderr": "No company DRAFT repo selected."}
    framework = {"vendored": False, "vendoredPath": "", "syncedCommit": "", "installedCommit": ""}
    if repo_path and repo_path.exists():
        git_process = git_status(repo_path)
        git = {
            "returncode": git_process.returncode,
            "stdout": git_process.stdout,
            "stderr": git_process.stderr,
        }
        framework = framework_status(repo_path, framework_repo)
        validation_result = validate_workspace(repo_path, framework_repo)
        validation = {
            "returncode": validation_result.returncode,
            "stdout": validation_result.stdout,
            "stderr": validation_result.stderr,
        }
    return {
        "contentRepoPath": str(repo_path) if repo_path else "",
        "isWorkspace": is_workspace(repo_path) if repo_path and repo_path.exists() else False,
        "provider": {
            "type": provider_status.provider_type,
            "available": provider_status.available,
            "executable": provider_status.executable,
            "detail": provider_status.detail,
            "model": str(provider.get("model") or ""),
            "endpoint": str(provider.get("endpoint") or ""),
        },
        "github": github_status().__dict__,
        "git": git,
        "framework": framework,
        "validation": validation,
    }


def safe_upload_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in name)
    return safe.strip(".-") or "upload"


def extract_upload_text(name: str, content_type: str, content: bytes) -> str:
    lowered = name.lower()
    if content_type.startswith("text/") or lowered.endswith((".txt", ".md", ".csv", ".json", ".yaml", ".yml")):
        try:
            return content.decode("utf-8")[:20000]
        except UnicodeDecodeError:
            return content.decode("utf-8", errors="replace")[:20000]
    return ""


def catalog_object_payload(object_id: str, obj: dict[str, Any], referenced_by: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "id": object_id,
        "uid": object_id,
        "name": str(obj.get("name") or object_id),
        "type": str(obj.get("type") or ""),
        "typeLabel": type_label(str(obj.get("type") or "")),
        "status": str(obj.get("catalogStatus") or ""),
        "lifecycleStatus": str(obj.get("lifecycleStatus") or ""),
        "source": str(obj.get("_source") or ""),
        "description": str(obj.get("description") or "").strip(),
        "tags": string_list(obj.get("tags")),
        "owner": obj.get("owner") if isinstance(obj.get("owner"), dict) else {},
        "capabilities": string_list(obj.get("capabilities")),
        "requirementGroups": string_list(obj.get("requirementGroups")),
        "outboundRefs": [{"ref": ref, "path": path} for ref, path in extract_refs(obj)],
        "referencedBy": referenced_by,
        "summaryFields": summary_fields(obj),
    }


def catalog_counts(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for obj in objects:
        label = str(obj.get("typeLabel") or "Artifact")
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def summary_fields(obj: dict[str, Any]) -> list[dict[str, str]]:
    skip = {
        "_source",
        "schemaVersion",
        "uid",
        "id",
        "type",
        "name",
        "description",
        "tags",
        "owner",
        "catalogStatus",
        "lifecycleStatus",
        "requirementGroups",
        "requirementImplementations",
        "requirements",
        "implementations",
    }
    fields: list[dict[str, str]] = []
    for key, value in obj.items():
        if key in skip or value in (None, "", [], {}):
            continue
        if isinstance(value, (str, int, float, bool)):
            rendered = str(value)
        elif isinstance(value, list):
            rendered = ", ".join(str(item) for item in value if isinstance(item, (str, int, float, bool)))
            if not rendered:
                rendered = f"{len(value)} entries"
        elif isinstance(value, dict):
            rendered = f"{len(value)} entries"
        else:
            rendered = str(value)
        if rendered:
            fields.append({"key": key, "value": rendered[:300]})
        if len(fields) >= 10:
            break
    return fields


def type_label(object_type: str) -> str:
    labels = {
        "technology_component": "TechnologyComponent",
        "edge_gateway_service": "EdgeGatewayService",
        "host": "Host",
        "runtime_service": "RuntimeService",
        "data_store_service": "DataStoreService",
        "product_component": "ProductComponent",
        "edge_gateway_service": "EdgeGatewayService",
        "reference_architecture": "ReferenceArchitecture",
        "software_deployment_pattern": "SoftwareDeploymentPattern",
        "capability": "Capability",
        "requirement_group": "RequirementGroup",
        "decision_record": "DecisionRecord",
        "drafting_session": "DraftingSession",
        "domain": "Domain",
    }
    return labels.get(object_type, object_type.replace("_", " ").title() if object_type else "Artifact")


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DRAFT Table</title>
  <style>
    :root {
      color-scheme: dark;
      --page: #0f172a;
      --panel: #111827;
      --card: #1e293b;
      --border: #334155;
      --muted: #94a3b8;
      --text: #e2e8f0;
      --subtle: #cbd5e1;
      --accent: #38bdf8;
      --ok: #10b981;
      --warn: #f59e0b;
      --bad: #ef4444;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      min-height: 100%;
      background: var(--page);
      color: var(--text);
      font-family: "SF Pro Display", "Segoe UI", ui-sans-serif, system-ui, sans-serif;
    }
    button, input, textarea { font: inherit; }
    .page-shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 380px minmax(0, 1fr);
      gap: 1px;
      background: var(--border);
    }
    .sidebar,
    .main {
      background: linear-gradient(180deg, rgba(15,23,42,0.98), rgba(17,24,39,0.98));
    }
    .sidebar {
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      gap: 18px;
      padding: 24px 20px;
      border-right: 1px solid rgba(51,65,85,0.7);
      min-height: 100vh;
    }
    .browser-brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .browser-logo {
      width: 54px;
      height: 54px;
      object-fit: contain;
      flex: 0 0 auto;
    }
    .sidebar h1 {
      margin: 0;
      font-size: 18px;
      letter-spacing: 0.02em;
    }
    .catalog-name {
      color: var(--subtle);
      font-size: 13px;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }
    .mode-badge {
      display: inline-flex;
      width: fit-content;
      margin-top: 10px;
      padding: 5px 9px;
      border: 1px solid rgba(56,189,248,0.38);
      border-radius: 999px;
      color: #bae6fd;
      background: rgba(56,189,248,0.12);
      font-size: 11px;
      font-weight: 700;
    }
    .side-tabs,
    .top-nav,
    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .nav-button,
    .side-tab,
    .action-button {
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(15,23,42,0.72);
      color: var(--text);
      padding: 10px 16px;
      cursor: pointer;
      transition: border-color 120ms ease, background 120ms ease, transform 120ms ease;
    }
    .side-tab {
      flex: 1 1 auto;
      border-radius: 14px;
      padding: 10px 12px;
      font-size: 13px;
      font-weight: 700;
    }
    .nav-button:hover,
    .side-tab:hover,
    .action-button:hover {
      border-color: rgba(56,189,248,0.55);
      transform: translateY(-1px);
    }
    .nav-button.active,
    .side-tab.active,
    .action-button.primary {
      background: rgba(56,189,248,0.18);
      border-color: rgba(56,189,248,0.6);
      color: #dff7ff;
    }
    .nav-button:disabled,
    .action-button:disabled {
      cursor: default;
      opacity: 0.45;
      transform: none;
    }
    .sidebar-panel {
      min-height: 0;
      overflow: auto;
      display: grid;
      align-content: start;
      gap: 14px;
      padding-right: 4px;
    }
    .sidebar-block,
    .section-card,
    .object-card,
    .empty-card,
    .header-card,
    .message,
    .proposal-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
    }
    .sidebar-block {
      padding: 14px;
      display: grid;
      gap: 12px;
    }
    .sidebar-block h2,
    .sidebar-block h3,
    .section-card h3 {
      margin: 0;
      font-size: 14px;
      letter-spacing: 0.02em;
    }
    .muted {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .messages {
      display: grid;
      gap: 10px;
      min-height: 280px;
      max-height: 42vh;
      overflow: auto;
      padding: 10px;
      border: 1px solid rgba(51,65,85,0.75);
      border-radius: 14px;
      background: rgba(15,23,42,0.55);
    }
    .message {
      padding: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
      font-size: 13px;
    }
    .message.user {
      border-color: rgba(56,189,248,0.38);
      background: rgba(56,189,248,0.12);
    }
    .message.draftsman {
      background: rgba(30,41,59,0.92);
    }
    textarea,
    input[type="text"],
    input[type="search"],
    input[type="file"] {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 11px 12px;
      background: rgba(15,23,42,0.72);
      color: var(--text);
    }
    textarea {
      min-height: 96px;
      resize: vertical;
      line-height: 1.4;
    }
    label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .main {
      padding: 28px;
      overflow: auto;
    }
    .view-shell {
      display: grid;
      gap: 22px;
    }
    .view-title {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 14px;
      color: var(--muted);
      font-size: 14px;
    }
    .content-rows {
      display: grid;
      gap: 24px;
    }
    .content-row {
      display: grid;
      gap: 14px;
    }
    .content-row-header {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(51,65,85,0.72);
    }
    .content-row-title {
      margin: 0;
      font-size: 15px;
      letter-spacing: 0.02em;
    }
    .content-row-count {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      gap: 18px;
    }
    .object-card {
      padding: 18px;
      display: grid;
      gap: 12px;
      cursor: pointer;
      min-height: 168px;
      transition: border-color 120ms ease, transform 120ms ease, box-shadow 120ms ease;
    }
    .object-card:hover {
      border-color: rgba(56,189,248,0.5);
      transform: translateY(-2px);
      box-shadow: 0 12px 24px rgba(2,6,23,0.22);
    }
    .object-card h3 {
      margin: 0;
      font-size: 16px;
      line-height: 1.35;
    }
    .object-id,
    .field-value {
      color: var(--muted);
      font-size: 12px;
      word-break: break-word;
    }
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      border: 1px solid rgba(148,163,184,0.18);
      background: rgba(15,23,42,0.65);
      color: var(--subtle);
      width: fit-content;
    }
    .catalog-approved,
    .ok-badge {
      border-color: rgba(16,185,129,0.45);
      color: #d1fae5;
    }
    .catalog-draft,
    .warn-badge {
      border-color: rgba(245,158,11,0.45);
      color: #fde68a;
    }
    .catalog-stub,
    .info-badge {
      border-color: rgba(148,163,184,0.35);
      color: #cbd5e1;
    }
    .header-card {
      padding: 22px;
      display: grid;
      gap: 14px;
    }
    .header-top {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
    }
    .header-title h2 {
      margin: 0;
      font-size: 28px;
      line-height: 1.15;
    }
    .header-title .object-id {
      margin-top: 6px;
      font-size: 13px;
    }
    .header-description {
      color: var(--subtle);
      line-height: 1.6;
      font-size: 14px;
    }
    .section-card {
      padding: 18px;
      display: grid;
      gap: 12px;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
    }
    .definition-list {
      display: grid;
      gap: 10px;
      margin: 0;
    }
    .definition-list dt {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .definition-list dd {
      margin: 2px 0 0;
      color: var(--subtle);
      line-height: 1.5;
      word-break: break-word;
    }
    .proposal-card {
      display: grid;
      gap: 10px;
      padding: 14px;
      cursor: pointer;
    }
    .proposal-card.active {
      border-color: rgba(56,189,248,0.6);
      background: rgba(56,189,248,0.1);
    }
    .command-list {
      display: grid;
      gap: 10px;
    }
    .guide-list {
      display: grid;
      gap: 12px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .guide-list li {
      padding-left: 14px;
      border-left: 3px solid rgba(56,189,248,0.45);
      color: var(--subtle);
      line-height: 1.55;
    }
    .guide-list strong {
      color: var(--text);
    }
    .command {
      margin: 0;
      white-space: pre-wrap;
      overflow: auto;
      padding: 12px;
      border: 1px solid rgba(51,65,85,0.85);
      border-radius: 14px;
      background: rgba(15,23,42,0.72);
      color: #bfdbfe;
      font-size: 12px;
      line-height: 1.5;
    }
    .empty-card {
      padding: 22px;
      color: var(--muted);
      line-height: 1.5;
    }
    @media (max-width: 980px) {
      .page-shell { grid-template-columns: 1fr; }
      .sidebar { min-height: auto; border-right: 0; border-bottom: 1px solid rgba(51,65,85,0.7); }
      .messages { max-height: 320px; }
      .main { padding: 20px; }
    }
  </style>
</head>
<body>
  <div class="page-shell">
    <aside class="sidebar">
      <div class="browser-brand">
        <img class="browser-logo brand-logo" src="/assets/draftlogo.png" alt="DRAFT">
        <div>
          <h1>DRAFT Table</h1>
          <div class="catalog-name" id="catalog-name">Loading workspace...</div>
          <div class="mode-badge">Local Draftsman</div>
        </div>
      </div>
      <div class="side-tabs">
        <button class="side-tab active" data-side-tab="draftsman">Draftsman</button>
        <button class="side-tab" data-side-tab="guide">Guide</button>
        <button class="side-tab" data-side-tab="catalog">Catalog</button>
        <button class="side-tab" data-side-tab="configuration">Configuration</button>
      </div>
      <div class="sidebar-panel" id="sidebar-panel"></div>
    </aside>
    <main class="main">
      <div id="main-root" class="view-shell"></div>
    </main>
  </div>
  <script>
    let sessionId = null;
    let statusData = null;
    let catalogData = {objects: [], counts: {}};
    let activeSideTab = 'draftsman';
    let searchTerm = '';
    let focused = null;
    let latestProposals = [];
    let messages = [];

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char]));
    }

    function statusBadge(value) {
      const normalized = String(value || '').toLowerCase();
      const cls = normalized === 'approved' ? 'catalog-approved' : normalized === 'draft' ? 'catalog-draft' : normalized === 'stub' ? 'catalog-stub' : 'info-badge';
      return value ? `<span class="badge ${cls}">${escapeHtml(value)}</span>` : '';
    }

    function setSideTab(tab) {
      activeSideTab = tab;
      renderSidebar();
      renderMain();
    }

    function syncSideTabs() {
      document.querySelectorAll('[data-side-tab]').forEach(button => {
        button.classList.toggle('active', button.dataset.sideTab === activeSideTab);
      });
    }

    function addMessage(role, text) {
      messages.push({role, text});
      renderSidebar();
      scrollMessages();
    }

    function replaceLastDraftsmanMessage(text) {
      if (messages.length) {
        messages[messages.length - 1].text = text;
      } else {
        messages.push({role: 'draftsman', text});
      }
      renderSidebar();
      scrollMessages();
    }

    function scrollMessages() {
      requestAnimationFrame(() => {
        const node = document.getElementById('messages');
        if (node) node.scrollTop = node.scrollHeight;
      });
    }

    async function readJson(response) {
      const text = await response.text();
      if (!text) return {};
      try {
        return JSON.parse(text);
      } catch (error) {
        return {detail: text};
      }
    }

    async function refreshStatus() {
      const response = await fetch('/api/status');
      statusData = await response.json();
      const repo = statusData.contentRepoPath || 'No company DRAFT repo selected';
      document.getElementById('catalog-name').textContent = repo;
    }

    async function refreshCatalog() {
      const response = await fetch('/api/catalog');
      catalogData = await response.json();
    }

    async function refreshAll() {
      await refreshStatus();
      await refreshCatalog();
      renderSidebar();
      renderMain();
    }

    function renderSidebar() {
      syncSideTabs();
      const panel = document.getElementById('sidebar-panel');
      if (activeSideTab === 'catalog') {
        panel.innerHTML = catalogSidebarMarkup();
        bindCatalogSidebar();
      } else if (activeSideTab === 'guide') {
        panel.innerHTML = guideSidebarMarkup();
      } else if (activeSideTab === 'configuration') {
        panel.innerHTML = configurationSidebarMarkup();
      } else {
        panel.innerHTML = draftsmanSidebarMarkup();
        bindDraftsmanSidebar();
      }
    }

    function draftsmanSidebarMarkup() {
      const messageMarkup = messages.length
        ? messages.map(message => `<div class="message ${escapeHtml(message.role)}">${escapeHtml(message.text)}</div>`).join('')
        : '<div class="empty-card">Start the drafting conversation.</div>';
      const proposalMarkup = latestProposals.length ? `
        <div class="sidebar-block">
          <h3>Proposed Artifacts</h3>
          ${latestProposals.map(proposal => `
            <div class="proposal-card ${focused?.kind === 'proposal' && focused.data.id === proposal.id ? 'active' : ''}" data-proposal-id="${escapeHtml(proposal.id)}">
              <div class="badges">
                <span class="badge warn-badge">${escapeHtml(proposal.action || 'propose')}</span>
                <span class="badge">${escapeHtml(proposal.artifactType || 'Artifact')}</span>
              </div>
              <strong>${escapeHtml(proposal.name || proposal.id)}</strong>
              <div class="muted">${escapeHtml(proposal.summary || 'No summary provided.')}</div>
            </div>
          `).join('')}
          <button class="action-button primary" id="apply-proposals">Apply Proposed Artifacts</button>
        </div>
      ` : '';
      return `
        <div class="sidebar-block">
          <h2>Draftsman Conversation</h2>
          <div class="quick-actions">
            <button class="action-button" data-draftsman-prompt="start setup mode">Start Setup Mode</button>
            <button class="action-button" data-draftsman-prompt="Start a guided drafting session for one product or system.">Start DraftingSession</button>
          </div>
          <div class="messages" id="messages">${messageMarkup}</div>
          <label for="upload">Source Material</label>
          <input id="upload" type="file">
          <button class="action-button" id="upload-button">Attach Source</button>
          <div class="muted" id="upload-message"></div>
          <label for="draftsman-message">Message</label>
          <textarea id="draftsman-message"></textarea>
          <button class="action-button primary" id="send-message">Send</button>
        </div>
        ${proposalMarkup}
      `;
    }

    function guideSidebarMarkup() {
      return `
        <div class="sidebar-block">
          <h2>New User Guide</h2>
          <div class="muted">DRAFT is a structured architecture catalog for deployable systems. The Draftsman helps you turn conversations, diagrams, notes, and product intent into architecture artifacts that can be reviewed, validated, and reused.</div>
        </div>
        <div class="sidebar-block">
          <h3>Good First Questions</h3>
          <ul class="guide-list">
            <li>What is a TechnologyComponent?</li>
            <li>Start setup mode.</li>
            <li>What deployable objects already exist for this product?</li>
            <li>Where is the Falcon agent used?</li>
            <li>Start a drafting session for my new service.</li>
          </ul>
        </div>
        <div class="sidebar-block">
          <h3>Daily Path</h3>
          <ul class="guide-list">
            <li>Ask the Draftsman to explain or draft.</li>
            <li>Review the focused artifact on the right.</li>
            <li>Apply proposed changes when they look right.</li>
            <li>Validate, commit, and push through Git.</li>
          </ul>
        </div>
      `;
    }

    function bindDraftsmanSidebar() {
      document.querySelectorAll('[data-proposal-id]').forEach(card => {
        card.addEventListener('click', () => {
          const proposal = latestProposals.find(item => item.id === card.dataset.proposalId);
          if (proposal) {
            focused = {kind: 'proposal', data: proposal};
            renderSidebar();
            renderMain();
          }
        });
      });
      const input = document.getElementById('draftsman-message');
      if (input) {
        input.addEventListener('keydown', event => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
          }
        });
      }
      document.getElementById('send-message')?.addEventListener('click', sendMessage);
      document.querySelectorAll('[data-draftsman-prompt]').forEach(button => {
        button.addEventListener('click', () => {
          const prompt = button.dataset.draftsmanPrompt || '';
          const messageInput = document.getElementById('draftsman-message');
          if (messageInput) {
            messageInput.value = prompt;
          }
          sendMessage();
        });
      });
      document.getElementById('upload-button')?.addEventListener('click', uploadSource);
      document.getElementById('apply-proposals')?.addEventListener('click', applyProposals);
    }

    function catalogSidebarMarkup() {
      const counts = Object.entries(catalogData.counts || {});
      return `
        <div class="sidebar-block">
          <h2>Catalog</h2>
          <input type="search" id="catalog-search" value="${escapeHtml(searchTerm)}">
          <div class="pill-row">
            ${counts.map(([label, count]) => `<span class="badge">${escapeHtml(label)}: ${count}</span>`).join('') || '<span class="badge">No objects loaded</span>'}
          </div>
        </div>
      `;
    }

    function bindCatalogSidebar() {
      const input = document.getElementById('catalog-search');
      input?.addEventListener('input', event => {
        searchTerm = event.target.value;
        renderMain();
      });
    }

    function configurationSidebarMarkup() {
      const provider = statusData?.provider || {};
      const framework = statusData?.framework || {};
      const repo = statusData?.contentRepoPath || 'Not selected';
      const providerCommand = providerCommandFor(provider.type);
      return `
        <div class="sidebar-block">
          <h2>Configuration</h2>
          <dl class="definition-list">
            <div><dt>Company Repo</dt><dd>${escapeHtml(repo)}</dd></div>
            <div><dt>AI Provider</dt><dd>${escapeHtml(provider.type || 'Not selected')}</dd></div>
            <div><dt>Provider Status</dt><dd>${escapeHtml(provider.detail || 'Unknown')}</dd></div>
            <div><dt>Framework Copy</dt><dd>${escapeHtml(framework.vendoredPath || 'Not available')}</dd></div>
            <div><dt>Synced Commit</dt><dd>${escapeHtml(framework.syncedCommit || 'Unknown')}</dd></div>
          </dl>
        </div>
        <div class="sidebar-block">
          <h3>Commands</h3>
          <div class="command-list">
            <pre class="command">draft-table onboard</pre>
            <pre class="command">draft-table ai doctor</pre>
            <pre class="command">draft-table framework status</pre>
            <pre class="command">draft-table framework refresh</pre>
            <pre class="command">draft-table validate</pre>
            ${providerCommand ? `<pre class="command">${escapeHtml(providerCommand)}</pre>` : ''}
          </div>
        </div>
      `;
    }

    function providerCommandFor(providerType) {
      if (providerType === 'codex') return 'codex --login';
      if (providerType === 'claude-code') return 'claude';
      if (providerType === 'gemini-cli') return 'gemini';
      return '';
    }

    function renderMain() {
      const root = document.getElementById('main-root');
      const canFocus = Boolean(focused);
      const mainMode = activeSideTab === 'configuration'
        ? 'configuration'
        : activeSideTab === 'guide'
          ? 'guide'
          : focused
            ? 'focus'
            : 'catalog';
      const focusActive = mainMode === 'focus';
      root.innerHTML = `
        <div class="top-nav">
          <button class="nav-button ${mainMode === 'catalog' ? 'active' : ''}" id="nav-catalog">Catalog Browser</button>
          <button class="nav-button ${focusActive ? 'active' : ''}" id="nav-focus" ${canFocus ? '' : 'disabled'}>Focused Artifact</button>
          <button class="nav-button ${mainMode === 'guide' ? 'active' : ''}" id="nav-guide">Guide</button>
          <button class="nav-button ${activeSideTab === 'configuration' ? 'active' : ''}" id="nav-config">Configuration</button>
          <button class="nav-button" id="nav-refresh">Refresh</button>
        </div>
        ${mainMode === 'configuration' ? renderConfigurationDetail() : mainMode === 'guide' ? renderGuideDetail() : mainMode === 'focus' ? renderFocus() : renderCatalog()}
      `;
      document.getElementById('nav-catalog')?.addEventListener('click', () => {
        focused = null;
        setSideTab('catalog');
      });
      document.getElementById('nav-focus')?.addEventListener('click', () => {
        if (!focused) return;
        if (activeSideTab === 'configuration' || activeSideTab === 'guide') {
          activeSideTab = 'catalog';
          renderSidebar();
        }
        renderMain();
      });
      document.getElementById('nav-guide')?.addEventListener('click', () => setSideTab('guide'));
      document.getElementById('nav-config')?.addEventListener('click', () => setSideTab('configuration'));
      document.getElementById('nav-refresh')?.addEventListener('click', refreshAll);
      bindObjectCards();
      document.getElementById('focus-apply-proposals')?.addEventListener('click', applyProposals);
      document.getElementById('focus-clear')?.addEventListener('click', () => {
        focused = null;
        renderMain();
      });
    }

    function renderGuideDetail() {
      return `
        <section class="header-card">
          <div class="header-top">
            <div class="header-title">
              <h2>What DRAFT Is</h2>
              <div class="object-id">Deployable Reference Architecture Framework Toolkit</div>
            </div>
            <div class="badges">
              <span class="badge ok-badge">Architecture Catalog</span>
              <span class="badge">Git Source Of Truth</span>
              <span class="badge">AI Assisted</span>
            </div>
          </div>
          <div class="header-description">DRAFT helps a company describe deployable architecture as reusable artifacts. The framework provides the rules, checklists, schemas, examples, and Draftsman guidance. Your company repo contains the private catalog: the deployable objects, product deployment patterns, decisions, and compliance posture that describe how your systems should be built and operated.</div>
        </section>
        <div class="detail-grid">
          <section class="section-card">
            <h3>How To Navigate</h3>
            <ul class="guide-list">
              <li><strong>Draftsman</strong> is the conversation workspace. Ask questions, attach source material, and review proposed artifacts.</li>
              <li><strong>Setup Mode</strong> is the first-run guided path. It shows the current step, next step, remaining setup work, and revisit-later choices.</li>
              <li><strong>Guide</strong> explains the working model and the common object types.</li>
              <li><strong>Catalog</strong> browses the loaded artifacts from the framework and company workspace.</li>
              <li><strong>Configuration</strong> shows the selected company repo, AI provider, framework copy, validation status, and repair commands.</li>
            </ul>
          </section>
          <section class="section-card">
            <h3>Core Artifacts</h3>
            <ul class="guide-list">
              <li><strong>TechnologyComponent</strong>: a discrete product, operating system, software package, tool, runtime, or agent.</li>
              <li><strong>Host</strong>: a reusable compute standard built from an operating system, compute platform, and required operational capabilities.</li>
              <li><strong>RuntimeService</strong>: a reusable service building block that combines a host or platform with the primary internal component that makes it useful.</li>
              <li><strong>DataStoreService</strong>: a data service standard with durability, protection, operation, and compliance expectations.</li>
              <li><strong>EdgeGatewayService</strong>: a vendor product that behaves like a service but does not expose a host model.</li>
            </ul>
          </section>
          <section class="section-card">
            <h3>Architecture Artifacts</h3>
            <ul class="guide-list">
              <li><strong>ReferenceArchitecture</strong>: a reusable architecture pattern for a class of deployments.</li>
              <li><strong>SoftwareDeploymentPattern</strong>: the intended deployable shape of a product or system that follows a reference architecture.</li>
              <li><strong>DecisionRecord</strong>: a documented architecture decision or risk that affects deployment choices.</li>
              <li><strong>DraftingSession</strong>: a work-in-progress record for assumptions, source material, generated objects, and unanswered questions.</li>
            </ul>
          </section>
          <section class="section-card">
            <h3>Controls And Completeness</h3>
            <ul class="guide-list">
              <li><strong>Capability</strong>: a first-class capability that can point the Draftsman to approved TechnologyComponent implementations.</li>
              <li><strong>RequirementGroup</strong>: the required questions an artifact must answer, including always-on definition requirements and workspace-activated controls.</li>
              <li><strong>Validation</strong>: the executable check that confirms objects follow the framework and resolve their relationships.</li>
            </ul>
          </section>
          <section class="section-card">
            <h3>How Content Gets Updated</h3>
            <ul class="guide-list">
              <li>Start in the Draftsman tab and describe what you are building, changing, or trying to understand.</li>
              <li>For a new workspace, start setup mode before drafting product architecture.</li>
              <li>Attach source material when useful: diagrams, documents, notes, inventories, or screenshots.</li>
              <li>The Draftsman searches the current catalog first, reuses existing artifacts when possible, and asks focused follow-up questions for gaps.</li>
              <li>Proposed artifacts appear as plain-language review cards. Applying them updates the company repo internally and runs validation.</li>
              <li>After review, use normal Git workflow to commit, push, and open a pull request when your company requires review.</li>
            </ul>
          </section>
          <section class="section-card">
            <h3>How To Think About DRAFT</h3>
            <ul class="guide-list">
              <li>The framework is shared. The company catalog is private.</li>
              <li>Artifacts should be reusable, deployable, and specific enough for automation to trust later.</li>
              <li>Missing facts should be recorded as questions or drafting-session gaps, not hidden in prose.</li>
              <li>Compliance is selected by the company and then becomes part of the drafting conversation for new and updated artifacts.</li>
            </ul>
          </section>
        </div>
      `;
    }

    function renderCatalog() {
      const filtered = filteredObjects();
      const grouped = groupByType(filtered);
      return `
        <div class="view-title">
          <span>${filtered.length} objects</span>
          <span>${escapeHtml(statusData?.contentRepoPath || 'Example framework catalog')}</span>
        </div>
        <div class="content-rows">
          ${Object.entries(grouped).map(([label, objects]) => `
            <section class="content-row">
              <div class="content-row-header">
                <h2 class="content-row-title">${escapeHtml(label)}</h2>
                <span class="content-row-count">${objects.length} objects</span>
              </div>
              <div class="cards-grid">
                ${objects.map(objectCardMarkup).join('')}
              </div>
            </section>
          `).join('') || '<div class="empty-card">No matching catalog objects.</div>'}
        </div>
      `;
    }

    function filteredObjects() {
      const query = searchTerm.trim().toLowerCase();
      if (!query) return catalogData.objects || [];
      return (catalogData.objects || []).filter(object => [
        object.id,
        object.name,
        object.typeLabel,
        object.description,
        object.source
      ].join(' ').toLowerCase().includes(query));
    }

    function groupByType(objects) {
      return objects.reduce((groups, object) => {
        const label = object.typeLabel || 'Artifact';
        groups[label] = groups[label] || [];
        groups[label].push(object);
        return groups;
      }, {});
    }

    function objectCardMarkup(object) {
      return `
        <article class="object-card" data-object-id="${escapeHtml(object.id)}">
          <div class="badges">
            <span class="badge">${escapeHtml(object.typeLabel)}</span>
            ${statusBadge(object.status)}
          </div>
          <h3>${escapeHtml(object.name)}</h3>
          <div class="object-id">${escapeHtml(object.id)}</div>
          <div class="muted">${escapeHtml(object.description || object.source || 'No description available.')}</div>
        </article>
      `;
    }

    function bindObjectCards() {
      document.querySelectorAll('[data-object-id]').forEach(card => {
        card.addEventListener('click', () => {
          const object = (catalogData.objects || []).find(item => item.id === card.dataset.objectId);
          if (object) {
            focused = {kind: 'object', data: object};
            renderMain();
          }
        });
      });
    }

    function renderFocus() {
      if (!focused) return renderCatalog();
      return focused.kind === 'proposal' ? renderProposalFocus(focused.data) : renderObjectFocus(focused.data);
    }

    function renderObjectFocus(object) {
      return `
        <section class="header-card">
          <div class="header-top">
            <div class="header-title">
              <h2>${escapeHtml(object.name)}</h2>
              <div class="object-id">${escapeHtml(object.id)}</div>
            </div>
            <div class="badges">
              <span class="badge">${escapeHtml(object.typeLabel)}</span>
              ${statusBadge(object.status)}
              ${object.lifecycleStatus ? `<span class="badge">${escapeHtml(object.lifecycleStatus)}</span>` : ''}
            </div>
          </div>
          <div class="header-description">${escapeHtml(object.description || 'No description available.')}</div>
        </section>
        <div class="detail-grid">
          <section class="section-card">
            <h3>Object Facts</h3>
            ${definitionList([
              ['Source', object.source],
              ['Owner', object.owner?.team || object.owner?.contact || ''],
              ['Capabilities', (object.capabilities || []).join(', ')],
              ['RequirementGroups', (object.requirementGroups || []).join(', ')]
            ])}
          </section>
          <section class="section-card">
            <h3>Relationships</h3>
            ${relationshipList(object)}
          </section>
          <section class="section-card">
            <h3>Additional Fields</h3>
            ${definitionList((object.summaryFields || []).map(field => [field.key, field.value]))}
          </section>
        </div>
      `;
    }

    function renderProposalFocus(proposal) {
      return `
        <section class="header-card">
          <div class="header-top">
            <div class="header-title">
              <h2>${escapeHtml(proposal.name || proposal.id)}</h2>
              <div class="object-id">${escapeHtml(proposal.artifactId || proposal.path || proposal.id)}</div>
            </div>
            <div class="badges">
              <span class="badge warn-badge">Proposal</span>
              <span class="badge">${escapeHtml(proposal.action || 'create')}</span>
              <span class="badge">${escapeHtml(proposal.artifactType || 'Artifact')}</span>
            </div>
          </div>
          <div class="header-description">${escapeHtml(proposal.summary || 'No summary provided.')}</div>
          <div class="pill-row">
            <button class="action-button primary" id="focus-apply-proposals">Apply Proposed Artifacts</button>
            <button class="action-button" id="focus-clear">Back To Catalog</button>
          </div>
        </section>
        <div class="detail-grid">
          <section class="section-card">
            <h3>Review</h3>
            ${definitionList([
              ['Artifact ID', proposal.artifactId],
              ['Path', proposal.path],
              ['Action', proposal.action],
              ['Status', proposal.applied ? 'Applied' : 'Not applied']
            ])}
          </section>
          <section class="section-card">
            <h3>Validation</h3>
            <div class="muted">${escapeHtml(statusData?.validation?.stdout || statusData?.validation?.stderr || 'Validation has not run yet.')}</div>
          </section>
        </div>
      `;
    }

    function relationshipList(object) {
      const refs = object.outboundRefs || [];
      const incoming = object.referencedBy || [];
      const rows = [
        ...refs.map(item => ['Uses', `${item.ref} via ${item.path}`]),
        ...incoming.map(item => ['Used By', `${item.source} via ${item.path}`])
      ];
      return definitionList(rows.length ? rows : [['Relationships', 'No relationships found in the loaded model.']]);
    }

    function definitionList(rows) {
      const normalized = rows.filter(row => row[1]);
      if (!normalized.length) return '<div class="muted">No values recorded.</div>';
      return `<dl class="definition-list">${normalized.map(row => `<div><dt>${escapeHtml(row[0])}</dt><dd>${escapeHtml(row[1])}</dd></div>`).join('')}</dl>`;
    }

    function renderConfigurationDetail() {
      const provider = statusData?.provider || {};
      const framework = statusData?.framework || {};
      const github = statusData?.github || {};
      return `
        <section class="header-card">
          <div class="header-top">
            <div class="header-title">
              <h2>Configuration</h2>
              <div class="object-id">${escapeHtml(statusData?.contentRepoPath || 'No company DRAFT repo selected')}</div>
            </div>
            <div class="badges">
              <span class="badge ${provider.available ? 'ok-badge' : 'warn-badge'}">${provider.available ? 'Provider Available' : 'Provider Missing'}</span>
              <span class="badge ${statusData?.isWorkspace ? 'ok-badge' : 'warn-badge'}">${statusData?.isWorkspace ? 'Workspace Ready' : 'Workspace Needs Setup'}</span>
            </div>
          </div>
        </section>
        <div class="detail-grid">
          <section class="section-card">
            <h3>Repo And Framework</h3>
            ${definitionList([
              ['Company Repo', statusData?.contentRepoPath],
              ['Vendored Framework', framework.vendoredPath],
              ['Synced Commit', framework.syncedCommit],
              ['Installed Commit', framework.installedCommit]
            ])}
          </section>
          <section class="section-card">
            <h3>AI And GitHub</h3>
            ${definitionList([
              ['Provider', provider.type],
              ['Executable', provider.executable],
              ['Model', provider.model],
              ['Endpoint', provider.endpoint],
              ['GitHub', github.detail]
            ])}
          </section>
          <section class="section-card">
            <h3>Commands</h3>
            <div class="command-list">
              <pre class="command">draft-table onboard</pre>
              <pre class="command">draft-table ai doctor</pre>
              <pre class="command">draft-table framework status</pre>
              <pre class="command">draft-table framework refresh</pre>
              <pre class="command">draft-table validate</pre>
              ${providerCommandFor(provider.type) ? `<pre class="command">${escapeHtml(providerCommandFor(provider.type))}</pre>` : ''}
            </div>
          </section>
          <section class="section-card">
            <h3>Validation</h3>
            <div class="muted">${escapeHtml(statusData?.validation?.stdout || statusData?.validation?.stderr || 'Validation has not run yet.')}</div>
          </section>
        </div>
      `;
    }

    async function sendMessage() {
      const input = document.getElementById('draftsman-message');
      const message = input?.value.trim();
      if (!message) return;
      addMessage('user', message);
      input.value = '';
      addMessage('draftsman', 'Thinking...');
      try {
        const response = await fetch('/api/draftsman/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({message, sessionId})
        });
        const data = await readJson(response);
        sessionId = data.sessionId || sessionId;
        if (!response.ok) {
          throw new Error(data.detail || `Request failed with HTTP ${response.status}.`);
        }
        replaceLastDraftsmanMessage(data.answer || data.detail || 'No response.');
        if (data.questions?.length) {
          addMessage('draftsman', `I need to confirm:\\n- ${data.questions.join('\\n- ')}`);
        }
        latestProposals = data.proposals || [];
        if (latestProposals.length) {
          focused = {kind: 'proposal', data: latestProposals[0]};
        }
        activeSideTab = 'draftsman';
        renderSidebar();
        renderMain();
      } catch (error) {
        replaceLastDraftsmanMessage(`The Draftsman request failed: ${error.message}`);
        latestProposals = [];
        renderSidebar();
      }
    }

    async function uploadSource() {
      const input = document.getElementById('upload');
      const message = document.getElementById('upload-message');
      if (!input?.files.length) {
        if (message) message.textContent = 'Choose a file first.';
        return;
      }
      const form = new FormData();
      form.append('file', input.files[0]);
      const url = sessionId ? `/api/draftsman/upload?sessionId=${encodeURIComponent(sessionId)}` : '/api/draftsman/upload';
      const response = await fetch(url, {method: 'POST', body: form});
      const data = await response.json();
      sessionId = data.sessionId || sessionId;
      if (message) message.textContent = response.ok ? `Attached ${data.name}` : data.detail;
    }

    async function applyProposals() {
      if (!sessionId || !latestProposals.length) return;
      const response = await fetch('/api/draftsman/apply', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({sessionId, proposalIds: latestProposals.map(proposal => proposal.id)})
      });
      const data = await response.json();
      if (!response.ok) {
        addMessage('draftsman', data.detail || 'Could not apply the proposed artifacts.');
        return;
      }
      const applied = data.applied || [];
      addMessage('draftsman', `Applied artifact changes${applied.length ? `:\\n- ${applied.map(item => `${item.artifactType || 'Artifact'}: ${item.name || item.id}`).join('\\n- ')}` : '.'}\\nValidation ${data.validation?.ok ? 'passed' : 'needs attention'}.`);
      latestProposals = [];
      await refreshStatus();
      await refreshCatalog();
      const appliedObject = findAppliedObject(applied[0]);
      focused = appliedObject
        ? {kind: 'object', data: appliedObject}
        : applied.length ? {kind: 'proposal', data: {...applied[0], action: 'applied', summary: 'Applied to the company DRAFT repo.', applied: true}} : null;
      renderSidebar();
      renderMain();
    }

    function findAppliedObject(item) {
      if (!item) return null;
      const objects = catalogData.objects || [];
      return objects.find(object => object.id === item.artifactId)
        || objects.find(object => item.path && String(object.source || '').endsWith(item.path))
        || objects.find(object => object.name === item.name)
        || null;
    }

    document.querySelectorAll('[data-side-tab]').forEach(button => {
      button.addEventListener('click', () => setSideTab(button.dataset.sideTab));
    });

    refreshAll();
  </script>
</body>
</html>
"""
