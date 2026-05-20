const browserData = window.DRAFT_BROWSER_DATA || { objects: [], lookup: {}, lifecycleColors: {} };
const lifecycleColors = browserData.lifecycleColors;
const allObjects = browserData.objects.slice().sort((a, b) => a.name.localeCompare(b.name));
const objectLookup = browserData.lookup;
const referencedByIndex = browserData.referencedBy || {};
const repoUrl = browserData.repoUrl || '';
const businessTaxonomy = browserData.businessTaxonomy || { pillars: [] };
const businessPillarLookup = Object.fromEntries((businessTaxonomy.pillars || []).map(pillar => [pillar.id, pillar]));
const pageRoot = document.getElementById('page-root');
const sidebarContent = document.getElementById('sidebar-content');
const legend = document.getElementById('legend');
const editorOverlay = document.getElementById('editor-overlay');
document.getElementById('draft-logo').src = browserData.logoDataUri || 'draftlogo.png';
document.getElementById('catalog-name').textContent = browserData.catalogName || 'Catalog';
document.getElementById('browser-mode').textContent = 'GitHub Pages';
let editorState = null;
let requirementImportState = null;

// ── Deployment Targets view ─────────────────────────────────────────────────
const DT_PROVIDERS = [
  { id: 'aws',        name: 'AWS',            category: 'public-cloud' },
  { id: 'gcp',        name: 'Google Cloud',   category: 'public-cloud' },
  { id: 'azure',      name: 'Azure',          category: 'public-cloud' },
  { id: 'onprem',     name: 'On-Premises',    category: 'private'      },
  { id: 'colocation', name: 'Colocation',     category: 'private'      },
  { id: 'saas',       name: 'SaaS',           category: 'saas'         },
  { id: 'cloudflare', name: 'Cloudflare',     category: 'edge'         },
  { id: 'customer',   name: 'Customer Site',  category: 'customer'     },
  { id: 'unknown',    name: 'Unclassified',   category: 'unknown'      },
];
const DT_PROVIDER_COLORS = {
  aws:        'oklch(0.68 0.13 65)',
  gcp:        'oklch(0.60 0.13 240)',
  azure:      'oklch(0.60 0.13 220)',
  onprem:     'oklch(0.45 0.05 270)',
  colocation: 'oklch(0.55 0.04 270)',
  saas:       'oklch(0.55 0.13 320)',
  cloudflare: 'oklch(0.65 0.13 50)',
  customer:   'oklch(0.62 0.13 90)',
  unknown:    'oklch(0.65 0.00 0)',
};
const DT_TYPE_LABELS = {
  'cloud-region':  'Cloud region',
  'cloud-account': 'Cloud account',
  'k8s-cluster':   'Kubernetes cluster',
  'colocation':    'Colocation',
  'on-prem':       'On-premises',
  'saas-tenant':   'SaaS tenant',
  'customer-site': 'Customer site',
  'edge-network':  'Edge network',
};
const DT_STATUS_OPTS = [
  { id: 'all',      label: 'All'      },
  { id: 'approved', label: 'Approved' },
  { id: 'proposed', label: 'Proposed' },
  { id: 'ad-hoc',   label: 'Ad-hoc'  },
  { id: 'unused',   label: 'Unused'  },
];
let _dtVM             = null;      // built once per view entry
let _dtActiveId       = null;      // currently open drawer
let _dtQuery          = '';
let _dtTypeFilter     = 'all';
let _dtStatusFilter   = 'all';
let _dtProviderFilter = null;      // Set<string> | null (null = all)
let _dtResizeObserver = null;
let _dtWorldData      = null;
let _dtWorldPromise   = null;
let _dtMapSize        = { w: 900, h: 450 };
let _dtMapPreset      = 'world';   // 'world' | 'north-america'
let _dtEscHandler     = null;

// Map preset definitions.
// Each preset exposes buildProjection(w, h) → a ready D3 projection.
// World uses fitExtent with the full Sphere.
// Regional presets derive scale/translate from the world projection so the
// zoom is always proportional to the actual rendered viewport size.
const DT_MAP_PRESETS = {
  'world': {
    label: 'World',
    icon: '🌐',
    buildProjection: (w, h) =>
      d3.geoNaturalEarth1()
        .fitExtent([[8, 8], [w - 8, h - 8]], { type: 'Sphere' })
        .precision(0.1),
    graticuleStep: [20, 20],
  },
  'north-america': {
    label: 'N. America',
    icon: '🌎',
    buildProjection: (w, h) => {
      const base = d3.geoNaturalEarth1()
        .fitExtent([[8, 8], [w - 8, h - 8]], { type: 'Sphere' });
      const ws = base.scale();
      const [wtx, wty] = base.translate();
      const [cx, cy] = base([-100, 45]);
      const f = 2.5;
      return d3.geoNaturalEarth1()
        .scale(ws * f)
        .translate([w / 2 - f * (cx - wtx), h / 2 - f * (cy - wty)])
        .precision(0.1);
    },
    graticuleStep: [10, 10],
  },
  'europe': {
    label: 'Europe',
    icon: '🌍',
    buildProjection: (w, h) => {
      // 3.5× zoom, centred on [15°E, 52°N] — shows UK through western Russia
      // and from Scandinavia to the Mediterranean.
      const base = d3.geoNaturalEarth1()
        .fitExtent([[8, 8], [w - 8, h - 8]], { type: 'Sphere' });
      const ws = base.scale();
      const [wtx, wty] = base.translate();
      const [cx, cy] = base([15, 52]);
      const f = 3.5;
      return d3.geoNaturalEarth1()
        .scale(ws * f)
        .translate([w / 2 - f * (cx - wtx), h / 2 - f * (cy - wty)])
        .precision(0.1);
    },
    graticuleStep: [10, 10],
  },
  'asia': {
    label: 'Asia',
    icon: '🌏',
    buildProjection: (w, h) => {
      // 2.3× zoom, centred on [95°E, 35°N] — shows Middle East through Japan
      // and from Russia's south to the Indonesian archipelago.
      const base = d3.geoNaturalEarth1()
        .fitExtent([[8, 8], [w - 8, h - 8]], { type: 'Sphere' });
      const ws = base.scale();
      const [wtx, wty] = base.translate();
      const [cx, cy] = base([95, 35]);
      const f = 2.3;
      return d3.geoNaturalEarth1()
        .scale(ws * f)
        .translate([w / 2 - f * (cx - wtx), h / 2 - f * (cy - wty)])
        .precision(0.1);
    },
    graticuleStep: [10, 10],
  },
};
// ───────────────────────────────────────────────────────────────────────────

const DEPLOYABLE_OBJECT_TYPES = [
  'technology_component',
  'host',
  'runtime_service',
  'data_at_rest_service',
  'edge_gateway_service',
  'product_component',
  'data_component',
  'product_service',
  'software_deployment_pattern'
];
const SERVICE_OBJECT_TYPES = ['runtime_service', 'data_at_rest_service', 'edge_gateway_service'];
const DEPLOYABLE_STANDARD_TYPES = ['host', 'runtime_service', 'data_at_rest_service', 'edge_gateway_service', 'product_component', 'data_component', 'product_service'];
const CATEGORY_CONFIG = [
  {
    id: 'architecture',
    label: 'Architecture Content',
    filters: [
      { id: 'all', label: 'All', types: ['software_deployment_pattern', 'reference_architecture', 'host', 'runtime_service', 'data_at_rest_service', 'edge_gateway_service', 'product_component', 'data_component', 'product_service'] },
      { id: 'software_deployment_pattern', label: 'Software Deployment Patterns', types: ['software_deployment_pattern'] },
      { id: 'reference_architecture', label: 'Reference Architectures', types: ['reference_architecture'] },
      { id: 'deployable_objects', label: 'Deployable Objects', types: DEPLOYABLE_STANDARD_TYPES }
    ],
    rows: [
      { id: 'software_deployment_pattern', label: 'Software Deployment Patterns', types: ['software_deployment_pattern'] },
      { id: 'reference_architecture', label: 'Reference Architectures', types: ['reference_architecture'] },
      { id: 'host', label: 'Hosts', types: ['host'] },
      { id: 'runtime_service', label: 'Runtime Services', types: ['runtime_service'] },
      { id: 'data_at_rest_service', label: 'Data-at-Rest Services', types: ['data_at_rest_service'] },
      { id: 'edge_gateway_service', label: 'Edge/Gateway Services', types: ['edge_gateway_service'] },
      { id: 'product_component', label: 'Product Components', types: ['product_component'] },
      { id: 'data_component', label: 'Data Components', types: ['data_component'] },
      { id: 'product_service', label: 'Product Services', types: ['product_service'] }
    ]
  },
  {
    id: 'supporting',
    label: 'Supporting Content',
    filters: [
      { id: 'all', label: 'All', types: ['technology_component', 'decision_record'] },
      { id: 'technology_component', label: 'Technology Components', types: ['technology_component'] },
      { id: 'decision_record', label: 'Decision Records', types: ['decision_record'] }
    ],
    rows: [
      { id: 'technology_component', label: 'Technology Components', types: ['technology_component'] },
      { id: 'decision_record', label: 'Decision Records', types: ['decision_record'] }
    ]
  },
  {
    id: 'workspace',
    label: 'Workspace Configuration',
    filters: [
      { id: 'all', label: 'All', types: ['environment_tier'] },
      { id: 'environment_tier', label: 'Environment Tiers', types: ['environment_tier'] }
    ],
    rows: [
      { id: 'environment_tier', label: 'Environment Tiers', types: ['environment_tier'] }
    ]
  },
  {
    id: 'framework',
    label: 'Framework Content',
    filters: [
      { id: 'all', label: 'All', types: ['capability', 'requirement_group', 'domain'] },
      { id: 'capability', label: 'Capabilities', types: ['capability'] },
      { id: 'requirement_group', label: 'Requirement Groups', types: ['requirement_group'] },
      { id: 'domain', label: 'Strategy Map', types: ['domain'] }
    ],
    rows: [
      { id: 'capability', label: 'Capabilities', types: ['capability'] },
      { id: 'requirement_group', label: 'Requirement Groups', types: ['requirement_group'] },
      { id: 'domain', label: 'Strategy Domains', types: ['domain'] }
    ]
  }
];
const lifecycleValues = browserData.lifecycleValues || [];
const deployableTypes = new Set([
  'software_deployment_pattern',
  'reference_architecture',
  'host',
  'runtime_service',
  'data_at_rest_service',
  'edge_gateway_service',
  'product_component',
  'data_component',
  'product_service'
]);
let activeCategory = 'architecture';
let activeFilter = 'all';
let currentDetailId = null;
let currentMode = 'executive';
let executiveDrilldown = null;
let currentSubViewId = null;
const navHistory = [];
let listSearchTerm = '';
let detailCy = null;
let currentSdmScalingFilter = 'all';
let suppressHashSync = false;

Object.entries(lifecycleColors).forEach(([label, value]) => {
  const item = document.createElement('div');
  item.className = 'legend-item';
  item.innerHTML = `<span class="dot" style="background:${'#' + value}"></span><span>${label}</span>`;
  legend.appendChild(item);
});

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatTitleCase(value) {
  return String(value || '')
    .split(/[-_]/g)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function formatKeyLabel(value) {
  return formatTitleCase(String(value || '').replace(/\./g, '-'));
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function pluralize(count, singular, plural = `${singular}s`) {
  return `${formatNumber(count)} ${count === 1 ? singular : plural}`;
}

function relatedCapabilityOptions() {
  const values = new Set();
  allObjects
    .filter(object => object.type === 'requirement_group')
    .forEach(object => {
      (object.requirements || []).forEach(requirement => {
        if (requirement?.id) {
          values.add(String(requirement.id));
        }
      });
    });
  return Array.from(values).sort((a, b) => a.localeCompare(b));
}

function formatTypeLabel(typeValue) {
  const normalized = String(typeValue || '');
  if (normalized === 'technology_component') return 'Technology Component';
  if (normalized === 'edge_gateway_service') return 'Edge/Gateway Service';
  if (normalized === 'host') return 'Host';
  if (normalized === 'runtime_service') return 'Runtime Service';
  if (normalized === 'data_at_rest_service') return 'Data-at-Rest Service';
  if (normalized === 'capability') return 'Capability';
  if (normalized === 'requirement_group') return 'Requirement Group';
  if (normalized === 'decision_record') return 'Decision Record';
  if (normalized === 'software_deployment_pattern') return 'Software Deployment Pattern';
  if (normalized === 'reference_architecture') return 'Reference Architecture';
  return formatTitleCase(normalized.replace(/[._-]/g, ' '));
}

function capabilityClass(capability) {
  return ({
    'authentication': 'cap-authentication',
    'logging': 'cap-logging',
    'security': 'cap-security',
    'monitoring': 'cap-monitoring',
    'patch-management': 'cap-patch-management'
  }[capability] || 'cap-default');
}

function catalogStatusClass(status) {
  return ({
    'approved': 'catalog-approved',
    'draft': 'catalog-draft',
    'stub': 'catalog-stub'
  }[status] || 'catalog-stub');
}

function lifecycleBadge(status) {
  if (!status) return '';
  const color = '#' + (lifecycleColors[status] || lifecycleColors.unknown);
  return `<span class="badge"><span class="dot" style="background:${color}"></span>${escapeHtml(status)}</span>`;
}

function catalogBadge(status) {
  return `<span class="badge ${catalogStatusClass(status)}">${escapeHtml(status)}</span>`;
}

function ardCategoryBadge(category) {
  const normalized = category === 'decision' ? 'decision' : 'risk';
  return `<span class="badge ard-${normalized}">${escapeHtml(normalized)}</span>`;
}

function ardStatusBadge(status) {
  return `<span class="badge ard-status">${escapeHtml(status || 'unknown')}</span>`;
}

function productBadge(product) {
  return `<span class="badge ps-badge">${escapeHtml(product || 'unknown product')}</span>`;
}

function saasBadge() {
  return '<span class="badge saas-badge">SaaS</span>';
}

function paasBadge() {
  return '<span class="badge paas-badge">PaaS</span>';
}

function applianceBadge() {
  return '<span class="badge appliance-badge">appliance</span>';
}

function deliveryModelBadge(object) {
  if (!SERVICE_OBJECT_TYPES.includes(object?.type)) return '';
  const deliveryModel = object.deliveryModel || 'self-managed';
  if (deliveryModel === 'saas') return saasBadge();
  if (deliveryModel === 'paas') return paasBadge();
  if (deliveryModel === 'appliance') return applianceBadge();
  return '<span class="badge">self-managed</span>';
}

function intentBadge(intent) {
  const normalized = String(intent || '').toLowerCase();
  const cls = normalized === 'ha' ? 'intent-ha' : normalized === 'sa' ? 'intent-sa' : '';
  return `<span class="badge ${cls}">${escapeHtml((intent || '').toUpperCase())}</span>`;
}

function boolBadge(value, trueLabel = 'true', falseLabel = 'false') {
  const active = value === true;
  const text = active ? trueLabel : falseLabel;
  const cls = active ? 'saas-badge' : 'catalog-stub';
  return `<span class="badge ${cls}">${escapeHtml(text)}</span>`;
}

function currentHashState() {
  const raw = window.location.hash.replace(/^#/, '');
  return new URLSearchParams(raw);
}

function setHashState(values) {
  if (suppressHashSync) return;
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && String(value).trim() !== '') {
      params.set(key, value);
    }
  });
  const nextHash = params.toString();
  const currentHash = window.location.hash.replace(/^#/, '');
  if (nextHash === currentHash) return;
  suppressHashSync = true;
  window.location.hash = nextHash;
  window.setTimeout(() => {
    suppressHashSync = false;
  }, 0);
}

function categoryConfig(categoryId = activeCategory) {
  return CATEGORY_CONFIG.find(category => category.id === categoryId) || CATEGORY_CONFIG[0];
}

function activeFilterConfig() {
  const category = categoryConfig();
  return category.filters.find(filter => filter.id === activeFilter) || category.filters[0];
}

function formatListFilterLabel(filterId) {
  const category = categoryConfig();
  const filter = category.filters.find(item => item.id === filterId);
  return filter?.label || 'All';
}

function syncHashForExecutiveView() {
  setHashState({
    view: 'executive',
    drill: executiveDrilldown || null
  });
}

function syncHashForListView() {
  setHashState({
    view: 'list',
    category: activeCategory !== 'architecture' ? activeCategory : null,
    filter: activeFilter !== 'all' ? activeFilter : null,
    q: listSearchTerm.trim() || null
  });
}

function syncHashForDetailView(id) {
  setHashState({ view: 'detail', id });
}

function syncHashForImpactView() {
  setHashState({ view: 'impact', id: impactSelectedId, q: impactSearchTerm || null });
}

function syncHashForAcceptableUseView() {
  setHashState({ view: 'acceptable-use' });
}

function syncHashForObjectTypesView() {
  setHashState({ view: 'object-types' });
}

function syncHashForOnboardingView() {
  setHashState({ view: 'onboarding' });
}

function syncHashForRequirementGroupsView() {
  setHashState({ view: 'requirement-groups' });
}

function syncHashForBuiltInConfigsView() {
  setHashState({ view: 'built-in-configs' });
}

function syncHashForRequirementGroupDetailView(uid) {
  setHashState({ view: 'requirement-group-detail', id: uid });
}

function syncHashForVocabulariesView() {
  setHashState({ view: 'vocabularies' });
}

function syncHashForTaxonomiesView() {
  setHashState({ view: 'taxonomies' });
}

function syncHashForTechnologiesView() {
  setHashState({ view: 'technologies' });
}

function syncHashForDeploymentTargetsView() {
  setHashState({ view: 'deployment-targets' });
}

function syncHashForTeamsView() {
  setHashState({ view: 'teams' });
}

function syncHashForTeamDetailView(teamId) {
  setHashState({ view: 'team-detail', id: teamId });
}

function syncHashForTeamTypeView(teamId, objectType) {
  setHashState({ view: 'team-type', id: teamId, objectType });
}

function syncHashForSdpsByPillarView() {
  setHashState({ view: 'sdps-by-pillar' });
}

function syncHashForPillarSdpsView(pillarId) {
  setHashState({ view: 'pillar-sdps', id: pillarId });
}

function applyRouteFromHash() {
  if (suppressHashSync) return;
  const params = currentHashState();
  const view = params.get('view');
  if (view === 'executive' || (!view && !params.get('category') && !params.get('filter') && !params.get('q'))) {
    executiveDrilldown = params.get('drill') || null;
    currentDetailId = null;
    renderExecutiveView();
    return;
  }
  if (view === 'detail') {
    const objectId = params.get('id');
    if (objectId && objectLookup[objectId]) {
      currentDetailId = objectId;
      navHistory.length = 0;
      renderDetailView();
      return;
    }
  }
  if (view === 'acceptable-use') {
    renderAcceptableUseView();
    return;
  }
  if (view === 'object-types') {
    renderObjectTypesView();
    return;
  }
  if (view === 'onboarding') {
    renderCompanyOnboardingView();
    return;
  }
  if (view === 'requirement-groups') {
    renderRequirementGroupsView({ builtIn: false });
    return;
  }
  if (view === 'built-in-configs') {
    renderRequirementGroupsView({ builtIn: true });
    return;
  }
  if (view === 'requirement-group-detail') {
    const uid = params.get('id');
    if (uid && objectLookup[uid]) {
      const group = (browserData.requirements?.groups || []).find(g => g.uid === uid);
      renderRequirementGroupDetailView(uid, { builtIn: group ? isBuiltInGroup(group) : false });
      return;
    }
    renderRequirementGroupsView({ builtIn: false });
    return;
  }
  if (view === 'vocabularies') {
    renderVocabulariesView();
    return;
  }
  if (view === 'taxonomies') {
    renderTaxonomiesView();
    return;
  }
  if (view === 'technologies') {
    renderTechnologiesView();
    return;
  }
  if (view === 'deployment-targets') {
    renderDeploymentTargetsView();
    return;
  }
  if (view === 'teams') {
    renderTeamsView();
    return;
  }
  if (view === 'team-detail') {
    const teamId = params.get('id');
    if (teamId) { renderTeamDetailView(teamId); return; }
    renderTeamsView();
    return;
  }
  if (view === 'team-type') {
    const teamId = params.get('id');
    const objectType = params.get('objectType');
    if (teamId && objectType) { renderTeamTypeObjectsView(teamId, objectType); return; }
    if (teamId) { renderTeamDetailView(teamId); return; }
    renderTeamsView();
    return;
  }
  if (view === 'sdps-by-pillar') {
    renderSdpsByPillarView();
    return;
  }
  if (view === 'pillar-sdps') {
    const pillarId = params.get('id');
    if (pillarId) {
      renderPillarSdpsView(pillarId);
      return;
    }
    renderSdpsByPillarView();
    return;
  }
  executiveDrilldown = null;
  const category = params.get('category');
  activeCategory = CATEGORY_CONFIG.some(item => item.id === category) ? category : 'architecture';
  const requestedFilter = params.get('filter');
  const categoryFilters = categoryConfig(activeCategory).filters;
  activeFilter = categoryFilters.some(item => item.id === requestedFilter)
    ? requestedFilter
    : requestedFilter && categoryFilters.some(item => item.types.includes(requestedFilter))
      ? requestedFilter
      : 'all';
  listSearchTerm = params.get('q') || '';
  currentDetailId = null;
  renderListView();
}

function topNavMarkup() {
  return '';
}

function renderSidebarContent(contentHtml) {
  sidebarContent.innerHTML = contentHtml;
  updateSidebarNav();
}

function currentFilterMarkup() {
  return `
    <div class="sidebar-block">
      <div class="legend-title">Current Filter</div>
      <div class="current-filter"><span class="dot" style="background:#7c3a6b"></span><span>${escapeHtml(categoryConfig().label)} / ${escapeHtml(formatListFilterLabel(activeFilter))}</span></div>
    </div>
  `;
}

function sidebarMarkup(extraMarkup = '') {
  return `${currentFilterMarkup()}${extraMarkup}`;
}

function rerenderCurrentView() {
  if (currentMode === 'executive') {
    renderExecutiveView();
    return;
  }
  if (currentMode === 'detail') {
    renderDetailView();
    return;
  }
  if (currentMode === 'acceptable-use') {
    renderAcceptableUseView();
    return;
  }
  if (currentMode === 'object-types') {
    renderObjectTypesView();
    return;
  }
  if (currentMode === 'onboarding') {
    renderCompanyOnboardingView();
    return;
  }
  renderListView();
}

function attachSidebarHandlers() {}

function attachTopNavHandlers() {
  pageRoot.querySelectorAll('[data-nav]').forEach(button => {
    button.addEventListener('click', () => {
      const nav = button.dataset.nav;
      if (nav === 'executive') {
        destroyImpactCy();
        executiveDrilldown = null;
        renderExecutiveView();
        return;
      }
      if (nav === 'list') {
        destroyImpactCy();
        renderListView();
        return;
      }
      if (nav === 'object-types') {
        destroyImpactCy();
        renderObjectTypesView();
        return;
      }
      if (nav === 'onboarding') {
        destroyImpactCy();
        renderCompanyOnboardingView();
        return;
      }
      if (nav === 'detail' && currentDetailId) {
        destroyImpactCy();
        renderDetailView();
        return;
      }
      if (nav === 'acceptable-use') {
        renderAcceptableUseView();
      }
    });
  });
}

function destroyImpactCy() {}

function filterObjectsByTypes(types) {
  const allowed = new Set(types);
  return allObjects.filter(object => allowed.has(object.type));
}

function filterObjects() {
  return filterObjectsByTypes(activeFilterConfig().types);
}

function objectSearchText(object) {
  const aliases = Array.isArray(object.aliases) ? object.aliases.join(' ') : '';
  const values = [
    object.name,
    object.id,
    object.uid,
    object.type,
    object.typeLabel,
    object.description,
    object.product,
    object.vendor,
    object.catalogStatus,
    object.lifecycleStatus,
    object.deliveryModel,
    object.owner?.team,
    object.owner?.contact,
    aliases,
    objectNetworkBindingSearchText(object),
    componentNetworkBindingSearchText(object)
  ];
  return values.filter(Boolean).join(' ').toLowerCase();
}

function normalizedSearchTerm(value) {
  return String(value || '').trim().toLowerCase();
}

function objectMatchesSearch(object, searchTerm) {
  const tokens = normalizedSearchTerm(searchTerm).split(/\s+/).filter(Boolean);
  if (!tokens.length) return true;
  const searchText = objectSearchText(object);
  return tokens.every(token => searchText.includes(token));
}

function catalogSearchMarkup(matchCount, baseCount) {
  const hasSearch = Boolean(listSearchTerm.trim());
  return `
    <section class="catalog-search-panel">
      <div class="catalog-search-header">
        <label for="catalog-search">Search Current View</label>
        <span class="catalog-search-count">${hasSearch ? `${matchCount} of ${baseCount} matching` : `${baseCount} available`}</span>
      </div>
      <div class="catalog-search-control">
        <input id="catalog-search" class="catalog-search-input" type="search" autocomplete="off" placeholder="Name, UID, type, owner, product, vendor" value="${escapeHtml(listSearchTerm)}">
        ${hasSearch ? '<button class="filter-button" data-clear-list-search>Clear</button>' : ''}
      </div>
    </section>
  `;
}

function businessPillarForObject(object) {
  const pillarId = object.businessContext?.pillar || '';
  const pillar = pillarId ? businessPillarLookup[pillarId] : null;
  return {
    id: pillarId || 'unassigned',
    name: pillar?.name || (pillarId ? formatTitleCase(pillarId.replace(/^business-pillar\./, '').replace(/-/g, ' ')) : 'Unassigned Business Pillar'),
    owner: pillar?.owner || null
  };
}

function businessPillarBadge(object) {
  if (object.type !== 'software_deployment_pattern') {
    return '';
  }
  const pillar = businessPillarForObject(object);
  return `<div class="badge">${escapeHtml(pillar.name)}</div>`;
}

function businessPillarSidebarMarkup(objects) {
  if (activeFilter !== 'software_deployment_pattern') {
    return '';
  }
  const groups = groupSoftwareDeploymentPatternsByPillar(objects);
  return `
    <div class="sidebar-block">
      <div class="legend-title">Business Pillars</div>
      ${groups.map(group => `
        <div class="current-filter">
          <span class="dot" style="background:#f59e0b"></span>
          <span>${escapeHtml(group.pillar.name)}: ${group.objects.length}</span>
        </div>
      `).join('')}
    </div>
  `;
}

function groupSoftwareDeploymentPatternsByPillar(objects) {
  const groupsById = new Map();
  objects.forEach(object => {
    const pillar = businessPillarForObject(object);
    if (!groupsById.has(pillar.id)) {
      groupsById.set(pillar.id, { pillar, objects: [] });
    }
    groupsById.get(pillar.id).objects.push(object);
  });
  const order = new Map((businessTaxonomy.pillars || []).map((pillar, index) => [pillar.id, index]));
  return Array.from(groupsById.values()).sort((a, b) => {
    const aRank = order.has(a.pillar.id) ? order.get(a.pillar.id) : 999;
    const bRank = order.has(b.pillar.id) ? order.get(b.pillar.id) : 999;
    if (aRank !== bRank) return aRank - bRank;
    return a.pillar.name.localeCompare(b.pillar.name);
  });
}

function listRowMarkup(row, objects) {
  if (!objects.length) {
    return '';
  }
  if (row.id === 'software_deployment_pattern') {
    return softwareDeploymentPatternRowMarkup(row, objects);
  }
  return `
    <section class="content-row">
      <div class="content-row-header">
        <h2 class="content-row-title">${escapeHtml(row.label)}</h2>
        <span class="content-row-count">${objects.length} objects</span>
      </div>
      <div class="cards-grid">
        ${objects.map(object => objectCardMarkup(object)).join('')}
      </div>
    </section>
  `;
}

function softwareDeploymentPatternRowMarkup(row, objects) {
  const groups = groupSoftwareDeploymentPatternsByPillar(objects);
  return `
    <section class="content-row">
      <div class="content-row-header">
        <h2 class="content-row-title">${escapeHtml(row.label)}</h2>
        <span class="content-row-count">${objects.length} objects</span>
      </div>
      <div class="business-pillar-groups">
        ${groups.map(group => `
          <div class="business-pillar-group">
            <div class="business-pillar-header">
              <h3 class="business-pillar-title">${escapeHtml(group.pillar.name)}</h3>
              <span class="business-pillar-meta">${group.objects.length} ${group.objects.length === 1 ? 'pattern' : 'patterns'}</span>
            </div>
            <div class="cards-grid">
              ${group.objects.map(object => objectCardMarkup(object)).join('')}
            </div>
          </div>
        `).join('')}
      </div>
    </section>
  `;
}

function objectCardTitle(object) {
  if (object.type !== 'requirement_group') {
    return object.name;
  }
  const trimmed = String(object.name || '').replace(/\s+Requirement Group$/i, '');
  if (trimmed === 'Edge/Gateway Service') {
    return 'Appliance';
  }
  return trimmed;
}

function objectCardMarkup(object) {
  return `
    <article class="object-card" data-object-id="${object.id}" role="button" tabindex="0">
      <div>
        <h3>${escapeHtml(objectCardTitle(object))}</h3>
        <div class="object-id">${escapeHtml(object.id)}</div>
      </div>
      <div class="badges">
        ${lifecycleBadge(object.lifecycleStatus)}
        ${catalogBadge(object.catalogStatus)}
        ${object.type === 'decision_record' ? ardCategoryBadge(object.ardCategory) : ''}
        ${object.type === 'decision_record' ? ardStatusBadge(object.status) : ''}
        ${object.type === 'product_service' ? productBadge(object.product) : ''}
        ${deliveryModelBadge(object)}
        ${businessPillarBadge(object)}
      </div>
      <div class="badges">
        <div class="badge">${escapeHtml(object.typeLabel)}</div>
        ${object.type === 'product_service' ? `<div class="object-id">${escapeHtml(object.product)}</div>` : ''}
      </div>
    </article>
  `;
}

function abbClassificationLabel(value) {
  return formatTitleCase(String(value || 'unknown').replace(/-/g, ' '));
}

function networkBindingsForConfiguration(configuration) {
  return Array.isArray(configuration?.networkBindings) ? configuration.networkBindings : [];
}

function configurationsWithNetworkBindings(technology) {
  return (technology?.configurations || []).filter(configuration => networkBindingsForConfiguration(configuration).length);
}

function configurationById(technology, configurationId) {
  if (!configurationId) return null;
  return (technology?.configurations || []).find(configuration => configuration?.id === configurationId) || null;
}

function configurationDisplayName(configuration) {
  if (!configuration) return 'Not selected';
  const name = configuration.name || configuration.id || 'Configuration';
  return configuration.id && configuration.name ? `${name} (${configuration.id})` : name;
}

function networkBindingChipsMarkup(bindings) {
  if (!bindings.length) {
    return '<span class="interaction-notes">No network bindings documented.</span>';
  }
  return `
    <div class="network-binding-summary">
      ${bindings.map(binding => `
        <span class="network-binding-chip">
          <span class="network-binding-direction">${escapeHtml(binding.direction || 'network')}</span>
          ${escapeHtml(binding.port ?? 'unknown')}/${escapeHtml(binding.protocol || 'protocol')}
        </span>
      `).join('')}
    </div>
  `;
}

function networkBindingsTableMarkup(bindings, includeConfiguration = false) {
  if (!bindings.length) {
    return '<div class="interaction-notes">No network bindings documented.</div>';
  }
  return `
    <div class="table-scroll">
      <table class="data-table network-binding-table">
        <thead>
          <tr>
            ${includeConfiguration ? '<th>Configuration</th>' : ''}
            <th>Direction</th>
            <th>Port</th>
            <th>Protocol</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          ${bindings.map(row => {
            const binding = row.binding || row;
            return `
              <tr>
                ${includeConfiguration ? `<td>${escapeHtml(configurationDisplayName(row.configuration))}</td>` : ''}
                <td>${escapeHtml(binding.direction || '')}</td>
                <td>${escapeHtml(binding.port ?? '')}</td>
                <td>${escapeHtml(binding.protocol || '')}</td>
                <td>${escapeHtml(binding.description || '')}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function technologyNetworkBindingRows(technology) {
  return configurationsWithNetworkBindings(technology).flatMap(configuration =>
    networkBindingsForConfiguration(configuration).map(binding => ({ configuration, binding }))
  );
}

function groupedNetworkBindingChipsMarkup(rows) {
  if (!rows.length) {
    return '<span class="interaction-notes">No network bindings documented.</span>';
  }
  const groups = new Map();
  rows.forEach(row => {
    const key = row.configuration?.id || row.configuration?.name || 'configuration';
    if (!groups.has(key)) {
      groups.set(key, { configuration: row.configuration, bindings: [] });
    }
    groups.get(key).bindings.push(row.binding);
  });
  return `
    <div class="network-binding-groups">
      ${Array.from(groups.values()).map(group => `
        <div class="network-binding-group">
          <div class="interaction-notes"><strong>${escapeHtml(configurationDisplayName(group.configuration))}</strong></div>
          ${networkBindingChipsMarkup(group.bindings)}
        </div>
      `).join('')}
    </div>
  `;
}

function componentNetworkBindingResolution(component) {
  const target = objectLookup[component?.ref];
  if (!target || target.type !== 'technology_component') {
    return {
      target,
      configuration: null,
      bindings: [],
      availableRows: [],
      status: target ? 'not-technology' : 'missing'
    };
  }
  const availableRows = technologyNetworkBindingRows(target);
  const requestedConfiguration = component?.configuration || '';
  const configuration = configurationById(target, requestedConfiguration);
  if (requestedConfiguration && configuration) {
    return {
      target,
      configuration,
      bindings: networkBindingsForConfiguration(configuration),
      availableRows,
      status: 'selected'
    };
  }
  if (requestedConfiguration && !configuration) {
    return {
      target,
      configuration: null,
      bindings: [],
      availableRows,
      status: 'unknown-configuration'
    };
  }
  return {
    target,
    configuration: null,
    bindings: [],
    availableRows,
    status: availableRows.length ? 'available-unselected' : 'none'
  };
}

function componentNetworkBindingSearchText(object) {
  return (object.internalComponents || []).flatMap(component => {
    const resolution = componentNetworkBindingResolution(component);
    const parts = [component.ref, component.role, component.configuration, component.notes];
    if (resolution.target) {
      parts.push(resolution.target.name, resolution.target.vendor, resolution.target.productName, resolution.target.productVersion);
    }
    resolution.availableRows.forEach(row => {
      parts.push(
        row.configuration?.id,
        row.configuration?.name,
        row.binding?.direction,
        row.binding?.port,
        row.binding?.protocol,
        row.binding?.description
      );
    });
    return parts;
  }).filter(Boolean).join(' ');
}

function internalComponentNetworkMarkup(object) {
  const components = object?.internalComponents || [];
  const rows = components
    .map(component => ({ component, resolution: componentNetworkBindingResolution(component) }))
    .filter(row => {
      const resolution = row.resolution;
      return resolution.target?.type === 'technology_component'
        && (row.component.configuration || resolution.availableRows.length);
    });
  if (!rows.length) {
    return '';
  }
  return `
    <div class="component-network-section">
      <h3>Component Network Bindings</h3>
      <div class="table-scroll">
        <table class="data-table component-network-table">
          <thead>
            <tr>
              <th>Component</th>
              <th>Role</th>
              <th>Configuration</th>
              <th>Network Binding</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(row => {
              const component = row.component;
              const resolution = row.resolution;
              const target = resolution.target;
              let configurationCell = '';
              let bindingCell = '';
              let notesCell = component.notes || '';

              if (resolution.status === 'selected') {
                configurationCell = configurationDisplayName(resolution.configuration);
                bindingCell = networkBindingChipsMarkup(resolution.bindings);
                if (!resolution.bindings.length) {
                  notesCell = notesCell || 'Selected configuration has no network bindings documented.';
                }
              } else if (resolution.status === 'unknown-configuration') {
                configurationCell = `Unknown configuration: ${component.configuration}`;
                bindingCell = groupedNetworkBindingChipsMarkup(resolution.availableRows);
                notesCell = notesCell || 'The referenced configuration does not exist on the Technology Component.';
              } else if (resolution.status === 'available-unselected') {
                configurationCell = 'No configuration selected';
                bindingCell = groupedNetworkBindingChipsMarkup(resolution.availableRows);
                notesCell = notesCell || 'Available on the referenced Technology Component; not asserted as the selected service configuration.';
              }

              return `
                <tr>
                  <td>
                    <span class="ard-link" data-object-link="${escapeHtml(target.id)}">${escapeHtml(target.name)}</span>
                    <div class="object-id">${escapeHtml(target.id)}</div>
                  </td>
                  <td>${escapeHtml(component.role || 'component')}</td>
                  <td>${escapeHtml(configurationCell || 'Not applicable')}</td>
                  <td>${bindingCell}</td>
                  <td>${escapeHtml(notesCell)}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function objectNetworkBindingSearchText(object) {
  return (object.configurations || []).flatMap(configuration => {
    const parts = [
      configuration.id,
      configuration.name,
      configuration.description,
      ...(configuration.capabilities || [])
    ];
    networkBindingsForConfiguration(configuration).forEach(binding => {
      parts.push(binding.direction, binding.port, binding.protocol, binding.description);
    });
    return parts;
  }).filter(Boolean).join(' ');
}

function lifecycleSortRank(status) {
  return ({
    'preferred': 0,
    'existing-only': 1,
    'candidate': 2,
    'deprecated': 3,
    'retired': 4
  }[status] ?? 99);
}

function implementationConfigurationLabel(technology, implementation) {
  const configurationId = implementation?.configuration || '';
  if (!configurationId) return '';
  const configuration = (technology?.configurations || [])
    .find(item => item && item.id === configurationId);
  if (!configuration) return configurationId;
  return `${configuration.name || configuration.id} (${configurationId})`;
}

const activeRequirementGroupIds = new Set(browserData.requirements?.activeRequirementGroups || []);
const requireActiveRequirementGroupDisposition = Boolean(browserData.requirements?.requireActiveRequirementGroupDisposition);
const requirementGroups = allObjects.filter(object => object.type === 'requirement_group');
const rawDetailCache = new Map();

function rawDetailObject(object) {
  if (!object) return {};
  if (!rawDetailCache.has(object.id)) {
    try {
      rawDetailCache.set(object.id, JSON.parse(object.detail || '{}'));
    } catch (error) {
      rawDetailCache.set(object.id, {});
    }
  }
  return rawDetailCache.get(object.id) || {};
}

function getNestedValue(node, dottedKey) {
  if (!node || typeof node !== 'object' || !dottedKey) return null;
  return String(dottedKey).split('.').reduce((current, key) => {
    if (!current || typeof current !== 'object' || !(key in current)) return null;
    return current[key];
  }, node);
}

function requirementFriendlyLabel(group, requirement) {
  const requirementId = requirement?.externalControlId || requirement?.id || 'unknown';
  const requirementName = String(requirement?.name || '').trim();
  if (requirementName && requirementName !== requirementId) {
    return `${requirementId} ${requirementName}`;
  }
  const prefix = requirementAuthorityPrefix(group);
  return prefix ? `${prefix} ${requirementId}` : requirementDisplayLabel(group, requirement || { id: requirementId });
}

function capabilityDisplayName(capabilityId) {
  const capability = objectLookup[capabilityId];
  return capability?.name || capabilityId;
}

function capabilityLabelsMarkup(capabilities) {
  const values = Array.isArray(capabilities) ? capabilities.filter(Boolean) : [];
  if (!values.length) return '';
  return `
    <div class="requirement-badges dependency-capabilities">
      ${values.map(capabilityId => `<span class="requirement-badge capability-label">${escapeHtml(capabilityDisplayName(capabilityId))}</span>`).join('')}
    </div>
  `;
}

function requirementGroupAppliesToObject(group, object) {
  const raw = rawDetailObject(group);
  const appliesTo = Array.isArray(raw.appliesTo) ? raw.appliesTo : [];
  if (!appliesTo.includes(object.type)) {
    return false;
  }
  const qualifiers = raw.appliesToQualifiers && typeof raw.appliesToQualifiers === 'object'
    ? raw.appliesToQualifiers
    : {};
  for (const [key, expected] of Object.entries(qualifiers)) {
    if (object[key] !== expected) {
      return false;
    }
  }
  if (object.type === 'host' && group.name === 'Host Requirement Group') {
    const tags = Array.isArray(object.tags) ? object.tags : [];
    if (tags.some(tag => tag === 'serverless' || tag === 'container')) {
      return false;
    }
  }
  return true;
}

function applicabilityClauseMatches(object, clause) {
  if (!clause || typeof clause !== 'object' || !clause.field) {
    return false;
  }
  const value = getNestedValue(object, clause.field);
  if (Object.prototype.hasOwnProperty.call(clause, 'equals')) {
    return value === clause.equals;
  }
  if (Array.isArray(clause.in)) {
    return clause.in.includes(value);
  }
  if (Object.prototype.hasOwnProperty.call(clause, 'contains')) {
    return Array.isArray(value) && value.includes(clause.contains);
  }
  if (Object.prototype.hasOwnProperty.call(clause, 'truthy')) {
    return Boolean(value) === Boolean(clause.truthy);
  }
  return false;
}

function requirementAppliesToObject(requirement, object) {
  if (Array.isArray(requirement?.appliesTo) && requirement.appliesTo.length && !requirement.appliesTo.includes(object.type)) {
    return false;
  }
  const applicability = requirement?.applicability;
  if (applicability && typeof applicability === 'object') {
    if (Array.isArray(applicability.allOf)) {
      return applicability.allOf.every(clause => applicabilityClauseMatches(object, clause));
    }
    if (Array.isArray(applicability.anyOf)) {
      return applicability.anyOf.some(clause => applicabilityClauseMatches(object, clause));
    }
  }
  return true;
}

function resolvedRequirementsForGroup(groupId, stack = new Set()) {
  if (!groupId || stack.has(groupId)) {
    return [];
  }
  const group = objectLookup[groupId];
  if (!group || group.type !== 'requirement_group') {
    return [];
  }
  stack.add(groupId);
  const raw = rawDetailObject(group);
  const parentRequirements = raw.inherits ? resolvedRequirementsForGroup(raw.inherits, stack) : [];
  const ownRequirements = Array.isArray(raw.requirements) ? raw.requirements : [];
  stack.delete(groupId);
  return [...parentRequirements, ...ownRequirements];
}

function applicableRequirementEntries(object) {
  const declaredGroupIds = new Set(Array.isArray(object.requirementGroups) ? object.requirementGroups : []);
  const entries = [];
  requirementGroups.forEach(group => {
    if (!requirementGroupAppliesToObject(group, object)) {
      return;
    }
    const activation = rawDetailObject(group).activation || group.activation || '';
    const included = activation === 'always'
      || declaredGroupIds.has(group.id)
      || (requireActiveRequirementGroupDisposition && activeRequirementGroupIds.has(group.id));
    if (!included) {
      return;
    }
    resolvedRequirementsForGroup(group.id).forEach(requirement => {
      if (requirement && requirementAppliesToObject(requirement, object)) {
        entries.push({ group, requirement });
      }
    });
  });
  return entries;
}

function interactionCapabilities(interaction) {
  return Array.isArray(interaction?.capabilities) ? interaction.capabilities.filter(Boolean).map(String) : [];
}

function referencedTechnologyComponents(object) {
  const refs = [];
  ['operatingSystemComponent', 'computePlatformComponent', 'primaryTechnologyComponent'].forEach(field => {
    if (object?.[field]) {
      refs.push(object[field]);
    }
  });
  (object?.internalComponents || []).forEach(component => {
    if (component?.ref) {
      refs.push(component.ref);
    }
  });
  if (object?.type === 'technology_component' && object.id) {
    refs.unshift(object.id);
  }
  return Array.from(new Set(refs))
    .map(ref => objectLookup[ref])
    .filter(target => target?.type === 'technology_component');
}

function technologyRefSatisfiesCriteria(ref, criteria) {
  const target = objectLookup[ref];
  if (!target || target.type !== 'technology_component') {
    return false;
  }
  if (criteria?.classification && target.classification !== criteria.classification) {
    return false;
  }
  const capability = criteria?.capability || criteria?.concern;
  if (!capability) {
    return true;
  }
  return Array.isArray(target.capabilities) && target.capabilities.includes(capability);
}

function technologyRefConfigurationSatisfiesCriteria(ref, criteria) {
  const target = objectLookup[ref];
  if (!target || target.type !== 'technology_component') {
    return false;
  }
  if (criteria?.classification && target.classification !== criteria.classification) {
    return false;
  }
  const capability = criteria?.capability || criteria?.concern;
  return (target.configurations || []).some(configuration =>
    configuration
    && Array.isArray(configuration.capabilities)
    && configuration.capabilities.includes(capability)
  );
}

function externalInteractionSatisfiesMechanism(interaction, mechanism) {
  if (mechanism?.mechanism !== 'externalInteraction') {
    return false;
  }
  const capability = mechanism.criteria?.capability;
  if (capability === 'any') {
    return true;
  }
  return Boolean(capability && interactionCapabilities(interaction).includes(capability));
}

function externalInteractionSatisfiesImplementation(interaction, implementation) {
  if (implementation?.status !== 'satisfied' || implementation?.mechanism !== 'externalInteraction') {
    return false;
  }
  const ref = implementation.ref;
  const capabilities = interactionCapabilities(interaction);
  if (ref && [interaction.ref, interaction.name, ...capabilities].includes(ref)) {
    return true;
  }
  const criteria = implementation.criteria && typeof implementation.criteria === 'object' ? implementation.criteria : {};
  const expected = Array.isArray(criteria.capabilities)
    ? criteria.capabilities
    : criteria.capability ? [criteria.capability] : [];
  return expected.some(capability => capabilities.includes(capability));
}

function internalComponentSatisfiesMechanism(object, component, mechanism) {
  const ref = component?.ref;
  if (!ref) {
    return false;
  }
  if (mechanism?.mechanism === 'field') {
    const raw = rawDetailObject(object);
    return Boolean(
      mechanism.key
      && (object?.[mechanism.key] === ref || raw?.[mechanism.key] === ref)
    );
  }
  if (mechanism?.mechanism === 'technologyComponent') {
    if (mechanism.ref && mechanism.ref !== ref) {
      return false;
    }
    return technologyRefSatisfiesCriteria(ref, mechanism.criteria || {});
  }
  if (mechanism?.mechanism === 'internalComponent') {
    const criteria = mechanism.criteria || {};
    if (criteria.role && component.role === criteria.role) {
      return true;
    }
    return technologyRefSatisfiesCriteria(ref, criteria);
  }
  if (mechanism?.mechanism === 'technologyComponentConfiguration') {
    return technologyRefConfigurationSatisfiesCriteria(ref, mechanism.criteria || {});
  }
  if (mechanism?.mechanism === 'externalInteraction') {
    return (object?.externalInteractions || []).some(interaction =>
      interaction
      && interaction.enabledBy === ref
      && externalInteractionSatisfiesMechanism(interaction, mechanism)
    );
  }
  return false;
}

function internalComponentSatisfiesImplementation(object, component, implementation) {
  if (implementation?.status !== 'satisfied' || !component?.ref) {
    return false;
  }
  const ref = component.ref;
  const mechanism = implementation.mechanism;
  if (mechanism === 'field') {
    const raw = rawDetailObject(object);
    return Boolean(
      implementation.key
      && (object?.[implementation.key] === ref || raw?.[implementation.key] === ref)
    );
  }
  if (mechanism === 'technologyComponent' || mechanism === 'internalComponent') {
    if (implementation.ref === ref) {
      return true;
    }
    return technologyRefSatisfiesCriteria(ref, implementation.criteria || {});
  }
  if (mechanism === 'technologyComponentConfiguration') {
    if (implementation.ref && implementation.ref !== ref) {
      return false;
    }
    return technologyRefConfigurationSatisfiesCriteria(ref, implementation.criteria || {});
  }
  if (mechanism === 'externalInteraction') {
    return (object?.externalInteractions || []).some(interaction =>
      interaction
      && interaction.enabledBy === ref
      && externalInteractionSatisfiesImplementation(interaction, implementation)
    );
  }
  return false;
}

function entryRationaleCandidates(entry, context, kind) {
  const candidates = [context];
  ['id', 'name', 'ref', 'enabledBy', 'role'].forEach(key => {
    if (entry?.[key]) {
      candidates.push(String(entry[key]));
    }
  });
  if (kind === 'external') {
    interactionCapabilities(entry).forEach(capability => candidates.push(capability));
  }
  return Array.from(new Set(candidates));
}

function rationaleEntriesForCandidates(bucketValue, candidates) {
  const entries = [];
  if (bucketValue && typeof bucketValue === 'object' && !Array.isArray(bucketValue)) {
    candidates.forEach(candidate => {
      if (!(candidate in bucketValue)) {
        return;
      }
      const value = bucketValue[candidate];
      if (value === true) {
        entries.push('Modeled as documented architectural decision.');
      } else if (value) {
        entries.push(String(value));
      }
    });
    return Array.from(new Set(entries));
  }
  if (Array.isArray(bucketValue)) {
    bucketValue.forEach(item => {
      if (!item || typeof item !== 'object') {
        return;
      }
      const itemCandidates = new Set(
        ['id', 'name', 'ref', 'enabledBy', 'role', 'capability']
          .map(key => item[key])
          .filter(Boolean)
          .map(String)
      );
      if (Array.isArray(item.capabilities)) {
        item.capabilities.filter(Boolean).forEach(capability => itemCandidates.add(String(capability)));
      }
      if (!candidates.some(candidate => itemCandidates.has(candidate))) {
        return;
      }
      const reason = item.reason || item.rationale || item.decision || item.notes;
      if (reason) {
        entries.push(String(reason));
      }
    });
  }
  return Array.from(new Set(entries));
}

function dependencyRationales(object, kind, entry, context) {
  const decisions = object?.architecturalDecisions;
  if (!decisions || typeof decisions !== 'object') {
    return [];
  }
  const candidates = entryRationaleCandidates(entry, context, kind);
  const bucketNames = kind === 'external'
    ? ['externalInteractionRationales', 'dependencyRationales']
    : ['internalComponentRationales', 'dependencyRationales'];
  return Array.from(new Set(
    bucketNames.flatMap(bucketName => rationaleEntriesForCandidates(decisions[bucketName], candidates))
  ));
}

function dependencyRequirementMatches(object, entry, kind, context) {
  const matches = new Map();
  applicableRequirementEntries(object).forEach(({ group, requirement }) => {
    const mechanisms = Array.isArray(requirement?.canBeSatisfiedBy) ? requirement.canBeSatisfiedBy : [];
    const satisfiedByMechanism = mechanisms.some(mechanism => {
      if (!mechanism || typeof mechanism !== 'object') return false;
      return kind === 'external'
        ? externalInteractionSatisfiesMechanism(entry, mechanism)
        : internalComponentSatisfiesMechanism(object, entry, mechanism);
    });
    if (satisfiedByMechanism) {
      matches.set(`${group.id}:${requirement.id || requirement.externalControlId || requirement.name}`, {
        group,
        requirement
      });
    }
  });

  (object.requirementImplementations || []).forEach(implementation => {
    if (!implementation || typeof implementation !== 'object') return;
    const matchesImplementation = kind === 'external'
      ? externalInteractionSatisfiesImplementation(entry, implementation)
      : internalComponentSatisfiesImplementation(object, entry, implementation);
    if (!matchesImplementation) {
      return;
    }
    const group = objectLookup[implementation.requirementGroup] || null;
    const requirement = findRequirementInGroup(group, implementation.requirementId) || {
      id: implementation.requirementId || implementation.key || 'unknown'
    };
    matches.set(`${implementation.requirementGroup}:${implementation.requirementId}:${implementation.key || ''}:${context}`, {
      group,
      requirement
    });
  });

  return Array.from(matches.values());
}

function dependencyJustificationMarkup(justification) {
  if (!justification) return '';
  if (justification.type === 'requirement') {
    return `
      <div class="dependency-justification">
        <div class="justification-label">Required By</div>
        <div class="requirement-badges">
          ${justification.items.map(item => `<span class="requirement-badge">${escapeHtml(requirementFriendlyLabel(item.group, item.requirement))}</span>`).join('')}
        </div>
      </div>
    `;
  }
  if (justification.type === 'decision') {
    return `
      <div class="dependency-justification">
        <div class="justification-label">Architectural Decision</div>
        <div class="interaction-notes">${escapeHtml(justification.items[0] || 'Modeled as documented architectural decision.')}</div>
      </div>
    `;
  }
  return `
    <div class="dependency-justification">
      <div class="justification-label">Justification Gap</div>
      <div class="interaction-notes">No requirement evidence or architectural decision rationale is documented for this dependency.</div>
    </div>
  `;
}

function dependencyJustificationForExternalInteraction(object, interaction, index) {
  const context = `externalInteractions[${index}]`;
  const requirementMatches = dependencyRequirementMatches(object, interaction, 'external', context);
  if (requirementMatches.length) {
    return { type: 'requirement', items: requirementMatches };
  }
  const rationales = dependencyRationales(object, 'external', interaction, context);
  if (rationales.length) {
    return { type: 'decision', items: rationales };
  }
  return { type: 'gap', items: [] };
}

function dependencyJustificationForInternalComponent(object, component, index) {
  const context = `internalComponents[${index}]`;
  const requirementMatches = dependencyRequirementMatches(object, component, 'internal', context);
  if (requirementMatches.length) {
    return { type: 'requirement', items: requirementMatches };
  }
  const rationales = dependencyRationales(object, 'internal', component, context);
  if (rationales.length) {
    return { type: 'decision', items: rationales };
  }
  return { type: 'gap', items: [] };
}

function acceptableUseGroups() {
  const groups = new Map();
  allObjects
    .filter(object => object.type === 'capability')
    .sort((a, b) => {
      const domainA = objectLookup[a.domain]?.name || a.domain || '';
      const domainB = objectLookup[b.domain]?.name || b.domain || '';
      return domainA.localeCompare(domainB) || a.name.localeCompare(b.name);
    })
    .forEach(capability => {
      const implementations = Array.isArray(capability.implementations)
        ? capability.implementations.slice().sort((a, b) => {
            const objectA = objectLookup[a.ref] || {};
            const objectB = objectLookup[b.ref] || {};
            const vendorA = objectA.vendor || '';
            const vendorB = objectB.vendor || '';
            const techA = objectA.name || a.ref || '';
            const techB = objectB.name || b.ref || '';
            return vendorA.localeCompare(vendorB)
              || techA.localeCompare(techB)
              || lifecycleSortRank(a.lifecycleStatus) - lifecycleSortRank(b.lifecycleStatus)
              || (a.lifecycleStatus || '').localeCompare(b.lifecycleStatus || '');
          })
        : [];
      if (!implementations.length) {
        return;
      }
      const domainId = capability.domain || 'domain.unassigned';
      const domain = objectLookup[domainId] || {
        id: domainId,
        name: capability.domain || 'Unassigned Domain',
        description: ''
      };
      if (!groups.has(domainId)) {
        groups.set(domainId, { domain, rows: [] });
      }
      const rows = groups.get(domainId).rows;
      implementations.forEach(implementation => {
        rows.push({
          capability,
          implementation,
          technology: objectLookup[implementation.ref] || null
        });
      });
    });
  return Array.from(groups.values())
    .sort((a, b) => (a.domain.name || a.domain.id).localeCompare(b.domain.name || b.domain.id));
}

function requirementEvidenceRows() {
  const rows = [];
  allObjects.forEach(object => {
    (object.requirementImplementations || []).forEach(implementation => {
      if (!implementation) return;
      const requirementGroup = objectLookup[implementation.requirementGroup] || null;
      const requirement = findRequirementInGroup(requirementGroup, implementation.requirementId);
      rows.push({
        object,
        implementation,
        requirementGroup,
        requirement,
        label: requirementDisplayLabel(requirementGroup, requirement || { id: implementation.requirementId })
      });
    });
  });
  return rows;
}

function requirementGroupName(group) {
  if (!group) return 'Requirement Group';
  return String(group.name || group.id || 'Requirement Group').replace(/\s+Requirement Group$/i, '').trim() || 'Requirement Group';
}

function requirementAuthorityPrefix(group) {
  const authority = group?.authority || {};
  const provider = group?.provider || {};
  return authority.shortName || authority.name || provider.shortName || provider.name || provider.id || '';
}

function findRequirementInGroup(group, requirementId) {
  if (!group || !Array.isArray(group.requirements)) return null;
  return group.requirements.find(requirement => requirement && requirement.id === requirementId) || null;
}

function requirementDisplayLabel(group, requirement) {
  const requirementId = requirement?.id || requirement?.externalControlId || 'unknown';
  if (requirement?.externalControlId) {
    const prefix = requirementAuthorityPrefix(group);
    return prefix ? `${prefix}.${requirementId}` : requirementId;
  }
  const prefix = requirementAuthorityPrefix(group);
  return prefix ? `${prefix} ${requirementGroupName(group)} / ${requirementId}` : `${requirementGroupName(group)} / ${requirementId}`;
}

function requirementSourceText(group) {
  if (!group) return 'Unknown Requirement Group';
  const source = group.authority?.source || group.name || group.id;
  const authority = group.authority?.name;
  if (authority && source && authority !== source) {
    return `${authority} - ${source}`;
  }
  return source || authority || group.id;
}

function executiveStats() {
  const acceptableGroups = acceptableUseGroups();
  const acceptableRows = acceptableGroups.flatMap(group => group.rows);
  const uniqueMappedTech = new Set(
    acceptableRows
      .map(row => row.implementation?.ref)
      .filter(Boolean)
  );
  const requirementGroups = browserData.requirements?.groups || [];
  const requirementEvidence = requirementEvidenceRows();
  const domainStats = acceptableGroups.map(group => {
    const capabilityIds = new Set(group.rows.map(row => row.capability.id));
    const technologyRefs = new Set(
      group.rows
        .map(row => row.implementation?.ref)
        .filter(Boolean)
    );
    return {
      domain: group.domain,
      capabilityCount: capabilityIds.size,
      technologyCount: technologyRefs.size
    };
  }).sort((a, b) => b.technologyCount - a.technologyCount || b.capabilityCount - a.capabilityCount);
  const lifecycleCounts = {};
  acceptableRows.forEach(row => {
    const status = row.implementation?.lifecycleStatus || 'unknown';
    lifecycleCounts[status] = (lifecycleCounts[status] || 0) + 1;
  });
  const objectTypes = {
    softwareDeploymentPatterns: allObjects.filter(object => object.type === 'software_deployment_pattern').length,
    referenceArchitectures: allObjects.filter(object => object.type === 'reference_architecture').length,
    hosts: allObjects.filter(object => object.type === 'host').length,
    runtimeServices: allObjects.filter(object => object.type === 'runtime_service').length,
    dataAtRestServices: allObjects.filter(object => object.type === 'data_at_rest_service').length,
    edgeGatewayServices: allObjects.filter(object => object.type === 'edge_gateway_service').length,
    productServices: allObjects.filter(object => object.type === 'product_service').length,
    productComponents: allObjects.filter(object => object.type === 'product_component').length,
    dataComponents: allObjects.filter(object => object.type === 'data_component').length,
    environmentTiers: allObjects.filter(object => object.type === 'environment_tier').length
  };
  return {
    objectCount: allObjects.length,
    technologyCount: allObjects.filter(object => object.type === 'technology_component').length,
    capabilityCount: allObjects.filter(object => object.type === 'capability').length,
    softwareDeploymentPatternCount: objectTypes.softwareDeploymentPatterns,
    referenceArchitectureCount: objectTypes.referenceArchitectures,
    requirementGroupCount: requirementGroups.length,
    activeRequirementGroupCount: requirementGroups.filter(group => group.active || group.activation === 'always').length,
    requirementDefinitionCount: requirementGroups.reduce((count, group) => count + (group.requirementCount || 0), 0),
    controlEvidenceCount: requirementEvidence.length,
    controlEvidenceObjectCount: new Set(requirementEvidence.map(row => row.object.id)).size,
    acceptableUseMappingCount: acceptableRows.length,
    acceptableUseTechnologyCount: uniqueMappedTech.size,
    domainCount: allObjects.filter(object => object.type === 'domain').length,
    domainStats,
    lifecycleCounts,
    objectTypes,
    requirementEvidence
  };
}

function executiveMetricTile({ target, value, label, description, size = 'medium', accent = 'cyan', big = false }) {
  return `
    <article class="executive-tile ${size} executive-accent-${accent}" role="button" tabindex="0" data-executive-target="${escapeHtml(target)}">
      <div class="executive-tile-title">
        <p class="executive-number ${big ? 'big' : ''}">${formatNumber(value)}</p>
        <h3>${escapeHtml(label)}</h3>
      </div>
      <p>${escapeHtml(description)}</p>
    </article>
  `;
}

function executiveSidebarMarkup(stats) {
  return `
    <div class="sidebar-block">
      <div class="legend-title">DRAFT Overview</div>
      <div class="current-filter"><span class="dot" style="background:#7c3a6b"></span><span>${pluralize(stats.objectCount, 'catalog object')}</span></div>
      <div class="current-filter"><span class="dot" style="background:#22c55e"></span><span>${pluralize(stats.acceptableUseTechnologyCount, 'mapped Technology Component')}</span></div>
      <div class="current-filter"><span class="dot" style="background:#f59e0b"></span><span>${pluralize(stats.controlEvidenceCount, 'control answer')}</span></div>
    </div>
  `;
}

function executiveLifecyclePanelMarkup(stats) {
  const orderedStatuses = ['preferred', 'existing-only', 'candidate', 'deprecated', 'retired', 'unknown'];
  const rows = orderedStatuses
    .filter(status => stats.lifecycleCounts[status])
    .map(status => ({ status, count: stats.lifecycleCounts[status] }));
  const maxCount = Math.max(...rows.map(row => row.count), 1);
  return `
    <section class="executive-panel wide">
      <h3>Technology Lifecycle Mix</h3>
      <div class="executive-bars">
        ${rows.map(row => {
          const color = '#' + (lifecycleColors[row.status] || lifecycleColors.unknown);
          const width = Math.max(6, Math.round((row.count / maxCount) * 100));
          return `
            <div class="executive-bar-row">
              <span>${escapeHtml(row.status)}</span>
              <span class="executive-bar-track"><span class="executive-bar-fill" style="width:${width}%;background:${color};"></span></span>
              <strong>${formatNumber(row.count)}</strong>
            </div>
          `;
        }).join('') || '<div class="empty-card">No lifecycle mappings are available.</div>'}
      </div>
    </section>
  `;
}

function executiveDomainPanelMarkup(stats) {
  return `
    <section class="executive-panel wide">
      <h3>Capability Domains</h3>
      <div class="executive-bars">
        ${stats.domainStats.slice(0, 6).map(item => `
          <div class="executive-snapshot-row">
            <span>${escapeHtml(item.domain.name || item.domain.id)}</span>
            <strong>${pluralize(item.technologyCount, 'tech')}</strong>
          </div>
          <div class="object-id">${pluralize(item.capabilityCount, 'capability', 'capabilities')}</div>
        `).join('') || '<div class="empty-card">No mapped capability domains are available.</div>'}
      </div>
    </section>
  `;
}

function executiveArchitecturePanelMarkup(stats) {
  const rows = [
    ['Software Deployment Patterns', stats.objectTypes.softwareDeploymentPatterns],
    ['Reference Architectures', stats.objectTypes.referenceArchitectures],
    ['Hosts', stats.objectTypes.hosts],
    ['Runtime Services', stats.objectTypes.runtimeServices],
    ['Data-at-Rest Services', stats.objectTypes.dataAtRestServices],
    ['Edge/Gateway Services', stats.objectTypes.edgeGatewayServices],
    ['Product Services', stats.objectTypes.productServices]
  ];
  const maxCount = Math.max(...rows.map(row => row[1]), 1);
  return `
    <section class="executive-panel wide">
      <h3>Architecture Inventory Mix</h3>
      <div class="executive-bars">
        ${rows.map(([label, count]) => {
          const width = Math.max(5, Math.round((count / maxCount) * 100));
          return `
            <div class="executive-bar-row">
              <span>${escapeHtml(label)}</span>
              <span class="executive-bar-track"><span class="executive-bar-fill" style="width:${width}%;"></span></span>
              <strong>${formatNumber(count)}</strong>
            </div>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

function executiveControlDrilldownMarkup(stats) {
  if (executiveDrilldown !== 'controls') {
    return '';
  }
  const grouped = new Map();
  stats.requirementEvidence.forEach(row => {
    const existing = grouped.get(row.object.id) || {
      object: row.object,
      count: 0,
      groups: new Set(),
      requirements: new Set(),
      statuses: {}
    };
    existing.count += 1;
    if (row.implementation.requirementGroup) {
      existing.groups.add(requirementGroupName(row.requirementGroup));
    }
    existing.requirements.add(row.label);
    const status = row.implementation.status || 'unknown';
    existing.statuses[status] = (existing.statuses[status] || 0) + 1;
    grouped.set(row.object.id, existing);
  });
  const rows = Array.from(grouped.values())
    .sort((a, b) => b.count - a.count || a.object.name.localeCompare(b.object.name));
  const requirementGroups = browserData.requirements?.groups || [];
  return `
    <section class="executive-panel full executive-drilldown">
      <div class="header-top">
        <div>
          <h3>Control Evidence Drill-Down</h3>
          <div class="object-id">${pluralize(stats.controlEvidenceCount, 'requirement evidence record')} across ${pluralize(stats.controlEvidenceObjectCount, 'catalog object')}</div>
        </div>
        <button class="action-button secondary" data-executive-target="clear-drilldown">Close</button>
      </div>
      ${rows.length ? `
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>Artifact</th>
                <th>Type</th>
                <th>Requirement Groups</th>
                <th>Requirements</th>
                <th>Evidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(row => `
                <tr>
                  <td>
                    <span class="ard-link" data-object-link="${escapeHtml(row.object.id)}">${escapeHtml(row.object.name)}</span>
                    <div class="object-id">${escapeHtml(row.object.id)}</div>
                  </td>
                  <td>${escapeHtml(row.object.typeLabel)}</td>
                  <td>${Array.from(row.groups).map(groupName => `<span class="badge">${escapeHtml(groupName)}</span>`).join('')}</td>
                  <td>${Array.from(row.requirements).slice(0, 4).map(label => `<span class="badge">${escapeHtml(label)}</span>`).join('')}${row.requirements.size > 4 ? `<div class="object-id">+${formatNumber(row.requirements.size - 4)} more</div>` : ''}</td>
                  <td>${formatNumber(row.count)}</td>
                  <td>${Object.entries(row.statuses).map(([status, count]) => `<span class="badge">${escapeHtml(status)}: ${formatNumber(count)}</span>`).join('')}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      ` : `
        <div class="empty-card">
          No object-level requirement evidence has been recorded yet. ${pluralize(stats.requirementDefinitionCount, 'requirement')} are available across ${pluralize(requirementGroups.length, 'Requirement Group')}.
        </div>
      `}
    </section>
  `;
}

// ── Helper: shared subview header with back button ──────────────────
function subviewHeaderMarkup(backLabel, backTarget, title, subtitle, metaHtml = '') {
  return `
    <div class="subview-header">
      <button class="subview-back" data-executive-target="${escapeHtml(backTarget)}">← ${escapeHtml(backLabel)}</button>
      <h1>${escapeHtml(title)}</h1>
      ${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ''}
      ${metaHtml ? `<div class="subview-meta">${metaHtml}</div>` : ''}
    </div>
  `;
}

// ── Requirement Group classifiers ──────────────────────────────────
// "Built-in" means authored and maintained by the DRAFT Framework itself.
// Third-party compliance packs (NIST, SOC 2, TX-RAMP, etc.) have their own
// authority and are distributed as plug-ins — they live with company groups
// in the UI, not in "Built-In DRAFT Configurations".
function isBuiltInGroup(group) {
  return group.authority?.name === 'DRAFT Framework';
}

function isThirdPartyGroup(group) {
  const a = group.authority?.name;
  return !!a && a !== 'DRAFT Framework';
}

// ── Requirement Groups list view ────────────────────────────────────
function renderRequirementGroupsView({ builtIn = false } = {}) {
  currentMode = builtIn ? 'builtin-configs' : 'requirement-groups';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  if (builtIn) syncHashForBuiltInConfigsView(); else syncHashForRequirementGroupsView();
  renderSidebarContent('');

  const allGroups = (browserData.requirements?.groups || []);
  const sortGroups = gs => [...gs].sort((a, b) => {
    const aActive = a.active || a.activation === 'always';
    const bActive = b.active || b.activation === 'always';
    if (aActive !== bActive) return aActive ? -1 : 1;
    return (a.name || '').localeCompare(b.name || '');
  });

  let sections, title, subtitle;
  if (builtIn) {
    const groups = sortGroups(allGroups.filter(g => isBuiltInGroup(g)));
    const activeCount = groups.filter(g => g.active || g.activation === 'always').length;
    title = 'Built-In DRAFT Configurations';
    subtitle = `${groups.length} group${groups.length === 1 ? '' : 's'} · ${activeCount} active`;
    sections = [{ heading: null, groups, thirdParty: false }];
  } else {
    const companyGroups = sortGroups(allGroups.filter(g => !isBuiltInGroup(g) && !isThirdPartyGroup(g)));
    const thirdPartyGroups = sortGroups(allGroups.filter(g => isThirdPartyGroup(g)));
    const totalCount = companyGroups.length + thirdPartyGroups.length;
    const activeCount = [...companyGroups, ...thirdPartyGroups].filter(g => g.active || g.activation === 'always').length;
    title = 'Requirement Groups';
    subtitle = `${totalCount} group${totalCount === 1 ? '' : 's'} · ${activeCount} active`;
    sections = [
      { heading: null, groups: companyGroups, thirdParty: false },
      { heading: 'Third-Party Compliance Packs', groups: thirdPartyGroups, thirdParty: true },
    ];
  }

  function renderGroupCard(group, thirdParty) {
    const fullGroup = objectLookup[group.uid] || {};
    const requirements = Array.isArray(fullGroup.requirements) ? fullGroup.requirements : [];
    const requiredCount = requirements.filter(r => r.requirementMode === 'required').length;
    const recommendedCount = requirements.filter(r => r.requirementMode === 'recommended').length;
    const isAlwaysOn = group.activation === 'always';
    const isActive = group.active || isAlwaysOn;
    const badgeClass = isAlwaysOn ? 'badge-always-on' : (isActive ? 'badge-active' : 'badge-inactive');
    const badgeLabel = isAlwaysOn ? 'Always On' : (isActive ? 'Active' : 'Inactive');
    const authorityName = group.authority?.shortName || group.authority?.name || null;
    const authorityBadge = (thirdParty || builtIn) && authorityName
      ? `<span class="badge badge-inactive">${escapeHtml(authorityName)}</span>`
      : '';
    return `
      <button class="rg-card ${isActive ? '' : 'rg-inactive'}" data-nav-rg="${escapeHtml(group.uid)}">
        <div class="rg-card-header">
          <span class="rg-name">${escapeHtml(group.name || group.uid)}</span>
          <span class="badge ${badgeClass}">${badgeLabel}</span>
          ${authorityBadge}
        </div>
        <div class="rg-card-counts">
          <span class="badge badge-inactive">${group.requirementCount || requirements.length} requirements</span>
          ${requiredCount ? `<span class="badge badge-required">${requiredCount} required</span>` : ''}
          ${recommendedCount ? `<span class="badge badge-recommended">${recommendedCount} recommended</span>` : ''}
        </div>
        ${group.description ? `<p class="rg-card-desc">${escapeHtml(group.description)}</p>` : ''}
      </button>
    `;
  }

  const sectionsHtml = sections.map(({ heading, groups, thirdParty }) => {
    if (!groups.length && !heading) return '<p class="empty-state">No requirement groups found.</p>';
    if (!groups.length) return '';
    const headingHtml = heading
      ? `<div class="rg-section-heading">
           <span>${escapeHtml(heading)}</span>
           <span class="badge badge-inactive">${groups.length}</span>
         </div>`
      : '';
    return headingHtml + groups.map(g => renderGroupCard(g, thirdParty)).join('');
  }).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup('Home', 'home', title, subtitle)}
      <div class="rg-list">
        ${sectionsHtml}
      </div>
    </div>
  `;

  pageRoot.querySelectorAll('[data-nav-rg]').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = allGroups.find(g => g.uid === btn.dataset.navRg);
      renderRequirementGroupDetailView(btn.dataset.navRg, { builtIn: group ? isBuiltInGroup(group) : builtIn });
    });
  });
  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
}

// ── Requirement Group detail — walk the requirements ────────────────
function renderRequirementGroupDetailView(uid, { builtIn = false } = {}) {
  currentMode = 'requirement-group-detail';
  currentSubViewId = uid;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForRequirementGroupDetailView(uid);
  renderSidebarContent('');

  const groupMeta = (browserData.requirements?.groups || []).find(g => g.uid === uid) || {};
  const fullGroup = objectLookup[uid] || {};
  const groupName = groupMeta.name || fullGroup.name || uid;
  const requirements = Array.isArray(fullGroup.requirements) ? fullGroup.requirements : [];

  // Index evidence by requirementId for this group
  const evidenceByReqId = {};
  (browserData.objects || []).forEach(obj => {
    (obj.requirementImplementations || []).forEach(impl => {
      if (impl.requirementGroup === uid) {
        if (!evidenceByReqId[impl.requirementId]) evidenceByReqId[impl.requirementId] = [];
        evidenceByReqId[impl.requirementId].push(obj);
      }
    });
  });

  const isAlwaysOn = groupMeta.activation === 'always';
  const isActive = groupMeta.active || isAlwaysOn;
  const badgeClass = isAlwaysOn ? 'badge-always-on' : (isActive ? 'badge-active' : 'badge-inactive');
  const badgeLabel = isAlwaysOn ? 'Always On' : (isActive ? 'Active' : 'Inactive');
  const metaHtml = `<span class="badge ${badgeClass}">${badgeLabel}</span><span style="font-size:0.82rem;color:var(--text-muted)">${requirements.length} requirement${requirements.length === 1 ? '' : 's'}</span>`;

  const reqCards = requirements.map(req => {
    const evidence = evidenceByReqId[req.id] || [];
    const mode = req.requirementMode || 'informational';
    const modeClass = mode === 'required' ? 'req-required' : mode === 'recommended' ? 'req-recommended' : 'req-informational';
    return `
      <div class="req-card ${modeClass}">
        <div class="req-card-header">
          <span class="badge badge-${mode}">${mode}</span>
          ${req.id ? `<span class="req-id">${escapeHtml(req.id)}</span>` : ''}
          ${req.naAllowed ? `<span class="badge badge-inactive">N/A allowed</span>` : ''}
        </div>
        <p class="req-description">${escapeHtml(req.description || '')}</p>
        ${evidence.length ? `
          <div class="req-evidence">
            <span class="req-evidence-label">${evidence.length} catalog object${evidence.length === 1 ? '' : 's'} address this</span>
            <div class="req-evidence-links">
              ${evidence.map(obj => `<span class="ard-link" data-object-link="${escapeHtml(obj.uid || '')}">${escapeHtml(obj.name || obj.uid || '')}</span>`).join('')}
            </div>
          </div>
        ` : `<span class="req-no-evidence">No catalog objects address this yet</span>`}
      </div>
    `;
  }).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup(builtIn ? 'Built-In DRAFT Configurations' : 'Requirement Groups', builtIn ? 'built-in-configs' : 'requirement-groups', groupName, groupMeta.description || fullGroup.description || '', metaHtml)}
      <div class="req-list">
        ${reqCards || '<p class="empty-state">No requirements defined in this group.</p>'}
      </div>
    </div>
  `;

  pageRoot.querySelectorAll('[data-nav-back="requirement-groups"], [data-nav-back="built-in-configs"]').forEach(btn => {
    btn.addEventListener('click', () => renderRequirementGroupsView({ builtIn }));
  });
  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
}

// ── Vocabularies view ───────────────────────────────────────────────
function renderVocabulariesView() {
  currentMode = 'vocabularies';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForVocabulariesView();
  renderSidebarContent('');

  const vocabulary = browserData.vocabulary || {};
  const listNames = Object.keys(vocabulary);
  const VOCAB_LABELS = {
    deploymentTargets: 'Deployment Targets',
    connectionProtocols: 'Connection Protocols',
    networkZones: 'Network Zones',
    dataClassificationLevels: 'Data Classification Levels',
    teams: 'Teams',
    availabilityTiers: 'Availability Tiers',
    failureDomains: 'Failure Domains',
  };

  const vocabCards = listNames.map(listName => {
    const listData = vocabulary[listName] || {};
    const mode = listData.mode || 'advisory';
    const values = Array.isArray(listData.values) ? listData.values : [];
    const label = VOCAB_LABELS[listName] || listName;
    const approvedValues = values.filter(v => (v.status || 'approved') === 'approved');
    const proposedValues = values.filter(v => v.status === 'proposed');
    return `
      <div class="vocab-card">
        <div class="vocab-card-header">
          <span class="vocab-card-name">${escapeHtml(label)}</span>
          <span class="badge badge-${mode}">${mode}</span>
          <span class="badge badge-inactive">${approvedValues.length} approved${proposedValues.length ? ` · ${proposedValues.length} proposed` : ''}</span>
          ${listData.reviewBy ? `<span style="font-size:0.75rem;color:var(--text-muted)">Review by ${escapeHtml(listData.reviewBy)}</span>` : ''}
        </div>
        ${values.length ? `
          <div class="vocab-card-values">
            ${values.map(v => `
              <span class="vocab-value-chip ${v.status === 'proposed' ? 'status-proposed' : ''}" title="${escapeHtml(v.description || v.notes || '')}">
                ${escapeHtml(v.name || v.id || '')}
              </span>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `;
  }).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup('Home', 'home', 'Vocabulary Lists', `${listNames.length} governed list${listNames.length === 1 ? '' : 's'} configured`)}
      <div class="vocab-list">
        ${vocabCards || '<p class="empty-state">No vocabulary lists declared in workspace.yaml yet.</p>'}
      </div>
    </div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
}

// ── Taxonomies / Business Pillars view ──────────────────────────────
function renderTaxonomiesView() {
  currentMode = 'taxonomies';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForTaxonomiesView();
  renderSidebarContent('');

  const pillars = (browserData.businessTaxonomy?.pillars || []);

  const pillarCards = pillars.map(pillar => `
    <div class="taxonomy-card">
      <p class="taxonomy-card-name">${escapeHtml(pillar.name || pillar.id || '')}</p>
      ${pillar.description ? `<p class="taxonomy-card-desc">${escapeHtml(pillar.description)}</p>` : ''}
    </div>
  `).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup('Home', 'home', 'Business Taxonomy', `${pillars.length} pillar${pillars.length === 1 ? '' : 's'} defined`)}
      <div class="taxonomy-grid">
        ${pillarCards || '<p class="empty-state">No business taxonomy pillars declared in workspace.yaml yet.</p>'}
      </div>
    </div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
}

// ── Technology Lifecycle view (domain → capability → tech) ──────────
function renderTechnologiesView() {
  currentMode = 'technologies';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForTechnologiesView();
  renderSidebarContent('');

  const groups = acceptableUseGroups(); // already groups by domain→capability
  const lifecycleColors = browserData.lifecycleColors || {};

  const domainSections = groups.map((group, gi) => {
    const domainId = `tech-domain-${gi}`;
    const capRows = [];
    // Group rows by capability
    const capMap = new Map();
    group.rows.forEach(row => {
      const capKey = row.capability?.uid || row.capability?.id || String(gi);
      if (!capMap.has(capKey)) capMap.set(capKey, { capability: row.capability, techs: [] });
      capMap.get(capKey).techs.push(row);
    });
    capMap.forEach(({ capability, techs }) => {
      // Sort by lifecycle
      const order = ['preferred','existing-only','candidate','deprecated','retired','unknown'];
      techs.sort((a, b) => {
        const ai = order.indexOf(a.implementation?.lifecycleStatus || 'unknown');
        const bi = order.indexOf(b.implementation?.lifecycleStatus || 'unknown');
        return ai - bi;
      });
      const techRows = techs.map(row => {
        const tech = row.technology;
        const status = row.implementation?.lifecycleStatus || tech?.lifecycleStatus || 'unknown';
        const color = lifecycleColors[status] ? `#${lifecycleColors[status]}` : '#7a6e60';
        return `
          <div class="tech-component-row">
            <span class="tech-lifecycle-dot" style="background:${color}" title="${escapeHtml(status)}"></span>
            ${tech ? `<span class="ard-link tech-component-name" data-object-link="${escapeHtml(tech.uid || '')}">${escapeHtml(tech.name || tech.uid || '')}</span>`
                   : `<span class="tech-component-name">${escapeHtml(row.implementation?.ref || '')}</span>`}
            <span class="badge badge-inactive" style="font-size:0.7rem">${escapeHtml(status)}</span>
          </div>
        `;
      }).join('');
      capRows.push(`
        <div class="tech-capability-group">
          <p class="tech-capability-label">${escapeHtml(capability?.name || 'Unassigned')}</p>
          ${techRows}
        </div>
      `);
    });

    const totalTechs = group.rows.length;
    return `
      <div class="tech-domain-section">
        <button class="tech-domain-header" data-domain-toggle="${domainId}">
          <span>${escapeHtml(group.domain?.name || 'Unassigned Domain')}</span>
          <span class="badge badge-inactive">${totalTechs} component${totalTechs === 1 ? '' : 's'}</span>
        </button>
        <div class="tech-domain-body" id="${domainId}" style="display:none">
          ${capRows.join('') || '<p class="empty-state">No technology components mapped.</p>'}
        </div>
      </div>
    `;
  }).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup('Home', 'home', 'Technology Lifecycle', 'Browse technology components by domain, capability, and lifecycle status')}
      <div class="tech-domain-list">
        ${domainSections || '<p class="empty-state">No technology components or domain mappings found.</p>'}
      </div>
    </div>
  `;

  pageRoot.querySelectorAll('[data-domain-toggle]').forEach(btn => {
    btn.addEventListener('click', () => {
      const body = document.getElementById(btn.dataset.domainToggle);
      if (body) body.style.display = body.style.display === 'none' ? '' : 'none';
    });
  });
  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
}

// ── Deployment Targets view — SDPs grouped by target ────────────────
// ── Deployment Targets view helpers ────────────────────────────────────────

function _dtInferProvider(s) {
  if (!s) return 'unknown';
  const u = s.toUpperCase();
  if (/\bAWS\b|AMAZON|EC2\b|EKS\b|ECS\b|LAMBDA|SAGEMAKER|\bS3\b/.test(u)) return 'aws';
  if (/\bGCP\b|GOOGLE.?CLOUD|GKE\b|BIGQUERY|CLOUD.?RUN/.test(u)) return 'gcp';
  if (/\bAZURE\b|MICROSOFT|AKS\b/.test(u)) return 'azure';
  if (/CLOUDFLARE/.test(u)) return 'cloudflare';
  if (/SNOWFLAKE|SALESFORCE|SERVICENOW|OKTA|WORKDAY|\bSAAS\b/.test(u)) return 'saas';
  if (/COLOC|EQUINIX|DATA.?CENTER|DATACENTER/.test(u)) return 'colocation';
  if (/ON.?PREM|MAINFRAME|OPENSTACK/.test(u)) return 'onprem';
  if (/\bCUSTOMER\b/.test(u)) return 'customer';
  return 'unknown';
}

function _dtBuildVM() {
  const vocabTargets = (browserData.vocabulary?.deploymentTargets?.values || []);
  const sdps = (browserData.objects || []).filter(o => o.type === 'software_deployment_pattern');

  // target-id → [ {id, name, pillar} ]
  const targetToSdps = new Map();
  sdps.forEach(sdp => {
    const seen = new Set();
    (sdp.serviceGroups || []).forEach(sg => {
      const tid = sg.deploymentTarget;
      if (!tid || seen.has(tid)) return;
      seen.add(tid);
      if (!targetToSdps.has(tid)) targetToSdps.set(tid, []);
      targetToSdps.get(tid).push({ id: sdp.uid, name: sdp.name || sdp.uid, pillar: sdp.pillar || '' });
    });
  });

  const out = [];
  const seenIds = new Set();

  vocabTargets.forEach(v => {
    seenIds.add(v.id);
    const sdpList = targetToSdps.get(v.id) || [];
    const rawStatus = v.status || 'approved';
    const status = sdpList.length === 0 ? 'unused' : rawStatus;
    out.push({
      id: v.id, name: v.name || v.id,
      provider: v.provider || _dtInferProvider(v.name || v.id),
      type: v.type || null, status,
      lat: v.lat != null ? v.lat : null,
      lon: v.lon != null ? v.lon : null,
      region: v.region || null, notes: v.notes || null,
      sdps: sdpList,
    });
  });

  // ad-hoc: referenced in SDPs but absent from vocabulary
  targetToSdps.forEach((sdpList, tid) => {
    if (seenIds.has(tid)) return;
    out.push({
      id: tid, name: tid,
      provider: _dtInferProvider(tid),
      type: null, status: 'ad-hoc',
      lat: null, lon: null, region: null, notes: null,
      sdps: sdpList,
    });
  });

  return out;
}

function _dtBuildClusters(targets, projection) {
  const projected = targets.map(t => {
    const xy = projection([t.lon, t.lat]);
    if (!xy || !isFinite(xy[0]) || !isFinite(xy[1])) return null;
    return { ...t, x: xy[0], y: xy[1] };
  }).filter(Boolean);

  const RAD = 18;
  const result = [];
  projected.forEach(t => {
    const existing = result.find(c => Math.hypot(c.x - t.x, c.y - t.y) < RAD);
    if (existing) {
      existing.targets.push(t);
      const n = existing.targets.length;
      existing.x = (existing.x * (n - 1) + t.x) / n;
      existing.y = (existing.y * (n - 1) + t.y) / n;
    } else {
      result.push({ x: t.x, y: t.y, targets: [t] });
    }
  });
  return result;
}

function _dtFilteredTargets() {
  if (!_dtVM) return [];
  const q = _dtQuery.trim().toLowerCase();
  return _dtVM.filter(t => {
    if (_dtStatusFilter !== 'all' && t.status !== _dtStatusFilter) return false;
    if (_dtTypeFilter !== 'all' && t.type !== _dtTypeFilter) return false;
    if (_dtProviderFilter && !_dtProviderFilter.has(t.provider)) return false;
    if (q && !t.name.toLowerCase().includes(q) && !t.id.toLowerCase().includes(q) && !(t.region || '').toLowerCase().includes(q)) return false;
    return true;
  });
}

function _dtLoadWorld() {
  if (_dtWorldData) return Promise.resolve(_dtWorldData);
  if (_dtWorldPromise) return _dtWorldPromise;

  // Return cached topojson from sessionStorage if available (avoids refetch
  // on every in-session navigation to the Deployment Targets view).
  const CACHE_KEY = 'draft-world-atlas-v2';
  let cachedJson = null;
  try { cachedJson = sessionStorage.getItem(CACHE_KEY); } catch (_) {}
  if (cachedJson) {
    try {
      const world = JSON.parse(cachedJson);
      _dtWorldData = topojson.feature(world, world.objects.countries);
      return (_dtWorldPromise = Promise.resolve(_dtWorldData));
    } catch (_) {
      try { sessionStorage.removeItem(CACHE_KEY); } catch (_2) {}
    }
  }

  const local = 'assets/world-atlas/countries-110m.json';
  const cdn = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json';
  _dtWorldPromise = fetch(local)
    .catch(() => fetch(cdn))
    .then(r => r.json())
    .then(world => {
      try { sessionStorage.setItem(CACHE_KEY, JSON.stringify(world)); } catch (_) {}
      _dtWorldData = topojson.feature(world, world.objects.countries);
      return _dtWorldData;
    });
  return _dtWorldPromise;
}

function _dtShowTooltip(e, cluster, container) {
  const tt = container.querySelector('#dt-map-tooltip');
  if (!tt) return;
  const rect = container.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = cluster.y;
  const sdpCount = cluster.targets.reduce((s, t) => s + t.sdps.length, 0);
  let html;
  if (cluster.targets.length === 1) {
    const t = cluster.targets[0];
    html = `<div class="tt-name">${escapeHtml(t.name)}</div>` +
      `<div class="tt-meta">${t.region ? escapeHtml(t.region) + ' · ' : ''}${sdpCount} SDP${sdpCount === 1 ? '' : 's'}</div>`;
  } else {
    html = `<div class="tt-name">${cluster.targets.length} targets here</div>` +
      `<div class="tt-meta">${cluster.targets.map(t => escapeHtml(t.name)).join(' · ')}</div>`;
  }
  tt.innerHTML = html;
  tt.style.display = '';
  tt.style.left = x + 'px';
  tt.style.top = y + 'px';
}

function _dtDrawMap() {
  const container = document.getElementById('dt-map-container');
  if (!container) return;

  const w = Math.max(600, container.clientWidth || 900);
  const h = Math.max(380, Math.min(640, Math.round(w * 0.5)));
  _dtMapSize = { w, h };

  if (!_dtWorldData || typeof d3 === 'undefined' || typeof topojson === 'undefined') {
    container.innerHTML = `<div class="dt-map-loading">Loading world map…</div>`;
    return;
  }

  const preset = DT_MAP_PRESETS[_dtMapPreset] || DT_MAP_PRESETS['world'];
  const projection = preset.buildProjection(w, h);

  const pathGen = d3.geoPath(projection);
  const graticule = d3.geoGraticule().step(preset.graticuleStep)();
  const spherePath = pathGen({ type: 'Sphere' }) || '';
  const graticulePath = pathGen(graticule) || '';

  const countryPaths = _dtWorldData.features.map(feat => {
    const d = pathGen(feat);
    return d ? `<path class="map-land" d="${d}"/>` : '';
  }).join('');

  // Map shows all geo targets, filtered only by provider toggle
  const allGeo = (_dtVM || []).filter(t => t.lat != null && t.lon != null);
  const mapTargets = _dtProviderFilter ? allGeo.filter(t => _dtProviderFilter.has(t.provider)) : allGeo;
  const clusters = _dtBuildClusters(mapTargets, projection);

  // Only render clusters whose projected position falls within the viewport (± 20 px margin).
  const visibleClusters = clusters.filter(c => c.x >= -20 && c.x <= w + 20 && c.y >= -20 && c.y <= h + 20);

  const markerSvg = visibleClusters.map((c, i) => {
    const isActive = c.targets.some(t => t.id === _dtActiveId);
    const dimmed = _dtActiveId != null && !isActive;
    const prov = c.targets[0].provider || 'unknown';
    const color = DT_PROVIDER_COLORS[prov] || 'var(--accent)';
    const count = c.targets.length;
    const r = count > 1 ? 11 : 7;
    const cls = ['dt-marker', isActive && 'is-active', dimmed && 'is-dimmed'].filter(Boolean).join(' ');
    return `<g class="${cls}" data-dt-ci="${i}" style="color:${color};cursor:pointer" transform="translate(${c.x.toFixed(1)},${c.y.toFixed(1)})">` +
      `<circle class="dt-marker-halo" r="${r + 8}"/>` +
      `<circle class="dt-marker-core" r="${r}"/>` +
      (count > 1 ? `<text class="dt-marker-count">${count}</text>` : '') +
      `</g>`;
  }).join('');

  container.innerHTML =
    `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet" style="display:block;width:100%;height:auto">` +
    `<defs><clipPath id="dt-sphere-clip"><path d="${spherePath}"/></clipPath></defs>` +
    `<path class="map-sphere" d="${spherePath}"/>` +
    `<g clip-path="url(#dt-sphere-clip)"><path class="map-graticule" d="${graticulePath}"/>` +
    countryPaths + `</g>` +
    `<g>${markerSvg}</g>` +
    `</svg>` +
    `<div id="dt-map-tooltip" class="dt-map-tooltip" style="display:none;position:absolute;pointer-events:none"></div>`;

  container.querySelectorAll('.dt-marker').forEach((el, i) => {
    const c = visibleClusters[i];
    if (!c) return;
    el.addEventListener('mouseenter', e => _dtShowTooltip(e, c, container));
    el.addEventListener('mousemove',  e => _dtShowTooltip(e, c, container));
    el.addEventListener('mouseleave', () => {
      const tt = container.querySelector('#dt-map-tooltip');
      if (tt) tt.style.display = 'none';
    });
    el.addEventListener('click', () => {
      if (c.targets.length === 1) {
        _dtOpenDrawer(c.targets[0].id);
      } else {
        const idx = c.targets.findIndex(t => t.id === _dtActiveId);
        const next = c.targets[(idx + 1) % c.targets.length];
        _dtOpenDrawer(next.id);
      }
    });
  });
}

function _dtProviderColor(id) {
  return DT_PROVIDER_COLORS[id] || DT_PROVIDER_COLORS['unknown'];
}

function _dtStatusTagClass(status) {
  switch (status) {
    case 'approved': return 'dt-tag dt-tag-approved';
    case 'proposed': return 'dt-tag dt-tag-proposed';
    case 'ad-hoc':   return 'dt-tag dt-tag-ad-hoc';
    case 'unused':   return 'dt-tag dt-tag-unused';
    default:         return 'dt-tag';
  }
}

function _dtCardMarkup(t) {
  const color = _dtProviderColor(t.provider);
  const providerMeta = DT_PROVIDERS.find(p => p.id === t.provider);
  const providerName = providerMeta ? providerMeta.name : t.provider;
  const typeLabel = DT_TYPE_LABELS[t.type] || t.type || '';
  const isActive = t.id === _dtActiveId;

  const sdpSection = t.sdps.length > 0
    ? `<div class="dt-card-sdps"><div class="dt-card-sdps-label">Software Deployment Patterns</div>` +
      `<div class="dt-card-sdps-list">${t.sdps.map(s => `<span class="dt-sdp-pill">${escapeHtml(s.name)}</span>`).join('')}</div></div>`
    : `<div class="dt-card-sdps"><div class="dt-card-sdps-empty">No SDPs reference this target</div></div>`;

  return `<div class="dt-card${isActive ? ' is-active' : ''}" data-dt-id="${escapeHtml(t.id)}" data-provider="${escapeHtml(t.provider)}">` +
    `<div class="dt-card-top"><div><div class="dt-card-name">${escapeHtml(t.name)}</div>` +
    `<div class="dt-card-id">${escapeHtml(t.id)}</div></div></div>` +
    (t.region ? `<div class="dt-card-region"><span class="pin"></span>${escapeHtml(t.region)}</div>` : '') +
    `<div class="dt-card-tags">` +
    `<span class="dt-tag" style="color:${color}"><span class="swatch" style="background:${color}"></span>${escapeHtml(providerName)}</span>` +
    (typeLabel ? `<span class="dt-tag dt-tag-type">${escapeHtml(typeLabel)}</span>` : '') +
    `<span class="${_dtStatusTagClass(t.status)}">${escapeHtml(t.status)}</span>` +
    `</div>${sdpSection}</div>`;
}

function _dtSectionMarkup(provider, targets) {
  if (!targets.length) return '';
  const p = DT_PROVIDERS.find(pr => pr.id === provider);
  const provName = p ? p.name : provider;
  const color = _dtProviderColor(provider);
  const sdpCount = [...new Set(targets.flatMap(t => t.sdps.map(s => s.id)))].length;
  return `<div class="dt-provider-section" data-provider="${escapeHtml(provider)}">` +
    `<div class="dt-section-head">` +
    `<div class="dt-section-title"><span class="dt-section-dot" style="color:${color}"></span><h2>${escapeHtml(provName)}</h2></div>` +
    `<span class="dt-section-meta">${targets.length} target${targets.length === 1 ? '' : 's'} · ${sdpCount} SDP${sdpCount === 1 ? '' : 's'}</span>` +
    `</div><div class="dt-grid">${targets.map(t => _dtCardMarkup(t)).join('')}</div></div>`;
}

function _dtDrawerMarkup(t) {
  if (!t) return '';
  const color = _dtProviderColor(t.provider);
  const providerMeta = DT_PROVIDERS.find(p => p.id === t.provider);
  const providerName = providerMeta ? providerMeta.name : t.provider;
  const typeLabel = DT_TYPE_LABELS[t.type] || t.type || '—';

  const coordRow = (t.lat != null && t.lon != null)
    ? `<div class="dt-drawer-row"><div class="k">Coordinates</div><div class="v">${t.lat.toFixed(3)}°, ${t.lon.toFixed(3)}°</div></div>`
    : '';
  const notesRow = t.notes
    ? `<div class="dt-drawer-row"><div class="k">Notes</div><div class="v">${escapeHtml(t.notes)}</div></div>`
    : '';
  const sdpList = t.sdps.length > 0
    ? `<div class="dt-drawer-row"><div class="k">Software Deployment Patterns</div><div class="dt-drawer-sdp-list">` +
      t.sdps.map(s =>
        `<div class="dt-drawer-sdp" data-dt-sdp="${escapeHtml(s.id)}">` +
        `<div><div class="name">${escapeHtml(s.name)}</div>${s.pillar ? `<div class="pillar">${escapeHtml(s.pillar)}</div>` : ''}</div>` +
        `<span class="arrow">→</span></div>`
      ).join('') +
      `</div></div>`
    : `<div class="dt-drawer-row"><div class="k">Software Deployment Patterns</div><div class="v" style="color:var(--muted)">None — target is unused</div></div>`;

  // TODO(v2): per-target detail route #view=deployment-target&id=<id>
  return `<div class="dt-drawer-head">` +
    `<button class="dt-drawer-close" id="dt-drawer-close" aria-label="Close">✕</button>` +
    `<div class="dt-drawer-eyebrow" style="color:${color}"><span class="dot" style="border-color:${color}"></span>${escapeHtml(providerName)}</div>` +
    `<h3>${escapeHtml(t.name)}</h3><div class="dt-drawer-uid">${escapeHtml(t.id)}</div></div>` +
    `<div class="dt-drawer-body">` +
    `<div class="dt-drawer-row"><div class="k">Type</div><div class="v">${escapeHtml(typeLabel)}</div></div>` +
    `<div class="dt-drawer-row"><div class="k">Status</div><div class="v"><span class="${_dtStatusTagClass(t.status)}">${escapeHtml(t.status)}</span></div></div>` +
    (t.region ? `<div class="dt-drawer-row"><div class="k">Region / Location</div><div class="v">${escapeHtml(t.region)}</div></div>` : '') +
    coordRow + notesRow + sdpList +
    `</div>`;
}

function _dtOpenDrawer(id) {
  _dtActiveId = id;
  const t = (_dtVM || []).find(v => v.id === id);
  const drawer = document.getElementById('dt-drawer');
  const overlay = document.getElementById('dt-drawer-overlay');
  if (!drawer || !t) return;
  drawer.innerHTML = _dtDrawerMarkup(t);
  requestAnimationFrame(() => {
    drawer.classList.add('open');
    if (overlay) overlay.classList.add('open');
  });
  document.querySelectorAll('.dt-card').forEach(el => {
    el.classList.toggle('is-active', el.dataset.dtId === id);
  });
  _dtDrawMap();
  if (_dtEscHandler) document.removeEventListener('keydown', _dtEscHandler);
  _dtEscHandler = e => { if (e.key === 'Escape') _dtCloseDrawer(); };
  document.addEventListener('keydown', _dtEscHandler);
  const closeBtn = drawer.querySelector('#dt-drawer-close');
  if (closeBtn) closeBtn.addEventListener('click', _dtCloseDrawer);
  drawer.querySelectorAll('[data-dt-sdp]').forEach(el => {
    el.addEventListener('click', () => {
      const sdpId = el.dataset.dtSdp;
      if (sdpId) { _dtCloseDrawer(); renderDetailView(sdpId); }
    });
  });
}

function _dtCloseDrawer() {
  _dtActiveId = null;
  const drawer = document.getElementById('dt-drawer');
  const overlay = document.getElementById('dt-drawer-overlay');
  if (drawer) drawer.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
  document.querySelectorAll('.dt-card').forEach(el => el.classList.remove('is-active'));
  _dtDrawMap();
  if (_dtEscHandler) { document.removeEventListener('keydown', _dtEscHandler); _dtEscHandler = null; }
}

function _dtSectionsMarkup() {
  const filtered = _dtFilteredTargets();
  if (!filtered.length) return `<div class="dt-empty-block">No targets match the current filters.</div>`;
  const byProvider = new Map(DT_PROVIDERS.map(p => [p.id, []]));
  filtered.forEach(t => {
    const list = byProvider.get(t.provider) || byProvider.get('unknown');
    list.push(t);
  });
  return DT_PROVIDERS
    .filter(p => (byProvider.get(p.id) || []).length > 0)
    .map(p => _dtSectionMarkup(p.id, byProvider.get(p.id)))
    .join('');
}

function _dtSummaryGridMarkup() {
  const all = _dtVM || [];
  const approved = all.filter(t => t.status === 'approved').length;
  const proposed = all.filter(t => t.status === 'proposed').length;
  const adHoc    = all.filter(t => t.status === 'ad-hoc').length;
  const unused   = all.filter(t => t.status === 'unused').length;
  const sdpCount = (browserData.objects || []).filter(o => o.type === 'software_deployment_pattern').length;

  const provCounts = new Map();
  all.forEach(t => provCounts.set(t.provider, (provCounts.get(t.provider) || 0) + 1));
  const maxCount = Math.max(...provCounts.values(), 1);

  const barRows = DT_PROVIDERS
    .filter(p => provCounts.has(p.id))
    .sort((a, b) => (provCounts.get(b.id) || 0) - (provCounts.get(a.id) || 0))
    .map(p => {
      const n = provCounts.get(p.id) || 0;
      const pct = Math.round((n / maxCount) * 100);
      const color = _dtProviderColor(p.id);
      return `<div class="dt-bar-row">` +
        `<div class="dt-bar-label"><span class="swatch" style="background:${color}"></span>${escapeHtml(p.name)}</div>` +
        `<div class="dt-bar-track"><div class="dt-bar-fill" style="width:${pct}%;background:${color}"></div></div>` +
        `<div class="dt-bar-count">${n}</div></div>`;
    }).join('');

  return `<div class="dt-summary-grid">` +
    `<div class="dt-provider-chart"><h3>By Provider</h3><div class="sub">Distribution across all ${all.length} targets</div>` +
    (barRows || `<p style="color:var(--muted);font-size:13px">No targets yet</p>`) + `</div>` +
    `<div class="dt-summary-card"><h3>Vocabulary Health</h3><div class="sub">Based on ${all.length} total targets</div>` +
    `<div class="dt-summary-stat"><span class="k">Approved</span><span class="v ok">${approved}</span></div>` +
    `<div class="dt-summary-stat"><span class="k">Proposed</span><span class="v">${proposed}</span></div>` +
    `<div class="dt-summary-stat"><span class="k">Ad-hoc</span><span class="v${adHoc > 0 ? ' warn' : ' ok'}">${adHoc}</span></div>` +
    `<div class="dt-summary-stat"><span class="k">Unused</span><span class="v${unused > 0 ? ' warn' : ''}">${unused}</span></div>` +
    `<div class="dt-summary-stat"><span class="k">SDPs covered</span><span class="v">${sdpCount}</span></div>` +
    `</div></div>`;
}

function _dtLegendMarkup() {
  const geoProviders = new Set((_dtVM || []).filter(t => t.lat != null && t.lon != null).map(t => t.provider));
  const items = DT_PROVIDERS.filter(p => geoProviders.has(p.id)).map(p => {
    const color = _dtProviderColor(p.id);
    const active = !_dtProviderFilter || _dtProviderFilter.has(p.id);
    return `<span class="dt-legend-item${active ? '' : ' is-off'}" data-dt-legend="${escapeHtml(p.id)}" style="color:${color}">` +
      `<span class="sw" style="border-color:${color}"></span>${escapeHtml(p.name)}</span>`;
  }).join('');
  if (!items) return '';
  return `<div class="dt-map-legend" id="dt-map-legend"><span class="dt-map-legend-label">Providers</span>${items}</div>`;
}

function _dtTypeChips() {
  const types = [...new Set((_dtVM || []).map(t => t.type).filter(Boolean))].sort();
  return ['all', ...types].map(t => {
    const label = t === 'all' ? 'All types' : (DT_TYPE_LABELS[t] || t);
    return `<button class="dt-chip${_dtTypeFilter === t ? ' active' : ''}" data-dt-type="${escapeHtml(t)}">${escapeHtml(label)}</button>`;
  }).join('');
}

function _dtStatusChips() {
  return DT_STATUS_OPTS.map(o =>
    `<button class="dt-chip${_dtStatusFilter === o.id ? ' active' : ''}" data-dt-status="${escapeHtml(o.id)}">${escapeHtml(o.label)}</button>`
  ).join('');
}

function _dtRerender() {
  const filtered = _dtFilteredTargets();
  const sectionsRoot = document.getElementById('dt-sections-root');
  if (sectionsRoot) sectionsRoot.innerHTML = _dtSectionsMarkup();
  const countEl = document.getElementById('dt-result-count');
  if (countEl) countEl.textContent = `${filtered.length} target${filtered.length === 1 ? '' : 's'}`;
  const typeChipGroup = document.getElementById('dt-type-chips');
  if (typeChipGroup) typeChipGroup.innerHTML = _dtTypeChips();
  const statusChipGroup = document.getElementById('dt-status-chips');
  if (statusChipGroup) statusChipGroup.innerHTML = _dtStatusChips();
  const legendEl = document.getElementById('dt-map-legend');
  if (legendEl) legendEl.outerHTML = _dtLegendMarkup() || '<div id="dt-map-legend"></div>';
  _dtDrawMap();
  attachDtHandlers();
}

function attachDtHandlers() {
  const view = pageRoot.querySelector('.dt-view');
  if (!view) return;
  if (view._dtHandler) view.removeEventListener('click', view._dtHandler);
  if (view._dtInputHandler) view.removeEventListener('input', view._dtInputHandler);

  view._dtHandler = function(e) {
    const card = e.target.closest('.dt-card');
    if (card && card.dataset.dtId) { _dtOpenDrawer(card.dataset.dtId); return; }
    const typeChip = e.target.closest('[data-dt-type]');
    if (typeChip) { _dtTypeFilter = typeChip.dataset.dtType; _dtRerender(); return; }
    const statusChip = e.target.closest('[data-dt-status]');
    if (statusChip) { _dtStatusFilter = statusChip.dataset.dtStatus; _dtRerender(); return; }
    const presetBtn = e.target.closest('[data-dt-preset]');
    if (presetBtn) {
      const pid = presetBtn.dataset.dtPreset;
      if (pid in DT_MAP_PRESETS && pid !== _dtMapPreset) {
        _dtMapPreset = pid;
        // Update active state on buttons
        document.querySelectorAll('[data-dt-preset]').forEach(b => {
          b.classList.toggle('is-active', b.dataset.dtPreset === pid);
        });
        _dtDrawMap();
      }
      return;
    }
    const legendItem = e.target.closest('[data-dt-legend]');
    if (legendItem) {
      const pid = legendItem.dataset.dtLegend;
      if (!_dtProviderFilter) {
        _dtProviderFilter = new Set([pid]);
      } else if (_dtProviderFilter.has(pid) && _dtProviderFilter.size === 1) {
        _dtProviderFilter = null;
      } else if (_dtProviderFilter.has(pid)) {
        _dtProviderFilter = new Set([..._dtProviderFilter].filter(x => x !== pid));
      } else {
        _dtProviderFilter = new Set([..._dtProviderFilter, pid]);
      }
      _dtRerender();
      return;
    }
  };
  view._dtInputHandler = function(e) {
    if (e.target.id === 'dt-search') { _dtQuery = e.target.value; _dtRerender(); }
  };
  view.addEventListener('click', view._dtHandler);
  view.addEventListener('input', view._dtInputHandler);

  const overlay = document.getElementById('dt-drawer-overlay');
  if (overlay && !overlay._dtClose) {
    overlay._dtClose = true;
    overlay.addEventListener('click', _dtCloseDrawer);
  }
}

function renderDeploymentTargetsView() {
  currentMode = 'deployment-targets';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();

  // Cleanup previous DT state
  if (_dtResizeObserver) { _dtResizeObserver.disconnect(); _dtResizeObserver = null; }
  if (_dtEscHandler) { document.removeEventListener('keydown', _dtEscHandler); _dtEscHandler = null; }
  _dtQuery = ''; _dtTypeFilter = 'all'; _dtStatusFilter = 'all';
  _dtProviderFilter = null; _dtActiveId = null;
  _dtMapPreset = (browserData.browserConfig?.defaultMapView in DT_MAP_PRESETS
    ? browserData.browserConfig.defaultMapView
    : 'world');

  syncHashForDeploymentTargetsView();
  renderSidebarContent('');

  _dtVM = _dtBuildVM();
  const all = _dtVM;
  const sdpCount = (browserData.objects || []).filter(o => o.type === 'software_deployment_pattern').length;
  const adHoc = all.filter(t => t.status === 'ad-hoc').length;

  pageRoot.innerHTML = `
    <div class="view-shell dt-view">
      ${topNavMarkup()}
      <div class="dt-page">
        ${subviewHeaderMarkup('Home', 'home', 'Deployment Targets',
          `${all.length} target${all.length === 1 ? '' : 's'} · ${sdpCount} SDP${sdpCount === 1 ? '' : 's'}`)}

        ${adHoc > 0
          ? `<div style="margin:16px 0 0;padding:10px 14px;background:var(--warn-soft);border:1px solid oklch(0.85 0.07 60);border-radius:8px;font-size:12.5px;color:oklch(0.48 0.12 60)">
              <strong>${adHoc} ad-hoc target${adHoc === 1 ? '' : 's'}</strong> referenced in SDPs but not declared in the vocabulary.
              Add them to <code>vocabulary/deployment-targets.yaml</code> to govern them.
             </div>`
          : ''}

        <div class="dt-map-panel">
          <div class="dt-map-panel-head">
            <div>
              <span class="eyebrow">Geographic footprint</span>
              <h2>Deployment map</h2>
            </div>
            <div class="dt-map-presets" id="dt-map-presets">
              ${Object.entries(DT_MAP_PRESETS).map(([id, cfg]) =>
                `<button class="dt-map-preset-btn${_dtMapPreset === id ? ' is-active' : ''}" data-dt-preset="${escapeHtml(id)}">${escapeHtml(cfg.icon)} ${escapeHtml(cfg.label)}</button>`
              ).join('')}
            </div>
          </div>
          <div class="dt-map-container" id="dt-map-container">
            <div class="dt-map-loading">Loading world map…</div>
          </div>
          ${_dtLegendMarkup()}
        </div>

        ${_dtSummaryGridMarkup()}

        <div class="dt-filter-row">
          <div class="dt-search-wrap">
            <span class="dt-search-icon">⌕</span>
            <input id="dt-search" type="text" placeholder="Search targets…" value="${escapeHtml(_dtQuery)}" autocomplete="off">
          </div>
          <span class="dt-filter-label">Type</span>
          <div class="dt-chip-group" id="dt-type-chips">${_dtTypeChips()}</div>
          <span class="dt-filter-label">Status</span>
          <div class="dt-chip-group" id="dt-status-chips">${_dtStatusChips()}</div>
          <span class="dt-result-count" id="dt-result-count">${all.length} target${all.length === 1 ? '' : 's'}</span>
        </div>

        <div id="dt-sections-root">${_dtSectionsMarkup()}</div>
      </div>
    </div>
    <div class="dt-drawer-overlay" id="dt-drawer-overlay"></div>
    <div class="dt-drawer" id="dt-drawer"></div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
  attachDtHandlers();

  if (typeof d3 !== 'undefined' && typeof topojson !== 'undefined') {
    _dtLoadWorld().then(() => {
      _dtDrawMap();
      // Refresh legend now that geo targets are known
      const legendEl = document.getElementById('dt-map-legend');
      if (legendEl) legendEl.outerHTML = _dtLegendMarkup() || '<div id="dt-map-legend"></div>';
      attachDtHandlers();
    }).catch(err => {
      console.warn('World atlas load failed', err);
      const c = document.getElementById('dt-map-container');
      if (c) c.innerHTML = `<div class="dt-map-loading">Map unavailable</div>`;
    });
  }

  const mapContainer = document.getElementById('dt-map-container');
  if (mapContainer && typeof ResizeObserver !== 'undefined') {
    _dtResizeObserver = new ResizeObserver(() => {
      if (document.getElementById('dt-map-container')) _dtDrawMap();
      else { _dtResizeObserver.disconnect(); _dtResizeObserver = null; }
    });
    _dtResizeObserver.observe(mapContainer);
  }
}

// ── Shared team helpers ─────────────────────────────────────────────
const TEAM_TYPES = ['software_deployment_pattern','reference_architecture','runtime_service','data_at_rest_service','edge_gateway_service','product_component','data_component','product_service','host'];
const TEAM_TYPE_LABELS = {
  software_deployment_pattern: 'Deployment Patterns',
  reference_architecture: 'Reference Architectures',
  runtime_service: 'Runtime Services',
  data_at_rest_service: 'Data-at-Rest Services',
  edge_gateway_service: 'Edge / Gateway Services',
  product_component: 'Product Components',
  data_component: 'Data Components',
  product_service: 'Product Services',
  host: 'Hosts',
};
const TEAM_TYPE_ICONS = {
  software_deployment_pattern: '🗺',
  reference_architecture: '📐',
  runtime_service: '⚙️',
  data_at_rest_service: '🗄',
  edge_gateway_service: '🌐',
  product_component: '📦',
  data_component: '🗃',
  product_service: '📦',
  host: '🖥',
};

function buildTeamMap() {
  const teamMap = new Map();
  const typeSet = new Set(TEAM_TYPES);
  (browserData.objects || []).filter(o => typeSet.has(o.type)).forEach(obj => {
    const team = obj.owner?.team || obj.definitionOwner?.team || '(unassigned)';
    if (!teamMap.has(team)) teamMap.set(team, []);
    teamMap.get(team).push(obj);
  });
  return teamMap;
}

function teamDisplayName(teamId) {
  const vocabTeams = browserData.vocabulary?.teams?.values || [];
  const match = vocabTeams.find(t => t.id === teamId);
  return match?.name || teamId;
}

// ── Teams tile view ─────────────────────────────────────────────────
function renderTeamsView() {
  currentMode = 'teams';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForTeamsView();
  renderSidebarContent('');

  const teamMap = buildTeamMap();
  const tiles = [...teamMap.entries()].map(([teamId, objects]) => {
    const label = teamDisplayName(teamId);
    const count = objects.length;
    return `
      <div class="home-tile team-tile" role="button" tabindex="0"
           data-executive-target="team-detail:${escapeHtml(teamId)}">
        <span class="home-tile-icon">👥</span>
        <span class="home-tile-title">${escapeHtml(label)}</span>
        <span class="home-tile-count">${count} object${count === 1 ? '' : 's'}</span>
      </div>
    `;
  }).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup('Home', 'home', 'Teams', `${teamMap.size} team${teamMap.size === 1 ? '' : 's'} with owned objects`)}
      <div class="home-tiles team-tile-grid">
        ${tiles || '<p class="empty-state">No team ownership assigned to any objects yet.</p>'}
      </div>
    </div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
}

// ── Team detail — object type tiles ────────────────────────────────
function renderTeamDetailView(teamId) {
  currentMode = 'team-detail';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForTeamDetailView(teamId);
  renderSidebarContent('');

  const teamMap = buildTeamMap();
  if (!teamMap.has(teamId)) { renderTeamsView(); return; }

  const objects = teamMap.get(teamId);
  const byType = {};
  objects.forEach(obj => {
    if (!byType[obj.type]) byType[obj.type] = [];
    byType[obj.type].push(obj);
  });

  const label = teamDisplayName(teamId);
  const tiles = TEAM_TYPES.filter(t => byType[t]?.length).map(type => {
    const count = byType[type].length;
    return `
      <div class="home-tile team-type-tile" role="button" tabindex="0"
           data-executive-target="team-type:${escapeHtml(teamId)}:${escapeHtml(type)}">
        <span class="home-tile-icon">${TEAM_TYPE_ICONS[type] || '📄'}</span>
        <span class="home-tile-title">${escapeHtml(TEAM_TYPE_LABELS[type] || type)}</span>
        <span class="home-tile-count">${count} object${count === 1 ? '' : 's'}</span>
      </div>
    `;
  }).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup('Teams', 'teams', escapeHtml(label), `${objects.length} owned object${objects.length === 1 ? '' : 's'}`)}
      <div class="home-tiles team-type-grid">
        ${tiles || '<p class="empty-state">No owned objects found for this team.</p>'}
      </div>
    </div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
}

// ── Team type objects — clickable object list for one type ──────────
function renderTeamTypeObjectsView(teamId, objectType) {
  currentMode = 'team-type-objects';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForTeamTypeView(teamId, objectType);
  renderSidebarContent('');

  const teamMap = buildTeamMap();
  if (!teamMap.has(teamId)) { renderTeamsView(); return; }

  const objects = (teamMap.get(teamId) || []).filter(o => o.type === objectType);
  const label = teamDisplayName(teamId);
  const typeLabel = TEAM_TYPE_LABELS[objectType] || objectType;

  const objectLinks = objects.map(obj => `
    <span class="ard-link team-object-link" data-object-link="${escapeHtml(obj.uid || '')}">
      ${escapeHtml(obj.name || obj.uid || '')}
    </span>
  `).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup(escapeHtml(label), `team-detail:${escapeHtml(teamId)}`, escapeHtml(typeLabel), `${objects.length} object${objects.length === 1 ? '' : 's'}`)}
      <div class="team-objects-list">
        ${objectLinks || '<p class="empty-state">No objects found.</p>'}
      </div>
    </div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
}

// ── SDP by Business Pillar — top-level pillar tiles ─────────────────
function renderSdpsByPillarView() {
  currentMode = 'sdps-by-pillar';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForSdpsByPillarView();
  renderSidebarContent('');

  const sdps = (browserData.objects || []).filter(o => o.type === 'software_deployment_pattern');
  const groups = groupSoftwareDeploymentPatternsByPillar(sdps);

  const pillarTiles = groups.map(({ pillar, objects }) => {
    const count = objects.length;
    return `
      <div class="home-tile sdp-pillar-tile" role="button" tabindex="0"
           data-executive-target="pillar-sdps:${escapeHtml(pillar.id)}">
        <span class="home-tile-icon">🏛</span>
        <span class="home-tile-title">${escapeHtml(pillar.name || pillar.id)}</span>
        <span class="home-tile-count">${count} pattern${count === 1 ? '' : 's'}</span>
      </div>
    `;
  }).join('');

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup('Home', 'home', 'Software Deployment Patterns', `Browse by Business Pillar · ${sdps.length} pattern${sdps.length === 1 ? '' : 's'}`)}
      <div class="home-tiles sdp-pillar-grid">
        ${pillarTiles || '<p class="empty-state">No software deployment patterns found.</p>'}
      </div>
    </div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
}

// ── SDP tiles for a single pillar, grouped by lifecycle ─────────────

// Returns HTML sections grouping `sdps` by lifecycleStatus in invest-first order.
function _sdpLifecycleSections(sdps) {
  const LC_CONFIG = [
    { id: 'preferred',     label: 'Preferred',     color: '#2e7d32' },
    { id: 'candidate',     label: 'Candidate',     color: '#f57f17' },
    { id: 'existing-only', label: 'Existing Only', color: '#1565c0' },
    { id: 'deprecated',    label: 'Deprecated',    color: '#6d4c41' },
    { id: 'retired',       label: 'Retired',       color: '#b71c1c' },
  ];
  const byLifecycle = new Map(LC_CONFIG.map(c => [c.id, { config: c, sdps: [] }]));
  const uncategorized = [];

  for (const sdp of sdps) {
    const lc = sdp.lifecycleStatus || '';
    if (byLifecycle.has(lc)) {
      byLifecycle.get(lc).sdps.push(sdp);
    } else {
      uncategorized.push(sdp);
    }
  }
  if (uncategorized.length) {
    byLifecycle.set('unknown', {
      config: { id: 'unknown', label: 'Uncategorized', color: '#7a6e60' },
      sdps: uncategorized,
    });
  }

  return [...byLifecycle.values()]
    .filter(g => g.sdps.length > 0)
    .map(({ config, sdps: groupSdps }) => {
      const tiles = groupSdps.map(sdp => `
        <div class="home-tile sdp-object-tile" role="button" tabindex="0"
             data-object-link="${escapeHtml(sdp.uid || sdp.id || '')}">
          <span class="home-tile-icon">🗺</span>
          <span class="home-tile-title">${escapeHtml(sdp.name || sdp.uid || '')}</span>
          ${sdp.description ? `<span class="home-tile-desc">${escapeHtml(sdp.description)}</span>` : ''}
        </div>
      `).join('');

      return `
        <section class="sdp-lifecycle-section">
          <h3 class="sdp-lifecycle-heading">
            <span class="sdp-lifecycle-dot" style="background:${config.color}"></span>
            ${escapeHtml(config.label)}
            <span class="sdp-lifecycle-count">${groupSdps.length}</span>
          </h3>
          <div class="home-tiles sdp-object-grid">
            ${tiles}
          </div>
        </section>
      `;
    }).join('');
}

function renderPillarSdpsView(pillarId) {
  currentMode = 'pillar-sdps';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForPillarSdpsView(pillarId);
  renderSidebarContent('');

  const sdps = (browserData.objects || []).filter(o => o.type === 'software_deployment_pattern');
  const groups = groupSoftwareDeploymentPatternsByPillar(sdps);
  const group = groups.find(g => g.pillar.id === pillarId);
  if (!group) {
    renderSdpsByPillarView();
    return;
  }

  const { pillar, objects } = group;
  const sections = _sdpLifecycleSections(objects);

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${subviewHeaderMarkup('Deployment Patterns', 'sdps-by-pillar', escapeHtml(pillar.name || pillar.id), `${objects.length} pattern${objects.length === 1 ? '' : 's'}`)}
      <div class="sdp-lifecycle-sections">
        ${sections || '<p class="empty-state">No patterns in this pillar.</p>'}
      </div>
    </div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
}

function renderExecutiveView() {
  currentMode = 'executive';
  currentDetailId = null;
  executiveDrilldown = null;
  currentSubViewId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForExecutiveView();
  const stats = executiveStats();
  renderSidebarContent(executiveSidebarMarkup(stats));

  // Alert banners
  const _openRisks = (browserData.objects || []).filter(o => o.type === 'decision_record' && o.category === 'risk' && (o.status === 'open' || o.status === 'accepted'));
  const _retiredInUse = (browserData.objects || []).filter(o => o.lifecycleStatus === 'retired' && (o.referencedBy || []).length > 0);
  const _stubs = (browserData.objects || []).filter(o => o.catalogStatus === 'stub');
  const _alerts = [];
  if (_openRisks.length) _alerts.push({ severity: 'critical', label: `${_openRisks.length} open risk${_openRisks.length === 1 ? '' : 's'}`, detail: 'Decision records with open or accepted-but-unmitigated risk', target: 'risks' });
  if (_retiredInUse.length) _alerts.push({ severity: 'warning', label: `${_retiredInUse.length} retired component${_retiredInUse.length === 1 ? '' : 's'} still referenced`, detail: 'Lifecycle = retired but inbound references exist', target: 'retired' });
  if (_stubs.length) _alerts.push({ severity: 'info', label: `${_stubs.length} stub${_stubs.length === 1 ? '' : 's'} awaiting authoring`, detail: 'Catalog status = stub', target: 'drafting-table' });
  const _alertSeverity = sev => ({ critical: '#b93a3a', warning: '#c47a14', info: '#2a6fdb' }[sev] || '#7a6e60');
  const _alertBanner = _alerts.length ? `
    <section class="dashboard-alerts" aria-label="Catalog posture alerts">
      ${_alerts.map(a => `
        <button class="alert-card alert-${a.severity}" data-executive-target="${escapeHtml(a.target)}" style="border-left:4px solid ${_alertSeverity(a.severity)};">
          <span class="alert-sev" style="color:${_alertSeverity(a.severity)};">${a.severity.toUpperCase()}</span>
          <span class="alert-label">${escapeHtml(a.label)}</span>
          <span class="alert-detail">${escapeHtml(a.detail)}</span>
        </button>
      `).join('')}
    </section>
  ` : '';

  // Tile data
  const vocab = browserData.vocabulary || {};
  const vocabCount = Object.keys(vocab).length;
  const pillarCount = (browserData.businessTaxonomy?.pillars || []).length;
  const rgGroups = browserData.requirements?.groups || [];
  const companyRgGroups = rgGroups.filter(g => !isBuiltInGroup(g) && !isThirdPartyGroup(g));
  const thirdPartyRgGroups = rgGroups.filter(g => isThirdPartyGroup(g));
  const builtInRgGroups = rgGroups.filter(g => isBuiltInGroup(g));
  const allNonDraftGroups = [...companyRgGroups, ...thirdPartyRgGroups];
  const activeRgCount = allNonDraftGroups.filter(g => g.active || g.activation === 'always').length;
  const activeBuiltInCount = builtInRgGroups.filter(g => g.active || g.activation === 'always').length;
  const sdps = (browserData.objects || []).filter(o => o.type === 'software_deployment_pattern');
  const targetSet = new Set();
  sdps.forEach(sdp => (sdp.serviceGroups || []).forEach(sg => { if (sg.deploymentTarget) targetSet.add(sg.deploymentTarget); }));
  const teamSet = new Set();
  const TEAM_TYPES_EXEC = new Set(['software_deployment_pattern','reference_architecture','runtime_service','data_at_rest_service','edge_gateway_service','product_component','data_component','product_service','host']);
  (browserData.objects || []).filter(o => TEAM_TYPES_EXEC.has(o.type)).forEach(obj => {
    const t = obj.owner?.team || obj.definitionOwner?.team;
    if (t) teamSet.add(t);
  });
  const techCount = (browserData.objects || []).filter(o => o.type === 'technology_component').length;

  const makeTile = (icon, title, desc, count, target) => `
    <button class="home-tile" data-executive-target="${escapeHtml(target)}">
      <span class="home-tile-icon">${icon}</span>
      <div class="home-tile-body">
        <div class="home-tile-title">
          ${escapeHtml(title)}
          ${count !== null ? `<span class="home-tile-count">${formatNumber(count)}</span>` : ''}
        </div>
        <p class="home-tile-desc">${escapeHtml(desc)}</p>
      </div>
    </button>
  `;

  const draftingTiles = [
    makeTile('🗺', 'Software Deployment Patterns', 'Architecture patterns showing how software is deployed across targets', sdps.length, 'deployments'),
    makeTile('🔬', 'Technology Lifecycle', 'Browse technology components by domain, capability, and lifecycle status', techCount, 'technologies'),
    makeTile('📍', 'Deployment Targets', 'See deployment patterns grouped by their execution boundaries', targetSet.size, 'deployment-targets'),
    makeTile('👥', 'Teams', 'View architecture objects grouped by owning team', teamSet.size, 'teams'),
  ];

  const configTiles = [
    makeTile('✅', 'Requirement Groups', `${activeRgCount} of ${allNonDraftGroups.length} active${thirdPartyRgGroups.length ? ` · ${thirdPartyRgGroups.length} compliance pack${thirdPartyRgGroups.length === 1 ? '' : 's'}` : ''}`, allNonDraftGroups.length, 'requirement-groups'),
    makeTile('📋', 'Vocabulary Lists', 'Governed choices for deployment targets, protocols, zones, and more', vocabCount, 'vocabularies'),
    makeTile('🏛', 'Business Taxonomy', 'Business pillars and strategy domains', pillarCount, 'taxonomies'),
    makeTile('🔧', 'Built-In DRAFT Configurations', `Framework-provided checklists and operational conformance checks · ${activeBuiltInCount} active`, builtInRgGroups.length, 'built-in-configs'),
  ];

  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      ${_alertBanner}
      <div class="home-header">
        <img class="home-header-logo" src="${escapeHtml(browserData.logoDataUri || 'draft-logo.png')}" alt="${escapeHtml(browserData.catalogName || 'DRAFT')}">
        <h1>Welcome to ${escapeHtml(browserData.catalogName || 'DRAFT')} Drafting Table</h1>
      </div>
      <div class="home-columns">
        <section>
          <p class="home-column-label">Drafting Table</p>
          <div class="home-tiles">${draftingTiles.join('')}</div>
        </section>
        <section>
          <p class="home-column-label">Draftsman's Office</p>
          <div class="home-tiles">${configTiles.join('')}</div>
        </section>
      </div>
    </div>
  `;

  attachExecutiveHandlers();
  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
}

const OBJECT_TYPE_GUIDE = {
  deployable: [
    {
      type: 'technology_component',
      label: 'Technology Component',
      purpose: 'A discrete vendor product, agent, operating system, platform, or software package with a specific product/version lifecycle.',
      deployableRole: 'Deployed as an ingredient inside Hosts and service objects.'
    },
    {
      type: 'host',
      label: 'Host',
      purpose: 'An operational platform that combines an operating system, compute platform, and required host capabilities.',
      deployableRole: 'Deploys the runtime substrate for self-managed services.'
    },
    {
      type: 'runtime_service',
      label: 'Runtime Service',
      purpose: 'A reusable behavioral service such as web, app, cache, worker, messaging, or serverless runtime.',
      deployableRole: 'Deploys runtime behavior on a host or through PaaS, SaaS, or appliance delivery.'
    },
    {
      type: 'data_at_rest_service',
      label: 'Data-at-Rest Service',
      purpose: 'A reusable service for durable data such as database, file, object, search, analytics, or storage.',
      deployableRole: 'Deploys persistence behavior on a host or through PaaS, SaaS, or appliance delivery.'
    },
    {
      type: 'edge_gateway_service',
      label: 'Edge/Gateway Service',
      purpose: 'A reusable boundary service such as WAF, firewall, API gateway, load balancer, ingress, or proxy.',
      deployableRole: 'Deploys traffic control behavior at a product or network boundary.'
    },
    {
      type: 'product_component',
      label: 'Product Component',
      purpose: 'A first-party code repository or deployable unit owned by a product team.',
      deployableRole: 'Deploys company-authored application behavior on a Runtime Service.'
    },
    {
      type: 'data_component',
      label: 'Data Component',
      purpose: 'A first-party data artifact such as a schema, migration set, or data pipeline owned by a product team.',
      deployableRole: 'Deploys company-owned data artifacts on a Data-at-Rest Service.'
    },
    {
      type: 'software_deployment_pattern',
      label: 'Software Deployment Pattern',
      purpose: 'The intended assembly of deployable objects for a product or product capability.',
      deployableRole: 'Defines the deployable package shape that automation can target.'
    }
  ],
  nonDeployable: [
    { type: 'capability', label: 'Capability', purpose: 'Names an ability required by architecture and records company-approved Technology Components for it.' },
    { type: 'requirement_group', label: 'Requirement Group', purpose: 'Groups requirements used by the Draftsman during interviews and by validation after authoring.' },
    { type: 'domain', label: 'Domain', purpose: 'Groups capabilities into a planning area such as compute, observability, identity, or data.' },
    { type: 'reference_architecture', label: 'Reference Architecture', purpose: 'Documents a reusable deployment approach that Software Deployment Patterns may follow.' },
    { type: 'decision_record', label: 'Decision Record', purpose: 'Records an architecture decision, risk, exception, or rationale.' },
    { type: 'drafting_session', label: 'Drafting Session', purpose: 'Stores interview memory, assumptions, unresolved questions, and generated work while drafting.' },
    { type: 'object_patch', label: 'Object Patch', purpose: 'A workspace overlay that changes selected fields on a framework-owned object without copying the full object.' },
    { type: 'environment_tier', label: 'Environment Tier', purpose: 'Defines a company-standard deployment environment class (e.g. dev, staging, production) with availability posture, cost posture, compliance scope, and the parameter surface the CI/CD pipeline must supply.' }
  ]
};

function objectTypeCount(type) {
  return allObjects.filter(object => object.type === type).length;
}

function objectTypeRowsMarkup(rows, deployable = false) {
  return rows.map(row => `
    <tr>
      <td><strong>${escapeHtml(row.label)}</strong><div class="object-id">${escapeHtml(row.type)}</div></td>
      <td>${escapeHtml(row.purpose)}</td>
      ${deployable ? `<td>${escapeHtml(row.deployableRole)}</td>` : ''}
      <td>${formatNumber(objectTypeCount(row.type))}</td>
    </tr>
  `).join('');
}

function objectTypesSidebarMarkup() {
  const deployableCount = OBJECT_TYPE_GUIDE.deployable.reduce((count, row) => count + objectTypeCount(row.type), 0);
  const nonDeployableCount = OBJECT_TYPE_GUIDE.nonDeployable.reduce((count, row) => count + objectTypeCount(row.type), 0);
  return `
    <div class="sidebar-block">
      <div class="legend-title">Object Types</div>
      <div class="current-filter"><span class="dot" style="background:#22c55e"></span><span>${pluralize(deployableCount, 'deployable object')}</span></div>
      <div class="current-filter"><span class="dot" style="background:#64748b"></span><span>${pluralize(nonDeployableCount, 'non-deployable object')}</span></div>
    </div>
  `;
}

function renderObjectTypesView() {
  currentMode = 'object-types';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForObjectTypesView();
  renderSidebarContent(objectTypesSidebarMarkup());
  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      <section class="header-card">
        <div class="header-top">
          <div class="header-title">
            <h2>DRAFT Object Types</h2>
            <div class="object-id">Deployable architecture versus framework content</div>
          </div>
        </div>
        <div class="header-description">Deployable objects describe architecture that can eventually become automation inputs. Non-deployable objects guide, govern, remember, or explain how deployable architecture is drafted.</div>
      </section>
      <section class="section-card">
        <h3>Deployable Architecture</h3>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Object Type</th><th>Purpose</th><th>Deployable Role</th><th>Catalog Count</th></tr></thead>
            <tbody>${objectTypeRowsMarkup(OBJECT_TYPE_GUIDE.deployable, true)}</tbody>
          </table>
        </div>
      </section>
      <section class="section-card">
        <h3>Non-Deployable Architecture</h3>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Object Type</th><th>Purpose</th><th>Catalog Count</th></tr></thead>
            <tbody>${objectTypeRowsMarkup(OBJECT_TYPE_GUIDE.nonDeployable, false)}</tbody>
          </table>
        </div>
      </section>
      <section class="section-card">
        <h3>Delivery Models</h3>
        <div class="header-description">PaaS, SaaS, appliance, and self-managed are delivery models on Runtime Service, Data-at-Rest Service, and Edge/Gateway Service objects. They are not separate object types.</div>
      </section>
    </div>
  `;
  attachTopNavHandlers();
}

function companyOnboardingSidebarMarkup() {
  return `
    <div class="sidebar-block">
      <div class="legend-title">Onboarding Path</div>
      <div class="current-filter"><span class="dot" style="background:#22c55e"></span><span>Run draft-table onboard</span></div>
      <div class="current-filter"><span class="dot" style="background:#7c3a6b"></span><span>Start setup mode</span></div>
      <div class="current-filter"><span class="dot" style="background:#8b5cf6"></span><span>Seed minimum baseline</span></div>
      <div class="current-filter"><span class="dot" style="background:#f59e0b"></span><span>Draft one real system</span></div>
    </div>
  `;
}

function onboardingStepMarkup(number, title, description, items = []) {
  return `
    <article class="object-card">
      <div>
        <h3>${number}. ${escapeHtml(title)}</h3>
        <div class="object-id">${escapeHtml(description)}</div>
      </div>
      ${items.length ? `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
    </article>
  `;
}

function renderCompanyOnboardingView() {
  currentMode = 'onboarding';
  currentDetailId = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForOnboardingView();
  renderSidebarContent(companyOnboardingSidebarMarkup());
  const steps = [
    ['Install', 'Install DRAFT Table and select or create a private company DRAFT repo.', ['Run draft-table onboard', 'Vendor the selected framework copy into .draft/framework/', 'Confirm draft-table doctor, framework status, and validation']],
    ['Start Setup Mode', 'Ask the Draftsman to guide the first-run setup conversation.', ['Open DRAFT Table', 'Ask: start setup mode', 'Track current step, next step, remaining work, and revisit-later items']],
    ['Define Minimum Governance', 'Make only the workspace decisions needed for useful first drafting.', ['Define business taxonomy in .draft/workspace.yaml', 'Activate the initial Requirement Groups', 'Keep strict active-group disposition off while migrating inventory']],
    ['Seed Acceptable Use', 'Connect the first capabilities to approved Technology Components and owners.', ['Start with identity, logging, monitoring, patching, backup, compute, operating systems, database, and edge', 'Use preferred, existing-only, candidate, deprecated, and retired deliberately']],
    ['Draft Baseline Standards', 'Create reusable deployable architecture from behavior first, delivery model second.', ['Host', 'Runtime Service', 'Data-at-Rest Service', 'Edge/Gateway Service', 'Product Service', 'Software Deployment Pattern']],
    ['Draft One Real System', 'Use one product, system, repository, diagram, or document to prove the workflow.', ['Capture unresolved facts in a Drafting Session', 'Run validation', 'Regenerate the browser and review the Git diff']]
  ];
  const gapSignals = [
    'Users cannot tell whether they are installing tooling or making catalog governance decisions.',
    'Setup asks too many open-ended questions before showing what is next.',
    'The Draftsman asks open-ended capability questions when approved implementations exist.',
    'Technology Components appear to have company lifecycle outside capability mappings.',
    'Approved capabilities have no requirement trace.',
    'Validation failures do not tell the Draftsman exactly what to add or where to look next.'
  ];
  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      <section class="header-card">
        <div class="header-top">
          <div class="header-title">
            <h2>Company Onboarding Tutorial</h2>
            <div class="object-id">From empty private repo to the first useful drafting session</div>
          </div>
        </div>
        <div class="header-description">A company implements DRAFT in two parts: local tooling onboarding, then Draftsman setup mode. Setup mode keeps the team aware of the current step, next step, remaining work, and revisit-later decisions while building the minimum useful catalog baseline.</div>
      </section>
      <section class="section-card">
        <h3>Operating Model</h3>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Area</th><th>Owned By</th><th>Purpose</th></tr></thead>
            <tbody>
              <tr><td>Upstream Framework</td><td>DRAFT project</td><td>Schemas, base Requirement Groups, base capabilities, templates, tools, examples, and Draftsman guidance.</td></tr>
              <tr><td>Vendored Framework</td><td>Company repo</td><td>The reviewed framework copy under .draft/framework/ used for normal private Draftsman work.</td></tr>
              <tr><td>Workspace Configuration</td><td>Company repo</td><td>Business taxonomy, active Requirement Groups, capability owners, implementation mappings, and overlays.</td></tr>
              <tr><td>Architecture Catalog</td><td>Company repo</td><td>Technology Components, deployable objects, Reference Architectures, Software Deployment Patterns, decisions, and Drafting Sessions.</td></tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="section-card">
        <h3>Implementation Path</h3>
        <div class="object-grid">
          ${steps.map((step, index) => onboardingStepMarkup(index + 1, step[0], step[1], step[2])).join('')}
        </div>
      </section>
      <section class="section-card">
        <h3>Readiness Checklist</h3>
        <ul>
          <li>Private repo contains .draft/framework/ and .draft/framework.lock.</li>
          <li>.draft/workspace.yaml declares business taxonomy and active Requirement Groups.</li>
          <li>Capability owners are identified wherever implementations are mapped.</li>
          <li>Approved capabilities are referenced by Requirement Group requirements.</li>
          <li>Acceptable-use Technology Components are mapped by capability.</li>
          <li>Baseline Hosts, Runtime Services, Data-at-Rest Services, and Edge/Gateway Services exist for common deployment patterns.</li>
          <li>Validation passes and the generated browser reflects the catalog.</li>
        </ul>
      </section>
      <section class="section-card">
        <h3>Gap Signals Before 1.0</h3>
        <ul>${gapSignals.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
      </section>
    </div>
  `;
  attachTopNavHandlers();
}

function navigateExecutiveTarget(target) {
  if (target === 'drafting-table') {
    activeCategory = 'architecture';
    activeFilter = 'all';
    listSearchTerm = '';
    executiveDrilldown = null;
    renderListView();
    return;
  }
  if (target === 'home') {
    renderExecutiveView();
    return;
  }
  if (target === 'requirement-groups') {
    renderRequirementGroupsView({ builtIn: false });
    return;
  }
  if (target === 'built-in-configs') {
    renderRequirementGroupsView({ builtIn: true });
    return;
  }
  if (target === 'vocabularies') {
    renderVocabulariesView();
    return;
  }
  if (target === 'taxonomies') {
    renderTaxonomiesView();
    return;
  }
  if (target === 'technologies') {
    renderTechnologiesView();
    return;
  }
  if (target === 'deployment-targets') {
    renderDeploymentTargetsView();
    return;
  }
  if (target === 'teams') {
    renderTeamsView();
    return;
  }
  if (target.startsWith('team-detail:')) {
    renderTeamDetailView(target.slice('team-detail:'.length));
    return;
  }
  if (target.startsWith('team-type:')) {
    const parts = target.slice('team-type:'.length).split(':');
    renderTeamTypeObjectsView(parts[0], parts[1]);
    return;
  }
  if (target === 'capabilities') {
    activeCategory = 'framework';
    activeFilter = 'capability';
    listSearchTerm = '';
    executiveDrilldown = null;
    renderListView();
    return;
  }
  if (target === 'deployments' || target === 'sdps-by-pillar') {
    renderSdpsByPillarView();
    return;
  }
  if (target.startsWith('pillar-sdps:')) {
    renderPillarSdpsView(target.slice('pillar-sdps:'.length));
    return;
  }
  if (target === 'requirements') {
    activeCategory = 'framework';
    activeFilter = 'requirement_group';
    listSearchTerm = '';
    executiveDrilldown = null;
    renderListView();
    return;
  }
  if (target === 'acceptable-use') {
    executiveDrilldown = null;
    renderAcceptableUseView();
    return;
  }
  if (target === 'controls') {
    executiveDrilldown = 'controls';
    renderExecutiveView();
    return;
  }
  if (target === 'clear-drilldown') {
    executiveDrilldown = null;
    renderExecutiveView();
  }
}

function attachExecutiveHandlers() {
  pageRoot.querySelectorAll('[data-executive-target]').forEach(item => {
    item.addEventListener('click', () => {
      navigateExecutiveTarget(item.dataset.executiveTarget);
    });
    item.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        navigateExecutiveTarget(item.dataset.executiveTarget);
      }
    });
  });
}

function acceptableUseSidebarMarkup(groups, mappedCount) {
  const capabilityCount = groups.reduce((count, group) => {
    const ids = new Set(group.rows.map(row => row.capability.id));
    return count + ids.size;
  }, 0);
  return `
    <div class="sidebar-block">
      <div class="legend-title">Acceptable Use Technology</div>
      <div class="current-filter"><span class="dot" style="background:#7c3a6b"></span><span>${mappedCount} mapped Technology Components</span></div>
      <div class="current-filter"><span class="dot" style="background:#22c55e"></span><span>${capabilityCount} capability groups</span></div>
      <div class="current-filter"><span class="dot" style="background:#f59e0b"></span><span>${groups.length} domain groups</span></div>
    </div>
  `;
}

function acceptableUseOwnerMarkup(owner) {
  if (!owner?.team && !owner?.contact) {
    return '<span>Owner: Not assigned</span><span>No contact documented</span>';
  }
  return `
    <span>Owner: ${escapeHtml(owner.team || 'Not assigned')}</span>
    <span>${escapeHtml(owner.contact || 'No contact documented')}</span>
  `;
}

function acceptableUseTechnologyMarkup(technology, implementation) {
  if (!technology) {
    return `<span class="muted-cell">${escapeHtml(implementation.ref || 'Unknown Technology Component')}</span>`;
  }
  return `
    <span class="ard-link" data-object-link="${escapeHtml(technology.id)}">${escapeHtml(technology.name)}</span>
    <div class="object-id">${escapeHtml(technology.id)}</div>
  `;
}

function acceptableUseCapabilityCount(rows) {
  const uniqueRefs = new Set(
    rows
      .map(row => row.implementation?.ref)
      .filter(Boolean)
  );
  const count = uniqueRefs.size;
  return `${count} ${count === 1 ? 'Technology Component' : 'Technology Components'}`;
}

function acceptableUseDomainMarkup(group) {
  const capabilityGroups = [];
  group.rows.forEach(row => {
    let capabilityGroup = capabilityGroups[capabilityGroups.length - 1];
    if (!capabilityGroup || capabilityGroup.capability.id !== row.capability.id) {
      capabilityGroup = { capability: row.capability, rows: [] };
      capabilityGroups.push(capabilityGroup);
    }
    capabilityGroup.rows.push(row);
  });
  return `
    <section class="section-card">
      <h3>${escapeHtml(group.domain.name || group.domain.id)}</h3>
      <div class="object-id">${escapeHtml(group.domain.id || '')}</div>
      ${group.domain.description ? `<div class="header-description">${escapeHtml(group.domain.description)}</div>` : ''}
      ${capabilityGroups.map(capabilityGroup => {
        const capability = capabilityGroup.capability;
        return `
          <div class="acceptable-use-capability">
            <div class="acceptable-use-capability-header">
              <div class="acceptable-use-capability-title">
                <span class="ard-link" data-object-link="${escapeHtml(capability.id)}">${escapeHtml(capability.name)}</span>
                <span class="badge">${acceptableUseCapabilityCount(capabilityGroup.rows)}</span>
                <span class="object-id">${escapeHtml(capability.id)}</span>
              </div>
              <div class="acceptable-use-owner">${acceptableUseOwnerMarkup(capability.owner)}</div>
            </div>
            <div class="table-scroll">
              <table class="data-table acceptable-use-table">
                <thead>
                  <tr>
                    <th>Vendor</th>
                    <th>Technology Component</th>
                    <th>Status</th>
                    <th>Configuration</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  ${capabilityGroup.rows.map(row => {
                    const implementation = row.implementation;
                    const technology = row.technology;
                    const configuration = implementationConfigurationLabel(technology, implementation);
                    return `
                      <tr>
                        <td>${technology?.vendor ? escapeHtml(technology.vendor) : '<span class="muted-cell">Not documented</span>'}</td>
                        <td>${acceptableUseTechnologyMarkup(technology, implementation)}</td>
                        <td>${lifecycleBadge(implementation.lifecycleStatus || 'unknown')}</td>
                        <td>${configuration ? escapeHtml(configuration) : '<span class="muted-cell">Default</span>'}</td>
                        <td>${implementation?.notes ? escapeHtml(implementation.notes) : '<span class="muted-cell">No notes</span>'}</td>
                      </tr>
                    `;
                  }).join('')}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }).join('')}
    </section>
  `;
}

function renderAcceptableUseView() {
  currentMode = 'acceptable-use';
  currentDetailId = null;
  executiveDrilldown = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  syncHashForAcceptableUseView();
  const groups = acceptableUseGroups();
  const mappedCount = groups.reduce(
    (count, group) => count + group.rows.filter(row => row.implementation).length,
    0
  );
  const capabilityCount = groups.reduce((count, group) => {
    const ids = new Set(group.rows.map(row => row.capability.id));
    return count + ids.size;
  }, 0);
  renderSidebarContent(acceptableUseSidebarMarkup(groups, mappedCount));
  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      <section class="header-card">
        <div class="header-top">
          <div class="header-title">
            <h2>Acceptable Use Technology</h2>
            <div class="object-id">Technology Component lifecycle map</div>
          </div>
          <div class="badges">
            <span class="badge">${mappedCount} mapped Technology Components</span>
            <span class="badge">${capabilityCount} capability groups</span>
            <span class="badge">${groups.length} domain groups</span>
          </div>
        </div>
        <div class="header-description">
          Technology Components grouped by governing domain and capability. Contact the capability owner when a Technology Component needs to be added, retired, or moved to a different lifecycle status.
        </div>
      </section>
      <div class="content-rows">
        ${groups.map(acceptableUseDomainMarkup).join('') || '<div class="empty-card" style="padding:24px;">No Technology Component implementations are mapped.</div>'}
      </div>
    </div>
  `;
  attachTopNavHandlers();
  attachObjectLinkHandlers(pageRoot);
}

function renderListView() {
  currentMode = 'list';
  currentDetailId = null;
  executiveDrilldown = null;
  destroyDetailCy();
  destroySdpGraphCy();
  destroyImpactCy();
  const category = categoryConfig();
  const baseObjects = filterObjects();
  const searchTerm = normalizedSearchTerm(listSearchTerm);
  const filtered = searchTerm
    ? baseObjects.filter(object => objectMatchesSearch(object, searchTerm))
    : baseObjects;
  const rows = activeFilter === 'all'
    ? category.rows.map(row => ({ row, objects: filterObjectsByTypes(row.types) })).filter(section => section.objects.length)
    : (() => {
        const filter = activeFilterConfig();
        const row = category.rows.find(item => item.id === activeFilter)
          || { id: filter.id, label: filter.label, types: filter.types };
        return [{ row, objects: filtered }];
      })();
  if (activeFilter === 'all' && searchTerm) {
    rows.forEach(section => {
      section.objects = section.objects.filter(object => objectMatchesSearch(object, searchTerm));
    });
  }
  const visibleRows = rows.filter(section => section.objects.length);
  syncHashForListView();
  renderSidebarContent(sidebarMarkup(businessPillarSidebarMarkup(filtered)));
  pageRoot.innerHTML = `
    <div class="view-shell">
      ${topNavMarkup()}
      <div class="tab-row">
        ${CATEGORY_CONFIG.map(categoryItem => `<button class="tab-button ${categoryItem.id === activeCategory ? 'active' : ''}" data-category-tab="${categoryItem.id}">${escapeHtml(categoryItem.label)}</button>`).join('')}
      </div>
      <div class="filter-row">
        ${category.filters.map(filter => `<button class="filter-button ${filter.id === activeFilter ? 'active' : ''}" data-filter="${filter.id}">${escapeHtml(filter.label)}</button>`).join('')}
      </div>
      ${catalogSearchMarkup(filtered.length, baseObjects.length)}
      <div class="view-title">
        <span>${filtered.length} objects</span>
        <span>${searchTerm ? 'Search results in ' : 'Showing '}${escapeHtml(category.label)}${activeFilter === 'all' ? '' : ` / ${escapeHtml(formatListFilterLabel(activeFilter))}`}</span>
      </div>
      <div class="content-rows">
        ${visibleRows.map(section => listRowMarkup(section.row, section.objects)).join('') || `<div class="empty-card" style="padding:24px;">${searchTerm ? 'No objects match this search.' : 'No objects in this view.'}</div>`}
      </div>
    </div>
  `;

  const searchInput = document.getElementById('catalog-search');
  if (searchInput) {
    searchInput.addEventListener('input', event => {
      listSearchTerm = event.target.value;
      const cursorStart = event.target.selectionStart ?? listSearchTerm.length;
      const cursorEnd = event.target.selectionEnd ?? listSearchTerm.length;
      renderListView();
      const refreshedInput = document.getElementById('catalog-search');
      if (refreshedInput) {
        refreshedInput.focus();
        refreshedInput.setSelectionRange(cursorStart, cursorEnd);
      }
    });
    searchInput.addEventListener('keydown', event => {
      if (event.key === 'Enter' && filtered.length) {
        event.preventDefault();
        showDetailView(filtered[0].id);
      }
      if (event.key === 'Escape' && listSearchTerm) {
        event.preventDefault();
        listSearchTerm = '';
        renderListView();
      }
    });
  }

  pageRoot.querySelector('[data-clear-list-search]')?.addEventListener('click', () => {
    listSearchTerm = '';
    renderListView();
    document.getElementById('catalog-search')?.focus();
  });

  pageRoot.querySelectorAll('[data-category-tab]').forEach(button => {
    button.addEventListener('click', () => {
      activeCategory = button.dataset.categoryTab;
      activeFilter = 'all';
      renderListView();
    });
  });

  pageRoot.querySelectorAll('[data-filter]').forEach(button => {
    button.addEventListener('click', () => {
      activeFilter = button.dataset.filter;
      renderListView();
    });
  });

  pageRoot.querySelectorAll('[data-object-id]').forEach(card => {
    card.addEventListener('click', () => {
      showDetailView(card.dataset.objectId);
    });
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        showDetailView(card.dataset.objectId);
      }
    });
  });

  attachTopNavHandlers();
  attachSidebarHandlers();
}

function flattenDecisionEntries(prefix, value, entries) {
  if (Array.isArray(value)) {
    if (value.every(item => item && typeof item === 'object' && !Array.isArray(item))) {
      value.forEach((item, index) => {
        flattenDecisionEntries(`${prefix}[${index + 1}]`, item, entries);
      });
    } else {
      entries.push({ key: prefix, value: value.join(', ') });
    }
    return;
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    Object.entries(value).forEach(([childKey, childValue]) => {
      flattenDecisionEntries(prefix ? `${prefix}.${childKey}` : childKey, childValue, entries);
    });
    return;
  }
  entries.push({ key: prefix, value: String(value) });
}

function decisionMarkup(object, excludedRootKeys = []) {
  const excluded = new Set(excludedRootKeys);
  const decisions = Object.fromEntries(
    Object.entries(object.architecturalDecisions || {}).filter(([key]) => !excluded.has(key))
  );
  const entries = [];
  flattenDecisionEntries('', decisions, entries);
  if (!entries.length) {
    return '<div class="empty-card">No architectural decisions are defined for this object.</div>';
  }
  return `
    <div class="decisions-grid single">
      <section class="decision-card">
        <h4>Architecture Decisions</h4>
        <dl class="definition-list">
          ${entries.map(entry => `<dt>${escapeHtml(entry.key)}</dt><dd>${escapeHtml(entry.value)}</dd>`).join('')}
        </dl>
      </section>
    </div>
  `;
}

function businessContextMarkup(object) {
  if (object.type !== 'software_deployment_pattern') {
    return '';
  }
  const context = object.businessContext || {};
  if (!context.pillar && !context.productFamily && !context.notes) {
    return '';
  }
  const pillar = businessPillarForObject(object);
  const additional = Array.isArray(context.additionalPillars)
    ? context.additionalPillars.map(id => businessPillarLookup[id]?.name || formatTitleCase(String(id).replace(/^business-pillar\./, '').replace(/-/g, ' ')))
    : [];
  return `
    <section class="section-card">
      <h3>Business Context</h3>
      <dl class="definition-list">
        <dt>Primary Pillar</dt>
        <dd>${escapeHtml(pillar.name)}</dd>
        ${additional.length ? `<dt>Additional Pillars</dt><dd>${escapeHtml(additional.join(', '))}</dd>` : ''}
        ${context.productFamily ? `<dt>Product Family</dt><dd>${escapeHtml(context.productFamily)}</dd>` : ''}
        ${context.notes ? `<dt>Notes</dt><dd>${escapeHtml(context.notes)}</dd>` : ''}
      </dl>
    </section>
  `;
}

function sourceRepositoryMarkup(object) {
  const repos = object.architecturalDecisions?.sourceRepositories || [];
  if (!Array.isArray(repos) || !repos.length) {
    return '';
  }
  return `
    <section class="section-card">
      <h3>Source Repositories</h3>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Repository</th>
              <th>Product Service</th>
              <th>Language</th>
              <th>Signals</th>
            </tr>
          </thead>
          <tbody>
            ${repos.map(repo => {
              const productService = repo.productService || '';
              const service = productService ? objectLookup[productService] : null;
              const repoName = repo.repositoryName || repo.sourceRepository || 'Unknown repository';
              const repoUrl = repo.sourceRepository || '';
              return `
                <tr>
                  <td>
                    ${repoUrl ? `<a href="${escapeHtml(repoUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(repoName)}</a>` : escapeHtml(repoName)}
                    ${repoUrl && repoUrl !== repoName ? `<div class="object-id">${escapeHtml(repoUrl)}</div>` : ''}
                  </td>
                  <td>
                    ${service ? `<span class="ard-link" data-object-link="${escapeHtml(productService)}">${escapeHtml(service.name)}</span>` : escapeHtml(productService || 'Not linked')}
                    ${productService ? `<div class="object-id">${escapeHtml(productService)}</div>` : ''}
                  </td>
                  <td>${escapeHtml(repo.repositoryPrimaryLanguage || '')}</td>
                  <td>${escapeHtml(repo.observedRuntimeSignals || '')}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function interactionMarkup(object) {
  const interactions = object.externalInteractions || [];
  if (!interactions.length) {
    return '<div class="empty-card">No external interactions are documented for this object.</div>';
  }
  return `
    <div class="interactions-list">
      ${interactions.map((interaction, index) => {
        const justification = dependencyJustificationForExternalInteraction(object, interaction, index);
        const target = interaction.ref && objectLookup[interaction.ref] ? objectLookup[interaction.ref] : null;
        const interactionName = target
          ? `<span class="ard-link" data-object-link="${escapeHtml(target.id)}">${escapeHtml(interaction.name || target.name || 'External Interaction')}</span>`
          : escapeHtml(interaction.name || 'External Interaction');
        return `
        <article class="interaction-card">
          <div class="interaction-top">
            <div class="interaction-heading">
              <div class="interaction-name">${interactionName}</div>
              ${capabilityLabelsMarkup(interaction.capabilities)}
            </div>
          </div>
          ${dependencyJustificationMarkup(justification)}
          ${interaction.notes ? `<div class="interaction-notes">${escapeHtml(interaction.notes)}</div>` : ''}
          ${interaction.ref ? `<div class="interaction-ref">${escapeHtml(interaction.ref)}</div>` : ''}
        </article>
      `;
      }).join('')}
    </div>
  `;
}

function internalComponentSummaryMarkup(object) {
  const components = object?.internalComponents || [];
  if (!components.length) {
    return '';
  }
  return `
    <div class="section-stack component-summary-list">
      ${components.map((component, index) => {
        const target = objectLookup[component.ref] || null;
        const justification = dependencyJustificationForInternalComponent(object, component, index);
        const resolution = componentNetworkBindingResolution(component);
        const configurationText = component.configuration
          ? configurationDisplayName(configurationById(target, component.configuration) || { id: component.configuration })
          : '';
        return `
          <article class="odc-card component-summary-card">
            <div class="component-summary-header">
              <div>
                <div class="odc-name">
                  ${target ? `<span class="ard-link" data-object-link="${escapeHtml(target.id)}">${escapeHtml(target.name)}</span>` : escapeHtml(component.ref || 'Unknown component')}
                </div>
                <div class="object-id">${escapeHtml(component.ref || '')}</div>
              </div>
              <div class="requirement-badges">
                <span class="requirement-badge">${escapeHtml(component.role || 'component')}</span>
                ${configurationText ? `<span class="requirement-badge capability-label">${escapeHtml(configurationText)}</span>` : ''}
              </div>
            </div>
            ${dependencyJustificationMarkup(justification)}
            ${component.notes ? `<div class="interaction-notes">${escapeHtml(component.notes)}</div>` : ''}
            ${resolution.status === 'unknown-configuration' ? `<div class="interaction-notes">Referenced configuration is not defined on the Technology Component.</div>` : ''}
          </article>
        `;
      }).join('')}
    </div>
  `;
}

function requirementMechanismSentence(mechanism) {
  if (mechanism.mechanism === 'externalInteraction') {
    return `externalInteraction(capability=${mechanism.criteria?.capability || 'unknown'})`;
  }
  if (mechanism.mechanism === 'internalComponent') {
    return `internalComponent(role=${mechanism.criteria?.role || 'unknown'})`;
  }
  if (mechanism.mechanism === 'architecturalDecision') {
    return `architecturalDecision(key=${mechanism.key || 'unknown'})`;
  }
  return mechanism.mechanism || 'unknown';
}

function odcRequirementsMarkup(object) {
  const requirements = object.requirements || [];
  if (!requirements.length) {
    return '<div class="empty-card">No requirements are documented for this Requirement Group.</div>';
  }
  return `
    <section class="section-card">
      <h3>Requirements</h3>
      <div class="section-stack">
        ${requirements.map(requirement => `
          <article class="requirement-card">
            <div class="requirement-name">${escapeHtml(requirementDisplayLabel(object, requirement))}</div>
            <div class="requirement-badges">
              ${requirement.externalControlId ? `<span class="requirement-badge">${escapeHtml(requirementSourceText(object))}</span>` : ''}
              ${requirement.relatedCapability ? `<span class="requirement-badge">${escapeHtml(requirement.relatedCapability)}</span>` : ''}
              <span class="requirement-badge ${requirement.requirementMode === 'conditional' ? 'conditional' : ''}">${escapeHtml(requirement.requirementMode || 'mandatory')}</span>
              ${requirement.naAllowed ? '<span class="requirement-badge conditional">N/A allowed</span>' : ''}
            </div>
            <div class="requirement-description">${escapeHtml(requirement.description || '')}</div>
            ${requirement.rationale ? `
              <div class="requirement-rationale-label">Rationale</div>
              <div class="requirement-rationale">${escapeHtml(requirement.rationale)}</div>
            ` : ''}
            <div class="mechanism-label">Can be satisfied by</div>
            <div class="mechanism-list">
              ${(requirement.canBeSatisfiedBy || []).map(mechanism => `
                <div class="mechanism-item">
                  <div class="mechanism-text">${escapeHtml(requirementMechanismSentence(mechanism))}</div>
                  ${mechanism.example ? `<div class="mechanism-example">${escapeHtml(mechanism.example)}</div>` : ''}
                </div>
              `).join('')}
            </div>
          </article>
        `).join('')}
      </div>
    </section>
  `;
}

function requirementEvidenceMarkup(object) {
  const implementations = object.requirementImplementations || [];
  if (!implementations.length) {
    return '';
  }
  return `
    <section class="section-card">
      <h3>Requirement Evidence</h3>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Requirement</th>
              <th>Status</th>
              <th>Mechanism</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            ${implementations.map(implementation => {
              const group = objectLookup[implementation.requirementGroup] || null;
              const requirement = findRequirementInGroup(group, implementation.requirementId);
              const refObject = implementation.ref ? objectLookup[implementation.ref] : null;
              const evidence = refObject
                ? `<span class="ard-link" data-object-link="${escapeHtml(refObject.id)}">${escapeHtml(refObject.name)}</span>`
                : escapeHtml(implementation.ref || implementation.key || implementation.notes || 'Not documented');
              return `
                <tr>
                  <td>
                    <strong>${escapeHtml(requirementDisplayLabel(group, requirement || { id: implementation.requirementId }))}</strong>
                    <div class="object-id">${escapeHtml(requirementSourceText(group))}</div>
                  </td>
                  <td><span class="badge">${escapeHtml(implementation.status || 'unknown')}</span></td>
                  <td>${escapeHtml(implementation.mechanism || 'unknown')}</td>
                  <td>${evidence}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function requirementGroupByName(name) {
  return allObjects.find(object => object.type === 'requirement_group' && object.name === name) || null;
}

function sdmRisksMarkup(object) {
  const references = object.decisionRecords || [];
  if (!references.length) {
    return '';
  }
  return `
    <section class="section-card">
      <h3>Decision Records</h3>
      <div class="section-stack">
        ${references.map(entry => {
          const ard = objectLookup[entry.ref];
          return `
            <article class="odc-card">
              <div class="odc-name">
                ${ard ? `<span class="ard-link" data-object-link="${ard.id}">${escapeHtml(ard.name)}</span>` : escapeHtml(entry.ref || 'Unknown Decision Record')}
              </div>
              <div class="object-id">${escapeHtml(entry.ref || '')}</div>
            </article>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

function sdmServiceGroupsMarkup(object) {
  const groups = object.serviceGroups || [];
  const scalingUnits = new Map((object.scalingUnits || []).map(unit => [unit.name, unit]));
  if (!groups.length) {
    return '<div class="empty-card">No service groups are documented for this Software Deployment Pattern.</div>';
  }
  return `
    <section class="section-card">
      <h3>Service Groups</h3>
      <div class="section-stack">
        ${groups.map(group => {
          const scalingUnit = group.scalingUnit ? scalingUnits.get(group.scalingUnit) : null;
          const externalInteractions = (group.externalInteractions || []).filter(item => (item.type || 'external') !== 'internal');
          const internalInteractions = (group.externalInteractions || []).filter(item => (item.type || 'external') === 'internal');
          const deployableEntries = group.deployableObjects || [];
          const productCount = deployableEntries.filter(entry => objectLookup[entry.ref]?.type === 'product_service').length;
          const paasCount = deployableEntries.filter(entry => objectLookup[entry.ref]?.deliveryModel === 'paas').length;
          const saasCount = deployableEntries.filter(entry => objectLookup[entry.ref]?.deliveryModel === 'saas').length;
          const applianceCount = deployableEntries.filter(entry => objectLookup[entry.ref]?.deliveryModel === 'appliance').length;
          const reusableCount = deployableEntries.filter(entry => objectLookup[entry.ref] && objectLookup[entry.ref]?.type !== 'product_service').length;
          return `
            <article class="odc-card">
              <div class="odc-name">${escapeHtml(group.name || 'Unnamed Service Group')}</div>
              <div class="interaction-notes">${escapeHtml(group.deploymentTarget || 'Unspecified deployment target')}</div>
              <div class="badges">
                ${group.scalingUnit ? `<span class="badge">${escapeHtml(group.scalingUnit)}</span>` : '<span class="badge">unscoped</span>'}
                ${scalingUnit?.type ? `<span class="badge">${escapeHtml(scalingUnit.type)}</span>` : ''}
                ${productCount ? `<span class="badge ps-badge">${productCount} PS</span>` : ''}
                ${paasCount ? `<span class="badge paas-badge">${paasCount} PaaS</span>` : ''}
                ${reusableCount ? `<span class="badge">${reusableCount} deployable</span>` : ''}
                ${applianceCount ? applianceBadge() : ''}
                ${saasCount ? saasBadge() : ''}
              </div>
              ${externalInteractions.length ? `<div class="interaction-notes"><strong>External:</strong> ${escapeHtml(externalInteractions.map(item => item.name).join(', '))}</div>` : ''}
              ${internalInteractions.length ? `<div class="interaction-notes"><strong>Internal:</strong> ${escapeHtml(internalInteractions.map(item => `${item.name} → ${item.ref || 'unknown'}`).join(', '))}</div>` : ''}
            </article>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

function productServiceDetailMarkup(object) {
  const runsOnObject = object.runsOn ? objectLookup[object.runsOn] : null;
  return `
    <section class="section-card">
      <h3>Product Service Classification</h3>
      <div class="section-stack">
        <div class="badges">
          ${productBadge(object.product)}
          ${lifecycleBadge(object.lifecycleStatus)}
          ${catalogBadge(object.catalogStatus)}
        </div>
        <dl class="definition-list">
          <dt>UID</dt><dd><span class="object-id">${escapeHtml(object.id)}</span></dd>
          <dt>Product</dt><dd>${escapeHtml(object.product || '')}</dd>
          <dt>Runs On</dt><dd>${runsOnObject ? `<span class="ard-link" data-object-link="${object.runsOn}">${escapeHtml(runsOnObject.name)}</span>` : escapeHtml(object.runsOn || '')}</dd>
          <dt>Underlying Deployable Object</dt><dd>${escapeHtml(object.runsOn || 'Not documented')}</dd>
        </dl>
        <div class="header-description">${escapeHtml(object.description || 'No description provided.')}</div>
      </div>
    </section>
  `;
}

function preferredInteractionSource(object, fallbackObject) {
  const ownInteractions = object?.externalInteractions || [];
  if (ownInteractions.length) {
    return object;
  }
  return fallbackObject;
}

function preferredComponentSource(object, fallbackObject) {
  const ownComponents = object?.internalComponents || [];
  if (ownComponents.length) {
    return object;
  }
  return fallbackObject;
}

function preferredDecisionSource(object, fallbackObject) {
  const ownDecisions = object?.architecturalDecisions || {};
  if (Object.keys(ownDecisions).length) {
    return object;
  }
  return fallbackObject;
}

function abbDetailMarkup(object) {
  return `
    <section class="section-card">
      <h3>Technology Component</h3>
      <div class="section-stack">
        <div class="badges">
          ${object.lifecycleStatus ? lifecycleBadge(object.lifecycleStatus) : ''}
          ${catalogBadge(object.catalogStatus)}
        </div>
        <dl class="definition-list">
          <dt>Vendor</dt><dd>${escapeHtml(object.vendor || '')}</dd>
          <dt>Product Name</dt><dd>${escapeHtml(object.productName || '')}</dd>
          <dt>Product Version</dt><dd>${escapeHtml(object.productVersion || '')}</dd>
          <dt>Classification</dt><dd>${escapeHtml(abbClassificationLabel(object.classification))}</dd>
          ${object.capabilities?.length ? `<dt>Capabilities</dt><dd>${escapeHtml(object.capabilities.map(abbClassificationLabel).join(', '))}</dd>` : ''}
          ${object.platformDependency ? `<dt>Platform Dependency</dt><dd>${escapeHtml(object.platformDependency)}</dd>` : ''}
          ${object.networkPlacement ? `<dt>Network Placement</dt><dd>${escapeHtml(object.networkPlacement || '')}</dd>` : ''}
          ${object.patchingOwner ? `<dt>Patching Owner</dt><dd>${escapeHtml(object.patchingOwner || '')}</dd>` : ''}
          <dt>Compliance Certs</dt><dd>${escapeHtml((object.complianceCerts || []).join(', ') || 'None documented')}</dd>
        </dl>
        ${object.configurations?.length ? `
          <div class="interaction-notes"><strong>Configurations:</strong></div>
          <div class="section-stack">
          ${object.configurations.map(configuration => `
              <article class="odc-card">
                <div class="odc-name">${escapeHtml(configuration.name || configuration.id || 'Configuration')}</div>
                <div class="interaction-notes">${escapeHtml(configuration.description || '')}</div>
                <div class="object-id">${escapeHtml((configuration.capabilities || []).map(abbClassificationLabel).join(', '))}</div>
                ${networkBindingsTableMarkup(networkBindingsForConfiguration(configuration))}
              </article>
            `).join('')}
          </div>
        ` : ''}
      </div>
    </section>
  `;
}

function deploymentConfigurationsMarkup(object) {
  const configurations = object.deploymentConfigurations || [];
  if (!configurations.length) {
    return '';
  }
  return `
    <section class="section-card">
      <h3>Deployment Configurations</h3>
      <div class="section-stack">
        ${configurations.map(configuration => `
          <article class="odc-card">
            <div class="odc-name">${escapeHtml(configuration.name || configuration.id || 'Deployment Configuration')}</div>
            <div class="interaction-notes">${escapeHtml(configuration.description || '')}</div>
            ${configuration.addressesQualities?.length ? `<div class="object-id">${escapeHtml(configuration.addressesQualities.join(', '))}</div>` : ''}
          </article>
        `).join('')}
      </div>
    </section>
  `;
}

function deliveryModelDetailMarkup(object) {
  if (!SERVICE_OBJECT_TYPES.includes(object.type)) {
    return '';
  }
  if (object.deliveryModel === 'saas') {
  return `
    <section class="section-card">
      <h3>SaaS Delivery</h3>
      <div class="section-stack">
        <div class="badges">
          ${saasBadge()}
          ${lifecycleBadge(object.lifecycleStatus)}
          ${catalogBadge(object.catalogStatus)}
          ${boolBadge(object.dataLeavesInfrastructure === true, 'Data Leaves Infrastructure', 'Data Stays In Boundary')}
        </div>
        <dl class="definition-list">
          <dt>Vendor</dt><dd>${escapeHtml(object.vendor || '')}</dd>
          ${object.capabilities?.length ? `<dt>Capabilities</dt><dd>${escapeHtml(object.capabilities.join(', '))}</dd>` : ''}
          <dt>Data Residency</dt><dd>${escapeHtml(object.dataResidencyCommitment || 'Not documented')}</dd>
          <dt>DPA Notes</dt><dd>${escapeHtml(object.dpaNotes || 'Not documented')}</dd>
          <dt>Vendor SLA</dt><dd>${escapeHtml(object.vendorSLA || 'Not documented')}</dd>
          <dt>Authentication Model</dt><dd>${escapeHtml(object.authenticationModel || 'Not documented')}</dd>
          <dt>Compliance Certs</dt><dd>${escapeHtml((object.complianceCerts || []).join(', ') || 'None documented')}</dd>
        </dl>
        ${object.incidentNotificationProcess ? `<div class="interaction-notes"><strong>Incident Notification:</strong> ${escapeHtml(object.incidentNotificationProcess)}</div>` : ''}
      </div>
    </section>
    ${requirementGroupByName('SaaS Delivery Requirement Group') ? odcRequirementsMarkup(requirementGroupByName('SaaS Delivery Requirement Group')) : ''}
  `;
}
  if (object.deliveryModel === 'paas') {
  return `
    <section class="section-card">
      <h3>PaaS Delivery</h3>
      <div class="section-stack">
        <div class="badges">
          ${paasBadge()}
          ${lifecycleBadge(object.lifecycleStatus)}
          ${catalogBadge(object.catalogStatus)}
        </div>
        <dl class="definition-list">
          <dt>Vendor</dt><dd>${escapeHtml(object.vendor || '')}</dd>
          ${object.capabilities?.length ? `<dt>Capabilities</dt><dd>${escapeHtml(object.capabilities.join(', '))}</dd>` : ''}
          <dt>Authentication Model</dt><dd>${escapeHtml(object.authenticationModel || 'Not documented')}</dd>
          <dt>Vendor SLA</dt><dd>${escapeHtml(object.vendorSLA || 'Not documented')}</dd>
          <dt>Compliance Certs</dt><dd>${escapeHtml((object.complianceCerts || []).join(', ') || 'None documented')}</dd>
        </dl>
      </div>
    </section>
    ${requirementGroupByName('PaaS Delivery Requirement Group') ? odcRequirementsMarkup(requirementGroupByName('PaaS Delivery Requirement Group')) : ''}
  `;
  }
  if (object.deliveryModel === 'appliance') {
    return `
      <section class="section-card">
        <h3>Appliance Delivery</h3>
        <div class="section-stack">
          <div class="badges">
            ${applianceBadge()}
            ${lifecycleBadge(object.lifecycleStatus)}
            ${catalogBadge(object.catalogStatus)}
          </div>
          <dl class="definition-list">
            <dt>Vendor</dt><dd>${escapeHtml(object.vendor || '')}</dd>
            ${object.capabilities?.length ? `<dt>Capabilities</dt><dd>${escapeHtml(object.capabilities.join(', '))}</dd>` : ''}
            <dt>Network Placement</dt><dd>${escapeHtml(object.networkPlacement || 'Not documented')}</dd>
            <dt>Patching Owner</dt><dd>${escapeHtml(object.patchingOwner || 'Not documented')}</dd>
            <dt>Compliance Certs</dt><dd>${escapeHtml((object.complianceCerts || []).join(', ') || 'None documented')}</dd>
          </dl>
        </div>
      </section>
      ${requirementGroupByName('Appliance Delivery Requirement Group') ? odcRequirementsMarkup(requirementGroupByName('Appliance Delivery Requirement Group')) : ''}
    `;
  }
  return '';
}

function domainDetailMarkup(object) {
  const domainCaps = object.capabilities || [];
  return `
    <section class="section-card">
      <h3>Capability Map: ${escapeHtml(object.name)}</h3>
      <div class="section-stack">
        ${domainCaps.map(cap => {
          const capId = String(cap);
          const capability = objectLookup[capId] || {};
          return `
            <article class="odc-card">
              <div class="odc-name">${capability.id ? `<span class="ard-link" data-object-link="${capability.id}">${escapeHtml(capability.name || capId)}</span>` : escapeHtml(capId)}</div>
              <div class="header-description">${escapeHtml(capability.description || '')}</div>
              <div class="interaction-notes"><strong>Lifecycle implementations:</strong></div>
              <div class="related-list">
                ${(capability.implementations || []).length ? capability.implementations.map(implementation => {
                  const implObject = objectLookup[implementation.ref] || {};
                  return `
                  <a href="#${escapeHtml(implementation.ref)}" class="related-link">
                    <span class="related-icon">${topologyNodeIcon({ref: implementation.ref}, 'host').icon}</span>
                    ${escapeHtml(implObject.name || implementation.ref)}
                    <span class="badge">${escapeHtml(implementation.lifecycleStatus || '')}</span>
                  </a>
                `}).join('') : '<div class="empty-card">No workspace implementations are mapped for this capability.</div>'}
              </div>
            </article>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

function capabilityDetailMarkup(object) {
  return `
    <section class="section-card">
      <h3>Capability</h3>
      <div class="section-stack">
        <dl class="definition-list">
          <dt>Domain</dt><dd>${object.domain && objectLookup[object.domain] ? `<span class="ard-link" data-object-link="${object.domain}">${escapeHtml(objectLookup[object.domain].name)}</span>` : escapeHtml(object.domain || 'Not documented')}</dd>
          <dt>Definition owner</dt><dd>${escapeHtml(object.definitionOwner?.team || object.definitionOwner?.provider || 'Not documented')}</dd>
          <dt>Company owner</dt><dd>${escapeHtml(object.owner?.team || 'Not assigned')}</dd>
          <dt>Implementations</dt><dd>${escapeHtml(String((object.implementations || []).length))}</dd>
        </dl>
        <div class="related-list">
          ${(object.implementations || []).length ? object.implementations.map(implementation => {
            const implObject = objectLookup[implementation.ref] || {};
            return `
              <a href="#${escapeHtml(implementation.ref)}" class="related-link">
                <span class="related-icon">${topologyNodeIcon({ref: implementation.ref}, 'host').icon}</span>
                ${escapeHtml(implObject.name || implementation.ref)}
                <span class="badge">${escapeHtml(implementation.lifecycleStatus || '')}</span>
              </a>
            `;
          }).join('') : '<div class="empty-card">No workspace implementations are mapped for this capability.</div>'}
        </div>
      </div>
    </section>
  `;
}

function instanceLabel(value) {
  return formatTitleCase(String(value || 'unnamed').replace(/\./g, ' ').replace(/_/g, ' '));
}

function shortRefLabel(ref) {
  const object = objectLookup[ref];
  if (!object) {
    return formatTitleCase((ref || '').split('.').slice(-1)[0] || 'service');
  }
  return object.name
    .replace(/\s+(Web Service|Application Service|Database Service|Service)$/i, '')
    .replace(/\s+Standard$/i, '');
}

const SOFTWARE_DEPLOYMENT_PATTERN_TIERS = ['frontend', 'application', 'data'];
const SOFTWARE_DEPLOYMENT_PATTERN_TIER_LABELS = {
  frontend: 'Frontend Services',
  application: 'Application Services',
  data: 'Data Services'
};

function isContainerHostObject(object) {
  return !!object && object.type === 'host' && String(object.id || '').startsWith('host.container.');
}

function objectIconSvg(name) {
  const icons = {
    document: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M6 2.8h8.2L18 6.6v14.6H6z"></path><path d="M14 2.8v4h4"></path><path d="M9 10h6"></path><path d="M9 13.4h6"></path><path d="M9 16.8h4"></path></svg>',
    monitor: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><rect x="3.4" y="4.4" width="17.2" height="11.8" rx="1.8"></rect><path d="M9 20h6"></path><path d="M12 16.2V20"></path><path d="M6.8 7.8h10.4"></path></svg>',
    gear: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.2"></circle><path d="M12 2.9v2.3"></path><path d="M12 18.8v2.3"></path><path d="M2.9 12h2.3"></path><path d="M18.8 12h2.3"></path><path d="M5.6 5.6l1.7 1.7"></path><path d="M16.7 16.7l1.7 1.7"></path><path d="M18.4 5.6l-1.7 1.7"></path><path d="M7.3 16.7l-1.7 1.7"></path></svg>',
    database: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><ellipse cx="12" cy="5.6" rx="7" ry="3"></ellipse><path d="M5 5.6v12.8c0 1.7 3.1 3 7 3s7-1.3 7-3V5.6"></path><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"></path></svg>',
    gateway: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M4 8h13"></path><path d="M13.5 4.5L17 8l-3.5 3.5"></path><path d="M20 16H7"></path><path d="M10.5 12.5L7 16l3.5 3.5"></path></svg>',
    cloud: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M7.6 18h9.4a4.2 4.2 0 0 0 .2-8.4 6.2 6.2 0 0 0-11.8 2A3.4 3.4 0 0 0 7.6 18z"></path></svg>',
    code: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M9.5 8.2L5.7 12l3.8 3.8"></path><path d="M14.5 8.2l3.8 3.8-3.8 3.8"></path><path d="M12.8 6.5l-1.6 11"></path></svg>',
    container: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M12 3.5l7.4 4.25v8.5L12 20.5l-7.4-4.25v-8.5z"></path><path d="M12 12l7.1-4.1"></path><path d="M12 12v8.2"></path><path d="M12 12L4.9 7.9"></path></svg>',
    wrench: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M14.7 5.3a4.6 4.6 0 0 0 4.4 6.1l-7.7 7.7a2.5 2.5 0 0 1-3.5-3.5l7.7-7.7a4.6 4.6 0 0 0-.9-2.6z"></path><path d="M7.3 17.9l-2 2"></path></svg>'
  };
  return icons[name] || icons.gear;
}

function objectIconStroke(cls) {
  if (cls === 'technology') return '#fdba74';
  if (cls === 'host' || cls === 'pod') return '#93c5fd';
  if (cls === 'runtime' || cls === 'product') return '#5eead4';
  if (cls === 'data') return '#d8b4fe';
  if (cls === 'gateway') return '#86efac';
  if (cls === 'cloud' || cls === 'appliance') return '#3a342c';
  return '#1f1a14';
}

function objectIconDataUri(svgMarkup, cls) {
  const stroke = objectIconStroke(cls);
  const source = svgMarkup.replace(
    '<svg ',
    `<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="${stroke}" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" `
  );
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(source)}`;
}

function topologyNodeIcon(entry, objectType = 'host') {
  const ref = entry.ref || '';
  const object = objectLookup[ref];
  const serviceObject = object?.type === 'product_service' && object?.runsOn ? objectLookup[object.runsOn] : object;
  if (objectType === 'appliance') {
    const caps = object?.capabilities || [];
    if (caps.some(c => ['file-storage', 'data-persistence', 'storage'].includes(c))) return { icon: objectIconSvg('database'), cls: 'data' };
    return { icon: objectIconSvg('wrench'), cls: 'appliance' };
  }
  if (object?.type === 'technology_component') return { icon: objectIconSvg('document'), cls: 'technology' };
  if (object?.type === 'host') return { icon: objectIconSvg('monitor'), cls: 'host' };
  if (object?.deliveryModel === 'saas') return { icon: objectIconSvg('cloud'), cls: 'cloud' };
  if (object?.deliveryModel === 'paas') return { icon: objectIconSvg('cloud'), cls: 'cloud' };
  if (object?.type === 'product_service' && isContainerHostObject(objectLookup[object?.runsOn])) {
    return { icon: objectIconSvg('container'), cls: 'pod' };
  }
  if (object?.type === 'product_service') return { icon: objectIconSvg('code'), cls: 'product' };
  if (object?.type === 'edge_gateway_service') return { icon: objectIconSvg('gateway'), cls: 'gateway' };
  if (serviceObject?.type === 'data_at_rest_service') return { icon: objectIconSvg('database'), cls: 'data' };
  if (serviceObject?.type === 'runtime_service') return { icon: objectIconSvg('gear'), cls: 'runtime' };
  return { icon: objectIconSvg('gear'), cls: 'runtime' };
}

function deploymentTargetPresentation(location) {
  const text = String(location || 'Unspecified');
  if (/AWS/i.test(text)) {
    return { cls: 'aws', badge: 'AWS', icon: objectIconSvg('cloud') };
  }
  if (/Datacenter|\bDC\b/i.test(text)) {
    return { cls: 'datacenter', badge: 'DC', icon: objectIconSvg('cloud') };
  }
  return { cls: 'generic', badge: 'Host', icon: objectIconSvg('monitor') };
}

function detailNodeVisual(object) {
  const icon = topologyNodeIcon({ref: object.id});
  return {
    image: objectIconDataUri(icon.icon, icon.cls),
    borderColor: object.color || '#e7e1d6'
  };
}

function colorForToken(value) {
  const palette = ['#7c3a6b', '#22c55e', '#f59e0b', '#a855f7', '#ef4444', '#14b8a6', '#e879f9', '#64748b'];
  const token = String(value || '');
  let hash = 0;
  for (let index = 0; index < token.length; index += 1) {
    hash = ((hash << 5) - hash) + token.charCodeAt(index);
    hash |= 0;
  }
  return palette[Math.abs(hash) % palette.length];
}

function entryDiagramTier(entry) {
  // Legacy helper for reference_architecture topology view — reads networkZone tier from lookup
  const zoneTier = entry?._zoneTier;
  return SOFTWARE_DEPLOYMENT_PATTERN_TIERS.includes(zoneTier) ? zoneTier : 'application';
}

function supportEntryTier(entry, objectType) {
  const object = objectLookup[entry?.ref];
  const capability = object?.capability || '';
  if (objectType === 'appliance') {
    if (capability === 'load-balancing') return 'presentation';
    if (['file-storage', 'data-persistence'].includes(capability)) return 'data';
    return 'utility';
  }
  if (object?.type === 'data_at_rest_service') return 'data';
  if (object?.type === 'edge_gateway_service') return 'presentation';
  return 'utility';
}

function entryLabel(entry) {
  if (entry?.instance) return instanceLabel(entry.instance);
  const object = objectLookup[entry?.ref];
  return object?.name || instanceLabel(entry?.ref);
}

function topologyBadgeMarkup(entry) {
  if (!entry) return '';
  const ard = entry.riskRef ? objectLookup[entry.riskRef] : null;
  if (entry.riskRef) {
    if (ard) {
      const isDecision = ard.ardCategory === 'decision' && ard.status === 'accepted';
      const cls = isDecision ? 'topology-info' : 'topology-risk';
      const symbol = isDecision ? 'ⓘ' : '⚠';
      return `<span class="${cls}" data-object-link="${ard.id}" title="${escapeHtml(ard.name)}">${symbol}</span>`;
    }
    return '<span class="topology-risk" title="Missing Decision Record reference">?</span>';
  }
  if (String(entry.intent || '').toLowerCase() === 'sa') {
    return '<span class="topology-info" title="Explicit architecture decision">ⓘ</span>';
  }
  return '';
}

function topologyNodeMarkup(entry, options = {}) {
  const {
    objectType = 'host',
    overrideLabel = null,
    meta = '',
    intent = entry.intent || '',
    badgeLabel = '',
    scalingUnit = '',
  } = options;
  const icon = topologyNodeIcon(entry, objectType);
  const targetId = entry.ref || '';
  const classes = ['topology-node'];
  if (objectType === 'product') classes.push('ps-node');
  if (objectType === 'host') classes.push('rbb-node');
  if (objectType === 'appliance') classes.push('appliance-node');
  if (objectType === 'paas') classes.push('cloud');
  if (objectType === 'saas') classes.push('saas-node');
  if (icon.cls) classes.push(icon.cls);
  return `
    <article class="${classes.join(' ')}" ${targetId && objectLookup[targetId] ? `data-object-link="${escapeHtml(targetId)}"` : ''} ${scalingUnit ? `data-scaling-unit="${escapeHtml(scalingUnit)}"` : ''}>
      ${topologyBadgeMarkup(entry)}
      <div class="topology-node-flags">
        ${badgeLabel ? `<span class="ps-corner">${escapeHtml(badgeLabel)}</span>` : '<span></span>'}
        ${intent ? intentBadge(intent) : '<span></span>'}
      </div>
      <span class="topology-node-icon ${icon.cls}">${icon.icon}</span>
      <div class="topology-node-label">${escapeHtml(overrideLabel || entryLabel(entry))}</div>
      ${meta ? `<div class="topology-node-meta">${escapeHtml(meta)}</div>` : ''}
    </article>
  `;
}

function serviceGroupSectionMarkup(group, tier) {
  const scalingUnit = group.scalingUnit || '';
  const accent = colorForToken(scalingUnit || group.name || tier);
  const groupMeta = [
    group.deploymentTarget || 'Unspecified deployment target',
    scalingUnit || 'No scaling unit'
  ].join(' • ');
  const topologyNodes = [];

  (group.deployableObjects || [])
    .filter(entry => entryDiagramTier(entry) === tier)
    .forEach(entry => {
      const target = objectLookup[entry.ref] || {};
      const deliveryModel = target.deliveryModel || '';
      const objectType = target.type === 'product_service'
        ? 'product'
        : (deliveryModel === 'paas' ? 'paas' : (deliveryModel === 'saas' ? 'saas' : (deliveryModel === 'appliance' ? 'appliance' : 'host')));
      const badgeLabel = target.type === 'product_service'
        ? 'PS'
        : (deliveryModel === 'paas' ? 'PaaS' : (deliveryModel === 'saas' ? 'SaaS' : (deliveryModel === 'appliance' ? 'APPL' : '')));
      topologyNodes.push(topologyNodeMarkup(entry, {
        objectType,
        badgeLabel,
        scalingUnit,
        meta: `${group.name} • ${groupMeta}`
      }));
    });

  if (!topologyNodes.length) {
    return '';
  }

  const internalInteractions = (group.externalInteractions || []).filter(item => (item.type || 'external') === 'internal');
  const externalInteractions = (group.externalInteractions || []).filter(item => (item.type || 'external') !== 'internal');

  return `
    <section class="service-group-section" style="--scaling-accent:${accent}" ${scalingUnit ? `data-scaling-unit-group="${escapeHtml(scalingUnit)}"` : ''}>
      <div class="service-group-section-header">
        <div class="service-group-section-title">${escapeHtml(group.name || 'Unnamed Service Group')}</div>
        <div class="service-group-section-meta">
          <span class="location-badge">${escapeHtml(tier)}</span>
          ${scalingUnit ? `<span class="scaling-unit-badge">${escapeHtml(scalingUnit)}</span>` : '<span class="scaling-unit-badge">unscoped</span>'}
        </div>
      </div>
      <div class="node-grid">
        ${topologyNodes.join('')}
      </div>
      ${(internalInteractions.length || externalInteractions.length) ? `
        <div class="service-group-support">
          ${internalInteractions.map(interaction => `<div class="topology-internal-link">${escapeHtml(interaction.name || 'Internal interaction')} → ${escapeHtml(interaction.ref || 'unknown')}</div>`).join('')}
          ${externalInteractions.map(interaction => `<div class="topology-internal-link">${escapeHtml(interaction.name || 'External interaction')} • ${escapeHtml(interaction.capability || 'other')}</div>`).join('')}
        </div>
      ` : ''}
    </section>
  `;
}

function tierColumnsMarkup(groups) {
  const columns = Object.fromEntries(SOFTWARE_DEPLOYMENT_PATTERN_TIERS.map(tier => [tier, []]));
  groups.forEach(group => {
    SOFTWARE_DEPLOYMENT_PATTERN_TIERS.forEach(tier => {
      const markup = serviceGroupSectionMarkup(group, tier);
      if (markup) {
        columns[tier].push(markup);
      }
    });
  });
  return `
    <div class="deployment-target-columns">
      ${SOFTWARE_DEPLOYMENT_PATTERN_TIERS.map(tier => `
        <section class="topology-tier-column">
          <div class="topology-tier-header ${escapeHtml(tier)}">${escapeHtml(SOFTWARE_DEPLOYMENT_PATTERN_TIER_LABELS[tier])}</div>
          <div class="topology-column-stack">
            ${columns[tier].join('') || `<div class="empty-card">No ${escapeHtml(tier)} services.</div>`}
          </div>
        </section>
      `).join('')}
    </div>
  `;
}

const SDP_GRAPH_PROTOCOL_COLORS = {
  REST:      '#2a6fdb',
  gRPC:      '#7c3a6b',
  AMQP:      '#c47a14',
  JDBC:      '#1f8a5b',
  SQL:       '#1f8a5b',
  WebSocket: '#0e6b62',
  HTTPS:     '#2a6fdb',
  GraphQL:   '#b93a3a',
  other:     '#7a6e60',
};

const SDP_GRAPH_TIER_COLORS = {
  presentation: '#f97316',
  application:  '#14b8a6',
  data:         '#3b82f6',
  utility:      '#a855f7',
  unknown:      '#64748b',
};

function buildSdpGraphElements(object) {
  const connections = object.sdpConnections || [];
  const zones = object.networkZones || [];
  const zoneIds = new Set(zones.map(z => z.id));

  // Collect all UIDs that appear in connections
  const referencedUids = new Set();
  connections.forEach(conn => {
    referencedUids.add(conn.from);
    referencedUids.add(conn.to);
  });

  // Fall back to all deployable objects if no connections recorded
  const allDeployableUids = new Set();
  (object.serviceGroups || []).forEach(group => {
    (group.deployableObjects || []).forEach(entry => {
      if (entry.ref) allDeployableUids.add(entry.ref);
    });
  });
  const nodeUids = referencedUids.size > 0 ? referencedUids : allDeployableUids;

  // Build a zone membership map from deployableObjectEntry.networkZone
  const uidToZone = {};
  (object.serviceGroups || []).forEach(group => {
    (group.deployableObjects || []).forEach(entry => {
      if (entry.ref && entry.networkZone) {
        uidToZone[entry.ref] = entry.networkZone;
      }
    });
  });

  // Build a tier map
  const uidToTier = {};
  (object.serviceGroups || []).forEach(group => {
    (group.deployableObjects || []).forEach(entry => {
      if (entry.ref && entry.diagramTier) {
        uidToTier[entry.ref] = entry.diagramTier;
      }
    });
  });

  const elements = [];

  // Compound zone parent nodes
  if (zones.length) {
    zones.forEach(zone => {
      elements.push({
        data: { id: `zone::${zone.id}`, label: zone.name || zone.id, isZone: true },
        classes: 'zone-compound'
      });
    });
  }

  // Service nodes
  nodeUids.forEach(uid => {
    const obj = objectLookup[uid];
    const tier = uidToTier[uid] || (obj ? (obj.diagramTier || 'unknown') : 'unknown');
    const zoneMembership = uidToZone[uid];
    const nodeData = {
      id: uid,
      label: obj ? obj.name : uid,
      tier,
      nodeColor: SDP_GRAPH_TIER_COLORS[tier] || SDP_GRAPH_TIER_COLORS.unknown,
    };
    if (zoneMembership && zoneIds.has(zoneMembership)) {
      nodeData.parent = `zone::${zoneMembership}`;
    }
    elements.push({ data: nodeData, classes: `tier-${tier}` });
  });

  // Edge elements
  connections.forEach((conn, index) => {
    const edgeColor = SDP_GRAPH_PROTOCOL_COLORS[conn.protocol] || SDP_GRAPH_PROTOCOL_COLORS.other;
    const edgeLabel = conn.protocol || '';
    elements.push({
      data: {
        id: `edge-${index}-${conn.from}-${conn.to}`,
        source: conn.from,
        target: conn.to,
        label: edgeLabel,
        protocol: conn.protocol,
        direction: conn.direction || 'outbound',
        edgeColor,
      },
      classes: `protocol-${(conn.protocol || 'other').toLowerCase()}`
    });
  });

  return elements;
}

let sdpGraphCy = null;

function destroySdpGraphCy() {
  if (sdpGraphCy) {
    sdpGraphCy.destroy();
    sdpGraphCy = null;
  }
  _sdpTeardown();
}

function renderSdpGraph(object) {
  const container = document.getElementById('sdp-graph-cy');
  if (!container || sdpGraphCy) return;

  const elements = buildSdpGraphElements(object);
  if (!elements.length) return;

  const protocolsPresent = [...new Set(
    (object.sdpConnections || []).map(c => c.protocol).filter(Boolean)
  )];

  // Build legend
  const legendEl = document.getElementById('sdp-graph-legend');
  if (legendEl) {
    const tierItems = Object.entries(SDP_GRAPH_TIER_COLORS)
      .filter(([tier]) => tier !== 'unknown')
      .map(([tier, color]) => `
        <span class="sdp-graph-legend-item">
          <span class="sdp-graph-legend-swatch" style="background:${color}"></span>
          ${escapeHtml(tier)}
        </span>
      `).join('');
    const protocolItems = protocolsPresent.map(protocol => {
      const color = SDP_GRAPH_PROTOCOL_COLORS[protocol] || SDP_GRAPH_PROTOCOL_COLORS.other;
      return `
        <span class="sdp-graph-legend-item">
          <span class="sdp-graph-legend-swatch" style="background:${color}"></span>
          ${escapeHtml(protocol)}
        </span>
      `;
    }).join('');
    legendEl.innerHTML = `<strong style="color:var(--subtle);margin-right:4px">Tiers:</strong>${tierItems}` +
      (protocolItems ? `<strong style="color:var(--subtle);margin-left:12px;margin-right:4px">Protocols:</strong>${protocolItems}` : '');
  }

  sdpGraphCy = cytoscape({
    container,
    elements,
    style: [
      {
        selector: 'node[!isZone]',
        style: {
          'background-color': 'data(nodeColor)',
          'label': 'data(label)',
          'color': '#1f1a14',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '11px',
          'font-family': '"SF Pro Display","Segoe UI",sans-serif',
          'text-wrap': 'wrap',
          'text-max-width': '110px',
          'width': '120px',
          'height': '44px',
          'shape': 'round-rectangle',
          'border-width': 1,
          'border-color': 'rgba(31,26,20,0.18)',
          'padding': '8px',
        }
      },
      {
        selector: 'node.zone-compound',
        style: {
          'background-color': 'rgba(231,225,214,0.35)',
          'background-opacity': 1,
          'border-style': 'dashed',
          'border-width': 2,
          'border-color': 'rgba(122,110,96,0.5)',
          'label': 'data(label)',
          'color': '#7a6e60',
          'text-valign': 'top',
          'text-halign': 'center',
          'font-size': '12px',
          'font-weight': '700',
          'text-margin-y': '10px',
          'padding': '24px',
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': 'data(edgeColor)',
          'target-arrow-color': 'data(edgeColor)',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '10px',
          'color': '#7a6e60',
          'text-background-color': '#ffffff',
          'text-background-opacity': 0.85,
          'text-background-padding': '2px',
          'edge-text-rotation': 'autorotate',
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 3,
          'border-color': '#7c3a6b',
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'width': 3,
          'line-color': '#7c3a6b',
          'target-arrow-color': '#7c3a6b',
        }
      }
    ],
    layout: {
      name: 'cose',
      animate: false,
      randomize: false,
      nodeRepulsion: () => 8000,
      idealEdgeLength: () => 120,
      edgeElasticity: () => 100,
      gravity: 0.5,
      numIter: 1000,
      fit: true,
      padding: 30,
    }
  });

  // Click node to navigate to object detail
  sdpGraphCy.on('tap', 'node[!isZone]', event => {
    const uid = event.target.id();
    if (objectLookup[uid]) {
      destroySdpGraphCy();
      showDetailView(uid);
    }
  });
}

function renderDeploymentTopology(object) {
  const serviceGroups = object.serviceGroups || [];

  if (!serviceGroups.length) {
    return `
      <div class="topology-layout">
        <div class="empty-card">No topology data is available for this object.</div>
      </div>
    `;
  }

  const scalingUnits = [...new Set(serviceGroups.map(group => group.scalingUnit).filter(Boolean))];
  const topologyToolbar = object.type === 'software_deployment_pattern' ? `
    <div class="topology-toolbar">
      <div class="topology-filter-buttons">
        <button class="topology-filter-button ${currentSdmScalingFilter === 'all' ? 'active' : ''}" data-scaling-filter="all">All scaling units</button>
        ${scalingUnits.map(unit => `<button class="topology-filter-button ${currentSdmScalingFilter === unit ? 'active' : ''}" data-scaling-filter="${escapeHtml(unit)}">${escapeHtml(unit)}</button>`).join('')}
      </div>
      <div class="topology-filter-help">Select a scaling unit to highlight participating services.</div>
    </div>
  ` : '';

  return `
    <div class="topology-layout">
      ${topologyToolbar}
      <div class="topology-scaling-units">
        ${tierColumnsMarkup(serviceGroups)}
      </div>
    </div>
  `;
}

function ardDetailMarkup(object) {
  return `
    <section class="ard-detail-card">
      <h2 class="ard-detail-title">${escapeHtml(object.name)}</h2>
      <div class="ard-meta">
        <span>${escapeHtml(object.id)}</span>
        ${ardCategoryBadge(object.ardCategory)}
        ${ardStatusBadge(object.status)}
        ${object.linkedSoftwareDeployment && objectLookup[object.linkedSoftwareDeployment] ? `<span>Linked Software Deployment Pattern: <span class="ard-link" data-object-link="${object.linkedSoftwareDeployment}">${escapeHtml(object.linkedSoftwareDeployment)}</span></span>` : object.linkedSoftwareDeployment ? `<span>Linked Software Deployment Pattern: ${escapeHtml(object.linkedSoftwareDeployment)}</span>` : ''}
      </div>
      <section class="ard-section">
        <h3>Description</h3>
        <p>${escapeHtml(object.description || '')}</p>
      </section>
      <section class="ard-section">
        <h3>Affected Component</h3>
        <div>${escapeHtml(object.affectedComponent || '')}</div>
      </section>
      <section class="ard-section">
        <h3>Impact</h3>
        <p>${escapeHtml(object.impact || '')}</p>
      </section>
      ${object.mitigationPath ? `
        <section class="ard-section">
          <h3>Mitigation Path</h3>
          <p>${escapeHtml(object.mitigationPath)}</p>
        </section>
      ` : ''}
      ${object.decisionRationale ? `
        <section class="ard-section">
          <h3>Decision Rationale</h3>
          <p>${escapeHtml(object.decisionRationale)}</p>
        </section>
      ` : ''}
      ${(object.relatedDecisionRecords || []).length ? `
        <section class="ard-section">
          <h3>Related Decision Records</h3>
          <div class="section-stack">
            ${object.relatedDecisionRecords.map(ardId => objectLookup[ardId]
              ? `<span class="ard-link" data-object-link="${ardId}">${escapeHtml(ardId)}</span>`
              : `<span>${escapeHtml(ardId)}</span>`
            ).join('')}
          </div>
        </section>
      ` : ''}
    </section>
  `;
}

function draftingSessionDetailMarkup(object) {
  const generatedObjects = object.generatedObjects || [];
  const unresolvedQuestions = object.unresolvedQuestions || [];
  const assumptions = object.assumptions || [];
  const nextSteps = object.nextSteps || [];
  const sourceArtifacts = object.sourceArtifacts || [];
  const primaryObject = object.primaryObjectUid && objectLookup[object.primaryObjectUid] ? objectLookup[object.primaryObjectUid] : null;

  return `
    <section class="section-card">
      <h3>Session Scope</h3>
      <dl class="definition-list">
        <dt>Session Status</dt>
        <dd>${escapeHtml(object.sessionStatus || 'unknown')}</dd>
        <dt>Primary Object Type</dt>
        <dd>${escapeHtml(object.primaryObjectType || 'unknown')}</dd>
        <dt>Primary Object</dt>
        <dd>${primaryObject ? `<span class="ard-link" data-object-link="${primaryObject.id}">${escapeHtml(primaryObject.name)}</span>` : escapeHtml(object.primaryObjectUid || 'Not created yet')}</dd>
      </dl>
    </section>
    <section class="section-card">
      <h3>Source Artifacts</h3>
      <div class="section-stack">
        ${sourceArtifacts.length ? sourceArtifacts.map(source => `
          <article class="odc-card">
            <div class="odc-name">${escapeHtml(source.name || 'Unnamed source')}</div>
            <div class="interaction-notes">${escapeHtml(source.type || 'source')}</div>
            ${source.location ? `<div class="object-id">${escapeHtml(source.location)}</div>` : ''}
            ${source.notes ? `<div class="interaction-notes">${escapeHtml(source.notes)}</div>` : ''}
          </article>
        `).join('') : '<div class="empty-card">No source artifacts are recorded for this session.</div>'}
      </div>
    </section>
    <section class="section-card">
      <h3>Generated Objects</h3>
      <div class="section-stack">
        ${generatedObjects.length ? generatedObjects.map(entry => `
          <article class="odc-card">
            <div class="odc-name">${escapeHtml(entry.name || 'Generated object')}</div>
            <div class="interaction-notes">${escapeHtml(entry.type || 'unknown')} / ${escapeHtml(entry.status || 'unknown')}</div>
            ${entry.ref && objectLookup[entry.ref] ? `<div class="object-id"><span class="ard-link" data-object-link="${entry.ref}">${escapeHtml(objectLookup[entry.ref].name)}</span></div>` : entry.ref ? `<div class="object-id">${escapeHtml(entry.ref)}</div>` : entry.proposedUid ? `<div class="object-id">${escapeHtml(entry.proposedUid)}</div>` : ''}
            ${entry.notes ? `<div class="interaction-notes">${escapeHtml(entry.notes)}</div>` : ''}
          </article>
        `).join('') : '<div class="empty-card">No generated objects are recorded for this session.</div>'}
      </div>
    </section>
    <section class="section-card">
      <h3>Unresolved Questions</h3>
      <div class="section-stack">
        ${unresolvedQuestions.length ? unresolvedQuestions.map(item => `
          <article class="decision-card">
            <h4>${escapeHtml(item.id || 'question')}</h4>
            <p>${escapeHtml(item.question || '')}</p>
            <dl class="definition-list">
              <dt>Status</dt>
              <dd>${escapeHtml(item.status || 'open')}</dd>
              ${item.reason ? `<dt>Reason</dt><dd>${escapeHtml(item.reason)}</dd>` : ''}
              ${item.currentBestGuess ? `<dt>Current Best Guess</dt><dd>${escapeHtml(item.currentBestGuess)}</dd>` : ''}
              ${item.impact ? `<dt>Impact</dt><dd>${escapeHtml(item.impact)}</dd>` : ''}
            </dl>
            ${(item.relatedObjects || []).length ? `<div class="section-stack">${item.relatedObjects.map(refEntry => refEntry.ref && objectLookup[refEntry.ref] ? `<span class="ard-link" data-object-link="${refEntry.ref}">${escapeHtml(refEntry.ref)}</span>` : refEntry.ref ? `<span>${escapeHtml(refEntry.ref)}</span>` : '').join('')}</div>` : ''}
          </article>
        `).join('') : '<div class="empty-card">No unresolved questions are recorded for this session.</div>'}
      </div>
    </section>
    <section class="middle-grid">
      <div class="section-card">
        <h3>Assumptions</h3>
        <div class="section-stack">
          ${assumptions.length ? assumptions.map(item => `
            <article class="decision-card">
              <h4>${escapeHtml(item.id || 'assumption')}</h4>
              <p>${escapeHtml(item.statement || '')}</p>
              ${item.rationale ? `<div class="interaction-notes">${escapeHtml(item.rationale)}</div>` : ''}
              ${item.impact ? `<div class="interaction-notes">${escapeHtml(item.impact)}</div>` : ''}
            </article>
          `).join('') : '<div class="empty-card">No assumptions are recorded for this session.</div>'}
        </div>
      </div>
      <div class="section-card">
        <h3>Next Steps</h3>
        <div class="section-stack">
          ${nextSteps.length ? nextSteps.map(item => `
            <article class="decision-card">
              <h4>${escapeHtml(item.id || 'next-step')}</h4>
              <p>${escapeHtml(item.action || '')}</p>
              <dl class="definition-list">
                <dt>Status</dt>
                <dd>${escapeHtml(item.status || 'open')}</dd>
                ${item.owner ? `<dt>Owner</dt><dd>${escapeHtml(item.owner)}</dd>` : ''}
                ${item.notes ? `<dt>Notes</dt><dd>${escapeHtml(item.notes)}</dd>` : ''}
              </dl>
            </article>
          `).join('') : '<div class="empty-card">No next steps are recorded for this session.</div>'}
        </div>
      </div>
    </section>
  `;
}

function usedByMarkup(object) {
  const inbound = object.referencedBy || [];
  if (!inbound.length) {
    return '';
  }
  return `
    <section class="section-card">
      <h3>Used By</h3>
      <div class="section-stack">
        ${inbound.map(reference => {
          const source = objectLookup[reference.source];
          return `
            <article class="odc-card">
              <div class="odc-name">
                ${source ? `<span class="ard-link" data-object-link="${source.id}">${escapeHtml(source.name)}</span>` : escapeHtml(reference.source)}
              </div>
              <div class="object-id">${escapeHtml(reference.source)}</div>
              <div class="interaction-notes">${escapeHtml(reference.path || '')}</div>
            </article>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

function detailDisclosureMarkup(title, bodyMarkup) {
  const content = String(bodyMarkup || '').trim();
  if (!content) {
    return '';
  }
  return `
    <details class="detail-disclosure">
      <summary>${escapeHtml(title)}</summary>
      <div class="detail-disclosure-content">
        ${content}
      </div>
    </details>
  `;
}

function secondaryDetailMarkup(sections) {
  const content = sections
    .map(section => detailDisclosureMarkup(section.title, section.body))
    .filter(Boolean)
    .join('');
  if (!content) {
    return '';
  }
  return `<section class="detail-disclosures">${content}</section>`;
}

function referencesMarkup(object) {
  return secondaryDetailMarkup([
    { title: 'References', body: usedByMarkup(object) }
  ]);
}

function architectureDetailMarkup(componentSource, interactionSource, decisionSource, emptyInteractionText, emptyDecisionText) {
  return `
    <section class="middle-grid">
      <div class="section-card">
        <h3>Internal Components</h3>
        <div id="detail-cy"></div>
        ${componentSource ? internalComponentNetworkMarkup(componentSource) : ''}
        ${componentSource ? internalComponentSummaryMarkup(componentSource) : ''}
      </div>
      <div class="section-card">
        <h3>External Interactions</h3>
        ${interactionSource ? interactionMarkup(interactionSource) : `<div class="empty-card">${escapeHtml(emptyInteractionText || 'No external interactions are documented for this object.')}</div>`}
      </div>
    </section>
    <section class="decisions-card">
      <h3>Architecture Decisions</h3>
      ${decisionSource ? decisionMarkup(decisionSource) : `<div class="empty-card">${escapeHtml(emptyDecisionText || 'No architectural decisions are documented for this object.')}</div>`}
    </section>
  `;
}

function genericObjectMarkup(object) {
  const detail = JSON.parse(object.detail || '{}');
  const rows = Object.entries(detail)
    .filter(([key]) => !key.startsWith('_'))
    .map(([key, value]) => {
      const rendered = typeof value === 'object' ? JSON.stringify(value) : String(value);
      return `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(rendered)}</dd>`;
    })
    .join('');
  return `
    <section class="section-card">
      <h3>Object Data</h3>
      <dl class="definition-list">
        ${rows}
      </dl>
    </section>
  `;
}

function attachObjectLinkHandlers(root = document) {
  root.querySelectorAll('[data-object-link]').forEach(link => {
    link.addEventListener('click', event => {
      event.stopPropagation();
      showDetailView(link.dataset.objectLink);
    });
  });
}

function sanitizeDetailObject(object) {
  const raw = JSON.parse(object.detail || '{}');
  const cleaned = {};
  Object.entries(raw).forEach(([key, value]) => {
    if (!key.startsWith('_')) {
      cleaned[key] = value;
    }
  });
  return cleaned;
}

function repoSourceUrl(object) {
  return repoUrl && object.source ? `${repoUrl}/blob/main/${object.source}` : '';
}

function orderedEditorFields(object) {
  const schema = object.editorSchema || {};
  const required = schema.requiredFields || [];
  const optional = schema.optionalFields || [];
  const priority = ['schemaVersion', 'uid', 'type', 'name', 'aliases', 'description', 'version', 'catalogStatus', 'lifecycleStatus', 'definitionOwner', 'owner', 'tags'];
  const ordered = [];
  const seen = new Set();
  [...priority, ...required, ...optional, ...Object.keys(sanitizeDetailObject(object))].forEach(field => {
    if (!field || field.startsWith('_') || seen.has(field)) return;
    seen.add(field);
    ordered.push(field);
  });
  return ordered;
}

function yamlFieldValue(value) {
  if (value === undefined || value === null) return '';
  if (typeof value === 'string') return value;
  return jsyaml.dump(value, { lineWidth: 100 }).trim();
}

function fieldInputMarkup(object, field, value) {
  const schema = object.editorSchema || {};
  const required = new Set(schema.requiredFields || []);
  const fieldTypes = schema.fieldTypes || {};
  const enumFields = schema.enumFields || {};
  const enumListFields = schema.enumListFields || {};
  const expectedType = fieldTypes[field] || '';
  const label = formatKeyLabel(field);
  const requiredText = required.has(field) ? '<span class="editor-required">*</span>' : '';

  if (expectedType === 'bool' || typeof value === 'boolean') {
    return `
      <div class="editor-field">
        <label>${escapeHtml(label)}${requiredText}</label>
        <label class="editor-checkbox">
          <input type="checkbox" data-editor-field="${escapeHtml(field)}" ${value ? 'checked' : ''}>
          <span>${escapeHtml(label)}</span>
        </label>
      </div>
    `;
  }

  if (enumFields[field]) {
    const options = ['<option value=""></option>']
      .concat(enumFields[field].map(option => `<option value="${escapeHtml(option)}" ${value === option ? 'selected' : ''}>${escapeHtml(option)}</option>`));
    return `
      <div class="editor-field">
        <label for="editor-${escapeHtml(field)}">${escapeHtml(label)}${requiredText}</label>
        <select id="editor-${escapeHtml(field)}" data-editor-field="${escapeHtml(field)}">
          ${options.join('')}
        </select>
      </div>
    `;
  }

  if (expectedType === 'dict' || expectedType === 'list' || enumListFields[field] || Array.isArray(value) || (value && typeof value === 'object')) {
    return `
      <div class="editor-field">
        <label for="editor-${escapeHtml(field)}">${escapeHtml(label)}${requiredText}</label>
        <textarea id="editor-${escapeHtml(field)}" data-editor-field="${escapeHtml(field)}" data-editor-complex="true">${escapeHtml(yamlFieldValue(value))}</textarea>
        <div class="editor-help">Edit structured values carefully.</div>
      </div>
    `;
  }

  const stringValue = value === undefined || value === null ? '' : String(value);
  const multiline = stringValue.length > 120 || stringValue.includes('\\n') || field === 'description' || field === 'notes';
  return multiline ? `
    <div class="editor-field">
      <label for="editor-${escapeHtml(field)}">${escapeHtml(label)}${requiredText}</label>
      <textarea id="editor-${escapeHtml(field)}" data-editor-field="${escapeHtml(field)}">${escapeHtml(stringValue)}</textarea>
    </div>
  ` : `
    <div class="editor-field">
      <label for="editor-${escapeHtml(field)}">${escapeHtml(label)}${requiredText}</label>
      <input id="editor-${escapeHtml(field)}" type="text" value="${escapeHtml(stringValue)}" data-editor-field="${escapeHtml(field)}">
    </div>
  `;
}

function serializeEditorObject(object, fieldValues) {
  const schema = object.editorSchema || {};
  const fieldTypes = schema.fieldTypes || {};
  const enumListFields = schema.enumListFields || {};
  const result = {};
  orderedEditorFields(object).forEach(field => {
    let value = fieldValues[field];
    const expectedType = fieldTypes[field] || '';
    if (value === undefined) return;
    if (typeof value === 'string') {
      if (expectedType === 'dict' || expectedType === 'list' || enumListFields[field]) {
        const trimmed = value.trim();
        if (!trimmed) return;
        result[field] = jsyaml.load(trimmed);
        return;
      }
      const trimmed = value.trim();
      if (!trimmed && field !== 'description') return;
      result[field] = value;
      return;
    }
    if (value === null) return;
    result[field] = value;
  });
  return result;
}

function updateEditorPreview(object) {
  const errorNode = editorOverlay.querySelector('#editor-error');
  const previewNode = editorOverlay.querySelector('#editor-structured-preview');
  if (!editorState || !errorNode || !previewNode) return;
  try {
    const serialized = serializeEditorObject(object, editorState.fieldValues);
    editorState.serialized = serialized;
    previewNode.textContent = jsyaml.dump(serialized, { lineWidth: 100, noRefs: true });
    errorNode.textContent = '';
  } catch (error) {
    editorState.serialized = null;
    previewNode.textContent = '';
    errorNode.textContent = error instanceof Error ? error.message : String(error);
  }
}

function blankApplicabilityClause() {
  return { field: '', operator: 'equals', value: '', valuesText: '', truthy: 'true' };
}

function normalizeApplicabilityClause(clause) {
  if (!clause || typeof clause !== 'object') {
    return blankApplicabilityClause();
  }
  if (Object.prototype.hasOwnProperty.call(clause, 'truthy')) {
    return {
      field: String(clause.field || ''),
      operator: 'truthy',
      value: '',
      valuesText: '',
      truthy: clause.truthy === false ? 'false' : 'true'
    };
  }
  if (Array.isArray(clause.in)) {
    return {
      field: String(clause.field || ''),
      operator: 'in',
      value: '',
      valuesText: clause.in.map(value => String(value)).join(', '),
      truthy: 'true'
    };
  }
  if (Object.prototype.hasOwnProperty.call(clause, 'contains')) {
    return {
      field: String(clause.field || ''),
      operator: 'contains',
      value: String(clause.contains || ''),
      valuesText: '',
      truthy: 'true'
    };
  }
  return {
    field: String(clause.field || ''),
    operator: 'equals',
    value: String(clause.equals || ''),
    valuesText: '',
    truthy: 'true'
  };
}

function showDetailView(id, pushHistory = true) {
  if (pushHistory && currentDetailId) {
    navHistory.push(currentDetailId);
  }
  currentDetailId = id;
  destroyImpactCy();
  renderDetailView();
}

// ═══════════════════════════════════════════════════════════════════════════════
// SDP Detail — scrolling layout with topology overlay, section nav, drawer
// ═══════════════════════════════════════════════════════════════════════════════

const _SDP_TIER_ORDER  = ['frontend', 'application', 'data'];
const _SDP_TIER_LABELS = { frontend: 'Frontend', application: 'Application', data: 'Data' };

// Per-render mutable state — reset on each new SDP detail render
let _sdpActive = null, _sdpHover = null, _sdpDrawer = null;
let _sdpTierFilter = 'all';
let _sdpResizeObs = null, _sdpSectionObs = null;
let _sdpCardRefs = {};

function _sdpTeardown() {
  if (_sdpResizeObs) { _sdpResizeObs.disconnect(); _sdpResizeObs = null; }
  if (_sdpSectionObs) { _sdpSectionObs.disconnect(); _sdpSectionObs = null; }
  _sdpActive = null; _sdpHover = null; _sdpDrawer = null;
  _sdpTierFilter = 'all'; _sdpCardRefs = {};
}

// ── View-model builder ────────────────────────────────────────────────────────
function _sdpBuildVM(object) {
  // Build zone→tier lookup from declared networkZones
  const zones = object.networkZones || [];
  const zoneToTier = {};
  zones.forEach(z => { if (z.tier) zoneToTier[z.id] = z.tier; });

  const members = [];
  (object.serviceGroups || []).forEach(sg => {
    (sg.deployableObjects || []).forEach(e => {
      const zone = e.networkZone || '';
      const tier = zoneToTier[zone] || 'application';
      members.push({
        ref: e.ref, tier, zone,
        intent: e.intent || 'sa', notes: e.notes || '', group: sg.name,
        riskRef: e.riskRef || null
      });
    });
  });
  const byZone = {};
  zones.forEach(z => (byZone[z.id] = { zone: z, tiers: {} }));
  members.forEach(m => {
    if (!byZone[m.zone]) byZone[m.zone] = { zone: { id: m.zone, name: m.zone, description: '' }, tiers: {} };
    const zt = byZone[m.zone].tiers;
    if (!zt[m.tier]) zt[m.tier] = [];
    zt[m.tier].push(m);
  });
  const connections = object.sdpConnections || [];
  const uidToZone = {};
  members.forEach(m => (uidToZone[m.ref] = m.zone));
  // activeZones: only zones that have at least one service (matches topology render logic)
  const activeZones = zones.filter(z => {
    const zt = byZone[z.id]?.tiers || {};
    return Object.values(zt).reduce((s, a) => s + a.length, 0) > 0;
  });
  return { members, zones, activeZones, byZone, connections, uidToZone };
}

// ── Lifecycle badge (SDP scoped) ──────────────────────────────────────────────
function _sdpLifecycleBadge(status) {
  const labels = {
    preferred: 'Preferred', 'existing-only': 'Existing Only',
    deprecated: 'Deprecated', retired: 'Retired',
    candidate: 'Candidate', unknown: 'Unknown'
  };
  const cls = status === 'existing-only' ? 'existing-only' : (status || 'unknown');
  return `<span class="lifecycle ${escapeHtml(cls)}">`
    + `<span class="dot"></span>${escapeHtml(labels[status] || status || 'Unknown')}</span>`;
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function _sdpHeroMarkup(object) {
  const d = object.architecturalDecisions || {};
  const fd = d.failureDomain || {};
  const owner = object.owner || {};
  const bc = object.businessContext || {};
  const pillarLabel = bc.pillarLabel || (bc.pillar || '').split('.').pop() || '';
  return `
<div class="sdp-hero">
  <div>
    <div class="hero-type"><span class="dot"></span>Software Deployment Pattern</div>
    <h1>${escapeHtml(object.name || '')}</h1>
    <div class="hero-id-row">
      <span class="hero-uid">${escapeHtml(object.id || object.uid || '')}</span>
      ${object.version ? `<span class="hero-version">v${escapeHtml(String(object.version))}</span>` : ''}
      ${_sdpLifecycleBadge(object.lifecycleStatus)}
    </div>
    ${object.description ? `<p class="hero-desc">${escapeHtml(object.description)}</p>` : ''}
  </div>
  <div class="hero-side">
    ${owner.team    ? `<div class="hero-side-row"><span class="k">Owner</span><span class="v">${escapeHtml(owner.team)}</span></div>` : ''}
    ${owner.contact ? `<div class="hero-side-row"><span class="k">Contact</span><span class="v contact">${escapeHtml(owner.contact)}</span></div>` : ''}
    ${pillarLabel   ? `<div class="hero-side-row"><span class="k">Pillar</span><span class="v">${escapeHtml(pillarLabel)}</span></div>` : ''}
    ${bc.productFamily ? `<div class="hero-side-row"><span class="k">Product</span><span class="v">${escapeHtml(bc.productFamily)}</span></div>` : ''}
    ${d.dataClassification ? `<div class="hero-side-row"><span class="k">Data</span><span class="v">${escapeHtml(d.dataClassification)}</span></div>` : ''}
    ${fd.scope ? `<div class="hero-side-row"><span class="k">Blast radius</span><span class="v">${escapeHtml(fd.scope)}</span></div>` : ''}
  </div>
</div>`;
}

// ── KPI strip ─────────────────────────────────────────────────────────────────
function _sdpKpiMarkup(object, vm) {
  const d = object.architecturalDecisions || {};
  const n = vm.members.length;
  const haCount  = vm.members.filter(m => m.intent === 'ha').length;
  const saGap    = vm.members.filter(m => m.intent !== 'ha' && !m.riskRef).length;
  const saAccepted = vm.members.filter(m => m.intent !== 'ha' && m.riskRef).length;
  let haSub;
  if (n === 0)           haSub = 'no services';
  else if (haCount === n) haSub = 'fully covered';
  else if (saGap === 0)  haSub = `${saAccepted} accepted risk`;
  else                   haSub = `${saGap} gap${saGap > 1 ? 's' : ''}${saAccepted ? ` · ${saAccepted} accepted` : ''}`;
  const kpis = [
    { label: 'Services',      value: n,                        sub: 'deployable objects' },
    { label: 'Zones',         value: vm.activeZones.length,    sub: 'network zones' },
    { label: 'Connections',   value: vm.connections.length,    sub: 'documented paths' },
    { label: 'Availability',  value: d.availabilityTarget || '—', sub: d.availabilityTarget ? 'target SLA' : 'not specified' },
    { label: 'HA Components', value: n > 0 ? `${haCount} / ${n}` : '—', sub: haSub }
  ];
  return `<div class="kpi-strip">${kpis.map(k => `
  <div class="kpi">
    <div class="kpi-label">${escapeHtml(k.label)}</div>
    <div class="kpi-value">${k.value}</div>
    <div class="kpi-sub">${k.sub}</div>
  </div>`).join('')}</div>`;
}

// ── Section nav ───────────────────────────────────────────────────────────────
function _sdpSectionNavMarkup(vm, object) {
  const sections = [
    { id: 'sdp-s-topology',    label: 'Topology' },
    { id: 'sdp-s-groups',      label: 'Service Groups' },
    { id: 'sdp-s-decisions',   label: 'Decisions' },
    { id: 'sdp-s-connections', label: 'Connections', skip: !vm.connections.length },
    { id: 'sdp-s-tiers',       label: 'Tier Variants', skip: !(object.tierVariants && object.tierVariants.length) },
    { id: 'sdp-s-metadata',    label: 'Metadata' }
  ].filter(s => !s.skip);
  return `<nav class="section-nav" id="sdp-section-nav">${sections.map((s, i) =>
    `<button class="${i === 0 ? 'active' : ''}" data-sdp-nav="${s.id}">${escapeHtml(s.label)}</button>`
  ).join('')}</nav>`;
}

// ── Topology section ──────────────────────────────────────────────────────────
function _sdpTopologyMarkup(vm) {
  const usedTiers = new Set(vm.members.map(m => m.tier).filter(Boolean));
  const tierChips = [{ id: 'all', label: 'All' }, ..._SDP_TIER_ORDER.filter(t => usedTiers.has(t)).map(t => ({ id: t, label: _SDP_TIER_LABELS[t] }))];
  const zoneColsHtml = vm.zones.map(zone => {
    const zt = vm.byZone[zone.id]?.tiers || {};
    const total = Object.values(zt).reduce((a, b) => a + b.length, 0);
    if (total === 0) return '';
    const bandsHtml = _SDP_TIER_ORDER.map(tier => {
      const members = zt[tier] || [];
      if (!members.length) return '';
      const cardsHtml = members.map(m => {
        const svc = objectLookup[m.ref] || { name: m.ref, role: '' };
        return `<div class="svc-card" data-ref="${escapeHtml(m.ref)}" data-tier="${escapeHtml(m.tier)}">
          <div class="svc-name"><span>${escapeHtml(svc.name || m.ref)}</span>
            <span class="intent-dot ${escapeHtml(m.intent)}" title="${m.intent === 'ha' ? 'Highly available' : 'Standalone'}"></span>
          </div>
          <div class="svc-role">${escapeHtml(svc.role || svc.type || '')}</div>
        </div>`;
      }).join('');
      return `<div class="tier-band" data-tier="${escapeHtml(tier)}">
        <div class="tier-band-head">
          <span>${escapeHtml(_SDP_TIER_LABELS[tier])}</span>
          <span class="bar"></span>
          <span>${members.length}</span>
        </div>
        <div class="svc-grid${members.length === 1 ? ' single' : ''}">${cardsHtml}</div>
      </div>`;
    }).join('');
    return `<div class="zone-col" data-zone="${escapeHtml(zone.id)}">
      <div class="zone-header">
        <div class="zone-eyebrow">
          <span class="dot"></span>
          <span>Zone · ${escapeHtml(zone.name)}</span>
          <span class="count">— ${total} services</span>
        </div>
        <div class="zone-name">${escapeHtml(zone.name)}</div>
        ${zone.description ? `<div class="zone-desc">${escapeHtml(zone.description)}</div>` : ''}
      </div>
      ${bandsHtml}
    </div>`;
  }).join('');

  const legendTiers = _SDP_TIER_ORDER.filter(t => usedTiers.has(t)).map(t =>
    `<span class="topo-legend-item"><span class="sw" style="background:var(--tier-${t})"></span>${escapeHtml(_SDP_TIER_LABELS[t])}</span>`
  ).join('');
  const legendProtos = ['REST', 'AMQP', 'Other'].map((p, i) => {
    const cls = ['rest', 'amqp', 'other'][i];
    return `<span class="topo-legend-item"><span class="ln" style="background:var(--proto-${cls})"></span>${p}</span>`;
  }).join('');

  return `
<div class="sdp-section" id="sdp-s-topology">
  <div class="section-head">
    <div><span class="eyebrow">01 — Topology</span><h2>Deployment Topology</h2></div>
    <div class="filter-bar">
      <span class="filter-label">Tier</span>
      <div class="chip-group">${tierChips.map(c =>
        `<button class="chip${c.id === 'all' ? ' active' : ''}" data-tier-filter="${escapeHtml(c.id)}">`
        + (c.id !== 'all' ? `<span class="swatch" style="background:var(--tier-${c.id})"></span>` : '')
        + escapeHtml(c.label) + `</button>`
      ).join('')}</div>
    </div>
  </div>
  <div class="topology-wrap">
    <div class="topology" id="sdp-topology-grid">
      <svg class="topology-svg" id="sdp-topology-svg" aria-hidden="true"></svg>
      ${zoneColsHtml}
    </div>
    <div class="topo-legend">
      <div class="topo-legend-group"><span class="topo-legend-label">Tiers</span>${legendTiers}</div>
      <div class="topo-legend-group"><span class="topo-legend-label">Protocols</span>${legendProtos}</div>
      <div class="topo-legend-group">
        <span class="topo-legend-label">Intent</span>
        <span class="topo-legend-item"><span class="sw" style="background:var(--ok)"></span>HA</span>
        <span class="topo-legend-item"><span class="sw" style="background:var(--warn)"></span>Single</span>
      </div>
    </div>
  </div>
</div>`;
}

// ── SVG path overlay ──────────────────────────────────────────────────────────
function _sdpRecomputePaths(vm) {
  const grid = document.getElementById('sdp-topology-grid');
  const svg  = document.getElementById('sdp-topology-svg');
  if (!grid || !svg) return;
  const box = grid.getBoundingClientRect();
  const paths = [];
  vm.connections.forEach((c, i) => {
    const aEl = _sdpCardRefs[c.from];
    const bEl = _sdpCardRefs[c.to];
    if (!aEl || !bEl) return;
    const ra = aEl.getBoundingClientRect();
    const rb = bEl.getBoundingClientRect();
    const ay = ra.top - box.top + ra.height / 2;
    const by = rb.top - box.top + rb.height / 2;
    let sx, ex;
    const sameCol = Math.abs(ra.left - rb.left) < 4;
    if (sameCol) {
      sx = ra.left - box.left + ra.width;
      ex = rb.left - box.left + rb.width;
    } else if (ra.left > rb.left) {
      sx = ra.left - box.left;
      ex = rb.left - box.left + rb.width;
    } else {
      sx = ra.left - box.left + ra.width;
      ex = rb.left - box.left;
    }
    const dx = ex - sx;
    const curve = sameCol ? 0 : Math.min(120, Math.max(40, Math.abs(dx) * 0.45));
    const path = sameCol
      ? `M ${sx} ${ay} C ${sx + 64} ${ay}, ${ex + 64} ${by}, ${ex} ${by}`
      : `M ${sx} ${ay} C ${sx + curve} ${ay}, ${ex - curve} ${by}, ${ex} ${by}`;
    paths.push({ ...c, path, key: `${c.from}-${c.to}-${i}` });
  });

  const proto = p => (p.protocol || '').toLowerCase();
  const active = _sdpActive || _sdpHover;
  svg.innerHTML = paths.map(p => {
    const isActive = active && (p.from === active || p.to === active);
    const isDimmed = active && !isActive;
    const cls = ['conn-path', proto(p), isActive && 'is-active', isDimmed && 'is-dimmed'].filter(Boolean).join(' ');
    return `<path d="${p.path}" class="${cls}"/>`;
  }).join('');
}

function _sdpUpdateCardStates(vm) {
  const active = _sdpActive || _sdpHover;
  const grid = document.getElementById('sdp-topology-grid');
  if (!grid) return;
  if (active) {
    const related = new Set([active]);
    vm.connections.forEach(c => {
      if (c.from === active) related.add(c.to);
      if (c.to === active)   related.add(c.from);
    });
    grid.dataset.active = '1';
    grid.querySelectorAll('.svc-card').forEach(el => {
      const ref = el.dataset.ref;
      el.classList.toggle('is-active',   ref === active);
      el.classList.toggle('is-related',  related.has(ref) && ref !== active);
    });
  } else {
    delete grid.dataset.active;
    grid.querySelectorAll('.svc-card').forEach(el => {
      el.classList.remove('is-active', 'is-related');
    });
  }
}

// ── Drawer ────────────────────────────────────────────────────────────────────
function _sdpOpenDrawer(ref, vm) {
  _sdpDrawer = ref;
  const drawer = document.getElementById('sdp-drawer');
  if (!drawer) return;
  const svc = objectLookup[ref] || { name: ref, id: ref };
  const m = vm.members.find(x => x.ref === ref) || {};
  const conns = vm.connections.filter(c => c.from === ref || c.to === ref);
  const connRows = conns.map(c => {
    const isOut = c.from === ref;
    const otherId = isOut ? c.to : c.from;
    const other = objectLookup[otherId] || { name: otherId };
    const proto = (c.protocol || '').toLowerCase();
    const arrow = isOut ? '→' : '←';
    return `<div class="drawer-conn" data-object-link="${escapeHtml(otherId)}">
      <span class="pill ${proto}">${escapeHtml(c.protocol || '')}</span>
      <div class="target-row">
        <span class="arrow">${arrow}</span>
        <span class="target">${escapeHtml(other.name || otherId)}</span>
      </div>
      ${c.label ? `<div class="note">${escapeHtml(c.label)}</div>` : ''}
    </div>`;
  }).join('');
  const intentLabel = m.intent === 'ha' ? 'Highly Available'
    : m.intent === 'sa' && m.riskRef  ? 'Standalone — accepted risk'
    : m.intent === 'sa'               ? 'Standalone — no HA decision recorded'
    : (m.intent || '—');
  const intent = intentLabel;
  const zone = vm.zones.find(z => z.id === m.zone);
  drawer.querySelector('.drawer-eyebrow').innerHTML =
    `<span class="dot" style="background:var(--tier-${escapeHtml(m.tier || 'application')})"></span>
     ${escapeHtml(_SDP_TIER_LABELS[m.tier] || m.tier || '')} · ${escapeHtml(m.group || '')}`;
  drawer.querySelector('#sdp-drawer-title').textContent = svc.name || ref;
  drawer.querySelector('.drawer-uid').textContent = ref;
  drawer.querySelector('.drawer-body').innerHTML = `
    ${svc.description ? `<div class="drawer-row"><div class="k">Description</div><div class="v">${escapeHtml(svc.description)}</div></div>` : ''}
    <div class="drawer-row"><div class="k">Zone</div><div class="v">${escapeHtml(zone?.name || m.zone || '—')}</div></div>
    <div class="drawer-row"><div class="k">Intent</div><div class="v">${escapeHtml(intent)}</div></div>
    ${m.riskRef ? `<div class="drawer-row"><div class="k">HA Decision</div><div class="v"><span class="drawer-risk-ref" data-object-link="${escapeHtml(m.riskRef)}">${escapeHtml(objectLookup[m.riskRef]?.name || m.riskRef)}</span></div></div>` : ''}
    ${m.notes ? `<div class="drawer-row"><div class="k">Notes</div><div class="v">${escapeHtml(m.notes)}</div></div>` : ''}
    ${conns.length ? `<div class="drawer-row"><div class="k">Connections</div><div class="drawer-list">${connRows}</div></div>` : ''}
  `;
  const canNavigate = !!objectLookup[ref];
  function navigateToRef() {
    _sdpCloseDrawer();
    currentDetailId = ref;
    navHistory.length = 0;
    renderDetailView();
    syncHashForDetailView(ref);
  }
  const openBtn = drawer.querySelector('#sdp-drawer-open');
  if (openBtn) {
    openBtn.hidden = !canNavigate;
    openBtn.onclick = canNavigate ? navigateToRef : null;
  }
  const titleEl = drawer.querySelector('#sdp-drawer-title');
  if (titleEl) {
    titleEl.classList.toggle('drawer-title-link', canNavigate);
    titleEl.onclick = canNavigate ? navigateToRef : null;
  }
  drawer.classList.add('open');
}

function _sdpCloseDrawer() {
  _sdpDrawer = null;
  const drawer = document.getElementById('sdp-drawer');
  if (drawer) drawer.classList.remove('open');
}

// ── Service Groups section ────────────────────────────────────────────────────
function _sdpGroupsMarkup(object, vm) {
  const groups = object.serviceGroups || [];
  if (!groups.length) return `<div class="sdp-section" id="sdp-s-groups">
    <div class="section-head"><div><span class="eyebrow">02 — Service Groups</span><h2>Service Groups</h2></div></div>
    <p style="color:var(--muted)">No service groups documented.</p>
  </div>`;
  const groupCards = groups.map((sg, gi) => {
    const entries = sg.deployableObjects || [];
    const ext = (sg.externalInteractions || []).filter(x => (x.type || 'external') !== 'internal');
    const rowsHtml = entries.map(e => {
      const svc = objectLookup[e.ref] || { name: e.ref };
      const zone = vm.zones.find(z => z.id === e.networkZone) || { id: e.networkZone || '', name: e.networkZone || '' };
      const intent = e.intent || 'sa';
      return `<div class="group-row">
        <div class="svc">
          <span class="svc-link" data-object-link="${escapeHtml(e.ref)}">${escapeHtml(svc.name || e.ref)}</span>
          <span class="svc-uid">${escapeHtml(e.ref)}</span>
        </div>
        <span class="zone-tag" data-zone="${escapeHtml(zone.id)}"><span class="dot"></span>${escapeHtml(zone.name || zone.id)}</span>
        <span class="intent-tag ${intent}"><span class="dot"></span>${intent.toUpperCase()}</span>
        <span class="notes">${escapeHtml(e.notes || '')}</span>
      </div>`;
    }).join('');
    const extHtml = ext.length ? `<div class="ext-block">
      <h4>External Interactions</h4>
      ${ext.map(x => `<div class="ext-item">
        <span class="name">${escapeHtml(x.name)}</span>
        <span class="desc">${escapeHtml(x.notes || '')}</span>
      </div>`).join('')}
    </div>` : '';
    return `<div class="group-card${gi === 0 ? ' open' : ''}" data-group-idx="${gi}">
      <div class="group-head">
        <div>
          <h3>${escapeHtml(sg.name || 'Service Group')}</h3>
          <div class="group-meta">${escapeHtml(sg.deploymentTarget || 'No deployment target')}</div>
        </div>
        <span class="group-toggle">▶</span>
      </div>
      <div class="group-body">
        ${entries.length ? `<div class="group-table">${rowsHtml}</div>` : ''}
        ${extHtml}
      </div>
    </div>`;
  }).join('');
  return `<div class="sdp-section" id="sdp-s-groups">
    <div class="section-head"><div>
      <span class="eyebrow">02 — Service Groups</span>
      <h2>Service Groups</h2>
    </div></div>
    <div class="group-list">${groupCards}</div>
  </div>`;
}

// ── Decisions section ─────────────────────────────────────────────────────────
function _sdpDecisionsMarkup(object) {
  const d = object.architecturalDecisions || {};
  const cards = [];

  if (d.availabilityTarget || d.availabilityRequirement) {
    const scope = d.availabilityTarget ? `<span class="badge info"><span class="dot"></span>${escapeHtml(d.availabilityTarget)}</span>` : '';
    cards.push({ key: 'Availability', text: d.availabilityRequirement || d.availabilityTarget, badge: scope });
  }
  if (d.dataClassification) {
    cards.push({ key: 'Data Classification', text: d.dataClassification, badge: '' });
  }
  if (d.failureDomain) {
    const fd = typeof d.failureDomain === 'object' ? d.failureDomain : { description: d.failureDomain };
    const scopeBadge = fd.scope ? `<span class="badge neutral"><span class="dot"></span>${escapeHtml(fd.scope)}</span>` : '';
    cards.push({ key: 'Failure Domain', text: fd.description || '', badge: scopeBadge });
  }
  if (d.patternDeviations && d.patternDeviations !== 'none') {
    cards.push({ key: 'Pattern Deviations', text: d.patternDeviations, badge: `<span class="badge warn">Deviations noted</span>` });
  }

  if (!cards.length) return `<div class="sdp-section" id="sdp-s-decisions">
    <div class="section-head"><div><span class="eyebrow">03 — Decisions</span><h2>Architectural Decisions</h2></div></div>
    <p style="color:var(--muted)">No architectural decisions documented.</p>
  </div>`;

  const cardsHtml = cards.map(c => `<div class="decision-card">
    <div class="eyebrow">${escapeHtml(c.key)}</div>
    <h3>${escapeHtml(c.key)}</h3>
    ${c.text ? `<div class="detail">${escapeHtml(c.text)}</div>` : ''}
    ${c.badge ? `<div class="badge-row">${c.badge}</div>` : ''}
  </div>`).join('');

  return `<div class="sdp-section" id="sdp-s-decisions">
    <div class="section-head"><div>
      <span class="eyebrow">03 — Decisions</span>
      <h2>Architectural Decisions</h2>
    </div></div>
    <div class="decisions-grid">${cardsHtml}</div>
  </div>`;
}

// ── Connections table ─────────────────────────────────────────────────────────
function _sdpConnectionsTableMarkup(vm) {
  if (!vm.connections.length) return '';
  const rows = vm.connections.map(c => {
    const fromSvc = objectLookup[c.from] || { name: c.from };
    const toSvc   = objectLookup[c.to]   || { name: c.to };
    const proto = (c.protocol || '').toLowerCase();
    const fz = vm.uidToZone[c.from] || '';
    const tz = vm.uidToZone[c.to]   || '';
    return `<tr data-object-link="${escapeHtml(c.from)}">
      <td><span class="svc-cell">
        <span class="zd" style="background:var(--zone-${escapeHtml(fz)},var(--muted))"></span>
        ${escapeHtml(fromSvc.name || c.from)}
      </span></td>
      <td><span class="arrow">→</span><span class="svc-cell">
        <span class="zd" style="background:var(--zone-${escapeHtml(tz)},var(--muted))"></span>
        ${escapeHtml(toSvc.name || c.to)}
      </span></td>
      <td><span class="proto ${proto}">${escapeHtml(c.protocol || '')}</span></td>
      <td class="label-cell">${escapeHtml(c.label || '')}</td>
    </tr>`;
  }).join('');
  return `<div class="sdp-section" id="sdp-s-connections">
    <div class="section-head"><div>
      <span class="eyebrow">04 — Connections</span>
      <h2>Service Connections</h2>
    </div><p>${vm.connections.length} documented connection${vm.connections.length === 1 ? '' : 's'}</p></div>
    <div class="conn-table-wrap">
      <table class="conn-table">
        <thead><tr>
          <th>From</th><th>To</th><th>Protocol</th><th>Label</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
}

// ── Metadata section ──────────────────────────────────────────────────────────
function _sdpTierVariantsMarkup(object) {
  const variants = object.tierVariants || [];
  if (!variants.length) return '';
  const allTiers = (browserData.objects || []).filter(o => o.type === 'environment_tier');
  const tierLookup = Object.fromEntries(allTiers.map(t => [t.id || t.uid, t]));
  const purposeIcon = { development: '🔧', test: '🧪', staging: '🚦', production: '🏭', other: '🔹' };

  const variantCards = variants.map(v => {
    const tierRef = v.tier;
    const tierObj = tierLookup[tierRef];
    const tierName = tierObj ? escapeHtml(tierObj.name) : escapeHtml(tierRef || 'Unknown Tier');
    const tierId = tierObj ? escapeHtml(tierObj.tierId || '') : '';
    const purpose = tierObj?.purpose || '';
    const icon = purposeIcon[purpose] || '🔹';
    const dt = v.deploymentTarget;
    const dtHtml = dt
      ? `<div class="interaction-notes">${escapeHtml(dt.provider)}${dt.region ? ` / ${escapeHtml(dt.region)}` : ''}</div>`
      : '';
    const sgv = v.serviceGroupVariants || [];
    const sgvHtml = sgv.length ? `
      <table class="def-table" style="margin-top:0.5rem">
        <thead><tr><th>Service Group</th><th>Replicas</th><th>Autoscaling</th></tr></thead>
        <tbody>
          ${sgv.map(s => {
            const auto = s.autoscaling;
            const autoText = auto
              ? (auto.enabled ? `enabled (${auto.min ?? '?'}–${auto.max ?? '?'})` : 'disabled')
              : '—';
            return `<tr>
              <td>${escapeHtml(s.serviceGroup || '')}</td>
              <td>${s.replicaCount != null ? escapeHtml(String(s.replicaCount)) : '—'}</td>
              <td>${escapeHtml(autoText)}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>` : '';
    return `<article class="odc-card">
      <div class="odc-name">${icon} ${tierName}${tierId ? ` <span class="badge">${tierId}</span>` : ''}</div>
      ${dtHtml}
      ${sgvHtml}
      ${v.notes ? `<div class="interaction-notes">${escapeHtml(v.notes)}</div>` : ''}
    </article>`;
  }).join('');

  return `<div class="sdp-section" id="sdp-s-tiers">
    <div class="section-head"><div>
      <span class="eyebrow">05 — Environment Tiers</span>
      <h2>Tier Variants</h2>
    </div></div>
    <div class="section-stack">${variantCards}</div>
  </div>`;
}

function _sdpMetadataMarkup(object) {
  const tags = object.tags || [];
  const refArch = object.followsReferenceArchitecture;
  const refObj = refArch ? objectLookup[refArch] : null;
  const cards = [
    { k: 'UID',     v: object.id || object.uid || '', mono: true },
    { k: 'Version', v: object.version ? `v${object.version}` : '—' },
    { k: 'Catalog Status', v: object.catalogStatus || '—' },
    { k: 'Lifecycle',      v: object.lifecycleStatus || '—' },
  ].filter(c => c.v && c.v !== '—');
  if (refArch) cards.push({ k: 'Reference Architecture', v: refObj ? refObj.name : refArch, link: refArch });

  const cardsHtml = cards.map(c =>
    `<div class="ref-card">
      <div class="k">${escapeHtml(c.k)}</div>
      <div class="v${c.mono ? ' mono' : ''}">${
        c.link ? `<span class="ard-link" data-object-link="${escapeHtml(c.link)}">${escapeHtml(c.v)}</span>`
               : escapeHtml(c.v)
      }</div>
    </div>`
  ).join('');
  const tagsHtml = tags.length ? `<div class="tag-row">${tags.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>` : '';

  return `<div class="sdp-section" id="sdp-s-metadata">
    <div class="section-head"><div>
      <span class="eyebrow">06 — Metadata</span>
      <h2>Metadata</h2>
    </div></div>
    <div class="ref-grid">${cardsHtml}</div>
    ${tagsHtml}
  </div>`;
}

// ── Drawer markup ─────────────────────────────────────────────────────────────
function _sdpDrawerMarkup() {
  return `<div class="sdp-drawer" id="sdp-drawer">
    <div class="drawer-head">
      <div class="drawer-head-actions">
        <button class="drawer-open-btn" id="sdp-drawer-open" title="Open full detail page" hidden>Open ↗</button>
        <button class="drawer-close" id="sdp-drawer-close" aria-label="Close">✕</button>
      </div>
      <div class="drawer-eyebrow"></div>
      <h3 class="drawer-title" id="sdp-drawer-title"></h3>
      <div class="drawer-uid"></div>
    </div>
    <div class="drawer-body"></div>
  </div>`;
}

// ── Full SDP markup ───────────────────────────────────────────────────────────
function _sdpDetailMarkup(object) {
  const vm = _sdpBuildVM(object);
  return {
    html: `<div class="sdp-detail">
      ${_sdpHeroMarkup(object)}
      ${_sdpKpiMarkup(object, vm)}
      ${_sdpSectionNavMarkup(vm, object)}
      ${_sdpTopologyMarkup(vm)}
      ${_sdpGroupsMarkup(object, vm)}
      ${_sdpDecisionsMarkup(object)}
      ${_sdpConnectionsTableMarkup(vm)}
      ${_sdpTierVariantsMarkup(object)}
      ${_sdpMetadataMarkup(object)}
      ${_sdpDrawerMarkup()}
    </div>`,
    vm
  };
}

// ── Attach all interactive handlers ──────────────────────────────────────────
function _sdpAttachHandlers(object, vm) {
  const root = pageRoot;

  // ── Collect card refs for SVG overlay
  _sdpCardRefs = {};
  root.querySelectorAll('.svc-card[data-ref]').forEach(el => {
    _sdpCardRefs[el.dataset.ref] = el;
  });

  // ── Tier filter chips
  root.querySelectorAll('[data-tier-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      _sdpTierFilter = btn.dataset.tierFilter;
      root.querySelectorAll('[data-tier-filter]').forEach(b =>
        b.classList.toggle('active', b.dataset.tierFilter === _sdpTierFilter)
      );
      // Show/hide tier bands
      root.querySelectorAll('.tier-band').forEach(band => {
        band.hidden = _sdpTierFilter !== 'all' && band.dataset.tier !== _sdpTierFilter;
      });
      // Re-collect card refs (some may have moved off screen)
      _sdpCardRefs = {};
      root.querySelectorAll('.svc-card[data-ref]').forEach(el => {
        _sdpCardRefs[el.dataset.ref] = el;
      });
      requestAnimationFrame(() => _sdpRecomputePaths(vm));
    });
  });

  // ── Service card hover + click
  root.querySelectorAll('.svc-card[data-ref]').forEach(el => {
    el.addEventListener('mouseenter', () => {
      _sdpHover = el.dataset.ref;
      _sdpUpdateCardStates(vm);
      _sdpRecomputePaths(vm);
    });
    el.addEventListener('mouseleave', () => {
      _sdpHover = null;
      _sdpUpdateCardStates(vm);
      _sdpRecomputePaths(vm);
    });
    el.addEventListener('click', () => {
      _sdpActive = _sdpActive === el.dataset.ref ? null : el.dataset.ref;
      _sdpUpdateCardStates(vm);
      _sdpRecomputePaths(vm);
      if (_sdpActive) _sdpOpenDrawer(_sdpActive, vm);
      else _sdpCloseDrawer();
    });
  });

  // ── Drawer close
  const drawerClose = document.getElementById('sdp-drawer-close');
  if (drawerClose) {
    drawerClose.addEventListener('click', () => {
      _sdpActive = null;
      _sdpUpdateCardStates(vm);
      _sdpRecomputePaths(vm);
      _sdpCloseDrawer();
    });
  }

  // ── ResizeObserver for SVG paths
  const grid = document.getElementById('sdp-topology-grid');
  if (grid) {
    _sdpRecomputePaths(vm);
    _sdpResizeObs = new ResizeObserver(() => _sdpRecomputePaths(vm));
    _sdpResizeObs.observe(grid);
    window.addEventListener('scroll', () => _sdpRecomputePaths(vm), { passive: true });
  }

  // ── Section nav IntersectionObserver
  const navEl = document.getElementById('sdp-section-nav');
  if (navEl) {
    const sections = root.querySelectorAll('.sdp-section[id]');
    _sdpSectionObs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          navEl.querySelectorAll('[data-sdp-nav]').forEach(btn =>
            btn.classList.toggle('active', btn.dataset.sdpNav === id)
          );
        }
      });
    }, { rootMargin: '-120px 0px -55% 0px' });
    sections.forEach(s => _sdpSectionObs.observe(s));

    navEl.querySelectorAll('[data-sdp-nav]').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = document.getElementById(btn.dataset.sdpNav);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  // ── Group card collapse/expand
  root.querySelectorAll('.group-card .group-head').forEach(head => {
    head.addEventListener('click', () => {
      head.closest('.group-card').classList.toggle('open');
    });
  });

  // ── Object links in drawer and service groups
  attachObjectLinkHandlers(root.querySelector('.sdp-detail'));
}


function renderDetailView() {
  currentMode = 'detail';
  executiveDrilldown = null;
  const object = objectLookup[currentDetailId];
  if (!object) {
    renderListView();
    return;
  }
  syncHashForDetailView(object.id);
  renderSidebarContent(sidebarMarkup());
  const softwareServiceRunsOn = object.type === 'product_service' && object.runsOn ? objectLookup[object.runsOn] : null;
  const componentSource = object.type === 'product_service' ? preferredComponentSource(object, softwareServiceRunsOn) : object;
  const detailDiagramSource = componentSource && DEPLOYABLE_STANDARD_TYPES.includes(componentSource.type) ? componentSource : object;
  const headerMarkup = `
    <section class="header-card">
      <div class="header-top">
        <div class="header-title">
          <h2>${escapeHtml(object.name)}</h2>
          <div class="object-id">${escapeHtml(object.id)}</div>
        </div>
        <div class="badges">
          <span class="badge">${escapeHtml(object.typeLabel)}</span>
          ${object.lifecycleStatus ? lifecycleBadge(object.lifecycleStatus) : ''}
          ${catalogBadge(object.catalogStatus)}
        </div>
      </div>
      <div class="header-description">${escapeHtml(object.description || 'No description provided.')}</div>
      ${object.type === 'capability' ? `
        <div class="owner-line">
          <span><strong>Definition owner:</strong> ${escapeHtml(object.definitionOwner?.team || object.definitionOwner?.provider || 'Unknown')}</span>
          <span><strong>Company owner:</strong> ${escapeHtml(object.owner?.team || 'Not assigned')}</span>
        </div>
      ` : `
        <div class="owner-line">
          <span><strong>Owner:</strong> ${escapeHtml(object.owner?.team || 'Unknown')}</span>
          <span><strong>Contact:</strong> ${escapeHtml(object.owner?.contact || 'Unknown')}</span>
        </div>
      `}
    </section>
  `;

  let detailBody = '';
  if (object.type === 'requirement_group') {
    detailBody = `
      ${headerMarkup}
      ${odcRequirementsMarkup(object)}
      ${referencesMarkup(object)}
    `;
  } else if (object.type === 'capability') {
    detailBody = `
      ${headerMarkup}
      ${capabilityDetailMarkup(object)}
      ${referencesMarkup(object)}
    `;
  } else if (object.type === 'domain') {
    detailBody = `
      ${headerMarkup}
      ${domainDetailMarkup(object)}
      ${referencesMarkup(object)}
    `;
  } else if (object.type === 'decision_record') {
    detailBody = `
      ${ardDetailMarkup(object)}
      ${referencesMarkup(object)}
    `;
  } else if (object.type === 'drafting_session') {
    detailBody = `
      ${headerMarkup}
      ${draftingSessionDetailMarkup(object)}
      ${referencesMarkup(object)}
    `;
  } else if (object.type === 'product_service') {
    const productComponentSource = preferredComponentSource(object, softwareServiceRunsOn);
    const interactionSource = preferredInteractionSource(object, softwareServiceRunsOn);
    const decisionSource = preferredDecisionSource(object, softwareServiceRunsOn);
    detailBody = `
      ${headerMarkup}
      ${architectureDetailMarkup(
        productComponentSource,
        interactionSource,
        decisionSource,
        'The underlying deployable object is not available for this Product Service.',
        'No architectural decisions are available because the underlying deployable object is not documented.'
      )}
      ${secondaryDetailMarkup([
        { title: 'Product Service Classification', body: productServiceDetailMarkup(object) },
        { title: 'Requirement Evidence', body: requirementEvidenceMarkup(object) },
        { title: 'References', body: usedByMarkup(object) }
      ])}
    `;
  } else if (object.type === 'software_deployment_pattern') {
    _sdpTeardown();
    const { html: sdpHtml, vm: sdpVm } = _sdpDetailMarkup(object);
    detailBody = sdpHtml;
    // Store vm on object for handler setup below
    object._sdpVm = sdpVm;
  } else if (object.type === 'reference_architecture') {
    detailBody = `
      ${headerMarkup}
      <div class="detail-tabs">
        <button class="detail-tab active" data-sdm-tab="topology">Deployment Pattern</button>
        <button class="detail-tab" data-sdm-tab="details">Governance & Decisions</button>
      </div>
      <div class="detail-panel" data-sdm-panel="details" hidden>
        ${requirementEvidenceMarkup(object)}
        ${sdmServiceGroupsMarkup(object)}
        <section class="decisions-card">
          <h3>Architecture Decisions</h3>
          ${decisionMarkup(object)}
        </section>
      </div>
      <div class="detail-panel" data-sdm-panel="topology">
        <section class="section-card">
          <h3>Deployment Pattern</h3>
          <div id="topology-canvas"></div>
        </section>
      </div>
      ${referencesMarkup(object)}
    `;
  } else if (object.type === 'technology_component') {
    detailBody = `
      ${headerMarkup}
      ${abbDetailMarkup(object)}
      ${referencesMarkup(object)}
    `;
  } else if (DEPLOYABLE_STANDARD_TYPES.includes(object.type)) {
    detailBody = `
      ${headerMarkup}
      ${architectureDetailMarkup(object, object, object)}
      ${secondaryDetailMarkup([
        { title: 'Delivery Details', body: deliveryModelDetailMarkup(object) },
        { title: 'Requirement Evidence', body: requirementEvidenceMarkup(object) },
        { title: 'Deployment Configurations', body: deploymentConfigurationsMarkup(object) },
        { title: 'References', body: usedByMarkup(object) }
      ])}
    `;
  } else {
    detailBody = `
      ${headerMarkup}
      ${genericObjectMarkup(object)}
      ${referencesMarkup(object)}
    `;
  }

  const backLabel = navHistory.length
    ? (objectLookup[navHistory[navHistory.length - 1]]?.name || 'Previous')
    : 'Drafting Table';
  pageRoot.innerHTML = `
    <div class="detail-layout">
      <div class="view-breadcrumb">
        <button class="view-breadcrumb-link" id="back-button">← ${escapeHtml(backLabel)}</button>
        <span class="view-breadcrumb-sep">/</span>
        <span>${escapeHtml(object.name)}</span>
      </div>
      ${detailBody}
    </div>
  `;

  document.getElementById('back-button').addEventListener('click', () => {
    destroyDetailCy();
    destroySdpGraphCy();
    if (navHistory.length) {
      const previousId = navHistory.pop();
      showDetailView(previousId, false);
      return;
    }
    currentDetailId = null;
    renderListView();
  });
  const openEditorButton = document.getElementById('open-editor-button');
  if (openEditorButton) {
    openEditorButton.addEventListener('click', () => openEditor(object));
  }

  attachTopNavHandlers();
  attachSidebarHandlers();
  attachObjectLinkHandlers(pageRoot);
  if (object.type === 'software_deployment_pattern') {
    _sdpAttachHandlers(object, object._sdpVm);
    delete object._sdpVm;
  } else if (object.type === 'reference_architecture') {
    currentSdmScalingFilter = 'all';
    const applySdmScalingFilter = () => {
      const topologyCanvas = document.getElementById('topology-canvas');
      if (!topologyCanvas) return;
      const filter = currentSdmScalingFilter;
      topologyCanvas.querySelectorAll('.topology-filter-button').forEach(button => {
        button.classList.toggle('active', button.dataset.scalingFilter === filter);
      });
      topologyCanvas.querySelectorAll('.topology-node').forEach(node => {
        const participates = filter === 'all' || node.dataset.scalingUnit === filter;
        node.classList.toggle('dimmed', filter !== 'all' && !participates);
        node.classList.toggle('highlighted', filter !== 'all' && participates);
      });
      topologyCanvas.querySelectorAll('.service-group-section').forEach(section => {
        const participates = filter === 'all' || section.dataset.scalingUnitGroup === filter;
        section.classList.toggle('dimmed', filter !== 'all' && !participates);
        section.classList.toggle('highlighted', filter !== 'all' && participates);
      });
    };
    const renderTopologyIntoCanvas = () => {
      const topologyCanvas = document.getElementById('topology-canvas');
      if (topologyCanvas && !topologyCanvas.dataset.rendered) {
        topologyCanvas.innerHTML = renderDeploymentTopology(object);
        topologyCanvas.dataset.rendered = 'true';
        attachObjectLinkHandlers(topologyCanvas);
        topologyCanvas.querySelectorAll('[data-scaling-filter]').forEach(button => {
          button.addEventListener('click', () => {
            currentSdmScalingFilter = button.dataset.scalingFilter || 'all';
            applySdmScalingFilter();
          });
        });
        applySdmScalingFilter();
      }
    };
    pageRoot.querySelectorAll('[data-sdm-tab]').forEach(button => {
      button.addEventListener('click', () => {
        const nextTab = button.dataset.sdmTab;
        pageRoot.querySelectorAll('[data-sdm-tab]').forEach(tab => {
          tab.classList.toggle('active', tab.dataset.sdmTab === nextTab);
        });
        pageRoot.querySelectorAll('[data-sdm-panel]').forEach(panel => {
          panel.hidden = panel.dataset.sdmPanel !== nextTab;
        });
        if (nextTab === 'topology') renderTopologyIntoCanvas();
      });
    });
    renderTopologyIntoCanvas();
  }
  if (DEPLOYABLE_STANDARD_TYPES.includes(object.type) && !['saas', 'paas', 'appliance'].includes(object.deliveryModel || '')) {
    renderInternalDiagram(detailDiagramSource);
  }
}

function destroyDetailCy() {
  if (detailCy) {
    detailCy.destroy();
    detailCy = null;
  }
}

function buildDetailElements(object) {
  const objectVisual = detailNodeVisual(object);
  const nodes = [
    {
      data: {
        id: object.id,
        label: object.name,
        color: '#ffffff',
        borderColor: objectVisual.borderColor,
        iconImage: objectVisual.image,
        lifecycleStatus: object.lifecycleStatus,
        nodeWidth: object.type === 'technology_component' || DEPLOYABLE_STANDARD_TYPES.includes(object.type) ? 172 : 160,
        nodeHeight: object.type === 'technology_component' || DEPLOYABLE_STANDARD_TYPES.includes(object.type) ? 132 : 122,
        textMaxWidth: object.type === 'technology_component' || DEPLOYABLE_STANDARD_TYPES.includes(object.type) ? 156 : 146
      },
      classes: object.name.length > 20 ? 'long-label' : ''
    }
  ];
  const edges = [];
  const seen = new Set([object.id]);

  (object.internalComponents || []).forEach((component, index) => {
    const refObject = objectLookup[component.ref];
    if (!refObject || seen.has(refObject.id)) {
      return;
    }
    seen.add(refObject.id);
    const refVisual = detailNodeVisual(refObject);
    nodes.push({
      data: {
        id: refObject.id,
        label: refObject.name,
        color: '#ffffff',
        borderColor: refVisual.borderColor,
        iconImage: refVisual.image,
        lifecycleStatus: refObject.lifecycleStatus,
        nodeWidth: refObject.type === 'technology_component' || DEPLOYABLE_STANDARD_TYPES.includes(refObject.type) ? 162 : 150,
        nodeHeight: refObject.type === 'technology_component' || DEPLOYABLE_STANDARD_TYPES.includes(refObject.type) ? 124 : 114,
        textMaxWidth: refObject.type === 'technology_component' || DEPLOYABLE_STANDARD_TYPES.includes(refObject.type) ? 148 : 138
      },
      classes: refObject.name.length > 20 ? 'long-label' : ''
    });
    edges.push({
      data: {
        id: `${object.id}-${refObject.id}-${index}`,
        source: object.id,
        target: refObject.id,
        label: component.configuration
          ? `${component.role || 'component'} / ${component.configuration}`
          : (component.role || 'component')
      }
    });
  });

  return [...nodes, ...edges];
}

function renderInternalDiagram(object) {
  destroyDetailCy();
  detailCy = cytoscape({
    container: document.getElementById('detail-cy'),
    elements: buildDetailElements(object),
    userZoomingEnabled: false,
    userPanningEnabled: false,
    boxSelectionEnabled: false,
    autoungrabify: true,
    layout: {
      name: 'breadthfirst',
      directed: true,
      padding: 30,
      spacingFactor: 1.5,
      roots: [object.id]
    },
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'shape': 'round-rectangle',
          'background-color': 'data(color)',
          'background-image': 'data(iconImage)',
          'background-fit': 'none',
          'background-width': 40,
          'background-height': 40,
          'background-position-x': '50%',
          'background-position-y': '28%',
          'border-width': 1,
          'border-color': 'data(borderColor)',
          'color': '#1f1a14',
          'font-size': 11,
          'font-weight': 600,
          'text-wrap': 'wrap',
          'text-max-width': 'data(textMaxWidth)',
          'text-valign': 'center',
          'text-halign': 'center',
          'text-margin-y': 36,
          'text-outline-width': 2,
          'text-outline-color': '#fbf8f3',
          'width': 'data(nodeWidth)',
          'height': 'data(nodeHeight)',
          'cursor': 'pointer'
        }
      },
      {
        selector: 'node.long-label',
        style: {
          'font-size': 10
        }
      },
      {
        selector: 'edge',
        style: {
          'label': 'data(label)',
          'curve-style': 'bezier',
          'width': 2,
          'line-color': '#a89784',
          'target-arrow-color': '#a89784',
          'target-arrow-shape': 'triangle',
          'font-size': 10,
          'color': '#5d5145',
          'text-background-color': '#fbf8f3',
          'text-background-opacity': 0.88,
          'text-background-padding': 3,
          'text-rotation': 'autorotate'
        }
      }
    ]
  });
  detailCy.on('tap', 'node', function(evt) {
    const nodeId = evt.target.data('id');
    const obj = objectLookup[nodeId];
    if (obj) {
      showDetailView(nodeId);
    }
  });
  detailCy.resize();
  detailCy.fit(detailCy.elements(), 28);
}

function outboundCatalogRefs(object) {
  return (object?.outboundRefs || [])
    .map(reference => objectLookup[reference.target])
    .filter(Boolean);
}

function inboundCatalogRefs(object) {
  return (referencedByIndex[object?.id] || [])
    .map(reference => objectLookup[reference.source])
    .filter(Boolean);
}

function traverseDown(object, visited, collector) {
  outboundCatalogRefs(object).forEach(target => {
    if (visited.has(target.id) || !deployableTypes.has(target.type)) {
      return;
    }
    visited.add(target.id);
    collector.add(target.id);
    traverseDown(target, visited, collector);
  });
}

function traverseUp(object, visited, collector) {
  inboundCatalogRefs(object).forEach(source => {
    if (visited.has(source.id) || !deployableTypes.has(source.type)) {
      return;
    }
    visited.add(source.id);
    collector.add(source.id);
    traverseUp(source, visited, collector);
  });
}

// ── Sidebar navigation ──────────────────────────────────────────────────
const SIDEBAR_NAV_ITEMS = [
  { id: 'executive',      label: 'Overview',        icon: '⊞' },
  { id: 'list',           label: 'Drafting Table',  icon: '▤' },
  { section: true,        label: 'Tools' },
  { id: 'acceptable-use', label: 'Acceptable Use',  icon: '✓' },
  { id: 'object-types',   label: 'Object Types',    icon: '⬡' },
  { id: 'onboarding',     label: 'Onboarding',      icon: '◉' },
  { id: 'vocabulary',     label: 'Vocabulary',      icon: '≡', href: 'company-vocabulary.html' },
  { id: 'manual',         label: 'User Manual',     icon: '?', href: 'user-manual.html' },
];

function updateSidebarNav() {
  document.querySelectorAll('#sidebar-nav .sidebar-nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.nav === currentMode);
  });
}

function initSidebarNav() {
  const nav = document.getElementById('sidebar-nav');
  if (!nav) return;
  let html = '';
  SIDEBAR_NAV_ITEMS.forEach(item => {
    if (item.section) {
      html += `<div class="sidebar-nav-section"><div class="sidebar-nav-label">${escapeHtml(item.label)}</div></div>`;
    } else if (item.href) {
      html += `<a class="sidebar-nav-btn" href="${escapeHtml(item.href)}"><span class="sidebar-nav-icon">${item.icon}</span><span>${escapeHtml(item.label)}</span></a>`;
    } else {
      html += `<button class="sidebar-nav-btn" data-nav="${escapeHtml(item.id)}"><span class="sidebar-nav-icon">${item.icon}</span><span>${escapeHtml(item.label)}</span></button>`;
    }
  });
  nav.innerHTML = html;
  nav.querySelectorAll('.sidebar-nav-btn[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => {
      const navId = btn.dataset.nav;
      if (navId === 'executive') { destroyImpactCy(); executiveDrilldown = null; renderExecutiveView(); }
      else if (navId === 'list') { destroyImpactCy(); renderListView(); }
      else if (navId === 'object-types') { destroyImpactCy(); renderObjectTypesView(); }
      else if (navId === 'onboarding') { destroyImpactCy(); renderCompanyOnboardingView(); }
      else if (navId === 'acceptable-use') { destroyImpactCy(); renderAcceptableUseView(); }
    });
  });
}

// ── Command palette ─────────────────────────────────────────────────────
let paletteFocusIndex = -1;
let paletteItems = [];

const PALETTE_VIEWS = [
  { id: 'executive',      label: 'Go to Overview',        icon: '⊞' },
  { id: 'list',           label: 'Go to Drafting Table',  icon: '▤' },
  { id: 'acceptable-use', label: 'Go to Acceptable Use',  icon: '✓' },
  { id: 'object-types',   label: 'Go to Object Types',    icon: '⬡' },
  { id: 'onboarding',     label: 'Go to Onboarding',      icon: '◉' },
  { id: 'vocabulary',     label: 'Open Vocabulary Guide', icon: '≡', href: 'company-vocabulary.html' },
  { id: 'manual',         label: 'Open User Manual',      icon: '?', href: 'user-manual.html' },
];

const PALETTE_TYPE_ICONS = {
  technology_component: '⬡',
  host: '⬛',
  runtime_service: '▶',
  data_at_rest_service: '◼',
  edge_gateway_service: '◈',
  product_service: '◉',
  software_deployment_pattern: '⊞',
  reference_architecture: '▤',
  capability: '✓',
  requirement_group: '≡',
  decision_record: '⊙',
  domain: '◎',
};

function openPalette() {
  const overlay = document.getElementById('cmd-overlay');
  const input = document.getElementById('cmd-input');
  if (!overlay || !input) return;
  overlay.hidden = false;
  paletteFocusIndex = -1;
  input.value = '';
  updatePaletteResults('');
  requestAnimationFrame(() => input.focus());
}

function closePalette() {
  const overlay = document.getElementById('cmd-overlay');
  if (overlay) overlay.hidden = true;
}

function updatePaletteResults(query) {
  const resultsEl = document.getElementById('cmd-results');
  if (!resultsEl) return;
  const q = query.trim().toLowerCase();
  paletteItems = [];
  let html = '';

  const matchingViews = PALETTE_VIEWS.filter(v => !q || v.label.toLowerCase().includes(q));
  if (matchingViews.length) {
    if (!q) html += '<div class="cmd-section-label">Views</div>';
    matchingViews.forEach(view => {
      const idx = paletteItems.length;
      paletteItems.push(view.href ? { type: 'link', href: view.href } : { type: 'view', id: view.id });
      html += `<button class="cmd-item" data-palette-idx="${idx}"><span class="cmd-item-icon">${view.icon}</span><div class="cmd-item-body"><div class="cmd-item-name">${escapeHtml(view.label)}</div></div><span class="cmd-item-enter">↵</span></button>`;
    });
  }

  const matchingObjects = q
    ? allObjects.filter(obj => objectMatchesSearch(obj, q)).slice(0, 20)
    : allObjects.slice(0, 10);

  if (matchingObjects.length) {
    html += `<div class="cmd-section-label">${q ? 'Objects' : 'All Objects'}</div>`;
    matchingObjects.forEach(obj => {
      const idx = paletteItems.length;
      paletteItems.push({ type: 'object', id: obj.id });
      const icon = PALETTE_TYPE_ICONS[obj.type] || '○';
      const lcColor = obj.lifecycleStatus ? ('#' + (lifecycleColors[obj.lifecycleStatus] || '7a6e60')) : null;
      html += `<button class="cmd-item" data-palette-idx="${idx}">
        <span class="cmd-item-icon">${icon}</span>
        <div class="cmd-item-body">
          <div class="cmd-item-name">${escapeHtml(obj.name)}</div>
          <div class="cmd-item-meta">
            <span class="cmd-item-badge">${escapeHtml(obj.typeLabel)}</span>
            ${lcColor ? `<span class="cmd-item-badge" style="color:${lcColor};border-color:${lcColor}20">${escapeHtml(obj.lifecycleStatus)}</span>` : ''}
          </div>
        </div>
        <span class="cmd-item-enter">↵</span>
      </button>`;
    });
  }

  if (!paletteItems.length) {
    html = `<div class="cmd-empty">No results for "${escapeHtml(query)}"</div>`;
  }

  resultsEl.innerHTML = html;
  paletteFocusIndex = paletteItems.length > 0 ? 0 : -1;

  resultsEl.querySelectorAll('.cmd-item').forEach(item => {
    item.addEventListener('click', () => selectPaletteItem(parseInt(item.dataset.paletteIdx)));
    item.addEventListener('mouseenter', () => {
      paletteFocusIndex = parseInt(item.dataset.paletteIdx);
      updatePaletteFocus();
    });
  });
  updatePaletteFocus();
}

function updatePaletteFocus() {
  document.querySelectorAll('#cmd-results .cmd-item').forEach(item => {
    item.classList.toggle('cmd-focused', parseInt(item.dataset.paletteIdx) === paletteFocusIndex);
  });
}

function selectPaletteItem(idx) {
  const item = paletteItems[idx];
  if (!item) return;
  closePalette();
  if (item.type === 'view') {
    const btn = document.querySelector(`#sidebar-nav .sidebar-nav-btn[data-nav="${item.id}"]`);
    if (btn) btn.click();
  } else if (item.type === 'link') {
    window.location.href = item.href;
  } else if (item.type === 'object') {
    showDetailView(item.id);
  }
}

function initPalette() {
  const input = document.getElementById('cmd-input');
  const overlay = document.getElementById('cmd-overlay');
  if (!input || !overlay) return;

  input.addEventListener('input', e => updatePaletteResults(e.target.value));
  input.addEventListener('keydown', e => {
    const count = paletteItems.length;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      paletteFocusIndex = Math.min(paletteFocusIndex + 1, count - 1);
      updatePaletteFocus();
      document.querySelector('#cmd-results .cmd-item.cmd-focused')?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      paletteFocusIndex = Math.max(paletteFocusIndex - 1, 0);
      updatePaletteFocus();
      document.querySelector('#cmd-results .cmd-item.cmd-focused')?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      selectPaletteItem(paletteFocusIndex >= 0 ? paletteFocusIndex : 0);
    } else if (e.key === 'Escape') {
      closePalette();
    }
  });
  overlay.addEventListener('click', e => { if (e.target === overlay) closePalette(); });
  document.getElementById('open-palette')?.addEventListener('click', openPalette);
}

// ── Global keyboard shortcuts ────────────────────────────────────────────
document.addEventListener('keydown', e => {
  // ⌘K / Ctrl+K → open palette
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    openPalette();
    return;
  }
  // Escape → close palette
  if (e.key === 'Escape') {
    closePalette();
    return;
  }
  // / → focus list search (when not already typing)
  const activeEl = document.activeElement;
  const isTyping = activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.isContentEditable);
  if (e.key === '/' && !isTyping && !e.metaKey && !e.ctrlKey) {
    const searchInput = document.getElementById('catalog-search');
    if (searchInput) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  }
});

window.addEventListener('resize', () => {
  if (detailCy) {
    detailCy.resize();
    detailCy.fit(detailCy.elements(), 28);
  }
  if (impactCy) {
    rerunImpactLayout();
  }
});

window.addEventListener('hashchange', () => {
  applyRouteFromHash();
});

initSidebarNav();
initPalette();
applyRouteFromHash();

// Warm up the world-atlas fetch in the background so the map is ready
// immediately when the user navigates to the Deployment Targets view.
if (typeof topojson !== 'undefined') {
  _dtLoadWorld().catch(() => {});
}
