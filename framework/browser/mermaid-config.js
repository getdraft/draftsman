// Generated catalog diagrams can exceed Mermaid's default 50 KB text limit.
// This asset also enhances the generated Diagrams view without changing the core
// browser bundle.
(function () {
  const MERMAID_MAX_TEXT_SIZE = 1000000;

  function patchMermaidInitialize() {
    if (!window.mermaid || window.mermaid.__draftMaxTextSizePatched) {
      return;
    }

    const originalInitialize = window.mermaid.initialize;
    if (typeof originalInitialize !== 'function') {
      return;
    }

    window.mermaid.initialize = function initializeWithDraftDefaults(config) {
      const safeConfig = config && typeof config === 'object' ? config : {};
      return originalInitialize.call(this, {
        ...safeConfig,
        maxTextSize: safeConfig.maxTextSize ?? MERMAID_MAX_TEXT_SIZE
      });
    };
    window.mermaid.__draftMaxTextSizePatched = true;
  }

  patchMermaidInitialize();
  window.addEventListener('DOMContentLoaded', patchMermaidInitialize);

  const DIAGRAM_OBJECT_TYPES = new Set([
    'host',
    'runtime_service',
    'data_store_service',
    'network_service',
    'product_component',
    'data_component'
  ]);
  const DATA_STORE_TYPES = new Set(['data_store_service', 'data_component']);
  const MAX_MERMAID_TEXT_SIZE = MERMAID_MAX_TEXT_SIZE;

  function objectUid(object) {
    return String(object?.uid || object?.id || '').trim();
  }

  function rawObject(object) {
    if (!object) return {};
    if (typeof rawDetailObject === 'function') return rawDetailObject(object);
    try {
      return JSON.parse(object.detail || '{}');
    } catch (error) {
      return {};
    }
  }

  function resolveObject(ref) {
    if (!ref) return null;
    const value = String(ref);
    if (typeof objectLookup !== 'undefined' && objectLookup[value]) return objectLookup[value];
    if (typeof objectAliasLookup !== 'undefined' && objectAliasLookup[value]) return objectAliasLookup[value];
    return null;
  }

  function html(value) {
    if (typeof escapeHtml === 'function') return escapeHtml(value);
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function typeName(type) {
    if (typeof formatTypeLabel === 'function') return formatTypeLabel(type);
    return String(type || '').replace(/[_-]/g, ' ');
  }

  function compactText(value, maxLength = 72) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    if (text.length <= maxLength) return text;
    return `${text.slice(0, maxLength - 1).trim()}...`;
  }

  function mermaidText(value, fallback = '') {
    return compactText(value || fallback, 96)
      .replace(/"/g, "'")
      .replace(/[{}[\];]/g, ' ')
      .replace(/\|/g, '/')
      .trim();
  }

  function safeId(value, prefix = 'node') {
    const cleaned = String(value || '')
      .replace(/[^a-zA-Z0-9_]/g, '_')
      .replace(/^_+/, '')
      .replace(/_+$/, '');
    return cleaned ? `${prefix}_${cleaned}` : `${prefix}_${Math.random().toString(36).slice(2)}`;
  }

  function nodeIdFactory() {
    const ids = new Map();
    return function nodeId(object) {
      const uid = objectUid(object);
      if (!ids.has(uid)) ids.set(uid, safeId(uid || object?.name, 'obj'));
      return ids.get(uid);
    };
  }

  function objectSummary(object) {
    const bits = [typeName(object.type)];
    if (object.deliveryModel) bits.push(object.deliveryModel);
    if (object.lifecycleStatus) bits.push(object.lifecycleStatus);
    return bits.filter(Boolean).join(' / ');
  }

  function objectBadge(object) {
    return `
      <button class="diagram-object-pill" type="button" data-object-link="${html(objectUid(object))}" title="${html(objectSummary(object))}">
        <span>${html(object.name || objectUid(object))}</span>
        <span class="diagram-object-type">${html(typeName(object.type))}</span>
        <span class="diagram-object-status">${html(object.lifecycleStatus || 'unknown')}</span>
      </button>
    `;
  }

  function refFromEntry(entry) {
    if (typeof entry === 'string') return entry;
    if (entry && typeof entry === 'object') return entry.ref || entry.uid || entry.id || '';
    return '';
  }

  function addUniqueObject(list, seen, object) {
    const uid = objectUid(object);
    if (!uid || seen.has(uid) || !DIAGRAM_OBJECT_TYPES.has(object.type)) return false;
    seen.add(uid);
    list.push(object);
    return true;
  }

  function edgeKey(edge) {
    return [edge.source, edge.target, edge.label || edge.name || '', edge.technology || ''].join('|');
  }

  function relationshipsFor(memberIds) {
    const edges = (window.DRAFT_BROWSER_DATA && window.DRAFT_BROWSER_DATA.topologyEdges) || [];
    const result = [];
    const seen = new Set();
    edges.forEach(edge => {
      if (!memberIds.has(edge.source) || !memberIds.has(edge.target)) return;
      const key = edgeKey(edge);
      if (seen.has(key)) return;
      seen.add(key);
      result.push(edge);
    });
    return result;
  }

  function buildSystemDiagrams() {
    const systems = allObjects.filter(object => object.type === 'system');
    const diagrams = [];
    systems.forEach(system => {
      const raw = rawObject(system);
      const containerEntries = Array.isArray(raw.containers) ? raw.containers : [];
      const seen = new Set();
      const nodes = [];
      containerEntries.forEach(entry => {
        addUniqueObject(nodes, seen, resolveObject(refFromEntry(entry)));
      });
      if (!nodes.length) return;
      const memberIds = new Set(nodes.map(objectUid));
      const externalActors = Array.isArray(raw.externalActors)
        ? raw.externalActors.filter(actor => actor && typeof actor === 'object')
        : [];
      diagrams.push({
        sourceType: 'System',
        object: system,
        title: system.name || 'System',
        description: system.description || raw.description || '',
        groups: [{ name: 'System containers', notes: '', nodes }],
        nodes,
        externalActors,
        edges: relationshipsFor(memberIds)
      });
    });
    return diagrams;
  }

  function collectServiceGroupNodes(group, diagramSeen) {
    const nodes = [];
    const substrate = resolveObject(group.substrate);
    addUniqueObject(nodes, diagramSeen, substrate);
    const deployableObjects = Array.isArray(group.deployableObjects) ? group.deployableObjects : [];
    deployableObjects.forEach(entry => {
      addUniqueObject(nodes, diagramSeen, resolveObject(refFromEntry(entry)));
    });
    return nodes;
  }

  function groupLabel(group) {
    const name = group.name || 'Service group';
    const details = [group.deploymentTarget, group.scalingUnit].filter(Boolean).join(' / ');
    return details ? `${name} (${details})` : name;
  }

  // Builds the diagram-shaped view model for a single SDP (nodes grouped by
  // service group, edges from relationship objects among those nodes).
  // Returns null when the SDP resolves to no deployable nodes.
  function buildSdpDiagram(sdp) {
    const raw = rawObject(sdp);
    const serviceGroups = Array.isArray(sdp.serviceGroups) && sdp.serviceGroups.length
      ? sdp.serviceGroups
      : Array.isArray(raw.serviceGroups)
        ? raw.serviceGroups
        : [];
    const diagramSeen = new Set();
    const groups = serviceGroups
      .map(group => ({
        name: groupLabel(group || {}),
        notes: [group?.substrate ? `substrate: ${group.substrate}` : '', group?.deploymentTarget || ''].filter(Boolean).join(' / '),
        nodes: collectServiceGroupNodes(group || {}, diagramSeen)
      }))
      .filter(group => group.nodes.length);
    const nodes = groups.flatMap(group => group.nodes);
    if (!nodes.length) return null;
    const memberIds = new Set(nodes.map(objectUid));
    return {
      sourceType: 'SoftwareDeploymentPattern',
      object: sdp,
      title: sdp.name || 'Software deployment pattern',
      description: sdp.description || raw.description || '',
      groups,
      nodes,
      externalActors: [],
      edges: relationshipsFor(memberIds)
    };
  }

  function buildSdpDiagrams() {
    const sdps = allObjects.filter(object => object.type === 'software_deployment_pattern');
    return sdps.map(buildSdpDiagram).filter(Boolean);
  }

  function classNameFor(object) {
    if (DATA_STORE_TYPES.has(object.type)) return 'dataStore';
    if (object.type === 'host') return 'host';
    if (object.type === 'network_service') return 'network';
    if (object.type === 'product_component') return 'product';
    return 'service';
  }

  function nodeLabel(object) {
    const primary = mermaidText(object.name || objectUid(object), 'Unnamed object');
    const secondary = mermaidText(typeName(object.type));
    const delivery = mermaidText(object.deliveryModel || '');
    const lines = [primary, secondary, delivery].filter(Boolean);
    return lines.join('<br/>');
  }

  function arrowFor(edge) {
    if (String(edge.flow || '').toLowerCase() === 'bidirectional') return '<-->';
    if (String(edge.direction || '').toLowerCase() === 'asynchronous') return '-.->';
    return '-->';
  }

  function edgeLabel(edge) {
    return mermaidText(edge.label || edge.name || edge.technology || 'uses', 'uses').slice(0, 64);
  }

  function buildMermaid(diagram) {
    const nodeId = nodeIdFactory();
    const lines = [
      'flowchart LR',
      '    classDef service fill:#eff6ff,stroke:#2563eb,color:#0f172a,stroke-width:1px;',
      '    classDef dataStore fill:#ecfdf5,stroke:#059669,color:#0f172a,stroke-width:1px;',
      '    classDef network fill:#fff7ed,stroke:#ea580c,color:#0f172a,stroke-width:1px;',
      '    classDef product fill:#f5f3ff,stroke:#7c3aed,color:#0f172a,stroke-width:1px;',
      '    classDef host fill:#f8fafc,stroke:#475569,color:#0f172a,stroke-width:1px;',
      '    classDef actor fill:#fef2f2,stroke:#dc2626,color:#0f172a,stroke-width:1px;',
      ''
    ];

    if (diagram.externalActors.length) {
      lines.push('    subgraph externalActors["External actors"]');
      diagram.externalActors.forEach((actor, index) => {
        const actorId = safeId(`${diagram.title}_${actor.name || index}`, 'actor');
        lines.push(`        ${actorId}["${mermaidText(actor.name || 'Actor')}"]`);
        lines.push(`        class ${actorId} actor;`);
      });
      lines.push('    end', '');
    }

    diagram.groups.forEach((group, index) => {
      const groupId = safeId(`${diagram.title}_${group.name}_${index}`, 'group');
      lines.push(`    subgraph ${groupId}["${mermaidText(group.name, 'Group')}"]`);
      group.nodes.forEach(object => {
        lines.push(`        ${nodeId(object)}["${nodeLabel(object)}"]`);
      });
      lines.push('    end', '');
    });

    diagram.edges.forEach(edge => {
      const source = resolveObject(edge.source);
      const target = resolveObject(edge.target);
      if (!source || !target) return;
      lines.push(`    ${nodeId(source)} ${arrowFor(edge)}|${edgeLabel(edge)}| ${nodeId(target)}`);
    });
    if (diagram.edges.length) lines.push('');

    diagram.nodes.forEach(object => {
      lines.push(`    class ${nodeId(object)} ${classNameFor(object)};`);
    });

    return lines.join('\n');
  }

  function ensureStyles() {
    if (document.getElementById('draft-diagrams-enhancement-styles')) return;
    const style = document.createElement('style');
    style.id = 'draft-diagrams-enhancement-styles';
    style.textContent = `
      .diagram-quality-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:16px; }
      .diagram-quality-card { border:1px solid #e2e8f0; border-radius:8px; padding:12px; background:#f8fafc; }
      .diagram-quality-card strong { display:block; color:#1e293b; margin-bottom:4px; }
      .diagram-quality-card p { margin:0; color:#64748b; font-size:13px; line-height:1.45; }
      .diagram-card-header { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:12px; }
      .diagram-card-header h3 { margin:0; color:#1e293b; font-size:16px; line-height:1.25; }
      .diagram-card-meta { display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; }
      .diagram-slot { overflow:auto; min-height:160px; border:1px solid #e2e8f0; border-radius:8px; background:#fff; padding:12px; }
      .diagram-slot svg { max-width:none; }
      .diagram-object-list { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
      .diagram-object-pill { display:inline-flex; align-items:center; gap:6px; border:1px solid #cbd5e1; border-radius:999px; background:#fff; color:#1e293b; padding:5px 9px; font:inherit; font-size:12px; cursor:pointer; }
      .diagram-object-pill:hover { border-color:#7c3a6b; color:#7c3a6b; }
      .diagram-object-type { color:#64748b; }
      .diagram-object-status { border-radius:999px; background:#f1f5f9; color:#475569; padding:2px 6px; }
      .diagram-source { margin-top:12px; }
      .diagram-source summary { cursor:pointer; color:#475569; font-size:13px; }
      .diagram-source pre { overflow:auto; max-height:320px; margin:8px 0 0; padding:12px; border-radius:8px; background:#0f172a; color:#e2e8f0; font-size:12px; line-height:1.45; }
      .diagram-empty-list { margin:8px 0 0 18px; color:#64748b; line-height:1.55; }
      .diagram-error { color:#b91c1c; font-size:13px; }
    `;
    document.head.appendChild(style);
  }

  function qualityCards(meta, diagrams) {
    const cards = [];
    if (!meta.systemCount) {
      cards.push({
        title: 'No system boundaries found',
        text: 'The old view rendered one large fallback diagram. This view avoids that and uses deployment patterns until system objects define clearer boundaries.'
      });
    }
    if (!meta.sdpCount) {
      cards.push({
        title: 'No deployment patterns found',
        text: 'Add software deployment patterns with service groups and deployable objects to create deployment-level diagrams.'
      });
    }
    if (!meta.relationshipCount) {
      cards.push({
        title: 'No relationship edges found',
        text: 'Add relationship objects with source, target, and label values so diagrams can show flow instead of disconnected boxes.'
      });
    } else if (diagrams.some(diagram => diagram.nodes.length && !diagram.edges.length)) {
      cards.push({
        title: 'Some diagrams have no edges',
        text: 'Those source objects have deployable members, but no relationship objects connect members inside the same boundary.'
      });
    }
    if (!cards.length) return '';
    return `
      <div class="diagram-quality-grid">
        ${cards.map(card => `
          <div class="diagram-quality-card">
            <strong>${html(card.title)}</strong>
            <p>${html(card.text)}</p>
          </div>
        `).join('')}
      </div>
    `;
  }

  function diagramCard(diagram, index, renderId) {
    const sourceUid = objectUid(diagram.object);
    const sourceLink = sourceUid
      ? `<span class="ard-link" data-object-link="${html(sourceUid)}">${html(diagram.title)}</span>`
      : html(diagram.title);
    const mermaidSource = buildMermaid(diagram);
    diagram.mermaidSource = mermaidSource;
    return `
      <section class="header-card" style="margin-bottom:16px;">
        <div class="diagram-card-header">
          <div>
            <h3>${sourceLink}</h3>
            <div class="object-id">${html(diagram.sourceType)}${sourceUid ? ` / ${html(sourceUid)}` : ''}</div>
          </div>
          <div class="diagram-card-meta">
            <span class="badge">${diagram.nodes.length} node${diagram.nodes.length === 1 ? '' : 's'}</span>
            <span class="badge">${diagram.edges.length} edge${diagram.edges.length === 1 ? '' : 's'}</span>
            <span class="badge">${diagram.groups.length} group${diagram.groups.length === 1 ? '' : 's'}</span>
          </div>
        </div>
        ${diagram.description ? `<p class="header-description">${html(diagram.description)}</p>` : ''}
        <div id="diagram-slot-${renderId}-${index}" class="diagram-slot">
          <span style="color:#94a3b8;font-size:13px;">Rendering...</span>
        </div>
        <div class="diagram-object-list">
          ${diagram.nodes.map(objectBadge).join('')}
        </div>
        <details class="diagram-source">
          <summary>Mermaid source</summary>
          <pre>${html(mermaidSource)}</pre>
        </details>
      </section>
    `;
  }

  function emptyState(meta) {
    return `
      <section class="header-card">
        <h3 style="margin:0 0 8px;color:#1e293b;">No scoped diagrams available</h3>
        <p style="margin:0;color:#64748b;">The catalog needs at least one scoped boundary before the Diagrams view can show a useful architecture diagram.</p>
        <ul class="diagram-empty-list">
          <li>${html(meta.systemCount ? 'System objects exist, but they do not reference deployable containers.' : 'Add system objects with containers to define C4-style boundaries.')}</li>
          <li>${html(meta.sdpCount ? 'Deployment patterns exist, but their service groups do not resolve to deployable objects.' : 'Add software deployment patterns with service groups for deployment views.')}</li>
          <li>${html(meta.relationshipCount ? 'Existing relationships will appear once their source and target are inside the same boundary.' : 'Add relationship objects to draw edges between services.')}</li>
        </ul>
      </section>
    `;
  }

  function renderEnhancedDiagramsView() {
    currentMode = 'diagrams';
    currentDetailId = null;
    executiveDrilldown = null;
    if (typeof setHashState === 'function') setHashState({ view: 'diagrams' });
    if (typeof destroyDetailCy === 'function') destroyDetailCy();
    if (typeof destroySdpGraphCy === 'function') destroySdpGraphCy();
    if (typeof destroyImpactCy === 'function') destroyImpactCy();
    ensureStyles();

    const systemDiagrams = buildSystemDiagrams();
    const sdpDiagrams = buildSdpDiagrams();
    const diagrams = [...systemDiagrams, ...sdpDiagrams];
    const edges = (window.DRAFT_BROWSER_DATA && window.DRAFT_BROWSER_DATA.topologyEdges) || [];
    const meta = {
      systemCount: allObjects.filter(object => object.type === 'system').length,
      sdpCount: allObjects.filter(object => object.type === 'software_deployment_pattern').length,
      relationshipCount: edges.length
    };
    const renderId = Date.now();
    const cardsHtml = diagrams.length
      ? diagrams.map((diagram, index) => diagramCard(diagram, index, renderId)).join('')
      : emptyState(meta);

    pageRoot.innerHTML = `
      <div class="view-shell">
        ${typeof topNavMarkup === 'function' ? topNavMarkup() : ''}
        <section class="header-card">
          <div class="header-top">
            <div class="header-title">
              <h2>Diagrams</h2>
              <div class="object-id">System and deployment-pattern diagrams</div>
            </div>
            <div class="badges">
              <span class="badge">${meta.systemCount} system${meta.systemCount === 1 ? '' : 's'}</span>
              <span class="badge">${meta.sdpCount} deployment pattern${meta.sdpCount === 1 ? '' : 's'}</span>
              <span class="badge">${meta.relationshipCount} relationship${meta.relationshipCount === 1 ? '' : 's'}</span>
            </div>
          </div>
          <div class="header-description">
            Diagrams are scoped from system container boundaries and software deployment pattern service groups, then connected with relationship objects.
          </div>
          ${qualityCards(meta, diagrams)}
        </section>
        <div class="content-rows">
          ${cardsHtml}
        </div>
      </div>
    `;

    if (typeof attachTopNavHandlers === 'function') attachTopNavHandlers();
    if (typeof attachObjectLinkHandlers === 'function') attachObjectLinkHandlers(pageRoot);
    if (!diagrams.length) return;
    renderDiagramsIntoSlots(diagrams, renderId);
  }

  // Renders diagram.mermaidSource into `#diagram-slot-${renderId}-${index}` for
  // each entry in `diagrams`. Shared by the catalog-wide Diagrams view and any
  // other view (e.g. the SDP detail page) that embeds a subset of diagrams
  // using the same slot-id convention.
  function renderDiagramsIntoSlots(diagrams, renderId) {
    if (!diagrams.length) return;

    if (typeof mermaid === 'undefined') {
      diagrams.forEach((diagram, index) => {
        const slot = document.getElementById(`diagram-slot-${renderId}-${index}`);
        if (slot) slot.innerHTML = '<span style="color:#94a3b8;font-size:13px;">Mermaid.js is not loaded. Check the browser network panel.</span>';
      });
      return;
    }

    mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose',
      maxTextSize: MAX_MERMAID_TEXT_SIZE,
      flowchart: { useMaxWidth: false, htmlLabels: true }
    });

    diagrams.forEach(async (diagram, index) => {
      const slot = document.getElementById(`diagram-slot-${renderId}-${index}`);
      if (!slot) return;
      try {
        const { svg } = await mermaid.render(`draft-diagram-${renderId}-${index}`, diagram.mermaidSource);
        const currentSlot = document.getElementById(`diagram-slot-${renderId}-${index}`);
        if (currentSlot) currentSlot.innerHTML = svg;
      } catch (error) {
        const currentSlot = document.getElementById(`diagram-slot-${renderId}-${index}`);
        if (currentSlot) {
          currentSlot.innerHTML = '<span class="diagram-error">Diagram rendering error. Expand Mermaid source and check the browser console for details.</span>';
        }
        console.error('Mermaid diagram render error:', diagram.title, error, '\nDiagram text:\n', diagram.mermaidSource);
      }
    });
  }

  // Public API so other views (e.g. the SDP detail page) can embed a single
  // SDP's diagram using the exact same node/edge rules and mermaid rendering
  // as the catalog-wide Diagrams view, instead of re-deriving their own.
  window.DraftDiagrams = {
    buildSdpDiagram,
    buildMermaid,
    objectBadge,
    ensureStyles,
    renderDiagramsIntoSlots
  };

  function install() {
    if (typeof pageRoot === 'undefined' || typeof allObjects === 'undefined') return;
    try {
      renderDiagramsView = renderEnhancedDiagramsView;
    } catch (error) {
      window.renderDiagramsView = renderEnhancedDiagramsView;
    }
    window.renderDiagramsView = renderEnhancedDiagramsView;

    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    if (params.get('view') === 'diagrams' || (typeof currentMode !== 'undefined' && currentMode === 'diagrams')) {
      renderEnhancedDiagramsView();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
