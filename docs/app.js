const state = {
  drugs: [],
  products: [],
  metadata: null,
  current: [],
  next: [],
  shardCache: new Map(),
};

const els = {
  dataStatus: document.querySelector("#dataStatus"),
  metadata: document.querySelector("#metadata"),
  currentSearch: document.querySelector("#currentSearch"),
  newSearch: document.querySelector("#newSearch"),
  currentSuggestions: document.querySelector("#currentSuggestions"),
  newSuggestions: document.querySelector("#newSuggestions"),
  currentSelected: document.querySelector("#currentSelected"),
  newSelected: document.querySelector("#newSelected"),
  checkButton: document.querySelector("#checkButton"),
  resetButton: document.querySelector("#resetButton"),
  clearCurrent: document.querySelector("#clearCurrent"),
  clearNew: document.querySelector("#clearNew"),
  results: document.querySelector("#results"),
  exampleButtons: document.querySelectorAll(".example-button"),
};

function normalizeText(value) {
  return String(value || "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function uniqueIngredients(ingredients) {
  const seen = new Set();
  const mapped = [];
  for (const ingredient of ingredients || []) {
    if (!ingredient.ddinterId || seen.has(ingredient.ddinterId)) continue;
    seen.add(ingredient.ddinterId);
    mapped.push(ingredient);
  }
  return mapped;
}

function productCandidate(product) {
  const ingredients = uniqueIngredients(product.ingredients);
  const unmatchedCount = (product.unmatchedIngredients || []).length;
  return {
    type: "product",
    label: product.productName,
    subtitle: [product.dosageForm, product.nie].filter(Boolean).join(" · "),
    detail: product.composition || "Composition unavailable in BPOM file",
    source: "BPOM",
    ingredients,
    unmatchedIngredients: product.unmatchedIngredients || [],
    matchStatus: product.matchStatus || "",
    matchMethod: product.matchMethod || "",
    mappingSummary: `${ingredients.length} mapped ingredient${ingredients.length === 1 ? "" : "s"}${unmatchedCount ? ` · ${unmatchedCount} not covered` : ""}`,
    raw: product,
  };
}

function ingredientCandidate(drug) {
  return {
    type: "ingredient",
    label: drug.name,
    subtitle: drug.id,
    detail: "Direct DDInter ingredient match",
    source: "DDInter",
    ingredients: [
      {
        raw: drug.name,
        ddinterId: drug.id,
        ddinterName: drug.name,
        matchedAs: drug.name,
        method: "direct",
      },
    ],
  };
}

function scoreCandidate(candidate, queryNorm) {
  const name = normalizeText(candidate.label);
  const detail = normalizeText(`${candidate.subtitle} ${candidate.detail}`);
  const unmappedPenalty = candidate.ingredients.length ? 0 : 5;
  if (name === queryNorm) return 0;
  if (candidate.type === "ingredient" && name === queryNorm) return 0;
  if (name.startsWith(queryNorm)) return 1 + unmappedPenalty;
  if (candidate.type === "ingredient" && name.startsWith(queryNorm)) return 1 + unmappedPenalty;
  if (name.includes(queryNorm)) return 2 + unmappedPenalty;
  if (detail.includes(queryNorm)) return 4 + unmappedPenalty;
  return 8 + unmappedPenalty;
}

function searchCandidates(query) {
  const q = normalizeText(query);
  if (q.length < 2) return [];

  const productMatches = state.products
    .filter((product) => normalizeText(`${product.productName} ${product.composition}`).includes(q))
    .map(productCandidate);

  const ingredientMatches = state.drugs
    .filter((drug) => normalizeText(drug.name).includes(q))
    .map(ingredientCandidate);

  const seen = new Set();
  const deduped = [];
  for (const candidate of [...productMatches, ...ingredientMatches]) {
    const key = [
      candidate.type,
      normalizeText(candidate.label),
      candidate.ingredients.map((ingredient) => ingredient.ddinterId).join("/"),
      candidate.mappingSummary || "",
    ].join("|");
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(candidate);
  }

  return deduped
    .sort((a, b) => scoreCandidate(a, q) - scoreCandidate(b, q) || a.label.localeCompare(b.label))
    .slice(0, 10);
}

function renderSuggestions(target, query, container) {
  const candidates = searchCandidates(query);
  if (!query.trim()) {
    container.innerHTML = "";
    return;
  }
  if (!candidates.length) {
    container.innerHTML = '<div class="empty-state">No match. Try an active ingredient or another product spelling.</div>';
    return;
  }

  container.innerHTML = candidates
    .map((candidate, index) => {
      const mappedCount = candidate.ingredients.length;
      const mappingText =
        candidate.type === "product"
          ? candidate.mappingSummary
          : "Ingredient";
      return `
        <button class="suggestion" type="button" data-target="${target}" data-index="${index}">
          <div class="suggestion-title">
            <span>${escapeHtml(candidate.label)}</span>
            <span class="tag">${escapeHtml(candidate.source)}</span>
          </div>
          <div class="suggestion-detail">${escapeHtml(candidate.subtitle || mappingText)}</div>
          <div class="suggestion-detail">${escapeHtml(candidate.detail)}</div>
          <div class="suggestion-detail">${escapeHtml(mappingText)}</div>
        </button>
      `;
    })
    .join("");

  container.querySelectorAll(".suggestion").forEach((button) => {
    button.addEventListener("click", () => {
      const candidate = candidates[Number(button.dataset.index)];
      addSelection(button.dataset.target, candidate);
      const input = button.dataset.target === "current" ? els.currentSearch : els.newSearch;
      input.value = "";
      container.innerHTML = "";
    });
  });
}

function addSelection(target, candidate) {
  const list = target === "current" ? state.current : state.next;
  list.push(candidate);
  renderSelections();
  updateCheckButton();
}

function removeSelection(target, index) {
  const list = target === "current" ? state.current : state.next;
  list.splice(index, 1);
  renderSelections();
  updateCheckButton();
}

function renderSelections() {
  renderSelectionList("current", state.current, els.currentSelected);
  renderSelectionList("new", state.next, els.newSelected);
  updateCheckButton();
}

function renderSelectionList(target, list, container) {
  if (!list.length) {
    container.innerHTML = '<div class="empty-state">No medications selected.</div>';
    return;
  }

  container.innerHTML = list
    .map((item, index) => {
      const ingredients = item.ingredients.length
        ? item.ingredients.map((ing) => `${ing.raw} → ${ing.ddinterName}`).join("; ")
        : "No DDInter ingredient mapping available";
      const unresolved = (item.unmatchedIngredients || []).length
        ? item.unmatchedIngredients.map((ing) => `${ing.raw}: ${ing.message}`).join("; ")
        : "";
      return `
        <div class="selected-item">
          <div class="selected-title">
            <span>${escapeHtml(item.label)}</span>
            <button class="remove-button" type="button" data-target="${target}" data-index="${index}" title="Remove">×</button>
          </div>
          <div class="resolved-detail">Type: ${escapeHtml(item.type)} · Source: ${escapeHtml(item.source)}</div>
          <div class="resolved-detail">Checked as: ${escapeHtml(ingredients)}</div>
          ${unresolved ? `<div class="resolved-warning">${escapeHtml(unresolved)}</div>` : ""}
        </div>
      `;
    })
    .join("");

  container.querySelectorAll(".remove-button").forEach((button) => {
    button.addEventListener("click", () => removeSelection(button.dataset.target, Number(button.dataset.index)));
  });
}

async function loadShard(firstId) {
  if (state.shardCache.has(firstId)) return state.shardCache.get(firstId);
  const response = await fetch(`data/interactions/${encodeURIComponent(firstId)}.json`);
  if (!response.ok) {
    state.shardCache.set(firstId, {});
    return {};
  }
  const shard = await response.json();
  state.shardCache.set(firstId, shard);
  return shard;
}

async function findInteraction(leftId, rightId) {
  const [first, second] = [leftId, rightId].sort();
  const shard = await loadShard(first);
  return shard[second] || null;
}

function severityClass(value) {
  const sev = String(value || "").toLowerCase();
  if (sev.includes("major")) return "major";
  if (sev.includes("moderate")) return "moderate";
  if (sev.includes("minor")) return "minor";
  if (sev.includes("unknown")) return "unknown";
  return "unrated";
}

function severityRank(interaction) {
  if (!interaction) return 60;
  const cls = severityClass(interaction.severity || "Severity unrated");
  if (cls === "major") return 10;
  if (cls === "moderate") return 20;
  if (cls === "minor") return 30;
  if (cls === "unknown") return 40;
  return 50;
}

function sortCheckedResults(results) {
  return [...results].sort((left, right) => {
    const rankDelta = severityRank(left.interaction) - severityRank(right.interaction);
    if (rankDelta) return rankDelta;

    const leftHasMechanism = Boolean(left.interaction?.mechanism);
    const rightHasMechanism = Boolean(right.interaction?.mechanism);
    if (leftHasMechanism !== rightHasMechanism) return leftHasMechanism ? -1 : 1;

    const leftLabel = `${left.newIngredient.name} ${left.currentIngredient.name}`;
    const rightLabel = `${right.newIngredient.name} ${right.currentIngredient.name}`;
    return leftLabel.localeCompare(rightLabel);
  });
}

function severityLabel(interaction) {
  if (!interaction) return "No record";
  return interaction.severity || "Severity unrated";
}

function severityBadgeText(interaction) {
  const label = severityLabel(interaction);
  if (label === "Severity unrated") return label;
  if (label === "No record") return label;
  return `Severity: ${label}`;
}

function resultGroup(interaction) {
  const rank = severityRank(interaction);
  if (rank === 10) return "Major";
  if (rank === 20) return "Moderate";
  if (rank === 30) return "Minor";
  if (rank === 40) return "Unknown";
  if (rank === 50) return "Unrated";
  return "No record";
}

function groupHeading(groupName) {
  const detail = {
    Major: "Highest attention. Review before proceeding.",
    Moderate: "Potentially important. Check context and monitoring.",
    Minor: "Lower-priority records from the local dataset.",
    Unknown: "DDInter has a record, but no classified risk level.",
    Unrated: "Mechanism or pair data exists, but DDInter severity is unavailable.",
    "No record": "No local interaction record found. This is not proof of safety.",
  }[groupName];
  return `
    <div class="result-group result-group-${groupName.toLowerCase().replaceAll(" ", "-")}">
      <div>
        <span>${escapeHtml(groupName)}</span>
        <p>${escapeHtml(detail)}</p>
      </div>
    </div>
  `;
}

function flattenSelections(list) {
  const rows = [];
  for (const selection of list) {
    for (const ingredient of selection.ingredients) {
      if (!ingredient.ddinterId) continue;
      rows.push({
        entered: selection.label,
        type: selection.type,
        id: ingredient.ddinterId,
        name: ingredient.ddinterName,
        raw: ingredient.raw,
      });
    }
  }
  return rows;
}

function collectUnmappedSelections(list) {
  const rows = [];
  for (const selection of list) {
    for (const ingredient of selection.unmatchedIngredients || []) {
      rows.push({
        entered: selection.label,
        raw: ingredient.raw,
        status: ingredient.status,
        message: ingredient.message,
      });
    }
  }
  return rows;
}

function pairCount() {
  return flattenSelections(state.current).length * flattenSelections(state.next).length;
}

function updateCheckButton() {
  const count = pairCount();
  els.checkButton.textContent = count ? `Check ${count} pair${count === 1 ? "" : "s"}` : "Check interaction";
}

function resultSummary(results, unmappedCount) {
  const counts = { major: 0, moderate: 0, minor: 0, unknown: 0, noMatch: 0 };
  for (const result of results) {
    if (!result.interaction) {
      counts.noMatch += 1;
      continue;
    }
    const cls = severityClass(result.interaction.severity || "Severity unrated");
    if (cls === "major") counts.major += 1;
    else if (cls === "moderate") counts.moderate += 1;
    else if (cls === "minor") counts.minor += 1;
    else counts.unknown += 1;
  }
  return `
    <section class="result-summary" aria-label="Interaction summary">
      <div><strong>${results.length}</strong><span>pairs checked</span></div>
      <div><strong>${counts.major}</strong><span>major</span></div>
      <div><strong>${counts.moderate}</strong><span>moderate</span></div>
      <div><strong>${counts.unknown}</strong><span>unknown</span></div>
      <div><strong>${counts.noMatch}</strong><span>no match</span></div>
      <div><strong>${unmappedCount}</strong><span>not covered</span></div>
    </section>
  `;
}

async function checkInteractions() {
  const current = flattenSelections(state.current);
  const next = flattenSelections(state.next);
  const unmapped = [...collectUnmappedSelections(state.current), ...collectUnmappedSelections(state.next)];
  if (!current.length || !next.length) {
    const extra = unmapped.length
      ? `<div class="coverage-note">${unmapped
          .map((item) => `<div><strong>${escapeHtml(item.raw)}</strong>: ${escapeHtml(item.message)}</div>`)
          .join("")}</div>`
      : "";
    els.results.innerHTML = `<div class="empty-state">Select at least one mapped current medication and one mapped new medication.</div>${extra}`;
    return;
  }

  els.results.innerHTML = '<div class="empty-state">Checking selected ingredient pairs...</div>';
  const checkedResults = [];

  for (const newIngredient of next) {
    for (const currentIngredient of current) {
      if (newIngredient.id === currentIngredient.id) continue;
      const interaction = await findInteraction(newIngredient.id, currentIngredient.id);
      checkedResults.push({ newIngredient, currentIngredient, interaction });
    }
  }

  const sortedResults = sortCheckedResults(checkedResults);
  const cards = [];
  let currentGroup = "";

  for (const { newIngredient, currentIngredient, interaction } of sortedResults) {
    const group = resultGroup(interaction);
    if (group !== currentGroup) {
      cards.push(groupHeading(group));
      currentGroup = group;
    }

    if (!interaction) {
      cards.push(`
        <article class="result-card">
          <div class="result-title">${escapeHtml(newIngredient.name)} vs ${escapeHtml(currentIngredient.name)}
            <span class="severity unrated">${escapeHtml(severityBadgeText(interaction))}</span>
          </div>
          <p class="result-body">No interaction record found in the local DDInter/MecDDI dataset. This is absence of data, not confirmation of safety.</p>
          <div class="source-line">Inputs: ${escapeHtml(newIngredient.entered)} vs ${escapeHtml(currentIngredient.entered)}</div>
        </article>
      `);
      continue;
    }

    const severity = interaction.severity || "Severity unrated";
    const mechanism = interaction.mechanism || "No mechanism description available.";
    const sourceBits = [
      interaction.severitySource ? `severity: ${interaction.severitySource}` : "severity: unrated",
      interaction.mechanismSource ? `mechanism: ${interaction.mechanismSource}` : "mechanism: unavailable",
    ];
    cards.push(`
      <article class="result-card">
        <div class="result-title">${escapeHtml(newIngredient.name)} vs ${escapeHtml(currentIngredient.name)}
          <span class="severity ${severityClass(severity)}">${escapeHtml(severityBadgeText(interaction))}</span>
        </div>
        <p class="result-body">${escapeHtml(mechanism)}</p>
        <div class="source-line">${escapeHtml(sourceBits.join(" · "))}</div>
        <div class="source-line">Inputs: ${escapeHtml(newIngredient.entered)} vs ${escapeHtml(currentIngredient.entered)}</div>
      </article>
    `);
  }

  if (unmapped.length) {
    cards.push(`
      <div class="result-group result-group-unrated">
        <div>
          <span>Coverage Notes</span>
          <p>Recognized ingredients that could not be checked against DDInter/MecDDI.</p>
        </div>
      </div>
      <article class="result-card">
        <div class="result-title">Not checked <span class="severity unrated">Not covered</span></div>
        <p class="result-body">${unmapped
          .map((item) => `${item.raw}: ${item.message}`)
          .map(escapeHtml)
          .join("<br>")}</p>
      </article>
    `);
  }

  els.results.innerHTML =
    resultSummary(checkedResults, unmapped.length) +
    (cards.join("") || '<div class="empty-state">No ingredient pairs to check.</div>');
}

function resetAll() {
  state.current = [];
  state.next = [];
  els.currentSearch.value = "";
  els.newSearch.value = "";
  els.currentSuggestions.innerHTML = "";
  els.newSuggestions.innerHTML = "";
  els.results.innerHTML = "";
  renderSelections();
}

function selectFirstCandidate(query) {
  return searchCandidates(query)[0] || null;
}

function loadExample(currentQuery, newQuery) {
  const current = selectFirstCandidate(currentQuery);
  const next = selectFirstCandidate(newQuery);
  state.current = current ? [current] : [];
  state.next = next ? [next] : [];
  els.currentSearch.value = "";
  els.newSearch.value = "";
  els.currentSuggestions.innerHTML = "";
  els.newSuggestions.innerHTML = "";
  renderSelections();
  checkInteractions();
}

async function init() {
  try {
    const [drugs, products, metadata] = await Promise.all([
      fetch("data/drugs.json").then((r) => r.json()),
      fetch("data/products.json").then((r) => r.json()),
      fetch("data/metadata.json").then((r) => r.json()),
    ]);
    state.drugs = drugs;
    state.products = products;
    state.metadata = metadata;
    els.dataStatus.textContent = "Ready";
    els.metadata.innerHTML = `
      <p><strong>${metadata.bpomRows.toLocaleString()}</strong> BPOM rows</p>
      <p><strong>${metadata.drugCount.toLocaleString()}</strong> DDInter drugs</p>
      <p><strong>${metadata.interactionRows.toLocaleString()}</strong> interaction pairs</p>
    `;
    renderSelections();
    loadExample("Teosal", "Sanmol");
  } catch (error) {
    els.dataStatus.textContent = "Data error";
    els.results.innerHTML = `<div class="empty-state">Could not load site data: ${escapeHtml(error.message)}</div>`;
  }
}

els.currentSearch.addEventListener("input", () => renderSuggestions("current", els.currentSearch.value, els.currentSuggestions));
els.newSearch.addEventListener("input", () => renderSuggestions("new", els.newSearch.value, els.newSuggestions));
els.checkButton.addEventListener("click", checkInteractions);
els.resetButton.addEventListener("click", resetAll);
els.clearCurrent.addEventListener("click", () => {
  state.current = [];
  renderSelections();
});
els.clearNew.addEventListener("click", () => {
  state.next = [];
  renderSelections();
});
els.exampleButtons.forEach((button) => {
  button.addEventListener("click", () => loadExample(button.dataset.current, button.dataset.new));
});

init();
