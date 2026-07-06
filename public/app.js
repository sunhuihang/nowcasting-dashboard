const state = {
  data: null,
  period: "test",
  caseTime: "",
  animationIndex: 0,
  animationTimer: null,
  animationDelay: 800
};

const metricLabels = {
  ts: "TS",
  bias: "BIAS",
  ssim: "SSIM"
};

const metricRanges = {
  ts: [0, 1],
  bias: [0, 2],
  ssim: [0, 1]
};

const modelColors = ["#1769aa", "#16825d", "#b78316", "#b43d3d", "#6f58a8", "#0c8195", "#7a5b2e"];
const thresholds = ["20", "35", "45", "composite"];

function fmt(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return Number(value).toFixed(digits);
}

function biasClass(value) {
  if (value === null || value === undefined) return "";
  return Math.abs(value - 1) <= 0.15 ? "score-good" : "score-warn";
}

function scoreClass(metric, value) {
  if (metric === "bias") return biasClass(value);
  return value >= 0.6 ? "score-good" : "score-warn";
}

async function loadData() {
  const res = await fetch("./data/dashboard.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`dashboard.json 加载失败: ${res.status}`);
  state.data = await res.json();
}

function fillSelectors() {
  const periodSelect = document.querySelector("#periodSelect");
  const radarLeadSelect = document.querySelector("#radarLeadSelect");
  const caseTimeSelect = document.querySelector("#caseTimeSelect");
  const animationSpeedSelect = document.querySelector("#animationSpeedSelect");

  periodSelect.innerHTML = state.data.periods
    .map((p) => `<option value="${p.id}">${p.label}</option>`)
    .join("");
  periodSelect.value = state.period;

  periodSelect.addEventListener("change", (event) => {
    state.period = event.target.value;
    render();
  });
  if (radarLeadSelect) {
    radarLeadSelect.addEventListener("change", renderRadarLeadFrame);
  }
  if (caseTimeSelect) {
    caseTimeSelect.addEventListener("change", (event) => {
      state.caseTime = event.target.value;
      renderRadarCase();
    });
  }
  if (animationSpeedSelect) {
    animationSpeedSelect.value = String(state.animationDelay);
    animationSpeedSelect.addEventListener("change", (event) => {
      state.animationDelay = Number(event.target.value);
      restartRadarAnimationTimer();
    });
  }
}

function periodData() {
  return state.data.results[state.period] || [];
}

function byLead(model, leadMinute) {
  return model?.lead_metrics?.find((item) => item.lead_minute === leadMinute) || null;
}

function thresholdComposite(values) {
  if (!values) return null;
  return values["20"] * 0.3 + values["35"] * 0.4 + values["45"] * 0.3;
}

function metricValueAt(model, metric, threshold, leadMinute) {
  const item = byLead(model, leadMinute);
  if (!item) return null;
  if (metric === "ssim") return threshold === "composite" ? item.ssim : item.ssim;
  if (threshold === "composite") return thresholdComposite(item[metric]);
  return item[metric]?.[threshold] ?? null;
}

function mean(values) {
  const clean = values.filter((value) => value !== null && value !== undefined && Number.isFinite(value));
  if (!clean.length) return null;
  return clean.reduce((sum, value) => sum + value, 0) / clean.length;
}

function periodScore(model, metric, threshold, startMinute, endMinute) {
  const values = (state.data.lead_minutes || [])
    .filter((lead) => lead >= startMinute && lead <= endMinute)
    .map((lead) => metricValueAt(model, metric, threshold, lead));
  return mean(values);
}

function totalScore(model, metric, threshold = "composite") {
  const s01 = periodScore(model, metric, threshold, 6, 60);
  const s12 = periodScore(model, metric, threshold, 66, 120);
  const s23 = periodScore(model, metric, threshold, 126, 180);
  if ([s01, s12, s23].some((value) => value === null)) return null;
  return s01 * 0.3 + s12 * 0.5 + s23 * 0.2;
}

function compositeScore(model) {
  const ts = totalScore(model, "ts", "composite");
  const ssim = totalScore(model, "ssim", "composite");
  const bias = totalScore(model, "bias", "composite");
  if ([ts, ssim, bias].some((value) => value === null)) return null;
  const biasScore = Math.max(0, 1 - Math.abs(bias - 1));
  return ts * 0.45 + ssim * 0.35 + biasScore * 0.2;
}

function sortedModels() {
  return [...periodData()].sort((a, b) => (compositeScore(b) ?? -1) - (compositeScore(a) ?? -1));
}

function renderHeader() {
  document.querySelector("#datasetVersion").textContent = `dataset: ${state.data.dataset_version}`;
  document.querySelector("#updatedAt").textContent = `updated: ${state.data.updated_at}`;
}

function renderSummary() {
  const models = sortedModels();
  const best = models[0];
  const cards = [
    ["模型数量", state.data.models.length, "参与公开对比的模型"],
    ["当前最佳", best ? best.model_name : "-", best ? `综合评分 ${fmt(compositeScore(best))}` : "-"],
    ["经典个例", state.caseTime || "2026-07-06 00:00", "观测与全部模型同步展示"],
    ["评估时效", "6-180 min", "逐 6 分钟，共 30 个时效"]
  ];
  document.querySelector("#summaryGrid").innerHTML = cards
    .map(([label, value, detail]) => `
      <article class="summary-card">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
        <div class="detail">${detail}</div>
      </article>
    `)
    .join("");
}

function renderRanking() {
  document.querySelector("#rankingHint").textContent = "总评分 = 0-1h*30% + 1-2h*50% + 2-3h*20%";
  const rows = sortedModels()
    .map((model, index) => {
      const ts = totalScore(model, "ts");
      const bias = totalScore(model, "bias");
      const ssim = totalScore(model, "ssim");
      const score = compositeScore(model);
      return `
        <tr>
          <td><span class="rank">${index + 1}</span></td>
          <td>
            <div class="model-name">
              <strong>${model.model_name}</strong>
              <small>${model.team_id} · ${model.version}</small>
            </div>
          </td>
          <td class="${scoreClass("ts", ts)}">${fmt(ts)}</td>
          <td class="${biasClass(bias)}">${fmt(bias)}</td>
          <td class="${scoreClass("ssim", ssim)}">${fmt(ssim)}</td>
          <td class="${scoreClass("ts", score)}">${fmt(score)}</td>
        </tr>
      `;
    })
    .join("");
  document.querySelector("#rankingTable").innerHTML = rows || `<tr><td colspan="6" class="empty">暂无数据</td></tr>`;
}

function renderScoreFormulaTable() {
  const rows = sortedModels().map((model) => {
    const ts = totalScore(model, "ts");
    const bias = totalScore(model, "bias");
    const ssim = totalScore(model, "ssim");
    const score = compositeScore(model);
    return `
      <tr>
        <td>${model.model_name}</td>
        <td>${fmt(ts)}</td>
        <td>${fmt(bias)}</td>
        <td>${fmt(ssim)}</td>
        <td>${fmt(score)}</td>
      </tr>
    `;
  }).join("");
  document.querySelector("#scoreFormulaTable").innerHTML = rows;
}

function axisTicks(metric) {
  if (metric === "bias") return [0, 0.5, 1, 1.5, 2];
  return [0, 0.25, 0.5, 0.75, 1];
}

function renderOneScoreChart(metric, threshold) {
  const leadMinutes = state.data.lead_minutes || [];
  const models = periodData();
  const width = 760;
  const height = 250;
  const pad = { left: 46, right: 18, top: 16, bottom: 38 };
  const [minValue, maxValue] = metricRanges[metric];
  const x = (lead) => pad.left + ((lead - 6) / (180 - 6)) * (width - pad.left - pad.right);
  const y = (value) => height - pad.bottom - ((value - minValue) / (maxValue - minValue)) * (height - pad.top - pad.bottom);
  const titleSuffix = threshold === "composite" ? "阈值综合" : `${threshold} dBZ`;

  const yGrid = axisTicks(metric).map((tick) => {
    const yy = y(tick);
    return `
      <line x1="${pad.left}" y1="${yy}" x2="${width - pad.right}" y2="${yy}" stroke="#e6ecf2" />
      <text x="${pad.left - 8}" y="${yy + 4}" text-anchor="end" font-size="11" fill="#607080">${tick}</text>
    `;
  }).join("");

  const xLabels = leadMinutes
    .filter((lead) => lead === 6 || lead % 24 === 0 || lead === 180)
    .map((lead) => `
      <line x1="${x(lead)}" y1="${height - pad.bottom}" x2="${x(lead)}" y2="${height - pad.bottom + 5}" stroke="#9dadbd" />
      <text x="${x(lead)}" y="${height - 13}" text-anchor="middle" font-size="11" fill="#607080">${lead}</text>
    `)
    .join("");

  const lines = models.map((model, index) => {
    const color = modelColors[index % modelColors.length];
    const points = leadMinutes
      .map((lead) => `${x(lead)},${y(metricValueAt(model, metric, threshold, lead))}`)
      .join(" ");
    const circles = leadMinutes.map((lead) => {
      const value = metricValueAt(model, metric, threshold, lead);
      return `<circle cx="${x(lead)}" cy="${y(value)}" r="1.9" fill="${color}"><title>${model.model_name} ${lead} min: ${fmt(value)}</title></circle>`;
    }).join("");
    return `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" />${circles}`;
  }).join("");

  const idealBias = metric === "bias"
    ? `<line x1="${pad.left}" y1="${y(1)}" x2="${width - pad.right}" y2="${y(1)}" stroke="#b43d3d" stroke-width="1.2" stroke-dasharray="5 5" />`
    : "";

  const legend = models.map((model, index) => `
    <span><i style="background:${modelColors[index % modelColors.length]}"></i>${model.model_name}</span>
  `).join("");

  return `
    <article class="mini-chart-card">
      <div class="mini-chart-head">
        <strong>${metricLabels[metric]} · ${titleSuffix}</strong>
        <span>逐 6 分钟</span>
      </div>
      <svg class="line-chart compact" viewBox="0 0 ${width} ${height}" role="img" aria-label="${metricLabels[metric]} ${titleSuffix}">
        ${yGrid}
        ${idealBias}
        <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" stroke="#c9d4df" />
        <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" stroke="#c9d4df" />
        ${lines}
        ${xLabels}
        <text x="${width - pad.right}" y="${height - 13}" text-anchor="end" font-size="11" fill="#607080">min</text>
      </svg>
      <div class="chart-legend">${legend}</div>
    </article>
  `;
}

function renderScoreCharts() {
  const html = ["ts", "bias", "ssim"].map((metric) => `
    <section class="metric-chart-group">
      <h3>${metricLabels[metric]} 逐时效评分</h3>
      <div class="mini-chart-grid">
        ${thresholds.map((threshold) => renderOneScoreChart(metric, threshold)).join("")}
      </div>
    </section>
  `).join("");
  document.querySelector("#scoreCharts").innerHTML = html;
}

function radarCases() {
  return state.data.radar_cases || (state.data.radar_case ? [state.data.radar_case] : []);
}

function caseGroups() {
  const cases = radarCases();
  const groups = new Map();
  for (const item of cases) {
    const key = item.init_time || "unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  return [...groups.entries()].map(([initTime, items]) => ({ initTime, items }));
}

function currentCaseGroup() {
  const groups = caseGroups();
  if (!state.caseTime && groups.length) state.caseTime = groups[0].initTime;
  return groups.find((group) => group.initTime === state.caseTime) || groups[0] || null;
}

function renderRadarCase() {
  const group = currentCaseGroup();
  const cases = group?.items || [];
  const select = document.querySelector("#radarLeadSelect");
  const caseTimeSelect = document.querySelector("#caseTimeSelect");
  if (!cases.length || !select || !caseTimeSelect) return;

  caseTimeSelect.innerHTML = caseGroups()
    .map((item) => `<option value="${item.initTime}">${item.initTime}</option>`)
    .join("");
  caseTimeSelect.value = group.initTime;

  document.querySelector("#radarCaseMeta").textContent = group.initTime;
  select.innerHTML = cases[0].lead_frames
    .map((frame) => `<option value="${frame.lead_minute}">${frame.lead_minute} min · ${frame.valid_time}</option>`)
    .join("");
  renderRadarLeadFrame();
  renderRadarAnimation();
}

function frameByLead(item, leadMinute) {
  return item.lead_frames?.find((frame) => frame.lead_minute === leadMinute) || item.lead_frames?.[0];
}

function renderRadarLeadFrame() {
  const group = currentCaseGroup();
  const cases = group?.items || [];
  const select = document.querySelector("#radarLeadSelect");
  if (!cases.length || !select) return;
  const selectedLead = Number(select.value || cases[0].lead_frames?.[0]?.lead_minute);
  const frameCards = cases.map((item) => {
    const frame = frameByLead(item, selectedLead);
    return `
      <div class="radar-tile">
        <img src="${frame.src}" alt="${item.model_name} ${selectedLead} min">
        <span>${item.model_name}</span>
      </div>
    `;
  }).join("");
  document.querySelector("#radarLeadImage").style.display = "none";
  document.querySelector("#radarLeadCaption").innerHTML = `
    <div class="radar-tile-grid">${frameCards}</div>
    <p>lead ${selectedLead} min · valid ${frameByLead(cases[0], selectedLead).valid_time}</p>
  `;
}

function renderRadarAnimation() {
  const group = currentCaseGroup();
  const cases = group?.items || [];
  if (!cases.length) return;
  if (state.animationTimer) {
    window.clearInterval(state.animationTimer);
    state.animationTimer = null;
  }
  state.animationIndex = 0;
  const html = cases.map((item, index) => {
    const frame = item.lead_frames[state.animationIndex];
    return `
      <div class="radar-tile animation-tile">
        <img data-animation-index="${index}" src="${frame.src}" alt="${item.model_name} 3小时预报">
        <span>${item.model_name}</span>
      </div>
    `;
  }).join("");
  document.querySelector("#radarAnimation").style.display = "none";
  document.querySelector("#radarAnimationCaption").innerHTML = `
    <div class="radar-tile-grid">${html}</div>
    <p id="animationTimeLabel">lead ${cases[0].lead_frames[0].lead_minute} min · valid ${cases[0].lead_frames[0].valid_time}</p>
  `;
  restartRadarAnimationTimer();
}

function restartRadarAnimationTimer() {
  if (state.animationTimer) {
    window.clearInterval(state.animationTimer);
  }
  state.animationTimer = window.setInterval(advanceRadarAnimation, state.animationDelay);
}

function advanceRadarAnimation() {
  const group = currentCaseGroup();
  const cases = group?.items || [];
  if (!cases.length) return;
  const frameCount = cases[0].lead_frames.length;
  state.animationIndex = (state.animationIndex + 1) % frameCount;
  cases.forEach((item, index) => {
    const image = document.querySelector(`#radarAnimationCaption img[data-animation-index="${index}"]`);
    const frame = item.lead_frames[state.animationIndex];
    if (image && frame) image.src = frame.src;
  });
  const label = document.querySelector("#animationTimeLabel");
  const refFrame = cases[0].lead_frames[state.animationIndex];
  if (label && refFrame) {
    label.textContent = `lead ${refFrame.lead_minute} min · valid ${refFrame.valid_time}`;
  }
}

function render() {
  renderHeader();
  renderSummary();
  renderScoreFormulaTable();
  renderRanking();
  renderScoreCharts();
  renderRadarCase();
}

loadData()
  .then(() => {
    fillSelectors();
    render();
  })
  .catch((error) => {
    document.body.innerHTML = `<main class="shell"><section class="panel empty">${error.message}</section></main>`;
  });
