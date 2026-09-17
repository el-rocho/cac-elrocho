// cac-elrocho: Frontend Application Logic

let currentPreviewData = null;
let chartsRendered = false;
let chartInstances = {};

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

async function getErrorMessage(res, defaultMsg = 'Error en la petición') {
  try {
    const err = await res.json();
    return err.detail || err.message || defaultMsg;
  } catch (_) {
    try {
      const text = await res.text();
      if (text && text.trim().length > 0 && text.length < 300) return text;
    } catch (_) {}
    return `${defaultMsg} (${res.status} ${res.statusText})`;
  }
}

// Inicialización al cargar la página
document.addEventListener('DOMContentLoaded', () => {
  if (window.Chart) {
    Chart.defaults.elements.line.spanGaps = true;
    Chart.defaults.elements.point.radius = 4;
    Chart.defaults.elements.point.hoverRadius = 6;
  }
  loadSummary();
  loadTables();
  loadAuditFiles();
  loadPatientConfig();
  setupDragAndDrop();
});

// 1. Gestión de Pestañas
function setTab(tabId) {
  const tabs = ['eval', 'charts', 'table', 'audit', 'config'];
  tabs.forEach(t => {
    const el = document.getElementById('tab-' + t);
    const btn = document.getElementById('tab-btn-' + t);
    if (!el || !btn) return;
    
    if (t === tabId) {
      el.classList.remove('hidden');
      btn.className = 'pb-3 px-4 border-b-2 tab-active transition-colors';
    } else {
      el.classList.add('hidden');
      btn.className = 'pb-3 px-4 border-b-2 tab-inactive transition-colors';
    }
  });

  if (tabId === 'charts') {
    setTimeout(() => {
      loadCharts();
    }, 60);
  } else if (tabId === 'audit') {
    loadAuditFiles();
  } else if (tabId === 'config') {
    loadPatientConfig();
    loadAiAuditorias();
  }
}

// 2. Cargar Resumen y KPIs
async function loadSummary() {
  try {
    const res = await fetch('/api/v1/analiticas/summary');
    if (!res.ok) throw new Error('Error al consultar summary');
    const data = await res.json();

    document.getElementById('badge-total-controles').textContent = `${data.total_controles} Controles (${data.periodo_historico})`;
    document.getElementById('badge-ultima-fecha').textContent = `Última analítica: ${data.ultima_fecha}`;

    const badgeMotor = document.getElementById('badge-motor-llm');
    if (badgeMotor && data.motor_llm_info) {
      const mInfo = data.motor_llm_info;
      if (mInfo.activo) {
        badgeMotor.className = 'px-2.5 py-1 bg-purple-100 text-purple-800 text-xs font-bold rounded-lg flex items-center gap-1 cursor-help';
        const modelName = (mInfo.modelos && mInfo.modelos.length > 0) ? mInfo.modelos[0] : 'Gemini';
        const modNames = (mInfo.modelos || []).join(', ');
        badgeMotor.innerHTML = `✨ LLM Activo: ${escapeHtml(modelName)}`;
        badgeMotor.title = `Modelo principal: ${modelName}. Alternativas configuradas: ${modNames}`;
      } else {
        badgeMotor.className = 'px-2.5 py-1 bg-amber-100 text-amber-800 text-xs font-bold rounded-lg flex items-center gap-1 cursor-help';
        badgeMotor.innerHTML = `⚠️ Extractor RegEx`;
        badgeMotor.title = 'No hay modelos LLM activos configurados en .env. La aplicación operará con el extractor basado en expresiones regulares.';
      }
    }

    if (data.app_version) {
      const verEl = document.getElementById('footer-app-version');
      if (verEl) {
        verEl.textContent = data.app_version.startsWith('v') ? data.app_version : `v${data.app_version}`;
      }
    }

    const p = data.paciente || {};
    const nombre = (p.nombre || '').trim();
    document.getElementById('paciente-nombre').textContent = 'Control de analíticas clínicas: ' + (nombre || 'Paciente');
    
    let partesDetalles = [];
    if (p.nacimiento && p.nacimiento !== '-') {
      let nacStr = `Fecha de nacimiento: <strong>${escapeHtml(p.nacimiento)}</strong>`;
      if (p.edad && p.edad !== '-') {
        nacStr += ` (${escapeHtml(p.edad)})`;
      }
      partesDetalles.push(nacStr);
    }
    if (p.sexo && p.sexo !== '-' && p.sexo !== 'No especificado') {
      partesDetalles.push(`Sexo: <strong>${escapeHtml(p.sexo)}</strong>`);
    }
    if (p.dni && p.dni !== '-') {
      partesDetalles.push(`Identificación fiscal (DNI): <strong>${escapeHtml(p.dni)}</strong>`);
    }

    document.getElementById('paciente-detalles').innerHTML = partesDetalles.length > 0 
      ? partesDetalles.join(' <span class="text-slate-300">•</span> ') 
      : 'Sin datos personales configurados';

    document.getElementById('dictamen-titulo').textContent = data.dictamen_global || 'Control favorable';
    const subEl = document.getElementById('dictamen-sub');
    if (subEl) {
      if (data.dictamen_subtitulo && data.dictamen_subtitulo !== 'Parámetros analizados por el sistema' && data.dictamen_subtitulo !== '-' && data.dictamen_subtitulo.trim().length > 0) {
        subEl.textContent = '— ' + data.dictamen_subtitulo;
        subEl.classList.remove('hidden');
      } else {
        subEl.textContent = '';
        subEl.classList.add('hidden');
      }
    }

    // Renderizar KPIs
    const container = document.getElementById('kpi-container');
    container.innerHTML = '';
    data.kpis.forEach(kpi => {
      const card = document.createElement('div');
      card.className = 'bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:shadow transition-shadow';
      card.innerHTML = `
        <div class="flex justify-between items-center">
          <span class="text-xs font-semibold text-slate-500 uppercase">${kpi.title}</span>
          <span class="text-[10px] ${kpi.tag_class} font-bold px-1.5 py-0.5 rounded">${kpi.tag}</span>
        </div>
        <div class="text-xl font-extrabold text-slate-900 mt-1">${kpi.main_value} <span class="text-xs font-normal text-slate-500">${kpi.unit}</span></div>
        <div class="text-xs font-semibold text-slate-600 mt-0.5">${kpi.subtitle_1}</div>
        <div class="text-[10px] text-slate-500 mt-0.5">${kpi.subtitle_2}</div>
        <div class="mt-2 inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${kpi.badge_class}">
          ${kpi.badge_text}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Fallo al cargar summary:', err);
  }
}

// 3. Reglas de Estilo Clínico para Celdas
function getCellFormatClient(name, v) {
  if (v === null || v === undefined || v === '-') return { cls: 'text-slate-300', title: 'Sin dato' };
  let num = parseFloat(v);

  if (name === 'HbA1c') {
    if (num >= 5.7) return { cls: 'text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded', title: 'Límite Prediabetes (>5.6%)' };
    if (num >= 5.4) return { cls: 'text-slate-800 font-medium', title: 'Bueno / En rango' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo' };
  }
  if (name === 'HbA1c (IFCC)') {
    if (num >= 38.8) return { cls: 'text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded', title: 'Límite Prediabetes (>=38.8)' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo' };
  }
  if (name === 'Glucosa Basal') {
    if (num > 100) return { cls: 'text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded', title: 'Ligeramente alto (>100)' };
    if (num >= 96) return { cls: 'text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded', title: 'Bueno / Próximo a 100' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo' };
  }
  if (name === 'LDL-Colesterol') {
    if (num > 116) return { cls: 'text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded', title: 'Sobrepasa ref. SEA (>116)' };
    if (num >= 100) return { cls: 'text-yellow-800 bg-yellow-50 border border-yellow-200 font-medium px-1.5 py-0.5 rounded', title: 'Bueno' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo' };
  }
  if (name === 'Colesterol Total') {
    if (num > 200) return { cls: 'text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded', title: 'Alto (>200)' };
    if (num >= 180) return { cls: 'text-slate-800 font-bold', title: 'Bueno / Próximo a 200' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo (<180)' };
  }
  if (name.includes('Castelli II') || name === 'Cociente LDL/HDL' || name === 'LDL / HDL') {
    if (num > 4.3) return { cls: 'text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded', title: 'Riesgo Alto (>4.3)' };
    if (num >= 3.0) return { cls: 'text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded', title: 'Bueno / Límite intermedio' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo (<3.0)' };
  }
  if ((name.includes('Castelli I') && !name.includes('Castelli II')) || name === 'Cociente Col/HDL' || name === 'Colesterol Total / HDL') {
    if (num > 5.0) return { cls: 'text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded', title: 'Riesgo Aumentado / Alto (>5.0)' };
    if (num >= 4.0) return { cls: 'text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded', title: 'Bueno / Límite (Óptimo <4.0)' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo (<4.0)' };
  }
  if (name === 'Triglicéridos / HDL' || name === 'Cociente TG/HDL' || name === 'Ratio TG/HDL') {
    if (num > 2.0) return { cls: 'text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded', title: 'Elevado / Resistencia Insulínica (>2.0)' };
    if (num >= 1.5) return { cls: 'text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded', title: 'Bueno / Límite' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo (<1.5)' };
  }
  if (name === 'Vitamina D (25-OH)') {
    if (num < 20) return { cls: 'text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded', title: 'Déficit (<20)' };
    if (num < 30) return { cls: 'text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded', title: 'Insuficiencia (20-29)' };
    if (num <= 35) return { cls: 'text-emerald-800 bg-emerald-50 border border-emerald-300 font-semibold px-1.5 py-0.5 rounded', title: 'Normalizada (>30)' };
    return { cls: 'text-emerald-700 font-bold', title: 'Óptimo (>35)' };
  }

  return { cls: 'text-slate-800', title: 'Normal' };
}

// 4. Cargar Tablas
async function loadTables() {
  try {
    const res = await fetch('/api/v1/analiticas/tables');
    if (!res.ok) throw new Error('Error al cargar tablas');
    const data = await res.json();

    // 4.1 Encabezados de Fechas
    const thead = document.getElementById('tableHeaderDates');
    let hHtml = `
      <tr>
        <th class="p-3 sticky left-0 bg-slate-800 z-10">Parámetro</th>
        <th class="p-3">Unidad</th>
        <th class="p-3 text-center">Ref. Oficial</th>
    `;
    const infList = data.informes || [];
    data.dates.forEach((d, idx) => {
      let bgCls = 'bg-slate-700 hover:bg-slate-600';
      if (idx === data.dates.length - 1) bgCls = 'bg-emerald-800 hover:bg-emerald-700 font-bold';
      else if (idx === data.dates.length - 2) bgCls = 'bg-indigo-900 hover:bg-indigo-800 font-bold';
      else if (idx === data.dates.length - 3) bgCls = 'bg-blue-900 hover:bg-blue-800 font-bold';

      const inf = infList[idx];
      if (inf && inf.id) {
        hHtml += `
          <th class="p-3 text-center ${bgCls} cursor-pointer group transition-all select-none border-b-2 border-transparent hover:border-amber-400"
              onclick="openEditInformeModal(${inf.id})"
              title="Hacer clic para revisar o editar analítica del ${escapeHtml(inf.fecha)} (${escapeHtml(inf.laboratorio)})">
            <div class="flex items-center justify-center gap-1.5">
              <span>${escapeHtml(d)}</span>
              <span class="text-[10px] opacity-70 group-hover:opacity-100 group-hover:scale-110 transition-transform" title="Editar este control">✏️</span>
            </div>
          </th>`;
      } else {
        hHtml += `<th class="p-3 text-center ${bgCls}">${escapeHtml(d)}</th>`;
      }
    });
    hHtml += `
        <th class="p-3 text-center bg-blue-800 font-extrabold text-white border-l-2 border-r-2 border-blue-400 shadow-inner">
          Promedio 18 meses
        </th>
      </tr>
    `;
    thead.innerHTML = hHtml;

    // 4.2 Filas Bioquímica
    const tbody = document.getElementById('tableBodyRows');
    tbody.innerHTML = '';
    let currentGroup = null;
    const totalCols = 3 + data.dates.length + 1;

    data.bioquimica.forEach(row => {
      // Cabecera visual de grupo clínico
      if (row.group && row.group !== currentGroup) {
        currentGroup = row.group;
        const groupTr = document.createElement('tr');
        groupTr.className = 'group-header bg-slate-100 border-t-2 border-b border-slate-300';
        groupTr.innerHTML = `
          <td colspan="${totalCols}" class="px-4 py-2 text-xs font-black text-slate-800 tracking-wider bg-slate-100/95 uppercase shadow-sm">
            ${row.group}
          </td>
        `;
        tbody.appendChild(groupTr);
      }

      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-50 transition-colors';
      let cells = `
        <td class="p-3 font-bold sticky left-0 bg-white shadow-sm">${row.name}</td>
        <td class="p-3 text-slate-500">${row.unit}</td>
        <td class="p-3 text-center text-slate-500 text-[11px]">${row.ref}</td>
      `;
      row.vals.forEach(v => {
        if (v === null || v === undefined) {
          cells += `<td class="p-3 text-center text-slate-300">-</td>`;
        } else {
          const fmt = getCellFormatClient(row.name, v);
          cells += `<td class="p-3 text-center"><span class="${fmt.cls}" title="${fmt.title}">${v}</span></td>`;
        }
      });

      // Promedio 18 meses
      if (row.recentAvg && row.recentAvg !== '-') {
        let fmt = getCellFormatClient(row.name, row.recentAvg);
        cells += `
          <td class="p-3 text-center bg-blue-50/70 border-l border-r border-blue-200">
            <span class="${fmt.cls} text-xs font-bold" title="Promedio últimos 18 meses: ${fmt.title}">${row.recentAvg}</span>
          </td>
        `;
      } else {
        cells += `<td class="p-3 text-center bg-blue-50/40 border-l border-r border-blue-200 text-slate-300 font-normal">-</td>`;
      }

      tr.innerHTML = cells;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Fallo al cargar tablas:', err);
  }
}

// 5. Cargar Gráficos Evolutivos
async function loadCharts() {
  if (typeof Chart === 'undefined') {
    console.error('Chart.js no está cargado todavía.');
    return;
  }

  try {
    const res = await fetch('/api/v1/analiticas/charts');
    if (!res.ok) throw new Error('Error al cargar datos de gráficos: ' + res.statusText);
    const cData = await res.json();
    chartsRendered = true;

    // Destruir instancias previas de forma segura
    Object.values(chartInstances).forEach(c => {
      if (c && typeof c.destroy === 'function') {
        try { c.destroy(); } catch (e) {}
      }
    });
    chartInstances = {};

    const renderChart = (key, canvasId, config, extraOptions = {}) => {
      const el = document.getElementById(canvasId);
      if (!el || !config || !config.labels || config.labels.length === 0) return;
      try {
        if (config.datasets) {
          config.datasets.forEach(ds => {
            ds.spanGaps = true;
            if (!ds.yAxisID) ds.yAxisID = 'y';
            if (!ds.pointRadius) ds.pointRadius = 4;
            if (!ds.pointHoverRadius) ds.pointHoverRadius = 6;
          });
        }
        chartInstances[key] = new Chart(el, {
          type: 'line',
          data: config,
          options: Object.assign({
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 350 },
            spanGaps: true,
            elements: {
              line: { tension: 0.2, spanGaps: true },
              point: { radius: 4, hoverRadius: 6 }
            }
          }, extraOptions)
        });
      } catch (e) {
        console.error(`Error al crear gráfico ${key} (${canvasId}):`, e);
      }
    };

    // 1. Glucosa
    renderChart('glucosa', 'chartGlucosa', cData.glucosa, {
      plugins: { legend: { display: false } },
      scales: { y: { suggestedMin: 70, suggestedMax: 125 } }
    });

    // 2. Lípidos
    renderChart('lipidos', 'chartLipidos', cData.lipidos, {
      scales: { y: { suggestedMin: 40, suggestedMax: 220 } }
    });

    // 3. Castelli
    renderChart('castelli', 'chartCastelli', cData.castelli, {
      scales: { y: { suggestedMin: 1.0, suggestedMax: 5.5 } }
    });

    // 4. Cociente Triglicéridos / HDL
    renderChart('ratios', 'chartRatiosLipidos', cData.ratios_tg, {
      scales: { y: { suggestedMin: 0.5, suggestedMax: 3.5 } }
    });

    // 5. Renal
    renderChart('renal', 'chartRenal', cData.renal, {
      scales: {
        y: { type: 'linear', position: 'left', suggestedMin: 20, suggestedMax: 60, title: { display: true, text: 'Urea (mg/dL)' } },
        y1: { type: 'linear', position: 'right', suggestedMin: 0.6, suggestedMax: 1.3, grid: { drawOnChartArea: false }, title: { display: true, text: 'Creatinina (mg/dL)' } }
      }
    });

    // 6. Ácido Úrico
    renderChart('urico', 'chartUrico', cData.urico, {
      plugins: { legend: { display: false } },
      scales: { y: { suggestedMin: 3.5, suggestedMax: 8.0 } }
    });

    // 7. PSA
    renderChart('psa', 'chartPSA', cData.psa, {
      scales: {
        y: { suggestedMin: 0.2, suggestedMax: 4.0, title: { display: true, text: 'PSA Total (ng/mL)' } },
        y1: { suggestedMin: 10, suggestedMax: 70, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Ratio (%)' } }
      }
    });

    // 8. TSH
    renderChart('tsh', 'chartTSH', cData.tsh, {
      scales: { y: { suggestedMin: 0.2, suggestedMax: 4.5 } }
    });

    // Trigger de redimensionado tras terminar la animación de pestaña
    setTimeout(() => {
      Object.values(chartInstances).forEach(c => {
        if (c && typeof c.resize === 'function') {
          try { c.resize(); } catch (e) {}
        }
      });
    }, 100);

  } catch (err) {
    console.error('Fallo al cargar gráficos:', err);
  }
}

// 6. Cargar Auditorías de Rango con IA y Gestión de Trazabilidad
let lastAuditCheckTime = null;

function showAiAuditoriaAlert(message, type = 'success') {
  const alertEl = document.getElementById('ai-auditorias-alert');
  if (!alertEl) return;
  alertEl.className = type === 'success'
    ? 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 text-emerald-800 border-emerald-200 block'
    : 'p-3 rounded-xl text-xs font-medium border bg-rose-50 text-rose-800 border-rose-200 block';
  alertEl.textContent = message;
  setTimeout(() => {
    alertEl.className = 'hidden';
  }, 6000);
}

async function loadAiAuditorias(manualTrigger = false) {
  const list = document.getElementById('ai-auditorias-list');
  const syncBtn = document.getElementById('btn-sync-auditorias');
  const syncIcon = document.getElementById('btn-sync-icon');
  const lastCheckEl = document.getElementById('ai-auditorias-last-check');
  const badgeStatus = document.getElementById('ai-auditorias-badge-status');

  if (syncIcon) syncIcon.classList.add('animate-spin');
  if (syncBtn) syncBtn.disabled = true;

  if (!list.hasChildNodes() || manualTrigger) {
    list.innerHTML = '<div class="text-xs text-slate-400 py-4 text-center">Consultando registros de auditoría y rangos de referencia...</div>';
  }

  try {
    const res = await fetch('/api/v1/ai/auditorias');
    if (!res.ok) throw new Error('Error al obtener auditorías');
    const items = await res.json();

    const now = new Date();
    lastAuditCheckTime = now;
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const dateStr = now.toLocaleDateString([], { day: '2-digit', month: '2-digit', year: 'numeric' });
    
    if (lastCheckEl) {
      lastCheckEl.textContent = `Última comprobación: ${dateStr} ${timeStr}`;
    }
    if (badgeStatus) {
      badgeStatus.classList.remove('hidden');
    }

    if (items.length === 0) {
      list.innerHTML = '<div class="text-xs text-slate-500 py-4">No se han registrado modificaciones de rangos de laboratorio todavía.</div>';
      if (manualTrigger) {
        showAiAuditoriaAlert('✓ Comprobación completada: No hay nuevos criterios pendientes de laboratorio.', 'success');
      }
      return;
    }

    list.innerHTML = '';

    const pendientes = items.filter(a => !a.aplicado_en_historico);
    const aplicados = items.filter(a => a.aplicado_en_historico);

    function createCardHtml(aud) {
      const safeAnalito = String(aud.analito).replace(/'/g, "\\'");
      const safeRangoNuevo = String(aud.rango_nuevo).replace(/'/g, "\\'");

      // Limpieza de referencias personales del paciente en la explicación clínica
      let expLimpia = aud.explicacion || 'El laboratorio ha actualizado el criterio de referencia.';
      if (expLimpia.includes('El valor de')) {
        expLimpia = expLimpia.split('El valor de')[0].trim();
      }

      const statusBadge = aud.aplicado_en_historico
        ? `
          <div class="flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-[11px] font-medium">
            <span>✓</span>
            <span>Criterio homologado y aplicado al historial clínico (${aud.fecha_aplicacion || 'Activo'})</span>
          </div>
        `
        : `
          <div class="flex items-center gap-1.5 px-3 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded-lg text-[11px] font-medium">
            <span>ℹ️</span>
            <span>Criterio registrado (Vigente en informes desde ${aud.fecha_analitica})</span>
          </div>
        `;

      const actionBtnText = aud.aplicado_en_historico
        ? 'Volver a aplicar a todo el historial'
        : 'Aplicar a todo el historial';

      const actionBtnClass = aud.aplicado_en_historico
        ? 'px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-1'
        : 'px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-1 shadow-sm';

      const actionBtnIcon = aud.aplicado_en_historico ? '🔄' : '⚡';

      return `
        <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-2">
          <!-- Línea 1: Información básica unificada en una única fila -->
          <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-slate-800 text-xs">
            <span class="font-bold text-slate-900">${aud.analito}</span>
            <span class="text-slate-300">-</span>
            <span class="text-slate-600"><span class="font-medium text-slate-500">Rango Anterior:</span> ${aud.rango_anterior || 'No especificado'}</span>
            <span class="text-slate-300">-</span>
            <span class="text-purple-800 font-semibold"><span class="font-medium text-slate-500">Nuevo Rango:</span> ${aud.rango_nuevo}</span>
            <span class="text-slate-300">-</span>
            <span class="text-slate-500 text-[11px] font-medium">📄 Origen: ${aud.fecha_analitica}</span>
          </div>

          <!-- Línea 2: Criterio clínico simplificado sin datos personales -->
          <div class="text-[11px] text-slate-600 leading-relaxed">
            💡 <strong>Criterio Clínico:</strong> ${expLimpia}
          </div>

          <!-- Línea 3: Tarjeta informativa inferior con estado y botón -->
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-slate-200/60">
            ${statusBadge}
            <button onclick="applyAuditCriteria(${aud.id}, '${safeAnalito}', '${safeRangoNuevo}')" class="${actionBtnClass}">
              <span>${actionBtnIcon}</span> <span>${actionBtnText}</span>
            </button>
          </div>
        </div>
      `;
    }

    // 1. Mostrar rangos pendientes (no aplicados) directamente
    if (pendientes.length > 0) {
      pendientes.forEach(aud => {
        const div = document.createElement('div');
        div.innerHTML = createCardHtml(aud);
        list.appendChild(div.firstElementChild);
      });
    }

    // 2. Colapsar rangos ya aplicados en un acordeón desplegable
    if (aplicados.length > 0) {
      const details = document.createElement('details');
      details.className = 'group bg-white border border-slate-200 rounded-xl overflow-hidden transition-all';
      
      const summary = document.createElement('summary');
      summary.className = 'p-3 cursor-pointer text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-50 flex items-center justify-between transition-colors select-none';
      summary.innerHTML = `
        <span class="flex items-center gap-2">
          <span class="text-slate-400 group-open:rotate-90 transition-transform inline-block text-[10px]">▶</span>
          <span>${aplicados.length} rango(s) de referencia ya aplicado(s) al historial</span>
        </span>
        <span class="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">Aplicados</span>
      `;
      details.appendChild(summary);

      const content = document.createElement('div');
      content.className = 'p-3 pt-0 space-y-2.5 border-t border-slate-100 mt-2';
      aplicados.forEach(aud => {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = createCardHtml(aud);
        content.appendChild(wrapper.firstElementChild);
      });
      details.appendChild(content);

      list.appendChild(details);
    }

    if (manualTrigger) {
      showAiAuditoriaAlert(`✓ Detección completada: ${items.length} registro(s) de rangos supervisados.`, 'success');
    }
  } catch (err) {
    list.innerHTML = `<div class="text-xs text-rose-600 py-2">Error al consultar auditorías: ${err.message}</div>`;
    showAiAuditoriaAlert(`Error al actualizar auditorías: ${err.message}`, 'error');
  } finally {
    if (syncIcon) syncIcon.classList.remove('animate-spin');
    if (syncBtn) syncBtn.disabled = false;
  }
}

// Opción 3: Aplicar criterio individual al histórico
async function applyAuditCriteria(auditId, analitoName, newRange) {
  const confirmMsg = `¿Deseas aplicar el criterio "${newRange}" a todas las analíticas históricas de ${analitoName}?\n\nEsta acción homologará los rangos de referencia en las mediciones anteriores para que los semáforos y tablas reflejen el nuevo criterio.`;
  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch(`/api/v1/ai/aplicar-criterio/${auditId}`, { method: 'POST' });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Error al aplicar criterio');
    }
    const data = await res.json();
    showAiAuditoriaAlert(`✓ ${data.message}`, 'success');
    await loadAiAuditorias(false);
    if (typeof loadSummary === 'function') loadSummary();
    if (typeof loadAllCategories === 'function') loadAllCategories();
  } catch (err) {
    alert(`Error al aplicar criterio: ${err.message}`);
  }
}

// Opción 3: Aplicar todos los criterios al histórico
async function applyAllAuditCriteria() {
  const confirmMsg = '¿Deseas homologar TODOS los criterios de auditoría de rango a todo tu historial de analíticas pasadas?\\n\\nEsto actualizará los rangos de referencia de los analitos en todas las mediciones previas.';
  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch('/api/v1/ai/aplicar-todos', { method: 'POST' });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Error al homologar criterios');
    }
    const data = await res.json();
    showAiAuditoriaAlert(`✓ ${data.message}`, 'success');
    await loadAiAuditorias(false);
    if (typeof loadSummary === 'function') loadSummary();
    if (typeof loadAllCategories === 'function') loadAllCategories();
  } catch (err) {
    alert(`Error al homologar criterios: ${err.message}`);
  }
}

// 7. Lógica de Subida y Revisión de Analíticas (Drag & Drop + Modal)
function openUploadModal() {
  document.getElementById('uploadModal').classList.remove('hidden');
  document.getElementById('uploadStep1').classList.remove('hidden');
  document.getElementById('uploadStep2').classList.add('hidden');
  document.getElementById('uploadStep3').classList.add('hidden');
  currentPreviewData = null;
}

function closeUploadModal() {
  document.getElementById('uploadModal').classList.add('hidden');
  document.getElementById('pdfInput').value = '';
}

function setupDragAndDrop() {
  const dropZone = document.getElementById('dropZone');
  if (!dropZone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add('border-blue-600', 'bg-blue-100/50');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.remove('border-blue-600', 'bg-blue-100/50');
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0 && files[0].type === 'application/pdf') {
      uploadPdfFile(files[0]);
    } else {
      alert('Por favor selecciona un archivo PDF válido.');
    }
  }, false);
}

function handleFileSelected(event) {
  const files = event.target.files;
  if (files && files.length > 0) {
    uploadPdfFile(files[0]);
  }
}

async function uploadPdfFile(file) {
  // Mostrar paso 2 (Spinner)
  document.getElementById('uploadStep1').classList.add('hidden');
  document.getElementById('uploadStep2').classList.remove('hidden');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/v1/upload', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const errMsg = await getErrorMessage(res, 'Error al procesar el archivo');
      throw new Error(errMsg);
    }

    const data = await res.json();
    currentPreviewData = data;
    renderUploadPreview(data);

  } catch (err) {
    alert(`Error: ${err.message}`);
    document.getElementById('uploadStep2').classList.add('hidden');
    document.getElementById('uploadStep1').classList.remove('hidden');
  }
}

function renderUploadPreview(data) {
  document.getElementById('uploadStep2').classList.add('hidden');
  document.getElementById('uploadStep3').classList.remove('hidden');

  // Actualizar banner y etiqueta de motor según el resultado de extracción
  const badgeMotor = document.getElementById('badge-motor-llm');
  const bannerContainer = document.getElementById('previewBannerContainer');
  const bannerHeader = document.getElementById('previewBannerHeader');

  if (data.motor_extraccion === 'mock') {
    if (badgeMotor) {
      badgeMotor.className = 'px-2.5 py-1 bg-amber-100 text-amber-800 text-xs font-bold rounded-lg flex items-center gap-1 cursor-help';
      badgeMotor.innerHTML = '⚠️ Extractor RegEx';
      badgeMotor.title = 'Los modelos LLM configurados no respondieron o no están activos. Se ha utilizado el extractor de contingencia basado en expresiones regulares.';
    }
    if (bannerContainer) {
      bannerContainer.className = 'p-4 bg-amber-50 border-2 border-amber-300 rounded-2xl text-xs space-y-3';
    }
    if (bannerHeader) {
      bannerHeader.innerHTML = `
        <span class="flex items-center gap-1.5 text-amber-900 font-extrabold">
          <span>⚠️</span> Extractor RegEx:
        </span>
        <span class="text-[11px] text-amber-800 bg-amber-100 px-2 py-0.5 rounded-full font-medium">
          Modelos LLM inaccesibles o sin cuota. Extraídos ${data.total_parametros} parámetros con patrones estándar.
        </span>
      `;
    }
  } else {
    if (badgeMotor) {
      badgeMotor.className = 'px-2.5 py-1 bg-purple-100 text-purple-800 text-xs font-bold rounded-lg flex items-center gap-1 cursor-help';
      badgeMotor.innerHTML = `✨ LLM Activo: ${escapeHtml(data.modelo_utilizado || 'Gemini')}`;
      badgeMotor.title = `Extraído con éxito mediante ${data.modelo_utilizado || 'modelo LLM'}`;
    }
    if (bannerContainer) {
      bannerContainer.className = 'p-4 bg-purple-50 border border-purple-200 rounded-2xl text-xs space-y-3';
    }
    if (bannerHeader) {
      const modeloNombre = data.modelo_utilizado ? ` (${escapeHtml(data.modelo_utilizado)})` : '';
      bannerHeader.innerHTML = `
        <span class="flex items-center gap-1.5 text-purple-900 font-bold">
          <span>✨</span> Datos Extraídos por LLM${modeloNombre}:
        </span>
        <span class="text-[11px] text-purple-600 bg-purple-100 px-2 py-0.5 rounded-full font-medium">
          Revisa los datos antes de incorporarlos a la base de datos
        </span>
      `;
    }
  }

  // Metadatos editables
  const fechaEl = document.getElementById('previewFechaInput');
  if (fechaEl) fechaEl.value = data.fecha || '';

  const labEl = document.getElementById('previewLabInput');
  if (labEl) labEl.value = data.laboratorio || '';

  const facEl = document.getElementById('previewFacultativoInput');
  if (facEl) facEl.value = data.facultativo || '';

  const dictEl = document.getElementById('previewDictamenInput');
  if (dictEl) dictEl.value = data.dictamen_preliminar || '';

  const alertsContainer = document.getElementById('previewAlerts');
  alertsContainer.innerHTML = '';

  // Control de analítica duplicada
  const dupContainer = document.getElementById('previewDuplicateWarning');
  const dupTitle = document.getElementById('previewDuplicateTitle');
  const dupMsg = document.getElementById('previewDuplicateMessage');
  const overwriteRadio = document.getElementById('duplicateActionOverwrite');

  if (data.es_duplicado && data.aviso_duplicado) {
    if (dupContainer) dupContainer.classList.remove('hidden');
    if (dupTitle) {
      dupTitle.innerHTML = data.tipo_duplicado === 'exacto_archivo'
        ? '📄 <strong>Documento PDF idéntico detectado en el historial</strong>'
        : '📅 <strong>Analítica con misma fecha registrada previamente</strong>';
    }
    if (dupMsg) {
      dupMsg.textContent = `${data.aviso_duplicado} Elige a continuación si deseas actualizar el registro existente o guardarlo como una nueva analítica independiente.`;
    }
    if (overwriteRadio) overwriteRadio.checked = true;
  } else {
    if (dupContainer) dupContainer.classList.add('hidden');
  }
  
  if (data.aviso_discrepancia_paciente) {
    const mismatchDiv = document.createElement('div');
    mismatchDiv.className = 'flex items-center gap-2 bg-rose-50 border border-rose-300 p-2.5 rounded-xl text-rose-800 text-xs font-semibold';
    mismatchDiv.innerHTML = `<span>⚠️</span> <span><strong>Atención de Identidad:</strong> ${escapeHtml(data.aviso_discrepancia_paciente)} Verifica si es el documento correcto.</span>`;
    alertsContainer.appendChild(mismatchDiv);
  }

  if (data.alertas_ia && data.alertas_ia.length > 0) {
    data.alertas_ia.forEach(al => {
      if (data.aviso_discrepancia_paciente && al.includes(data.aviso_discrepancia_paciente)) return;
      if (data.aviso_duplicado && al.includes(data.aviso_duplicado)) return;
      const div = document.createElement('div');
      div.className = 'flex items-center gap-1.5 bg-amber-50/80 border border-amber-200 px-2.5 py-1 rounded-lg text-amber-900';
      div.innerHTML = `<span>⚠️</span> <span>${escapeHtml(al)}</span>`;
      alertsContainer.appendChild(div);
    });
  }

  const syncNotice = document.getElementById('previewDictamenSyncNotice');
  if (syncNotice) syncNotice.classList.add('hidden');

  const tbody = document.getElementById('previewTableBody');
  tbody.innerHTML = '';
  data.mediciones.forEach(m => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-50 transition-colors';
    tr.dataset.code = m.codigo || '';
    tr.dataset.initialEstado = m.estado_estimado || 'Normal';

    tr.innerHTML = `
      <td class="p-2">
        <input type="text" class="preview-nombre w-full text-xs font-semibold text-slate-800 bg-white border border-slate-200 rounded-lg px-2 py-1 focus:ring-1 focus:ring-purple-500 focus:outline-none" value="${escapeHtml(m.nombre)}" placeholder="Nombre analito">
      </td>
      <td class="p-2 text-center">
        <input type="text" class="preview-valor w-full text-xs font-bold text-center text-slate-900 bg-white border border-slate-200 rounded-lg px-2 py-1 focus:ring-1 focus:ring-purple-500 focus:outline-none" value="${escapeHtml(String(m.valor ?? ''))}" placeholder="Valor">
      </td>
      <td class="p-2 text-center">
        <input type="text" class="preview-unidad w-full text-xs text-center text-slate-600 bg-white border border-slate-200 rounded-lg px-1.5 py-1 focus:ring-1 focus:ring-purple-500 focus:outline-none" value="${escapeHtml(m.unidad || '')}" placeholder="Unidad">
      </td>
      <td class="p-2 text-center">
        <input type="text" class="preview-rango w-full text-[11px] text-center text-slate-500 bg-white border border-slate-200 rounded-lg px-1.5 py-1 focus:ring-1 focus:ring-purple-500 focus:outline-none" value="${escapeHtml(m.rango_referencia || '')}" placeholder="Rango ref.">
      </td>
      <td class="p-2 text-center">
        <span class="preview-estado-badge px-2 py-0.5 font-semibold rounded text-[10px] whitespace-nowrap border">${escapeHtml(m.estado_estimado || 'Normal')}</span>
      </td>
      <td class="p-2 text-center">
        <button type="button" onclick="removePreviewRow(this)" class="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 transition-colors" title="Eliminar fila">
          🗑️
        </button>
      </td>
    `;

    const onValOrRangoChange = () => {
      updateRowEstado(tr);
      markPreviewDataChanged();
    };

    tr.querySelector('.preview-valor')?.addEventListener('input', onValOrRangoChange);
    tr.querySelector('.preview-rango')?.addEventListener('input', onValOrRangoChange);
    tr.querySelector('.preview-nombre')?.addEventListener('input', () => {
      updateRowEstado(tr);
      markPreviewDataChanged();
    });
    tr.querySelector('.preview-unidad')?.addEventListener('input', markPreviewDataChanged);

    tbody.appendChild(tr);
    // Calcular de inmediato el estado reactivo con sus colores correspondientes
    updateRowEstado(tr);
  });

  updatePreviewParamCount();
}

// Cálculo ultra-ligero y reactivo del estado clínico (ejecutado en <0.1ms en el navegador)
function calculateEstadoFromValorAndRango(valStr, refStr, nombreStr = '', fallbackEstado = 'Normal') {
  if (valStr === null || valStr === undefined || String(valStr).trim() === '') {
    return { text: 'Pendiente', badgeClass: 'bg-slate-100 text-slate-500 border-slate-200' };
  }

  const rawVal = String(valStr).trim();
  const rawRef = String(refStr || '').trim();

  // 1. Chequeo cualitativo directo
  const lowerVal = rawVal.toLowerCase();
  if (lowerVal.includes('negativo') || lowerVal.includes('no reactivo') || lowerVal.includes('no detectado') || lowerVal.includes('ausente')) {
    return { text: 'Normal', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
  }
  if (lowerVal.includes('positivo') || lowerVal.includes('reactivo') || lowerVal.includes('detectado') || lowerVal.includes('presente')) {
    return { text: 'Atención', badgeClass: 'bg-rose-100 text-rose-800 border-rose-300' };
  }

  // 2. Extraer número (soporta decimales con coma o punto, ignora asteriscos ej: "* 1.5")
  const numMatch = rawVal.replace(',', '.').match(/[-+]?\d+(?:\.\d+)?/);
  if (!numMatch) {
    return formatBadgeForEstado(fallbackEstado || 'Normal');
  }
  const val = parseFloat(numMatch[0]);
  if (isNaN(val)) {
    return formatBadgeForEstado(fallbackEstado || 'Normal');
  }

  // 3. Analizar rango de referencia si existe
  if (rawRef) {
    const cleanRef = rawRef.replace(',', '.');

    // Patrón A: Rango Min - Max (ej: "59 - 160", "0.70 - 1.20", "10 a 20", "4.0 - 5.6")
    const rangeMatch = cleanRef.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:-|–|—|\ba\b|\bhasta\b)\s*([0-9]+(?:\.[0-9]+)?)/i);
    if (rangeMatch) {
      const min = parseFloat(rangeMatch[1]);
      const max = parseFloat(rangeMatch[2]);
      if (!isNaN(min) && !isNaN(max)) {
        if (val < min) {
          return { text: 'Bajo', badgeClass: 'bg-amber-100 text-amber-800 border-amber-300' };
        } else if (val > max) {
          return { text: 'Alto', badgeClass: 'bg-rose-100 text-rose-800 border-rose-300' };
        } else {
          return { text: 'Normal', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
        }
      }
    }

    // Patrón B: Menor que (ej: "< 1.2", "<= 100", "Menos de 0.10", "Inf. 150", "Hasta 150")
    const maxMatch = cleanRef.match(/(?:<=?|<|menos de|inferior a|inf\.?|hasta)\s*([0-9]+(?:\.[0-9]+)?)/i);
    if (maxMatch) {
      const max = parseFloat(maxMatch[1]);
      if (!isNaN(max)) {
        if (val > max) {
          return { text: 'Alto', badgeClass: 'bg-rose-100 text-rose-800 border-rose-300' };
        } else {
          return { text: 'Óptimo', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
        }
      }
    }

    // Patrón C: Mayor que (ej: "> 50", ">= 60", "Superior a 30", "Sup. 40", "mas de 20")
    const minMatch = cleanRef.match(/(?:>=?|>|mas de|más de|superior a|sup\.?)\s*([0-9]+(?:\.[0-9]+)?)/i);
    if (minMatch) {
      const min = parseFloat(minMatch[1]);
      if (!isNaN(min)) {
        if (val < min) {
          return { text: 'Bajo', badgeClass: 'bg-amber-100 text-amber-800 border-amber-300' };
        } else {
          return { text: 'Óptimo', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
        }
      }
    }
  }

  // 4. Reglas específicas para biomarcadores clave cuando no hay rango explícito o para afinar
  const cleanNom = String(nombreStr || '').trim().toLowerCase();
  if (cleanNom.includes('hba1c')) {
    if (val >= 5.7) return { text: 'Atención', badgeClass: 'bg-amber-100 text-amber-800 border-amber-300' };
    return { text: 'Óptimo', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
  }
  if (cleanNom.includes('glucosa')) {
    if (val > 100) return { text: 'Atención', badgeClass: 'bg-amber-100 text-amber-800 border-amber-300' };
    return { text: 'Óptimo', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
  }
  if (cleanNom.includes('ldl')) {
    if (val > 116) return { text: 'Atención', badgeClass: 'bg-amber-100 text-amber-800 border-amber-300' };
    return { text: 'Óptimo', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
  }
  if (cleanNom.includes('colesterol total') || cleanNom === 'colesterol') {
    if (val > 200) return { text: 'Alto', badgeClass: 'bg-rose-100 text-rose-800 border-rose-300' };
    return { text: 'Normal', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
  }
  if (cleanNom.includes('vitamina d')) {
    if (val < 20) return { text: 'Alerta', badgeClass: 'bg-rose-100 text-rose-800 border-rose-300' };
    if (val < 30) return { text: 'Bajo', badgeClass: 'bg-amber-100 text-amber-800 border-amber-300' };
    return { text: 'Óptimo', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
  }

  return formatBadgeForEstado(fallbackEstado || 'Normal');
}

function formatBadgeForEstado(estado) {
  const est = (estado || 'Normal').trim();
  const lower = est.toLowerCase();
  if (lower.includes('optimo') || lower.includes('óptimo') || lower.includes('bueno')) {
    return { text: est || 'Óptimo', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
  }
  if (lower.includes('atencion') || lower.includes('atención') || lower.includes('limite') || lower.includes('límite') || lower.includes('bajo')) {
    return { text: est || 'Atención', badgeClass: 'bg-amber-100 text-amber-800 border-amber-300' };
  }
  if (lower.includes('alto') || lower.includes('alerta')) {
    return { text: est || 'Alto', badgeClass: 'bg-rose-100 text-rose-800 border-rose-300' };
  }
  return { text: est || 'Normal', badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
}

function updateRowEstado(tr) {
  if (!tr) return;
  const valorInput = tr.querySelector('.preview-valor');
  const rangoInput = tr.querySelector('.preview-rango');
  const nombreInput = tr.querySelector('.preview-nombre');
  const badge = tr.querySelector('.preview-estado-badge');
  if (!badge) return;

  const val = valorInput ? valorInput.value : '';
  const ref = rangoInput ? rangoInput.value : '';
  const nom = nombreInput ? nombreInput.value : '';
  const initialEst = tr.dataset.initialEstado || badge.textContent || 'Normal';

  const res = calculateEstadoFromValorAndRango(val, ref, nom, initialEst);
  badge.textContent = res.text;
  badge.className = `preview-estado-badge px-2 py-0.5 font-semibold rounded text-[10px] whitespace-nowrap border ${res.badgeClass} transition-colors`;
}

function markPreviewDataChanged() {
  const notice = document.getElementById('previewDictamenSyncNotice');
  if (notice) notice.classList.remove('hidden');
}

async function regeneratePreviewDictamen(modo = 'completo') {
  const rows = document.querySelectorAll('#previewTableBody tr');
  const mediciones = [];
  rows.forEach(tr => {
    const nombre = tr.querySelector('.preview-nombre')?.value.trim() || '';
    const valor = tr.querySelector('.preview-valor')?.value.trim() || '';
    const unidad = tr.querySelector('.preview-unidad')?.value.trim() || '';
    const rango = tr.querySelector('.preview-rango')?.value.trim() || '';
    const estado = tr.querySelector('.preview-estado-badge')?.textContent.trim() || 'Normal';
    const codigo = tr.dataset.code || null;
    if (nombre && valor !== '') {
      mediciones.push({ codigo, nombre, valor, unidad, rango_referencia: rango, estado_estimado: estado });
    }
  });

  if (mediciones.length === 0) {
    alert('No hay mediciones en la tabla para evaluar.');
    return;
  }

  const btnRegen = document.getElementById('btnRegenerateDictamen');
  const btnRegenText = document.getElementById('btnRegenText');
  const btnRegenIcon = document.getElementById('btnRegenIcon');

  const btnSummary = document.getElementById('btnSummarizeDictamen');
  const btnSummaryText = document.getElementById('btnSummaryText');
  const btnSummaryIcon = document.getElementById('btnSummaryIcon');

  if (btnRegen) btnRegen.disabled = true;
  if (btnSummary) btnSummary.disabled = true;

  if (modo === 'resumido') {
    if (btnSummaryIcon) btnSummaryIcon.textContent = '⏳';
    if (btnSummaryText) btnSummaryText.textContent = 'Resumiendo...';
  } else {
    if (btnRegenIcon) btnRegenIcon.textContent = '⏳';
    if (btnRegenText) btnRegenText.textContent = 'Analizando...';
  }

  const fecha = document.getElementById('previewFechaInput')?.value.trim() || '';
  const lab = document.getElementById('previewLabInput')?.value.trim() || '';
  const fac = document.getElementById('previewFacultativoInput')?.value.trim() || '';

  try {
    const res = await fetch('/api/v1/upload/regenerate-dictamen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mediciones, fecha, laboratorio: lab, facultativo: fac, modo })
    });

    if (!res.ok) {
      const errMsg = await getErrorMessage(res, 'Error al regenerar dictamen');
      throw new Error(errMsg);
    }

    const data = await res.json();
    const dictInput = document.getElementById('previewDictamenInput');
    if (dictInput) dictInput.value = data.dictamen_global || '';

    const alertsContainer = document.getElementById('previewAlerts');
    if (alertsContainer) {
      alertsContainer.innerHTML = '';
      if (data.alertas_ia && data.alertas_ia.length > 0) {
        data.alertas_ia.forEach(al => {
          const div = document.createElement('div');
          div.className = 'flex items-center gap-1.5 bg-amber-50/80 border border-amber-200 px-2.5 py-1 rounded-lg text-amber-900';
          div.innerHTML = `<span>⚠️</span> <span>${escapeHtml(al)}</span>`;
          alertsContainer.appendChild(div);
        });
      }
    }

    const notice = document.getElementById('previewDictamenSyncNotice');
    if (notice) notice.classList.add('hidden');

  } catch (err) {
    alert(`Error al regenerar dictamen: ${err.message}`);
  } finally {
    if (btnRegen) btnRegen.disabled = false;
    if (btnRegenIcon) btnRegenIcon.textContent = '🔄';
    if (btnRegenText) btnRegenText.textContent = 'Regenerar dictamen';

    if (btnSummary) btnSummary.disabled = false;
    if (btnSummaryIcon) btnSummaryIcon.textContent = '📝';
    if (btnSummaryText) btnSummaryText.textContent = 'Resumir dictamen';
  }
}

function addPreviewRow() {
  const tbody = document.getElementById('previewTableBody');
  const tr = document.createElement('tr');
  tr.className = 'hover:bg-slate-50 transition-colors bg-purple-50/30';
  tr.dataset.code = '';
  tr.dataset.initialEstado = 'Pendiente';

  tr.innerHTML = `
    <td class="p-2">
      <input type="text" class="preview-nombre w-full text-xs font-semibold text-slate-800 bg-white border border-purple-300 rounded-lg px-2 py-1 focus:ring-1 focus:ring-purple-500 focus:outline-none" placeholder="Nombre analito (ej: Ferritina)">
    </td>
    <td class="p-2 text-center">
      <input type="text" class="preview-valor w-full text-xs font-bold text-center text-slate-900 bg-white border border-purple-300 rounded-lg px-2 py-1 focus:ring-1 focus:ring-purple-500 focus:outline-none" placeholder="0.0">
    </td>
    <td class="p-2 text-center">
      <input type="text" class="preview-unidad w-full text-xs text-center text-slate-600 bg-white border border-purple-300 rounded-lg px-1.5 py-1 focus:ring-1 focus:ring-purple-500 focus:outline-none" placeholder="mg/dL">
    </td>
    <td class="p-2 text-center">
      <input type="text" class="preview-rango w-full text-[11px] text-center text-slate-500 bg-white border border-purple-300 rounded-lg px-1.5 py-1 focus:ring-1 focus:ring-purple-500 focus:outline-none" placeholder="Rango ref.">
    </td>
    <td class="p-2 text-center">
      <span class="preview-estado-badge px-2 py-0.5 bg-slate-100 text-slate-500 border border-slate-200 text-[10px] font-semibold rounded whitespace-nowrap">Pendiente</span>
    </td>
    <td class="p-2 text-center">
      <button type="button" onclick="removePreviewRow(this)" class="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 transition-colors" title="Eliminar fila">
        🗑️
      </button>
    </td>
  `;

  const onValOrRangoChange = () => {
    updateRowEstado(tr);
    markPreviewDataChanged();
  };

  tr.querySelector('.preview-valor')?.addEventListener('input', onValOrRangoChange);
  tr.querySelector('.preview-rango')?.addEventListener('input', onValOrRangoChange);
  tr.querySelector('.preview-nombre')?.addEventListener('input', () => {
    updateRowEstado(tr);
    markPreviewDataChanged();
  });
  tr.querySelector('.preview-unidad')?.addEventListener('input', markPreviewDataChanged);

  tbody.appendChild(tr);
  updatePreviewParamCount();
  markPreviewDataChanged();
  tr.querySelector('.preview-nombre').focus();
}

function removePreviewRow(btn) {
  const tr = btn.closest('tr');
  if (tr) {
    tr.remove();
    updatePreviewParamCount();
    markPreviewDataChanged();
  }
}

function updatePreviewParamCount() {
  const count = document.querySelectorAll('#previewTableBody tr').length;
  const el = document.getElementById('previewParamCount');
  if (el) el.textContent = count;
}

async function confirmUploadData() {
  if (!currentPreviewData) return;

  const fecha = document.getElementById('previewFechaInput').value.trim();
  const laboratorio = document.getElementById('previewLabInput').value.trim();
  const facultativo = document.getElementById('previewFacultativoInput').value.trim();

  // Si se modificaron valores en la tabla y aún no se ha sincronizado el dictamen, ofrecer regenerarlo
  const syncNotice = document.getElementById('previewDictamenSyncNotice');
  if (syncNotice && !syncNotice.classList.contains('hidden')) {
    const wantRegen = confirm('Has modificado valores en la tabla.\n\n¿Deseas regenerar el dictamen clínico automáticamente antes de guardar para que las observaciones concuerden con los nuevos valores?');
    if (wantRegen) {
      await regeneratePreviewDictamen();
    }
  }
  const dictamen = document.getElementById('previewDictamenInput').value.trim();

  if (!fecha) {
    alert('Por favor, indica una fecha válida para la analítica.');
    return;
  }

  const rows = document.querySelectorAll('#previewTableBody tr');
  const mediciones = [];

  rows.forEach(tr => {
    const nombre = tr.querySelector('.preview-nombre').value.trim();
    const valor = tr.querySelector('.preview-valor').value.trim();
    const unidad = tr.querySelector('.preview-unidad').value.trim();
    const rango = tr.querySelector('.preview-rango').value.trim();
    const estado = tr.querySelector('.preview-estado-badge')?.textContent.trim() || 'Normal';
    const codigo = tr.dataset.code || null;

    if (nombre && valor !== '') {
      mediciones.push({
        codigo: codigo,
        nombre: nombre,
        valor: valor,
        unidad: unidad,
        rango_referencia: rango,
        estado_estimado: estado
      });
    }
  });

  if (mediciones.length === 0) {
    alert('La analítica debe contener al menos un parámetro o medición para ser incorporada.');
    return;
  }

  const btn = document.getElementById('btnConfirmUpload');
  btn.disabled = true;
  btn.innerHTML = '<span>⏳</span> Guardando en base de datos...';

  const overwriteRadio = document.getElementById('duplicateActionOverwrite');
  const sobrescribir = (currentPreviewData.es_duplicado && overwriteRadio && overwriteRadio.checked) ? true : false;

  try {
    const payload = {
      temp_id: currentPreviewData.temp_id,
      fecha: fecha,
      laboratorio: laboratorio || 'Laboratorio Clínico',
      facultativo: facultativo || 'No especificado',
      mediciones: mediciones,
      dictamen_global: dictamen || 'Control favorable',
      sha256: currentPreviewData.sha256 || null,
      sobrescribir_existente: sobrescribir,
      informe_id_a_reemplazar: currentPreviewData.informe_existente_id || null
    };

    const res = await fetch('/api/v1/upload/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errMsg = await getErrorMessage(res, 'Error al confirmar analítica');
      throw new Error(errMsg);
    }

    const resData = await res.json();
    alert(resData.message || '¡Analítica procesada con éxito en el historial!');
    closeUploadModal();
    
    // Recargar componentes dinámicamente
    await loadSummary();
    await loadTables();
    await loadAuditFiles();
    chartsRendered = false;
    if (!document.getElementById('tab-charts').classList.contains('hidden')) {
      await loadCharts();
    }

  } catch (err) {
    alert(`Error al confirmar: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>✅</span> Confirmar e Incorporar al Historial';
  }
}

// 7.2 Edición de Analíticas Guardadas en Base de Datos (Post-Ingesta)
let currentEditingInformeId = null;

async function openEditInformeModal(informeId) {
  try {
    const res = await fetch(`/api/v1/analiticas/informes/${informeId}`);
    if (!res.ok) throw new Error('No se pudo recuperar la analítica solicitada.');
    const data = await res.json();
    
    currentEditingInformeId = data.id;
    document.getElementById('editInformeId').value = data.id;
    document.getElementById('editInformeFecha').value = data.fecha;
    document.getElementById('editInformeLab').value = data.laboratorio || '';
    document.getElementById('editInformeFacultativo').value = data.facultativo || '';
    const dictamenEl = document.getElementById('editInformeDictamen');
    if (dictamenEl) {
      dictamenEl.value = data.dictamen_global || '';
      // Auto-ajustar altura para que todo el texto sea visible inmediatamente
      dictamenEl.style.height = 'auto';
      dictamenEl.style.height = Math.max(90, Math.min(300, dictamenEl.scrollHeight + 6)) + 'px';
    }

    const syncNotice = document.getElementById('editDictamenSyncNotice');
    if (syncNotice) syncNotice.classList.add('hidden');

    renderEditInformeRows(data.mediciones || []);
    document.getElementById('editInformeModal').classList.remove('hidden');
  } catch (err) {
    alert('Error al abrir editor de analítica: ' + err.message);
  }
}

function closeEditInformeModal() {
  document.getElementById('editInformeModal').classList.add('hidden');
  currentEditingInformeId = null;
}

function markEditDictamenUnsynced() {
  const notice = document.getElementById('editDictamenSyncNotice');
  if (notice) notice.classList.remove('hidden');
}

async function regenerateEditInformeDictamen(modo = 'completo') {
  const rows = document.querySelectorAll('#editTableBody tr');
  const mediciones = [];
  rows.forEach(tr => {
    let nombre = tr.querySelector('.edit-nombre')?.value.trim() || '';
    const customInput = tr.querySelector('.edit-nombre-custom');
    if (customInput && !customInput.classList.contains('hidden') && customInput.value.trim()) {
      nombre = customInput.value.trim();
    }
    const valor = tr.querySelector('.edit-valor')?.value.trim() || '';
    const unidad = tr.querySelector('.edit-unidad')?.value.trim() || '';
    const rango = tr.querySelector('.edit-rango')?.value.trim() || '';
    const codigo = tr.dataset.code || null;
    if (nombre && valor !== '') {
      mediciones.push({ codigo, nombre, valor, unidad, rango_referencia: rango, estado_estimado: 'Normal' });
    }
  });

  if (mediciones.length === 0) {
    alert('No hay mediciones en la tabla para evaluar.');
    return;
  }

  const btnRegen = document.getElementById('btnEditRegenerateDictamen');
  const btnRegenText = document.getElementById('btnEditRegenText');
  const btnRegenIcon = document.getElementById('btnEditRegenIcon');

  const btnSummary = document.getElementById('btnEditSummarizeDictamen');
  const btnSummaryText = document.getElementById('btnEditSummaryText');
  const btnSummaryIcon = document.getElementById('btnEditSummaryIcon');

  if (btnRegen) btnRegen.disabled = true;
  if (btnSummary) btnSummary.disabled = true;

  if (modo === 'resumido') {
    if (btnSummaryIcon) btnSummaryIcon.textContent = '⏳';
    if (btnSummaryText) btnSummaryText.textContent = 'Resumiendo...';
  } else {
    if (btnRegenIcon) btnRegenIcon.textContent = '⏳';
    if (btnRegenText) btnRegenText.textContent = 'Analizando...';
  }

  const fecha = document.getElementById('editInformeFecha')?.value.trim() || '';
  const lab = document.getElementById('editInformeLab')?.value.trim() || '';
  const fac = document.getElementById('editInformeFacultativo')?.value.trim() || '';

  try {
    const res = await fetch('/api/v1/upload/regenerate-dictamen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mediciones, fecha, laboratorio: lab, facultativo: fac, modo })
    });

    if (!res.ok) {
      const errMsg = await getErrorMessage(res, 'Error al regenerar dictamen');
      throw new Error(errMsg);
    }

    const data = await res.json();
    const dictInput = document.getElementById('editInformeDictamen');
    if (dictInput) {
      dictInput.value = data.dictamen_global || '';
      dictInput.style.height = 'auto';
      dictInput.style.height = Math.max(90, Math.min(320, dictInput.scrollHeight + 6)) + 'px';
    }

    const notice = document.getElementById('editDictamenSyncNotice');
    if (notice) notice.classList.add('hidden');

  } catch (err) {
    alert(`Error al regenerar dictamen: ${err.message}`);
  } finally {
    if (btnRegen) btnRegen.disabled = false;
    if (btnRegenIcon) btnRegenIcon.textContent = '🔄';
    if (btnRegenText) btnRegenText.textContent = 'Regenerar dictamen';

    if (btnSummary) btnSummary.disabled = false;
    if (btnSummaryIcon) btnSummaryIcon.textContent = '📝';
    if (btnSummaryText) btnSummaryText.textContent = 'Resumir dictamen';
  }
}

let canonicalCatalogCache = null;

async function getCanonicalCatalog() {
  if (canonicalCatalogCache) return canonicalCatalogCache;
  try {
    const res = await fetch('/api/v1/analiticas/catalog');
    if (res.ok) {
      canonicalCatalogCache = await res.json();
    }
  } catch (e) {
    console.error('Error al cargar catálogo canónico:', e);
  }
  return canonicalCatalogCache || {};
}

function renderEditInformeRows(mediciones) {
  const tbody = document.getElementById('editTableBody');
  tbody.innerHTML = '';

  mediciones.forEach(m => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-50 transition-colors';
    tr.dataset.id = m.id || '';
    tr.dataset.code = m.codigo || '';
    tr.dataset.isRatio = m.es_ratio ? '1' : '0';

    const ratioBadge = m.es_ratio 
      ? `<span class="px-2 py-0.5 bg-purple-100 text-purple-800 text-[10px] font-bold rounded-full" title="Ratio derivado (se recalcula automáticamente al guardar)">Ratio Auto</span>`
      : `<span class="px-2 py-0.5 bg-slate-100 text-slate-600 text-[10px] font-medium rounded-full">Basal</span>`;

    tr.innerHTML = `
      <td class="p-2">
        <div class="flex items-center gap-1.5 py-1">
          <span class="text-xs font-bold text-slate-800" title="Código canónico: ${escapeHtml(m.codigo || '')}">${escapeHtml(m.nombre)}</span>
          <input type="hidden" class="edit-nombre" value="${escapeHtml(m.nombre)}">
        </div>
      </td>
      <td class="p-2 text-center">
        <input type="text" class="edit-valor w-full text-xs font-bold text-center text-slate-900 bg-white border border-slate-200 rounded-lg px-2 py-1 focus:ring-1 focus:ring-blue-500 focus:outline-none" value="${escapeHtml(String(m.valor ?? ''))}" placeholder="Valor">
      </td>
      <td class="p-2 text-center">
        <input type="text" class="edit-unidad w-full text-xs text-center text-slate-600 bg-white border border-slate-200 rounded-lg px-1.5 py-1 focus:ring-1 focus:ring-blue-500 focus:outline-none" value="${escapeHtml(m.unidad || '')}" placeholder="Unidad">
      </td>
      <td class="p-2 text-center">
        <input type="text" class="edit-rango w-full text-[11px] text-center text-slate-500 bg-white border border-slate-200 rounded-lg px-1.5 py-1 focus:ring-1 focus:ring-blue-500 focus:outline-none" value="${escapeHtml(m.rango_referencia || '')}" placeholder="Rango ref.">
      </td>
      <td class="p-2 text-center">
        ${ratioBadge}
      </td>
      <td class="p-2 text-center">
        <button type="button" onclick="removeEditMeasurementRow(this)" class="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 transition-colors" title="Eliminar medición">
          🗑️
        </button>
      </td>
    `;

    const onEditRowChange = () => {
      markEditDictamenUnsynced();
    };
    tr.querySelector('.edit-valor')?.addEventListener('input', onEditRowChange);
    tr.querySelector('.edit-unidad')?.addEventListener('input', onEditRowChange);
    tr.querySelector('.edit-rango')?.addEventListener('input', onEditRowChange);

    tbody.appendChild(tr);
  });

  updateEditParamCount();
}

async function addEditMeasurementRow() {
  const tbody = document.getElementById('editTableBody');
  const tr = document.createElement('tr');
  tr.className = 'hover:bg-slate-50 transition-colors bg-blue-50/30';
  tr.dataset.id = '';
  tr.dataset.code = '';
  tr.dataset.isRatio = '0';

  const catalog = await getCanonicalCatalog();
  let optionsHtml = '<option value="">-- Selecciona analito del catálogo --</option>';
  for (const [group, items] of Object.entries(catalog)) {
    optionsHtml += `<optgroup label="${escapeHtml(group)}">`;
    items.forEach(item => {
      optionsHtml += `<option value="${escapeHtml(item.codigo)}" data-nombre="${escapeHtml(item.nombre)}" data-unidad="${escapeHtml(item.unidad || '')}" data-ref="${escapeHtml(item.ref || '')}">${escapeHtml(item.nombre)}</option>`;
    });
    optionsHtml += `</optgroup>`;
  }
  optionsHtml += `<option value="__custom__">➕ Otro analito no catalogado...</option>`;

  tr.innerHTML = `
    <td class="p-2">
      <select class="edit-select-analito w-full text-xs font-semibold text-slate-800 bg-white border border-blue-300 rounded-lg px-2 py-1.5 focus:ring-1 focus:ring-blue-500 focus:outline-none" onchange="handleCatalogSelect(this)">
        ${optionsHtml}
      </select>
      <input type="text" class="edit-nombre-custom hidden w-full text-xs font-semibold text-slate-800 bg-white border border-blue-300 rounded-lg px-2 py-1 mt-1 focus:ring-1 focus:ring-blue-500 focus:outline-none" placeholder="Nombre analito manual">
      <input type="hidden" class="edit-nombre" value="">
    </td>
    <td class="p-2 text-center">
      <input type="text" class="edit-valor w-full text-xs font-bold text-center text-slate-900 bg-white border border-blue-300 rounded-lg px-2 py-1 focus:ring-1 focus:ring-blue-500 focus:outline-none" placeholder="0.0">
    </td>
    <td class="p-2 text-center">
      <input type="text" class="edit-unidad w-full text-xs text-center text-slate-600 bg-white border border-blue-300 rounded-lg px-1.5 py-1 focus:ring-1 focus:ring-blue-500 focus:outline-none" placeholder="mg/dL">
    </td>
    <td class="p-2 text-center">
      <input type="text" class="edit-rango w-full text-[11px] text-center text-slate-500 bg-white border border-blue-300 rounded-lg px-1.5 py-1 focus:ring-1 focus:ring-blue-500 focus:outline-none" placeholder="Rango ref.">
    </td>
    <td class="p-2 text-center">
      <span class="px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] font-bold rounded-full">Nuevo</span>
    </td>
    <td class="p-2 text-center">
      <button type="button" onclick="removeEditMeasurementRow(this)" class="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 transition-colors" title="Eliminar medición">
        🗑️
      </button>
    </td>
  `;

  const onEditRowChange = () => {
    markEditDictamenUnsynced();
  };
  tr.querySelector('.edit-valor')?.addEventListener('input', onEditRowChange);
  tr.querySelector('.edit-unidad')?.addEventListener('input', onEditRowChange);
  tr.querySelector('.edit-rango')?.addEventListener('input', onEditRowChange);
  tr.querySelector('.edit-nombre-custom')?.addEventListener('input', onEditRowChange);

  tbody.appendChild(tr);
  updateEditParamCount();
  markEditDictamenUnsynced();
  tr.querySelector('.edit-select-analito').focus();
}

function handleCatalogSelect(selectEl) {
  const tr = selectEl.closest('tr');
  const customInput = tr.querySelector('.edit-nombre-custom');
  const hiddenNombre = tr.querySelector('.edit-nombre');
  const unidadInput = tr.querySelector('.edit-unidad');
  const rangoInput = tr.querySelector('.edit-rango');
  const val = selectEl.value;

  if (val === '__custom__') {
    customInput.classList.remove('hidden');
    customInput.focus();
    tr.dataset.code = '';
    hiddenNombre.value = '';
    markEditDictamenUnsynced();
  } else if (val) {
    customInput.classList.add('hidden');
    tr.dataset.code = val;
    const opt = selectEl.selectedOptions[0];
    hiddenNombre.value = opt.dataset.nombre || '';
    if (opt.dataset.unidad) unidadInput.value = opt.dataset.unidad;
    if (opt.dataset.ref) rangoInput.value = opt.dataset.ref;
    markEditDictamenUnsynced();
  } else {
    customInput.classList.add('hidden');
    tr.dataset.code = '';
    hiddenNombre.value = '';
    markEditDictamenUnsynced();
  }
}

function removeEditMeasurementRow(btn) {
  const tr = btn.closest('tr');
  if (tr) {
    tr.remove();
    updateEditParamCount();
    markEditDictamenUnsynced();
  }
}

function updateEditParamCount() {
  const count = document.querySelectorAll('#editTableBody tr').length;
  const el = document.getElementById('editParamCount');
  if (el) el.textContent = count;
}

async function saveEditedInforme() {
  if (!currentEditingInformeId) return;

  const syncNotice = document.getElementById('editDictamenSyncNotice');
  if (syncNotice && !syncNotice.classList.contains('hidden')) {
    const wantRegen = confirm('Has modificado valores en la tabla.\n\n¿Deseas regenerar el dictamen clínico automáticamente antes de guardar para que las observaciones concuerden con los nuevos valores?');
    if (wantRegen) {
      await regenerateEditInformeDictamen();
    }
  }

  const fecha = document.getElementById('editInformeFecha').value.trim();
  const laboratorio = document.getElementById('editInformeLab').value.trim();
  const facultativo = document.getElementById('editInformeFacultativo').value.trim();
  const dictamen = document.getElementById('editInformeDictamen').value.trim();

  if (!fecha) {
    alert('Por favor, introduce una fecha válida para la analítica.');
    return;
  }

  const rows = document.querySelectorAll('#editTableBody tr');
  const mediciones = [];

  rows.forEach(tr => {
    let nombre = tr.querySelector('.edit-nombre').value.trim();
    const customInput = tr.querySelector('.edit-nombre-custom');
    if (customInput && !customInput.classList.contains('hidden') && customInput.value.trim()) {
      nombre = customInput.value.trim();
    }
    const valor = tr.querySelector('.edit-valor').value.trim();
    const unidad = tr.querySelector('.edit-unidad').value.trim();
    const rango = tr.querySelector('.edit-rango').value.trim();
    const id = tr.dataset.id ? parseInt(tr.dataset.id) : null;
    const codigo = tr.dataset.code || null;
    const esRatio = tr.dataset.isRatio === '1';

    if (nombre && valor !== '') {
      mediciones.push({
        id: id,
        codigo: codigo,
        nombre: nombre,
        valor: valor,
        unidad: unidad,
        rango_referencia: rango,
        es_ratio: esRatio
      });
    }
  });

  if (mediciones.length === 0) {
    alert('La analítica debe contener al menos una medición.');
    return;
  }

  const btn = document.getElementById('btnSaveEditedInforme');
  btn.disabled = true;
  btn.innerHTML = '<span>⏳</span> Guardando y recalculando...';

  try {
    const payload = {
      fecha: fecha,
      laboratorio: laboratorio || 'Laboratorio Clínico',
      facultativo: facultativo || 'No especificado',
      dictamen_global: dictamen || 'Control favorable',
      mediciones: mediciones
    };

    const res = await fetch(`/api/v1/analiticas/informes/${currentEditingInformeId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errMsg = await getErrorMessage(res, 'Error al actualizar la analítica');
      throw new Error(errMsg);
    }

    alert('¡Analítica actualizada y ratios recalculados con éxito!');
    closeEditInformeModal();

    // Refrescar todos los componentes de la aplicación
    await loadSummary();
    await loadTables();
    await loadAuditFiles();
    chartsRendered = false;
    if (!document.getElementById('tab-charts').classList.contains('hidden')) {
      await loadCharts();
    }
  } catch (err) {
    alert('Error al guardar cambios: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>💾</span> Guardar Cambios y Recalcular';
  }
}

// 8. Filtro en Vivo de la Tabla Bioquímica
function filterTable() {
  const query = document.getElementById('tableFilter').value.trim().toLowerCase();
  const rows = document.getElementById('tableBodyRows').getElementsByTagName('tr');
  if (!query) {
    for (let i = 0; i < rows.length; i++) rows[i].style.display = '';
    return;
  }
  
  let currentGroupHeader = null;
  let groupHasMatch = false;

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    if (row.classList.contains('group-header')) {
      if (currentGroupHeader) {
        currentGroupHeader.style.display = groupHasMatch ? '' : 'none';
      }
      currentGroupHeader = row;
      groupHasMatch = row.textContent.toLowerCase().includes(query);
    } else {
      const match = row.textContent.toLowerCase().includes(query);
      row.style.display = match ? '' : 'none';
      if (match) groupHasMatch = true;
    }
  }
  if (currentGroupHeader) {
    currentGroupHeader.style.display = groupHasMatch ? '' : 'none';
  }
}

// 9. Funciones del Panel de Gestión y Respaldo de Datos (Tab 7)

function calculateAgeFromBirthdate(birthdateStr) {
  if (!birthdateStr) return null;
  const birth = new Date(birthdateStr);
  if (isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) {
    age--;
  }
  return (age >= 0 && age <= 125) ? age : null;
}

function updateAgeBadgePreview() {
  const nacInput = document.getElementById('cfg-paciente-nacimiento');
  const badge = document.getElementById('cfg-paciente-badge-edad');
  if (!nacInput || !badge) return;
  const age = calculateAgeFromBirthdate(nacInput.value);
  if (age !== null) {
    badge.textContent = `Edad calculada: ${age} años`;
    badge.classList.remove('hidden');
  } else {
    badge.textContent = 'Edad: -';
    badge.classList.add('hidden');
  }
}

async function loadPatientConfig() {
  try {
    const res = await fetch('/api/v1/analiticas/paciente');
    if (!res.ok) return;
    const p = await res.json();
    
    const nombreEl = document.getElementById('cfg-paciente-nombre');
    const dniEl = document.getElementById('cfg-paciente-dni');
    const nacEl = document.getElementById('cfg-paciente-nacimiento');
    const sexoEl = document.getElementById('cfg-paciente-sexo');

    if (nombreEl) nombreEl.value = p.nombre_completo || '';
    if (dniEl) dniEl.value = p.dni || '';
    if (nacEl) nacEl.value = p.fecha_nacimiento || '';
    if (sexoEl) {
      if (p.sexo && ['Masculino', 'Femenino'].includes(p.sexo)) {
        sexoEl.value = p.sexo;
      } else {
        sexoEl.value = 'No especificado';
      }
    }

    updateAgeBadgePreview();
  } catch (err) {
    console.warn('No se pudo cargar la configuración del paciente:', err);
  }
}

async function savePatientConfig(event) {
  if (event) event.preventDefault();
  const statusEl = document.getElementById('cfg-paciente-status');
  const btn = document.getElementById('btn-save-paciente');

  const payload = {
    nombre_completo: document.getElementById('cfg-paciente-nombre').value.trim(),
    dni: document.getElementById('cfg-paciente-dni').value.trim() || null,
    fecha_nacimiento: document.getElementById('cfg-paciente-nacimiento').value || null,
    sexo: document.getElementById('cfg-paciente-sexo').value
  };

  try {
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Guardando...';
    }

    const res = await fetch('/api/v1/analiticas/paciente', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errDetail = await getErrorMessage(res, 'Fallo al guardar datos del paciente');
      throw new Error(errDetail);
    }

    const updated = await res.json();

    if (statusEl) {
      statusEl.textContent = '✓ Datos del paciente actualizados correctamente.';
      statusEl.className = 'text-xs font-semibold text-emerald-600 inline-block';
      setTimeout(() => {
        statusEl.className = 'text-xs font-semibold text-emerald-600 hidden';
      }, 4000);
    }

    updateAgeBadgePreview();
    await loadSummary();

  } catch (err) {
    alert(`Error al guardar: ${err.message}`);
    if (statusEl) {
      statusEl.textContent = `❌ ${err.message}`;
      statusEl.className = 'text-xs font-semibold text-rose-600 inline-block';
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>💾</span> Guardar Datos del Paciente';
    }
  }
}

async function downloadBackup() {
  const btn = document.getElementById('btnExportBackup');
  const pass = document.getElementById('exportPassphrase').value.trim();
  let url = '/api/v1/backup/export';
  if (pass) {
    url += '?passphrase=' + encodeURIComponent(pass);
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Generando copia de seguridad...';
  }

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Error al generar la copia de seguridad');

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition');
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
    let filename = pass ? `cac-elrocho-backup-${ts}.enc.json` : `cac-elrocho-backup-${ts}.json`;
    if (disposition && disposition.includes('filename=')) {
      filename = disposition.split('filename=')[1].replace(/["']/g, '').trim();
    }

    // 1. Si el navegador soporta el selector nativo de guardado de archivos
    if (window.showSaveFilePicker) {
      try {
        const fileHandle = await window.showSaveFilePicker({
          suggestedName: filename,
          types: [{
            description: 'Copia de seguridad JSON',
            accept: { 'application/json': ['.json'] }
          }]
        });
        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();

        if (btn) {
          btn.innerHTML = '<span>✅</span> ¡Copia guardada con éxito!';
          setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = '<span>💾</span> Generar y Descargar Respaldo JSON';
          }, 2500);
        }
        return;
      } catch (pickerErr) {
        if (pickerErr.name === 'AbortError') {
          // El usuario canceló la ventana de guardado: restaurar botón sin mensaje de éxito erróneo
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>💾</span> Generar y Descargar Respaldo JSON';
          }
          return;
        }
        // Si ocurrió otro tipo de error, continuar con el método de descarga por enlace
      }
    }

    // 2. Método estándar para navegadores tradicionales
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);

    if (btn) {
      btn.innerHTML = '<span>✅</span> Descarga iniciada';
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = '<span>💾</span> Generar y Descargar Respaldo JSON';
      }, 2500);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>💾</span> Generar y Descargar Respaldo JSON';
    }
  }
}

async function uploadBackupFile() {
  const fileInput = document.getElementById('importFileInput');
  const passInput = document.getElementById('importPassphrase');

  if (!fileInput.files || fileInput.files.length === 0) {
    alert('Por favor, selecciona un archivo JSON de copia de seguridad.');
    return;
  }

  const confirmMsg = "⚠️ ATENCIÓN: La importación de una copia de seguridad realiza una RESTAURACIÓN COMPLETA.\n\n" +
    "• Se sustituirán todos los datos actuales de la base de datos por los datos contenidos en el archivo de respaldo seleccionado.\n" +
    "• No se producirá duplicación de analíticas, pero cualquier informe o cambio posterior que no esté en este archivo se perderá.\n\n" +
    "¿Deseas continuar con la restauración?";

  if (!confirm(confirmMsg)) {
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  if (passInput.value.trim()) {
    formData.append('passphrase', passInput.value.trim());
  }

  try {
    const res = await fetch('/api/v1/backup/import', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Fallo al importar la copia de seguridad');
    }

    alert('¡Copia de seguridad restaurada con éxito!');
    fileInput.value = '';
    passInput.value = '';

    // Recargar toda la interfaz
    await loadSummary();
    await loadTables();
    chartsRendered = false;
    setTab('eval');

  } catch (err) {
    alert(`Error al importar: ${err.message}`);
  }
}

async function confirmWipeDatabase() {
  const confirm1 = confirm('⚠️ ATENCIÓN: ¿Estás seguro de que deseas vaciar por completo la base de datos?\n\nEsta acción borrará todos los análisis, informes y mediciones actuales.');
  if (!confirm1) return;

  try {
    const res = await fetch('/api/v1/backup/wipe?confirm=true', {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al vaciar base de datos');

    alert(data.message);
    await loadSummary();
    await loadTables();
    await loadAuditFiles();
    chartsRendered = false;
    setTab('eval');
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

async function confirmResetDemo() {
  const confirm1 = confirm('¿Deseas cargar los datos del modo Demo? Esta acción eliminará cualquier dato previamente existente en la base de datos.');
  if (!confirm1) return;

  try {
    const res = await fetch('/api/v1/backup/reset-demo', {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al restablecer demo');

    alert(data.message);
    await loadSummary();
    await loadTables();
    await loadAuditFiles();
    chartsRendered = false;
    setTab('eval');
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

// 8. Auditoría Documental de Archivos
async function loadAuditFiles() {
  const tbody = document.getElementById('auditFilesTableBody');
  try {
    const res = await fetch('/api/v1/analiticas/files');
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const files = await res.json();
    const countEl = document.getElementById('audit-files-count');
    if (countEl) countEl.textContent = `${files.length} Informes`;

    if (!tbody) return;
    if (files.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-slate-400">No hay informes cargados en el historial. Sube un PDF para comenzar.</td></tr>`;
      return;
    }

    tbody.innerHTML = '';
    files.forEach(f => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-50 transition-colors';
      tr.innerHTML = `
        <td class="p-3 font-bold text-slate-900">${escapeHtml(f.fecha)} <span class="text-[10px] text-slate-400 font-normal">(${escapeHtml(f.etiqueta_corta)})</span></td>
        <td class="p-3 font-medium text-slate-800">${escapeHtml(f.laboratorio)}</td>
        <td class="p-3 text-slate-600">${escapeHtml(f.facultativo || 'No especificado')}</td>
        <td class="p-3 font-mono text-[11px] text-slate-500">${escapeHtml(f.archivo_pdf || '-')}</td>
        <td class="p-3 text-center"><span class="px-2 py-0.5 bg-blue-100 text-blue-800 font-bold rounded-full">${f.total_mediciones}</span></td>
        <td class="p-3 text-slate-600 max-w-xs truncate" title="${escapeHtml(f.dictamen_global || '')}">${escapeHtml(f.dictamen_global || '-')}</td>
        <td class="p-3 text-center">
          <div class="flex items-center justify-center gap-1.5">
            <button onclick="openEditInformeModal(${f.id})" class="px-2.5 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1 shadow-sm" title="Editar analítica y recalcular">
              <span>✏️</span> Editar
            </button>
            <button onclick="deleteAuditFile(${f.id}, '${escapeHtml(f.fecha)}')" class="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1 shadow-sm" title="Eliminar del historial">
              <span>🗑️</span>
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Fallo al cargar archivos de auditoría:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-rose-500 font-medium">⚠️ Error al cargar informes: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

async function deleteAuditFile(id, fecha) {
  if (!confirm(`¿Estás seguro de que deseas eliminar la analítica del ${fecha} (ID: ${id}) del historial? Esta acción no se puede deshacer.`)) {
    return;
  }
  try {
    const res = await fetch(`/api/v1/analiticas/files/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Error al eliminar analítica');
    alert(`Analítica del ${fecha} eliminada correctamente.`);
    // Recargar todo el estado de la aplicación
    await loadAuditFiles();
    await loadSummary();
    await loadTables();
    chartsRendered = false;
    if (!document.getElementById('tab-charts').classList.contains('hidden')) {
      await loadCharts();
    }
  } catch (err) {
    alert('Error al eliminar: ' + err.message);
  }
}


