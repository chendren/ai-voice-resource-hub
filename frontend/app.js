const CATEGORY_LABELS = {
  stt: "Speech-to-text",
  tts: "Text-to-speech",
  llm: "LLM",
  slm: "SLM",
  embedding: "Embeddings",
  realtime: "Realtime media",
  s2s: "Speech-to-speech",
  "voice-agent": "Voice agents",
  orchestration: "Orchestration",
  telephony: "Telephony",
  hosting: "Cloud hosting",
  container: "Containers",
  observability: "Observability",
  other: "Other",
};

const DEFAULT_ANSWER =
  "Describe the kind of voice product or workflow you want, and Voice Hub will turn the library into a shortlist-style recommendation.";

const state = {
  meta: null,
  dashboard: null,
  resources: [],
  selectedCategory: "",
  currentQuery: "",
  resourceLookup: new Map(),
};

const elements = {
  navAppTitle: document.getElementById("nav-app-title"),
  footerAppTitle: document.getElementById("footer-app-title"),
  appDescription: document.getElementById("app-description"),
  modelStatusLabel: document.getElementById("model-status-label"),
  modelStatusDetail: document.getElementById("model-status-detail"),
  navModelPill: document.getElementById("nav-model-pill"),
  notice: document.getElementById("notice"),
  searchForm: document.getElementById("search-form"),
  queryInput: document.getElementById("query-input"),
  categorySelect: document.getElementById("category-select"),
  includeUpdates: document.getElementById("include-updates"),
  clearSearchButton: document.getElementById("clear-search-button"),
  answerText: document.getElementById("answer-text"),
  rerankPill: document.getElementById("rerank-pill"),
  statsGrid: document.getElementById("stats-grid"),
  heroSignalStrip: document.getElementById("hero-signal-strip"),
  providerMarquee: document.getElementById("provider-marquee"),
  categoryChipRow: document.getElementById("category-chip-row"),
  resourceGrid: document.getElementById("resource-grid"),
  resourceResultMeta: document.getElementById("resource-result-meta"),
  localReadyGrid: document.getElementById("local-ready-grid"),
  cloudReadyGrid: document.getElementById("cloud-ready-grid"),
  realtimeGrid: document.getElementById("realtime-grid"),
  openSourceGrid: document.getElementById("open-source-grid"),
  updatesList: document.getElementById("updates-list"),
  feedSourceList: document.getElementById("feed-source-list"),
  refreshRunList: document.getElementById("refresh-run-list"),
  suggestedQueryGrid: document.getElementById("suggested-query-grid"),
  refreshCatalogButton: document.getElementById("refresh-catalog-button"),
  refreshSummary: document.getElementById("refresh-summary"),
  resourceModal: document.getElementById("resource-modal"),
  resourceModalBody: document.getElementById("resource-modal-body"),
};

document.addEventListener("DOMContentLoaded", () => {
  elements.searchForm.addEventListener("submit", (event) => {
    void handleSearchSubmit(event);
  });
  elements.refreshCatalogButton.addEventListener("click", () => {
    void triggerRefresh();
  });
  elements.clearSearchButton.addEventListener("click", () => {
    void resetSearchExperience({ announce: true });
  });
  elements.categorySelect.addEventListener("change", () => {
    state.selectedCategory = elements.categorySelect.value;
    renderCategoryChips(state.dashboard?.categories || []);
    if (state.currentQuery) {
      void rerunCurrentSearch();
    } else {
      void loadResources().catch((error) => {
        showNotice(`Could not update the library: ${formatError(error)}`, "error");
      });
    }
  });
  elements.includeUpdates.addEventListener("change", () => {
    if (state.currentQuery) {
      void rerunCurrentSearch();
    }
  });
  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("keydown", handleGlobalKeydown);
  void initialize();
});

async function initialize() {
  try {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("q")?.trim() || "";
    const category = params.get("category")?.trim() || "";
    const includeUpdates = params.get("includeUpdates") !== "false";

    state.selectedCategory = category;
    elements.includeUpdates.checked = includeUpdates;
    elements.answerText.textContent = DEFAULT_ANSWER;

    state.meta = await requestJson("/api/meta");
    document.title = `${state.meta.display_name} - Voice AI research workspace`;
    elements.navAppTitle.textContent = state.meta.display_name;
    elements.footerAppTitle.textContent = state.meta.display_name;
    elements.appDescription.textContent = state.meta.description;
    populateCategorySelect(state.meta.categories);
    elements.categorySelect.value = category;
    renderSuggestedQueries(state.meta.suggested_queries);
    renderModelStatus(state.meta.model_status);

    await loadDashboard();

    if (query) {
      elements.queryInput.value = query;
      await runSearch(query, { category, includeUpdates });
    }
  } catch (error) {
    showNotice(`Failed to load the library: ${formatError(error)}`, "error");
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

function showNotice(message, tone = "info") {
  elements.notice.textContent = message;
  elements.notice.dataset.tone = tone;
}

function clearNotice() {
  elements.notice.textContent = "";
  delete elements.notice.dataset.tone;
}

function formatError(error) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function handleDocumentClick(event) {
  const detailButton = event.target.closest("[data-resource-id]");
  if (detailButton) {
    void openResourceModal(detailButton.dataset.resourceId);
    return;
  }
  if (event.target.closest("[data-close-modal='true']")) {
    closeResourceModal();
  }
}

function handleGlobalKeydown(event) {
  if (event.key === "Escape") {
    closeResourceModal();
  }
}

function formatDate(value) {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}

function shortDate(value) {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function categoryLabel(category) {
  return CATEGORY_LABELS[category] || category;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function providerMonogram(provider) {
  const parts = String(provider)
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean);
  if (!parts.length) {
    return "VH";
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function providerTone(provider) {
  const tones = ["ink", "indigo", "teal", "amber", "rose"];
  const score = Array.from(String(provider)).reduce((sum, character) => sum + character.charCodeAt(0), 0);
  return tones[score % tones.length];
}

function renderProviderMark(provider, { small = false } = {}) {
  return `
    <span class="provider-mark tone-${providerTone(provider)} ${small ? "small-mark" : ""}" aria-hidden="true">
      ${escapeHtml(providerMonogram(provider))}
    </span>
  `;
}

function friendlyCadence(hours) {
  if (!hours || hours <= 0) {
    return "Regularly updated";
  }
  if (hours === 24) {
    return "Updated daily";
  }
  if (hours < 24) {
    return `Updated every ${hours} hours`;
  }
  const days = Math.round(hours / 24);
  return `Updated every ${days} day${days === 1 ? "" : "s"}`;
}

function resourcePerspective(resource) {
  if (resource.local_model_ready && resource.open_source) {
    return "A strong option for teams that want more ownership and room to customize.";
  }
  if (resource.local_model_ready) {
    return "Well suited to self-hosted or privacy-conscious workflows.";
  }
  if (resource.hosted_service && resource.category === "voice-agent") {
    return "Appealing when speed to production matters more than infrastructure work.";
  }
  if (resource.hosted_service) {
    return "Helpful for teams that want a faster path from prototype to launch.";
  }
  if (resource.open_source) {
    return "Useful as a foundational building block inside a broader stack.";
  }
  return "Worth reviewing as part of a modern voice AI evaluation shortlist.";
}

function resourceBadges(resource) {
  const badges = [];
  if (resource.local_model_ready) {
    badges.push("Self-hosted friendly");
  }
  if (resource.hosted_service) {
    badges.push("Managed option");
  }
  if (resource.open_source) {
    badges.push("Open source");
  }
  if (resource.freshness_score >= 85) {
    badges.push("Recently updated");
  }
  return badges.slice(0, 3);
}

function registerResources(resources) {
  resources.forEach((resource) => {
    state.resourceLookup.set(resource.id, resource);
  });
}

function renderProviderMarquee(resources) {
  if (!elements.providerMarquee) {
    return;
  }
  const providerCounts = new Map();
  resources.forEach((resource) => {
    if (!resource.provider) {
      return;
    }
    providerCounts.set(resource.provider, (providerCounts.get(resource.provider) || 0) + 1);
  });
  const providers = [...providerCounts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 10)
    .map(([provider]) => provider);

  elements.providerMarquee.innerHTML = providers
    .map(
      (provider) => `
        <div class="provider-pill">
          ${renderProviderMark(provider, { small: true })}
          <span>${escapeHtml(provider)}</span>
        </div>
      `,
    )
    .join("");
}

function renderModelStatus(status) {
  if (!status) {
    return;
  }

  const fullyReady = status.available && status.detail === "available";
  const warning = status.available && status.detail !== "available";

  if (fullyReady) {
    elements.modelStatusLabel.textContent = "AI-assisted matching is available";
    elements.modelStatusDetail.textContent =
      "Recommendations are refined locally before they appear in the shortlist.";
    elements.navModelPill.textContent = "AI-assisted";
    elements.navModelPill.dataset.state = "online";
    return;
  }

  if (warning) {
    elements.modelStatusLabel.textContent = "Curated search is live";
    elements.modelStatusDetail.textContent =
      "The library is available now, though the enhanced matching layer needs a quick model check.";
    elements.navModelPill.textContent = "Enhanced matching limited";
    elements.navModelPill.dataset.state = "warning";
    return;
  }

  elements.modelStatusLabel.textContent = "Curated search is still available";
  elements.modelStatusDetail.textContent =
    "Voice Hub can still guide you with the library even when local AI refinement is temporarily unavailable.";
  elements.navModelPill.textContent = "Standard matching";
  elements.navModelPill.dataset.state = "fallback";
}

function populateCategorySelect(categories) {
  elements.categorySelect.innerHTML = '<option value="">All categories</option>';
  for (const category of categories) {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = CATEGORY_LABELS[category] || category;
    elements.categorySelect.append(option);
  }
}

function renderSuggestedQueries(queries) {
  elements.suggestedQueryGrid.innerHTML = "";
  queries.forEach((query) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "query-prompt";
    button.textContent = query;
    button.addEventListener("click", () => {
      elements.queryInput.value = query;
      void runSearch(query, {
        category: elements.categorySelect.value,
        includeUpdates: elements.includeUpdates.checked,
      }).catch((error) => {
        showNotice(`Search failed: ${formatError(error)}`, "error");
      });
    });
    elements.suggestedQueryGrid.append(button);
  });
}

function renderHeroSignals(stats) {
  const activeCategories = Object.values(stats.category_counts || {}).filter((value) => value > 0).length;
  const items = [
    {
      title: `${stats.curated_count} selected resources`,
      detail: "A curated starting point rather than a noisy list of links.",
    },
    {
      title: `${activeCategories} voice AI categories`,
      detail: "From speech models to deployment infrastructure.",
    },
    {
      title: stats.update_count ? `${stats.update_count} recent ecosystem updates` : "Daily refresh coverage",
      detail: "Trusted source monitoring helps the library stay current.",
    },
  ];

  elements.heroSignalStrip.innerHTML = items
    .map(
      (item) => `
        <article class="signal-card">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.detail)}</p>
        </article>
      `,
    )
    .join("");
}

function renderStats(stats) {
  const activeCategories = Object.values(stats.category_counts || {}).filter((value) => value > 0).length;
  const cards = [
    {
      label: "Curated",
      value: `${stats.curated_count} selected entries`,
      detail: "A cleaner starting point than a generic web search.",
    },
    {
      label: "Current",
      value: stats.update_count ? `${stats.update_count} fresh signals` : "Daily checks",
      detail: "The directory watches trusted sources for meaningful changes.",
    },
    {
      label: "Broad coverage",
      value: `${activeCategories} categories`,
      detail: "Speech, agents, hosting, observability, and more.",
    },
    {
      label: "Decision-ready",
      value: "Compare with confidence",
      detail: "Clear summaries, curated groupings, and detailed profiles help narrow the field.",
    },
  ];

  elements.statsGrid.innerHTML = cards
    .map(
      (card) => `
        <article class="stat-card">
          <span>${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(card.value)}</strong>
          <p>${escapeHtml(card.detail)}</p>
        </article>
      `,
    )
    .join("");
}

function renderRefreshSummary(refreshRuns) {
  const latest = refreshRuns[0];
  if (!latest) {
    elements.refreshSummary.textContent = "The first scheduled refresh will appear here.";
    return;
  }
  const source = latest.used_sample_fallback ? "sample data" : "tracked sources";
  elements.refreshSummary.innerHTML = `
    <strong>${escapeHtml(latest.mode)} refresh</strong>
    <span>${latest.items_upserted} items added from ${escapeHtml(source)}</span>
    <span>${escapeHtml(formatDate(latest.finished_at || latest.started_at))}</span>
  `;
}

function renderResourceMeta(count) {
  const headline = state.currentQuery
    ? `${count} recommendations${state.selectedCategory ? ` in ${categoryLabel(state.selectedCategory)}` : ""}`
    : `${count} resources${state.selectedCategory ? ` in ${categoryLabel(state.selectedCategory)}` : ""}`;
  const detail = state.currentQuery
    ? "Curated results shaped by the library, filters, and recent updates."
    : "Browse the full directory or refine the view with filters above.";

  elements.resourceResultMeta.innerHTML = `
    <strong>${escapeHtml(headline)}</strong>
    <span>${escapeHtml(detail)}</span>
  `;
}

function renderBadgeMarkup(resource) {
  return resourceBadges(resource)
    .map((badge) => `<span class="tag-badge">${escapeHtml(badge)}</span>`)
    .join("");
}

function renderResourceFacts(resource) {
  const facts = [
    {
      label: "Deployment",
      value: resource.deployment || "Flexible",
    },
    {
      label: "Pricing",
      value: resource.pricing_model || "Varies",
    },
    {
      label: "Updated",
      value: shortDate(resource.last_updated || resource.updated_at),
    },
  ];

  return `
    <div class="resource-fact-grid">
      ${facts
        .map(
          (fact) => `
            <div class="resource-fact">
              <span>${escapeHtml(fact.label)}</span>
              <strong>${escapeHtml(fact.value)}</strong>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderResourceCard(resource, { compact = false } = {}) {
  return `
    <article class="resource-card ${compact ? "compact-card" : ""}" data-category="${escapeHtml(resource.category)}">
      <div class="resource-card-top">
        <div class="resource-identity">
          ${renderProviderMark(resource.provider)}
          <div>
            <p class="provider-caption">${escapeHtml(resource.provider)}</p>
            <h3>${escapeHtml(resource.name)}</h3>
          </div>
        </div>
        <span class="resource-category-pill">${escapeHtml(categoryLabel(resource.category))}</span>
      </div>
      <p class="resource-summary">${escapeHtml(resource.summary)}</p>
      ${renderResourceFacts(resource)}
      <p class="resource-fit">${escapeHtml(resourcePerspective(resource))}</p>
      ${renderBadgeMarkup(resource) ? `<div class="badge-row">${renderBadgeMarkup(resource)}</div>` : ""}
      <div class="card-actions">
        <button type="button" class="tertiary-button" data-resource-id="${resource.id}">View details</button>
        <a class="secondary-button inline-link" href="${escapeHtml(resource.resource_url)}" target="_blank" rel="noreferrer">Open resource</a>
      </div>
    </article>
  `;
}

function renderCategoryChips(categories) {
  const chips = [
    {
      category: "",
      label: "All categories",
      count: state.dashboard?.stats?.curated_count || 0,
    },
    ...categories.map((item) => ({
      category: item.category,
      label: categoryLabel(item.category),
      count: item.count,
    })),
  ];

  elements.categoryChipRow.innerHTML = chips
    .map(
      (item) => `
        <button
          type="button"
          class="filter-chip ${item.category === state.selectedCategory ? "active" : ""}"
          data-category="${item.category}"
        >
          <span>${escapeHtml(item.label)}</span>
          <strong>${item.count}</strong>
        </button>
      `,
    )
    .join("");

  elements.categoryChipRow.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedCategory = button.dataset.category || "";
      elements.categorySelect.value = state.selectedCategory;
      renderCategoryChips(categories);
      if (state.currentQuery) {
        void rerunCurrentSearch();
      } else {
        void loadResources().catch((error) => {
          showNotice(`Could not update the library: ${formatError(error)}`, "error");
        });
      }
    });
  });
}

function renderResourceGrid(resources) {
  if (!resources.length) {
    elements.resourceGrid.innerHTML = `
      <div class="empty-state">
        <h3>No results matched this view</h3>
        <p>Try broadening the brief, switching categories, or returning to the full library.</p>
      </div>
    `;
    return;
  }
  elements.resourceGrid.innerHTML = resources.map((resource) => renderResourceCard(resource)).join("");
}

function renderCompactSection(target, resources, emptyMessage) {
  if (!resources.length) {
    target.innerHTML = `<p class="muted">${escapeHtml(emptyMessage)}</p>`;
    return;
  }
  registerResources(resources);
  target.innerHTML = resources.map((resource) => renderResourceCard(resource, { compact: true })).join("");
}

function renderUpdates(updates) {
  if (!updates.length) {
    elements.updatesList.innerHTML = '<p class="muted">No recent ecosystem updates have been added yet.</p>';
    return;
  }

  registerResources(updates);
  elements.updatesList.innerHTML = updates
    .map(
      (item, index) => `
        <article class="journal-item ${index === 0 ? "featured-update" : ""}">
          <div class="journal-topline">
            <span class="journal-source">${escapeHtml(item.source_name || item.provider)}</span>
            <span>${escapeHtml(shortDate(item.last_updated || item.updated_at))}</span>
          </div>
          <h3>${escapeHtml(item.name)}</h3>
          <p>${escapeHtml(item.summary)}</p>
          <div class="journal-actions">
            <button type="button" class="inline-text-button" data-resource-id="${item.id}">View details</button>
            <a href="${escapeHtml(item.resource_url)}" target="_blank" rel="noreferrer">Open source</a>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderFeedSources(items) {
  if (!items.length) {
    elements.feedSourceList.innerHTML = '<p class="muted">No tracked sources are configured yet.</p>';
    return;
  }

  elements.feedSourceList.innerHTML = items
    .map(
      (item) => `
        <article class="source-item">
          <div class="source-topline">
            <strong>${escapeHtml(item.name)}</strong>
            <span class="status-chip ${item.enabled ? "enabled" : "disabled"}">${item.enabled ? "Active" : "Paused"}</span>
          </div>
          <p>${escapeHtml(item.url)}</p>
          <div class="source-meta">
            <span>${escapeHtml(categoryLabel(item.category_hint))}</span>
            <span>${escapeHtml(friendlyCadence(item.update_interval_hours))}</span>
            <span>${escapeHtml(item.last_checked_at ? `Checked ${shortDate(item.last_checked_at)}` : "Awaiting first check")}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderRefreshRuns(items) {
  if (!items.length) {
    elements.refreshRunList.innerHTML = '<p class="muted">No refresh history is available yet.</p>';
    return;
  }

  elements.refreshRunList.innerHTML = items
    .map(
      (item) => `
        <article class="source-item run-item">
          <div class="source-topline">
            <strong>${escapeHtml(item.mode)} refresh</strong>
            <span class="status-chip ${item.status === "completed" ? "enabled" : "disabled"}">${escapeHtml(item.status)}</span>
          </div>
          <p>${escapeHtml(item.message)}</p>
          <div class="source-meta">
            <span>${item.items_upserted} items added</span>
            <span>${item.items_discovered} signals reviewed</span>
            <span>${escapeHtml(shortDate(item.finished_at || item.started_at))}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderDefinition(label, value) {
  return `
    <div class="detail-item">
      <dt>${escapeHtml(label)}</dt>
      <dd>${escapeHtml(value)}</dd>
    </div>
  `;
}

function renderResourceModal(resource) {
  const tags = (resource.tags || [])
    .map((tag) => `<span class="tag-badge">${escapeHtml(tag)}</span>`)
    .join("");
  const statuses = resourceBadges(resource);
  const sourceLabel = resource.source_name || resource.provider;
  const rerankReason = resource.rerank_reason
    ? `
      <article class="modal-note">
        <span>Why it may fit</span>
        <p>${escapeHtml(resource.rerank_reason)}</p>
      </article>
    `
    : "";

  return `
    <div class="modal-header">
      <div class="resource-identity">
        ${renderProviderMark(resource.provider)}
        <div>
          <p class="provider-caption">${escapeHtml(resource.provider)}</p>
          <h2 id="resource-modal-title">${escapeHtml(resource.name)}</h2>
        </div>
      </div>
      <span class="resource-category-pill">${escapeHtml(categoryLabel(resource.category))}</span>
    </div>

    <p class="modal-summary">${escapeHtml(resource.summary)}</p>
    <p class="resource-fit modal-fit">${escapeHtml(resourcePerspective(resource))}</p>

    <dl class="detail-grid">
      ${renderDefinition("Deployment", resource.deployment || "Flexible deployment")}
      ${renderDefinition("Pricing", resource.pricing_model || "Pricing varies")}
      ${renderDefinition("Updated", shortDate(resource.last_updated || resource.updated_at))}
      ${renderDefinition("Source", sourceLabel)}
      ${renderDefinition("Reference", resource.source_url || resource.resource_url)}
      ${renderDefinition("Availability", statuses.length ? statuses.join(", ") : "Curated listing")}
    </dl>

    ${tags ? `<div class="badge-row modal-tags">${tags}</div>` : ""}
    ${rerankReason}

    <div class="modal-actions">
      <a class="secondary-button inline-link" href="${escapeHtml(resource.resource_url)}" target="_blank" rel="noreferrer">Open official resource</a>
      ${resource.source_url ? `<a class="inline-text-button" href="${escapeHtml(resource.source_url)}" target="_blank" rel="noreferrer">View source reference</a>` : ""}
    </div>
  `;
}

function setModalOpen(isOpen) {
  elements.resourceModal.classList.toggle("hidden", !isOpen);
  elements.resourceModal.setAttribute("aria-hidden", String(!isOpen));
  document.body.classList.toggle("modal-open", isOpen);
}

function closeResourceModal() {
  setModalOpen(false);
}

async function openResourceModal(resourceIdValue) {
  const resourceId = Number(resourceIdValue);
  if (!Number.isFinite(resourceId)) {
    return;
  }

  try {
    let resource = state.resourceLookup.get(resourceId);
    if (!resource || !resource.summary) {
      resource = await requestJson(`/api/resources/${resourceId}`);
      state.resourceLookup.set(resourceId, resource);
    }
    elements.resourceModalBody.innerHTML = renderResourceModal(resource);
    setModalOpen(true);
  } catch (error) {
    showNotice(`Could not load resource details: ${formatError(error)}`, "error");
  }
}

async function loadDashboard() {
  state.dashboard = await requestJson("/api/dashboard");
  renderModelStatus(state.dashboard.model_status);
  renderHeroSignals(state.dashboard.stats);
  renderStats(state.dashboard.stats);
  renderCategoryChips(state.dashboard.categories);
  renderRefreshSummary(state.dashboard.refresh_runs);
  const featuredResources = [
    ...state.dashboard.featured.local_ready,
    ...state.dashboard.featured.cloud_ready,
    ...state.dashboard.featured.realtime_stack,
    ...state.dashboard.featured.open_source,
    ...state.dashboard.updates,
  ];
  registerResources(featuredResources);
  renderProviderMarquee(featuredResources);
  renderCompactSection(elements.localReadyGrid, state.dashboard.featured.local_ready, "No self-hosted highlights are available yet.");
  renderCompactSection(elements.cloudReadyGrid, state.dashboard.featured.cloud_ready, "No managed options are highlighted yet.");
  renderCompactSection(elements.realtimeGrid, state.dashboard.featured.realtime_stack, "No realtime highlights are available yet.");
  renderCompactSection(elements.openSourceGrid, state.dashboard.featured.open_source, "No open-source highlights are available yet.");
  renderUpdates(state.dashboard.updates);
  renderFeedSources(state.dashboard.feed_sources);
  renderRefreshRuns(state.dashboard.refresh_runs);
  await loadResources();
}

async function loadResources() {
  const params = new URLSearchParams();
  if (state.selectedCategory) {
    params.set("category", state.selectedCategory);
  }
  const url = params.toString() ? `/api/resources?${params.toString()}` : "/api/resources";
  const response = await requestJson(url);
  state.resources = response.results;
  registerResources(response.results);
  renderResourceGrid(response.results);
  renderResourceMeta(response.results.length);
}

function syncSearchParams(query, { category, includeUpdates }) {
  const params = new URLSearchParams(window.location.search);
  if (query) {
    params.set("q", query);
  } else {
    params.delete("q");
  }
  if (category) {
    params.set("category", category);
  } else {
    params.delete("category");
  }
  if (!includeUpdates) {
    params.set("includeUpdates", "false");
  } else {
    params.delete("includeUpdates");
  }
  const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
  window.history.replaceState({}, "", nextUrl);
}

async function runSearch(query, { category, includeUpdates }) {
  state.currentQuery = query;
  syncSearchParams(query, { category, includeUpdates });

  const params = new URLSearchParams({
    q: query,
    include_updates: String(includeUpdates),
  });
  if (category) {
    params.set("category", category);
  }

  const payload = await requestJson(`/api/search?${params.toString()}`);
  state.resources = payload.results;
  registerResources(payload.results);
  elements.answerText.textContent = payload.answer || DEFAULT_ANSWER;
  elements.rerankPill.classList.toggle("hidden", !payload.rerank_applied);
  renderResourceGrid(payload.results);
  renderResourceMeta(payload.results.length);
  showNotice(
    `Showing ${payload.results.length} recommendation${payload.results.length === 1 ? "" : "s"} for "${query}".`,
    payload.rerank_applied ? "success" : "info",
  );
}

async function rerunCurrentSearch() {
  try {
    if (!state.currentQuery) {
      await loadResources();
      return;
    }
    await runSearch(state.currentQuery, {
      category: state.selectedCategory,
      includeUpdates: elements.includeUpdates.checked,
    });
  } catch (error) {
    showNotice(`Search failed: ${formatError(error)}`, "error");
  }
}

async function resetSearchExperience({ announce = false } = {}) {
  clearNotice();
  try {
    state.currentQuery = "";
    elements.queryInput.value = "";
    elements.answerText.textContent = DEFAULT_ANSWER;
    elements.rerankPill.classList.add("hidden");
    syncSearchParams("", {
      category: state.selectedCategory,
      includeUpdates: elements.includeUpdates.checked,
    });
    await loadResources();
    if (announce) {
      showNotice("Back to the full library.", "info");
    }
  } catch (error) {
    showNotice(`Could not restore the library: ${formatError(error)}`, "error");
  }
}

async function handleSearchSubmit(event) {
  event.preventDefault();
  clearNotice();
  const query = elements.queryInput.value.trim();
  if (!query) {
    return;
  }
  try {
    await runSearch(query, {
      category: elements.categorySelect.value,
      includeUpdates: elements.includeUpdates.checked,
    });
  } catch (error) {
    showNotice(`Search failed: ${formatError(error)}`, "error");
  }
}

async function triggerRefresh() {
  clearNotice();
  showNotice("Refreshing the library...", "info");
  try {
    const payload = await requestJson("/api/refresh", {
      method: "POST",
      body: JSON.stringify({ mode: "smart" }),
    });
    state.dashboard = payload.dashboard;
    renderModelStatus(state.dashboard.model_status);
    renderHeroSignals(state.dashboard.stats);
    renderStats(state.dashboard.stats);
    renderCategoryChips(state.dashboard.categories);
    renderRefreshSummary(state.dashboard.refresh_runs);
    registerResources([
      ...state.dashboard.featured.local_ready,
      ...state.dashboard.featured.cloud_ready,
      ...state.dashboard.featured.realtime_stack,
      ...state.dashboard.featured.open_source,
      ...state.dashboard.updates,
    ]);
    renderCompactSection(elements.localReadyGrid, state.dashboard.featured.local_ready, "No self-hosted highlights are available yet.");
    renderCompactSection(elements.cloudReadyGrid, state.dashboard.featured.cloud_ready, "No managed options are highlighted yet.");
    renderCompactSection(elements.realtimeGrid, state.dashboard.featured.realtime_stack, "No realtime highlights are available yet.");
    renderCompactSection(elements.openSourceGrid, state.dashboard.featured.open_source, "No open-source highlights are available yet.");
    renderUpdates(state.dashboard.updates);
    renderFeedSources(state.dashboard.feed_sources);
    renderRefreshRuns(state.dashboard.refresh_runs);
    if (state.currentQuery) {
      await rerunCurrentSearch();
    } else {
      await loadResources();
    }
    showNotice(payload.message, payload.used_sample_fallback ? "info" : "success");
  } catch (error) {
    showNotice(`Refresh failed: ${formatError(error)}`, "error");
  }
}
