/* ══════════════════════════════════════════════════════════════
   STATE
══════════════════════════════════════════════════════════════ */
const APP = {
  patients: [],
  selectedId: null,
  selectedPatient: null,
  currentVital: 'dhs_score',
  ws: null,
  calcTimer: null,
  lastCalcResult: null,
};

const VITAL_CONFIG = {
  dhs_score:         { label:'DHS Score',        color:'#2563EB', unit:'',      min:0,    max:1,    normalMin:null, normalMax:null },
  respiratory_rate:  { label:'Respiratory Rate', color:'#2563EB', unit:'br/min',min:4,    max:40,   normalMin:12,   normalMax:20   },
  spo2:              { label:'SpO₂',             color:'#2563EB', unit:'%',     min:80,   max:100,  normalMin:96,   normalMax:100  },
  systolic_bp:       { label:'Systolic BP',      color:'#2563EB', unit:'mmHg',  min:60,   max:250,  normalMin:111,  normalMax:219  },
  heart_rate:        { label:'Heart Rate',       color:'#2563EB', unit:'bpm',   min:20,   max:180,  normalMin:51,   normalMax:90   },
  temperature:       { label:'Temperature',      color:'#2563EB', unit:'°C',    min:34,   max:42,   normalMin:36.1, normalMax:38.0 },
};

const RISK_COLORS = {
  CRITICAL: '#DC2626', HIGH: '#F59E0B', MEDIUM: '#F59E0B', LOW: '#16A34A'
};

const BD_CONFIG = [
  { key:'rr_score',            label:'Resp. Rate',  max:3 },
  { key:'spo2_score',          label:'SpO₂',        max:3 },
  { key:'sbp_score',           label:'Systolic BP', max:3 },
  { key:'hr_score',            label:'Heart Rate',  max:3 },
  { key:'temp_score',          label:'Temperature', max:3 },
  { key:'consciousness_score', label:'Conscious.',  max:3 },
  { key:'o2_score',            label:'Supp. O₂',   max:2 },
];

/* ══════════════════════════════════════════════════════════════
   BOOT
══════════════════════════════════════════════════════════════ */
window.addEventListener('load', () => {
  loadAll();
  connectWebSocket();
  ['rr','spo2','sbp','hr','temp'].forEach(id => {
    const el = document.getElementById('c-' + id);
    if (el) updateSlider(id, parseFloat(el.min), parseFloat(el.max), '');
  });
});

async function loadAll() {
  await Promise.all([loadPatients(), loadStats()]);
}

/* ══════════════════════════════════════════════════════════════
   WEBSOCKET
══════════════════════════════════════════════════════════════ */
function connectWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  APP.ws = new WebSocket(`${proto}://${location.host}/ws`);
  APP.ws.onopen    = () => setWsStatus('connected', 'Live');
  APP.ws.onclose   = () => { setWsStatus('off','Disconnected'); setTimeout(connectWebSocket, 5000); };
  APP.ws.onerror   = () => setWsStatus('off', 'Error');
  APP.ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    showToast(msg);
    flashPatientRow(msg.patient_id);
    loadAll();
  };
}

function setWsStatus(state, text) {
  const dot = document.getElementById('ws-dot');
  const lbl = document.getElementById('ws-label');
  dot.className = 'ws-dot' + (state === 'connected' ? ' connected' : state === 'off' ? '' : ' connecting');
  lbl.textContent = text;
}

/* ══════════════════════════════════════════════════════════════
   TOAST
══════════════════════════════════════════════════════════════ */
function showToast(msg) {
  const newRisk = msg.new_risk || 'UNKNOWN';
  const oldRisk = msg.old_risk || '?';
  const color   = RISK_COLORS[newRisk] || '#2563EB';
  const dir = newRisk === 'LOW' ? '↓' : (newRisk === 'CRITICAL' || newRisk === 'HIGH') ? '↑' : '→';

  const div = document.createElement('div');
  div.className = 'toast';
  div.style.borderLeftColor = color;
  div.style.borderLeftWidth = '4px';
  div.innerHTML = `
    <div class="toast-body">
      <div class="toast-type" style="color:${color}">${dir} Risk ${oldRisk === newRisk ? 'Update' : 'Change'}</div>
      <div class="toast-name">${escapeHtml(msg.name)}</div>
      <div class="toast-detail">
        ${escapeHtml(oldRisk)} → <strong style="color:${color}">${escapeHtml(newRisk)}</strong>
        &nbsp;·&nbsp; DHS: ${(+msg.dhs_score).toFixed(3)}
      </div>
    </div>
    <div class="toast-progress" style="background:${color}"></div>`;
  document.getElementById('toast-container').appendChild(div);

  const prog = div.querySelector('.toast-progress');
  prog.addEventListener('animationend', () => {
    div.style.animation = 'toastOut 0.4s ease forwards';
    div.addEventListener('animationend', () => div.remove(), { once: true });
  });
}

function flashPatientRow(pid) {
  const el = document.querySelector(`[data-pid="${pid}"]`);
  if (!el) return;
  el.classList.remove('flash-alert');
  void el.offsetWidth;
  el.classList.add('flash-alert');
}

/* ══════════════════════════════════════════════════════════════
   STATS
══════════════════════════════════════════════════════════════ */
async function loadStats() {
  try {
    const s = await fetch('/api/stats').then(r => r.json());
    document.getElementById('sv-patients').textContent = s.total_patients;
    document.getElementById('sv-alerts').textContent   = s.active_alerts;
    document.getElementById('sv-dhs').textContent      = (s.avg_dhs_score||0).toFixed(3);

    const st = document.getElementById('st-alerts');
    if (s.active_alerts > 0) st.classList.add('has-alerts');
    else st.classList.remove('has-alerts');

    renderRiskBar(s.risk_distribution, s.total_patients);
  } catch(e) {}
}

function renderRiskBar(dist, total) {
  const order  = ['CRITICAL','HIGH','MEDIUM','LOW'];
  const colors = { CRITICAL:'#DC2626', HIGH:'#F59E0B', MEDIUM:'#F59E0B', LOW:'#D1D5DB' };
  const track  = document.getElementById('risk-bar-track');
  const legend = document.getElementById('risk-dist-legend');
  track.innerHTML = '';
  legend.innerHTML = '';
  if (!total) return;

  order.forEach(r => {
    const n = dist[r] || 0;
    if (!n) return;
    const seg = document.createElement('div');
    seg.className = 'risk-bar-seg';
    seg.style.cssText = `flex:${n};background:${colors[r]}`;
    track.appendChild(seg);
  });

  order.forEach(r => {
    const n = dist[r] || 0;
    const item = document.createElement('div');
    item.className = 'legend-item';
    item.innerHTML = `
      <div class="legend-dot" style="background:${colors[r]}"></div>
      <span class="legend-count">${n}</span>
      <span class="legend-text">${r[0]}${r.slice(1).toLowerCase()}</span>`;
    legend.appendChild(item);
  });
}

/* ══════════════════════════════════════════════════════════════
   PATIENTS
══════════════════════════════════════════════════════════════ */
async function loadPatients() {
  try {
    APP.patients = await fetch('/api/patients').then(r => r.json());
    renderPatientList();
    document.getElementById('pc-badge').textContent = APP.patients.length;
  } catch(e) {}
}

function renderPatientList() {
  const list = document.getElementById('patient-list');
  if (!APP.patients.length) {
    list.innerHTML = '<div class="empty-state"><div class="empty-text">No patients found</div></div>';
    return;
  }
  const riskColors = { CRITICAL:'#DC2626', HIGH:'#F59E0B', MEDIUM:'#F59E0B', LOW:'#16A34A' };
  const order = { CRITICAL:0, HIGH:1, MEDIUM:2, LOW:3 };
  const sorted = [...APP.patients].sort((a,b) => (order[a.risk_level]??4)-(order[b.risk_level]??4));

  list.innerHTML = sorted.map(p => {
    const stripColor = riskColors[p.risk_level] || '#9CA3AF';
    const dhs100 = Math.min(100, (p.dhs_score||0)*100).toFixed(1);
    const alertChip = p.alert_triggered
      ? `<span class="alert-chip">⚠ HDet</span>` : '';
    return `
    <div class="patient-item ${p.id === APP.selectedId ? 'active' : ''}"
         data-pid="${p.id}" onclick="selectPatient(${p.id})">
      <div class="patient-risk-strip" style="background:${stripColor}"></div>
      <div class="patient-body">
        <div class="patient-row-top">
          <span class="status-dot dot-${p.risk_level}"></span>
          <span class="patient-name">${escapeHtml(p.name)}</span>
        </div>
        <div class="patient-meta">${escapeHtml(p.ward)}&nbsp;·&nbsp;NEWS2:&nbsp;${p.news2_score}${alertChip}</div>
        <div class="patient-dhs-bar-track">
          <div class="patient-dhs-bar-fill" style="width:${dhs100}%"></div>
        </div>
      </div>
    </div>`;
  }).join('');
}

async function selectPatient(id) {
  APP.selectedId = id;
  renderPatientList();
  document.getElementById('detail-empty').style.display = 'none';
  const content = document.getElementById('detail-content');
  content.classList.remove('visible');

  try {
    const p = await fetch(`/api/patients/${id}`).then(r => r.json());
    APP.selectedPatient = p;
    renderDetail(p);
    content.classList.add('visible');
  } catch(e) {
    document.getElementById('detail-empty').style.display = 'flex';
    document.getElementById('detail-empty').querySelector('.empty-text').textContent = 'Failed to load patient';
  }
}

/* ══════════════════════════════════════════════════════════════
   DETAIL
══════════════════════════════════════════════════════════════ */
function renderDetail(p) {
  // Hidden det banner
  const banner = document.getElementById('hd-banner');
  if (p.alert_triggered) banner.classList.add('visible');
  else banner.classList.remove('visible');

  // Header
  document.getElementById('d-name').textContent = p.name;
  document.getElementById('d-sub').textContent =
    `${p.ward} · Admitted ${p.admission_date}`;

  const pill = document.getElementById('d-risk-pill');
  pill.textContent = p.risk_level;
  pill.className = `risk-pill pill-bg-${p.risk_level}`;

  const badge = document.getElementById('d-admission-badge');
  badge.textContent = p.ward;
  badge.style.display = '';

  // DHS tile
  document.getElementById('d-dhs').textContent = (p.dhs_score||0).toFixed(3);
  document.getElementById('d-dhs-n2').style.width = '65%';
  document.getElementById('d-dhs-sn').style.width = '35%';

  // NEWS2 tile — color by risk
  const n2 = p.news2_score || 0;
  document.getElementById('d-news2').textContent = n2;
  const n2tile  = document.getElementById('d-news2-tile');
  const n2pill  = document.getElementById('d-news2-pill');
  const riskLabel = n2>=7 ? 'CRITICAL' : n2>=5 ? 'HIGH' : n2>=3 ? 'MEDIUM' : 'LOW';
  const bgMap   = { CRITICAL:'var(--critical-bg)', HIGH:'var(--warning-bg)', MEDIUM:'var(--warning-bg)', LOW:'var(--stable-bg)' };
  const clrMap  = { CRITICAL:'var(--critical)',    HIGH:'var(--warning)',    MEDIUM:'var(--warning)',    LOW:'var(--stable)'    };
  n2tile.style.background = bgMap[riskLabel];
  document.getElementById('d-news2').style.color = clrMap[riskLabel];
  n2pill.textContent = riskLabel;
  n2pill.style.cssText = `color:${clrMap[riskLabel]};font-size:0.65rem;`;

  // Trend tile
  const hist    = p.history || [];
  const trendDir = computeTrend(hist.map(h => h.dhs_score));
  const trendEl  = document.getElementById('d-trend');
  const trendLbl = document.getElementById('d-trend-label');
  trendEl.className = 'metric-tile-value trend-icon';
  if (trendDir === 'RISING')       { trendEl.textContent='↑'; trendEl.classList.add('trend-rising');  trendLbl.textContent='Rising'; }
  else if (trendDir === 'FALLING') { trendEl.textContent='↓'; trendEl.classList.add('trend-falling'); trendLbl.textContent='Falling'; }
  else                             { trendEl.textContent='→'; trendEl.classList.add('trend-stable');  trendLbl.textContent='Stable'; }

  // Reset chart tab to DHS and draw
  document.querySelectorAll('.vtab').forEach(b => b.classList.remove('active'));
  document.querySelector('.vtab').classList.add('active');
  APP.currentVital = 'dhs_score';
  requestAnimationFrame(() => drawVitalChart());

  // Notes
  renderNotes(hist);
}

function computeTrend(values) {
  if (values.length < 2) return 'STABLE';
  const n = values.length;
  let sumX=0, sumY=0, sumXY=0, sumX2=0;
  values.forEach((v,i) => { sumX+=i; sumY+=v; sumXY+=i*v; sumX2+=i*i; });
  const denom = n*sumX2 - sumX*sumX;
  if (!denom) return 'STABLE';
  const slope = (n*sumXY - sumX*sumY) / denom;
  if (slope > 0.005)  return 'RISING';
  if (slope < -0.005) return 'FALLING';
  return 'STABLE';
}

/* ══════════════════════════════════════════════════════════════
   VITAL CHART
══════════════════════════════════════════════════════════════ */
function setVitalTab(btn, key) {
  document.querySelectorAll('.vtab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  APP.currentVital = key;
  requestAnimationFrame(() => drawVitalChart());
}

function drawVitalChart() {
  const canvas = document.getElementById('history-canvas');
  if (!canvas) return;
  const p = APP.selectedPatient;
  if (!p || !p.history || !p.history.length) return;

  const cfg     = VITAL_CONFIG[APP.currentVital] || VITAL_CONFIG.dhs_score;
  const history = p.history;
  const raw     = history.map(h => +h[APP.currentVital] || 0);

  // Canvas size — retry if layout not yet complete
  const W = canvas.offsetWidth || 0;
  if (W < 100) { setTimeout(drawVitalChart, 60); return; }
  const H = 180;
  canvas.width  = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  // White background
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, W, H);

  // Padding
  const PAD_L = 38, PAD_R = 12, PAD_T = 12, PAD_B = 28;
  const chartW = W - PAD_L - PAD_R;
  const chartH = H - PAD_T - PAD_B;

  // Value range
  let lo = Math.min(...raw), hi = Math.max(...raw);
  if (cfg.normalMin != null) { lo = Math.min(lo, cfg.normalMin*0.95); hi = Math.max(hi, cfg.normalMax*1.05); }
  if (cfg.min != null) lo = Math.max(lo, cfg.min);
  if (cfg.max != null) hi = Math.min(hi, cfg.max);
  const range = hi - lo || 1;

  const toX = i  => PAD_L + (i / (raw.length-1||1)) * chartW;
  const toY = v  => PAD_T + (1 - (v - lo) / range) * chartH;

  // Light grey grid lines
  ctx.strokeStyle = '#E5E7EB';
  ctx.lineWidth   = 1;
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const y = PAD_T + (i / ticks) * chartH;
    ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD_R, y); ctx.stroke();
    // Y-axis label
    const val = hi - (i / ticks) * range;
    ctx.fillStyle = '#6B7280';
    ctx.font = '9px system-ui';
    ctx.textAlign = 'right';
    ctx.fillText(val.toFixed(cfg.unit === '%' || cfg.unit === '' ? 2 : 0), PAD_L - 4, y + 3);
  }

  // Normal-range band — light green
  if (cfg.normalMin != null) {
    const bandY1 = toY(Math.min(cfg.normalMax, hi));
    const bandY2 = toY(Math.max(cfg.normalMin, lo));
    ctx.fillStyle = 'rgba(22,163,74,0.06)';
    ctx.fillRect(PAD_L, bandY1, chartW, bandY2 - bandY1);
    ctx.strokeStyle = 'rgba(22,163,74,0.25)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(PAD_L, bandY1); ctx.lineTo(W-PAD_R, bandY1); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(PAD_L, bandY2); ctx.lineTo(W-PAD_R, bandY2); ctx.stroke();
    ctx.setLineDash([]);
  }

  // X-axis date labels
  ctx.fillStyle = '#9CA3AF';
  ctx.font = '9px system-ui';
  ctx.textAlign = 'center';
  history.forEach((h, i) => {
    const x = toX(i);
    const d = h.timestamp ? h.timestamp.split('T')[0].slice(5) : `D${i+1}`;
    ctx.fillText(d, x, H - 6);
  });

  // Gradient fill under line
  const grad = ctx.createLinearGradient(0, PAD_T, 0, H - PAD_B);
  grad.addColorStop(0, 'rgba(37,99,235,0.10)');
  grad.addColorStop(1, 'rgba(37,99,235,0.00)');
  ctx.beginPath();
  raw.forEach((v, i) => i===0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)));
  ctx.lineTo(toX(raw.length-1), H-PAD_B);
  ctx.lineTo(toX(0), H-PAD_B);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line — primary blue
  ctx.beginPath();
  raw.forEach((v, i) => i===0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)));
  ctx.strokeStyle = '#2563EB';
  ctx.lineWidth   = 2;
  ctx.lineJoin    = 'round';
  ctx.stroke();

  // Dots — static (no rAF on white to avoid smear)
  raw.forEach((v, i) => {
    ctx.beginPath();
    ctx.arc(toX(i), toY(v), 3.5, 0, Math.PI * 2);
    ctx.fillStyle   = '#2563EB';
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth   = 1.5;
    ctx.fill(); ctx.stroke();
  });

  // Hover crosshair
  const tooltipEl = document.getElementById('chart-tooltip');
  canvas.onmousemove = (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    let best = 0, bestDist = Infinity;
    raw.forEach((_, i) => { const d = Math.abs(toX(i) - mx); if (d < bestDist) { bestDist=d; best=i; } });
    if (bestDist > chartW / raw.length) { tooltipEl.style.display='none'; return; }

    const h   = history[best];
    const val = raw[best];
    tooltipEl.style.display = 'block';
    tooltipEl.style.left = (toX(best) * rect.width / W + rect.left - canvas.getBoundingClientRect().left + 8) + 'px';
    tooltipEl.style.top  = (toY(val)  * rect.height / H - 12) + 'px';
    tooltipEl.innerHTML  = `<strong>${val.toFixed(2)} ${cfg.unit}</strong><br><span style="color:var(--muted)">${(h.timestamp||'').split('T')[0]}</span>`;
  };
  canvas.onmouseleave = () => { tooltipEl.style.display='none'; };
}

/* ══════════════════════════════════════════════════════════════
   NOTES
══════════════════════════════════════════════════════════════ */
function renderNotes(history) {
  const list = document.getElementById('d-notes');
  const reversed = [...history].reverse();
  list.innerHTML = reversed.map(h => {
    const s = h.sentiment_score || 0;
    const cls   = s >  0.1 ? 'sent-pos' : s < -0.1 ? 'sent-neg' : 'sent-neu';
    const label = s >  0.1 ? 'Positive' : s < -0.1 ? 'Negative' : 'Neutral';
    const date  = (h.timestamp||'').split('T')[0] || '—';
    return `
    <div class="note-item">
      <div class="note-header">
        <span class="note-date">${date}</span>
        <span class="sent-badge ${cls}">${label} (${s.toFixed(2)})</span>
        ${h.alert_triggered ? '<span class="sent-badge sent-neg">⚠ HDet</span>' : ''}
      </div>
      <div class="note-text">${escapeHtml(h.clinical_note || '—')}</div>
    </div>`;
  }).join('');
}

/* ══════════════════════════════════════════════════════════════
   CALCULATOR — SLIDERS
══════════════════════════════════════════════════════════════ */
function updateSlider(id, min, max, unit) {
  const el = document.getElementById(`c-${id}`);
  if (!el) return;
  const val = parseFloat(el.value);
  const pct = ((val - min) / (max - min) * 100).toFixed(1);

  // Semantic zone colors
  let zoneColor = '#2563EB';
  if (id === 'rr') {
    zoneColor = (val<=8||val>=25) ? '#DC2626' : (val<=11||val>=21) ? '#F59E0B' : '#16A34A';
  } else if (id === 'spo2') {
    zoneColor = val<=91 ? '#DC2626' : val<=95 ? '#F59E0B' : '#16A34A';
  } else if (id === 'sbp') {
    zoneColor = val<=90||val>=220 ? '#DC2626' : val<=110 ? '#F59E0B' : '#16A34A';
  } else if (id === 'hr') {
    zoneColor = val<=40||val>=131 ? '#DC2626' : val<=50||val>=111 ? '#F59E0B' : '#16A34A';
  } else if (id === 'temp') {
    zoneColor = val<=35.0||val>=39.1 ? '#DC2626' : val<=36.0||val>=38.1 ? '#F59E0B' : '#16A34A';
  }

  el.style.setProperty('--pct', pct + '%');
  el.style.background = `linear-gradient(to right, ${zoneColor} 0%, ${zoneColor} ${pct}%, #E5E7EB ${pct}%)`;
  el.style.setProperty('--thumb-color', zoneColor);

  // Thumb border color via style (approximated via box-shadow)
  el.style.setProperty('border-color', zoneColor);

  // Readout
  const readout = document.getElementById(`${id}-readout`);
  if (readout) {
    const disp = id === 'temp' ? val.toFixed(1) : Math.round(val*2)/2;
    readout.innerHTML = `${disp} <small>${unit}</small>`;
    readout.style.color = zoneColor;
  }

  scheduleCalc();
}

function scheduleCalc() {
  clearTimeout(APP.calcTimer);
  APP.calcTimer = setTimeout(calculateDHS, 600);
}

/* ══════════════════════════════════════════════════════════════
   CALCULATOR — DHS
══════════════════════════════════════════════════════════════ */
async function calculateDHS() {
  clearTimeout(APP.calcTimer);
  const payload = {
    respiratory_rate:  parseFloat(document.getElementById('c-rr').value),
    spo2:              parseFloat(document.getElementById('c-spo2').value),
    systolic_bp:       parseFloat(document.getElementById('c-sbp').value),
    heart_rate:        parseFloat(document.getElementById('c-hr').value),
    temperature:       parseFloat(document.getElementById('c-temp').value),
    consciousness:     parseInt(document.getElementById('c-consciousness').value),
    on_supplemental_o2: document.getElementById('c-o2').value === 'true',
    clinical_note:     document.getElementById('c-note').value,
    use_llm:           false,
  };

  try {
    const r = await fetch('/api/calculate-dhs', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    }).then(res => res.json());

    APP.lastCalcResult = r;
    document.getElementById('gauge-wrap').classList.add('visible');
    document.getElementById('breakdown-section').classList.add('visible');

    animateGauge(r.dhs_score, r.risk_level, r.news2_score);
    renderBreakdownBars(r.breakdown, r.news2_score, r.risk_level);

    const hd = document.getElementById('calc-hd-alert');
    if (r.alert_triggered) hd.classList.add('visible');
    else hd.classList.remove('visible');

  } catch(e) {}
}

/* ══════════════════════════════════════════════════════════════
   GAUGE — flat numeric display
══════════════════════════════════════════════════════════════ */
function animateGauge(score, risk, news2) {
  const valEl  = document.getElementById('gauge-val');
  const rkEl   = document.getElementById('gauge-risk');
  const fillEl = document.getElementById('gauge-sev-fill');
  const n2El   = document.getElementById('gauge-n2');

  const color = RISK_COLORS[risk] || '#2563EB';
  rkEl.textContent = risk;
  rkEl.style.color = color;
  fillEl.style.background = color;
  n2El.textContent = `NEWS2: ${news2}`;

  // Animate fill width
  requestAnimationFrame(() => {
    fillEl.style.width = Math.min(100, parseFloat(score) * 100).toFixed(1) + '%';
  });

  // Count-up animation for score
  let frame = 0;
  const frames = 45;
  const target = parseFloat(score);
  function step() {
    frame++;
    const ease = 1 - Math.pow(1 - Math.min(1, frame / frames), 3);
    valEl.textContent = (target * ease).toFixed(3);
    if (frame < frames) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* ══════════════════════════════════════════════════════════════
   BREAKDOWN BARS
══════════════════════════════════════════════════════════════ */
function renderBreakdownBars(bd, totalNews2, risk) {
  if (!bd) return;
  const container = document.getElementById('breakdown-bars');
  const totalLabel = document.getElementById('bd-total-label');
  totalLabel.innerHTML = `NEWS2: <strong style="color:${RISK_COLORS[risk]}">${totalNews2} — ${risk}</strong>`;

  container.innerHTML = BD_CONFIG.map((cfg, idx) => {
    const score = bd[cfg.key] || 0;
    const pct   = (score / cfg.max * 100).toFixed(0);
    const color = score === 0 ? '#E5E7EB'
                : score <= 1 ? '#F59E0B'
                : score === 2 ? '#F97316'
                :               '#DC2626';
    return `
    <div class="breakdown-row">
      <div class="breakdown-key">${cfg.label}</div>
      <div class="breakdown-bar-track">
        <div class="breakdown-bar-fill"
             style="background:${color};transition-delay:${idx*60}ms"
             data-target="${pct}"></div>
      </div>
      <div class="breakdown-score">${score}/${cfg.max}</div>
    </div>`;
  }).join('');

  // Trigger animations
  requestAnimationFrame(() => {
    container.querySelectorAll('.breakdown-bar-fill').forEach(el => {
      el.style.width = el.dataset.target + '%';
    });
  });
}

/* ══════════════════════════════════════════════════════════════
   HELPERS
══════════════════════════════════════════════════════════════ */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
