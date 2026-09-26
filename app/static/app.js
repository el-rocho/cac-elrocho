// cac-elrocho: Frontend Application Logic

let currentPreviewData = null;
let chartsRendered = false;
let chartInstances = {};
let currentKpisData = [];
let activeKpiIndex = 0;

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
  loadAiConfiguration();
  setupDragAndDrop();
  setupBioTableScrollSync();
});

// 1. Gestión de Pestañas y Scroll Horizontal Sincronizado
let isSyncingBioScroll = false;

function syncBioTableScrollWidth() {
  const container = document.getElementById('bioTableContainer');
  const topContent = document.getElementById('bioTableTopScrollContent');
  if (container && topContent) {
    topContent.style.width = container.scrollWidth + 'px';
  }
}

function setupBioTableScrollSync() {
  const topScroll = document.getElementById('bioTableTopScroll');
  const bottomScroll = document.getElementById('bioTableContainer');

  if (!topScroll || !bottomScroll) return;

  topScroll.addEventListener('scroll', () => {
    if (isSyncingBioScroll) return;
    isSyncingBioScroll = true;
    bottomScroll.scrollLeft = topScroll.scrollLeft;
    requestAnimationFrame(() => { isSyncingBioScroll = false; });
  }, { passive: true });

  bottomScroll.addEventListener('scroll', () => {
    if (isSyncingBioScroll) return;
    isSyncingBioScroll = true;
    topScroll.scrollLeft = bottomScroll.scrollLeft;
    requestAnimationFrame(() => { isSyncingBioScroll = false; });
  }, { passive: true });

  window.addEventListener('resize', syncBioTableScrollWidth);
}

function scrollTableToEnd(smooth = false) {
  const container = document.getElementById('bioTableContainer');
  const topScroll = document.getElementById('bioTableTopScroll');
  if (!container) return;
  syncBioTableScrollWidth();
  requestAnimationFrame(() => {
    if (smooth) {
      container.scrollTo({ left: container.scrollWidth, behavior: 'smooth' });
      if (topScroll) topScroll.scrollTo({ left: topScroll.scrollWidth, behavior: 'smooth' });
    } else {
      container.scrollLeft = container.scrollWidth;
      if (topScroll) topScroll.scrollLeft = topScroll.scrollWidth;
    }
  });
}

function scrollTableToStart(smooth = false) {
  const container = document.getElementById('bioTableContainer');
  const topScroll = document.getElementById('bioTableTopScroll');
  if (!container) return;
  syncBioTableScrollWidth();
  requestAnimationFrame(() => {
    if (smooth) {
      container.scrollTo({ left: 0, behavior: 'smooth' });
      if (topScroll) topScroll.scrollTo({ left: 0, behavior: 'smooth' });
    } else {
      container.scrollLeft = 0;
      if (topScroll) topScroll.scrollLeft = 0;
    }
  });
}

function setTab(tabId) {
  const tabs = ['eval', 'table', 'charts', 'audit', 'config'];
  tabs.forEach(t => {
    const el = document.getElementById('tab-' + t);
    const btn = document.getElementById('tab-btn-' + t);
    if (!el || !btn) return;
    
    if (t === tabId) {
      el.classList.remove('hidden');
      btn.className = 'px-5 py-3 text-base rounded-t-lg border-b-2 tab-active transition-colors';
    } else {
      el.classList.add('hidden');
      btn.className = 'px-5 py-3 text-base rounded-t-lg border-b-2 tab-inactive transition-colors';
    }
  });

  if (tabId === 'charts') {
    setTimeout(() => {
      loadCharts();
    }, 60);
  } else if (tabId === 'table') {
    setTimeout(() => {
      syncBioTableScrollWidth();
      scrollTableToEnd();
    }, 50);
  } else if (tabId === 'audit') {
    loadAuditFiles();
  } else if (tabId === 'config') {
    loadPatientConfig();
    loadAiAuditorias();
    loadAiConfiguration();
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
        badgeMotor.title = 'No hay modelos LLM activos configurados. La aplicación operará con el extractor basado en expresiones regulares.';
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
    document.getElementById('paciente-nombre').textContent = nombre || 'Usuario (paciente)';

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

    // Renderizar KPIs Simplificados (clic para ver información completa)
    const container = document.getElementById('kpi-container');
    container.innerHTML = '';
    currentKpisData = data.kpis || [];
    currentKpisData.forEach((kpi, idx) => {
      const card = document.createElement('div');
      card.className = 'bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:shadow-md hover:border-blue-400 cursor-pointer transition-all flex flex-col justify-between group';
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', `Información completa de ${kpi.title}`);
      card.onclick = () => openKpiModal(idx);
      card.onkeydown = (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openKpiModal(idx);
        }
      };

      const labelHtml = kpi.main_label 
        ? `<div class="text-[11px] font-medium text-slate-500 mt-1 truncate" title="${kpi.main_label}">${kpi.main_label}</div>` 
        : '';
      const valColorClass = kpi.main_value_class ? kpi.main_value_class : (kpi.is_altered ? 'text-rose-600 font-semibold' : 'text-slate-900 font-semibold');
      
      const mainVarBadgeHtml = kpi.main_var_delta ? `
        <span class="inline-block px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200/80 text-slate-900 font-mono font-bold text-[10px] leading-tight" title="Variación vs control anterior">
          ${kpi.main_var_delta}
        </span>
      ` : '';
      let mainDotClass = 'bg-slate-300';
      let mainTrendTitle = 'Sin tendencia';
      if (kpi.main_clinical_trend === 'FAVORABLE') {
        mainDotClass = 'bg-emerald-500';
        mainTrendTitle = 'Tendencia favorable';
      } else if (kpi.main_clinical_trend === 'DESFAVORABLE') {
        mainDotClass = 'bg-rose-500';
        mainTrendTitle = 'Tendencia desfavorable';
      } else if (kpi.main_clinical_trend === 'ESTABLE') {
        mainDotClass = 'bg-blue-500';
        mainTrendTitle = 'Tendencia estable';
      }

      const mainFootnoteHtml = (kpi.main_is_historical && kpi.main_footnote_symbol) ? `
        <sup class="text-amber-700 font-bold text-xs ml-0.5" title="Dato de informe anterior: ${kpi.main_fecha_origen || ''}">${kpi.main_footnote_symbol}</sup>
      ` : '';

      const mainIndicatorsHtml = (mainVarBadgeHtml || kpi.main_clinical_trend) ? `
        <span class="inline-flex items-center gap-1.5 ml-2" title="Variación vs control anterior y tendencia">
          ${mainVarBadgeHtml}
          ${kpi.main_clinical_trend ? `
            <span class="w-3 flex items-center justify-center" title="${mainTrendTitle}">
              <span class="w-2 h-2 rounded-full ${mainDotClass} inline-block"></span>
            </span>
          ` : ''}
        </span>
      ` : '';

      const trendLabel = (kpi.trend_badge_text === 'SIN TENDENCIA' || kpi.trend_badge_text === 'Sin tendencia')
        ? 'Tendencia: Sin datos'
        : `Tendencia: ${kpi.trend_badge_text}`;

      const trendBadgeHtml = kpi.trend_badge_text ? `
        <span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${kpi.trend_badge_class || 'bg-slate-100 text-slate-600 border-slate-200'} shrink-0" title="Tendencia global de la tarjeta">
          ${trendLabel}
        </span>
      ` : '';

      card.innerHTML = `
        <div>
          <div class="text-xs font-semibold text-slate-500 uppercase tracking-wide truncate group-hover:text-blue-600 transition-colors" title="${kpi.title}">
            ${kpi.title}
          </div>
          ${labelHtml}
          <div class="text-xl ${valColorClass} ${kpi.main_label ? 'mt-0.5' : 'mt-1'} flex items-baseline flex-wrap">
            <span>${kpi.main_value}</span>
            <span class="text-xs font-normal text-slate-500 ml-1">${kpi.unit}</span>
            ${mainFootnoteHtml}
            ${mainIndicatorsHtml}
          </div>
        </div>
        <div class="mt-3.5 pt-2 border-t border-slate-100 flex flex-col items-start gap-1.5">
          <div class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${kpi.badge_class}">
            ${kpi.badge_text}
          </div>
          ${trendBadgeHtml}
          <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-blue-600 group-hover:text-blue-700 w-full transition-colors">
            <span class="flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
              Información completa
            </span>
            <span class="text-slate-400 group-hover:text-blue-600 group-hover:translate-x-1 transition-all">→</span>
          </div>
        </div>
      `;
      container.appendChild(card);
    });

    // Renderizar Tarjeta Ancho Completo: Otros Valores de Interés
    const otrosContainer = document.getElementById('otros-valores-card');
    if (otrosContainer) {
      if (data.otros_valores && data.otros_valores.length > 0) {
        otrosContainer.classList.remove('hidden');
        const gridColsClass = data.otros_valores.length === 1 ? 'grid-cols-1' :
                              data.otros_valores.length === 2 ? 'grid-cols-1 sm:grid-cols-2' :
                              data.otros_valores.length === 3 ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3' :
                              'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';
        otrosContainer.innerHTML = `
          <div class="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 shadow-sm">
            <div class="flex flex-wrap items-center justify-between gap-2 mb-3 pb-2 border-b border-slate-100">
              <div class="flex items-center gap-2">
                <span class="text-base">📌</span>
                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-700">Otros valores de interés clínico</h3>
                <span class="text-[11px] font-medium text-slate-400 hidden sm:inline">· Paneles complementarios dinámicos</span>
              </div>
              <span class="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                ${data.otros_valores.length} módulos disponibles
              </span>
            </div>
            <div class="grid ${gridColsClass} gap-3.5">
              ${data.otros_valores.map(sec => `
                <div class="bg-slate-50/90 border border-slate-200/90 rounded-xl p-3.5 flex flex-col justify-between hover:bg-slate-50 transition-colors">
                  <div>
                    <div class="flex items-center justify-between gap-1 mb-2.5">
                      <div class="flex items-center gap-1.5 font-bold text-slate-800 text-xs truncate" title="${sec.titulo}">
                        <span>${sec.icono || '🔹'}</span>
                        <span class="truncate">${sec.titulo}</span>
                      </div>
                      <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border ${sec.badge_class} shrink-0">
                        ${sec.badge_text}
                      </span>
                    </div>
                    <div class="space-y-1.5">
                      ${sec.items.map(item => `
                        <div class="flex items-baseline justify-between text-xs py-0.5 border-b border-slate-200/40 last:border-0">
                          <span class="text-slate-600 font-medium truncate mr-2" title="${item.label}${item.ref ? ' (' + item.ref + ')' : ''}">
                            ${item.label}
                          </span>
                          <span class="font-bold ${item.is_altered ? 'text-rose-600' : 'text-slate-900'} shrink-0 text-right">
                            ${item.val} <span class="text-[10px] font-normal text-slate-500">${item.unit || ''}</span>
                          </span>
                        </div>
                      `).join('')}
                    </div>
                  </div>
                  ${sec.nota ? `<div class="text-[10px] text-slate-400 mt-2.5 italic truncate" title="${sec.nota}">${sec.nota}</div>` : ''}
                </div>
              `).join('')}
            </div>
          </div>
        `;
      } else {
        otrosContainer.classList.add('hidden');
        otrosContainer.innerHTML = '';
      }
    }
  } catch (err) {
    console.error('Fallo al cargar summary:', err);
  }
}

// 3. Parser y Evaluación de Referencias Clínicas
function parseReferenceBoundsClient(refStr) {
  if (!refStr || typeof refStr !== 'string') return { low: null, high: null };
  const s = refStr.trim().replace(',', '.');
  if (['-', '', 'None', 'Sin referencia', 'No especificado'].includes(s)) {
    return { low: null, high: null };
  }

  // 1. Menor que / Inferior
  const mInf = s.match(/(?:<=?|<|menos de|inferior(?:\s+a)?|inf\.?|hasta)\s*(\d+(?:\.\d+)?)/i);
  if (mInf && !s.match(/\d+\s*[-a–—]\s*\d+/i)) {
    const val = parseFloat(mInf[1]);
    if (!isNaN(val)) return { low: null, high: val };
  }

  // 2. Mayor que / Superior
  const mSup = s.match(/(?:>=?|>|más de|mas de|superior(?:\s+a)?|sup\.?)\s*(\d+(?:\.\d+)?)/i);
  if (mSup && !s.match(/\d+\s*[-a–—]\s*\d+/i)) {
    const val = parseFloat(mSup[1]);
    if (!isNaN(val)) return { low: val, high: null };
  }

  // 3. Rango min - max (o 'min a max')
  const cleanS = s.replace(/[/\s]*(?:x?10[\^%3][36]?|[pµu]?l|g\/dl|g\/l|mg\/dl|ui\/ml|ng\/ml|%|ratio|segundos|mmol\/mol)\b.*$/i, '').trim();
  const mRange = cleanS.match(/(\d+(?:\.\d+)?)/g);
  if (mRange && mRange.length >= 2) {
    const low = parseFloat(mRange[0]);
    const high = parseFloat(mRange[1]);
    if (!isNaN(low) && !isNaN(high)) {
      return low <= high ? { low, high } : { low: high, high: low };
    }
  }

  return { low: null, high: null };
}

function evaluateStatusClient(valNum, refStr) {
  if (valNum === null || valNum === undefined || isNaN(valNum)) return 'Normal';
  const bounds = parseReferenceBoundsClient(refStr);
  if (bounds.low !== null && valNum < bounds.low - 1e-5) return 'Bajo';
  if (bounds.high !== null && valNum > bounds.high + 1e-5) return 'Alto';
  return 'Normal';
}

// Evaluación de zona límite / advertencia suave (Modelo Híbrido: 10% ancho relativo + consenso clínico)
function evaluateBorderlineClient(valNum, refStr, name = '') {
  if (valNum === null || valNum === undefined || isNaN(valNum)) return null;
  const cleanName = (name || '').trim().toLowerCase();

  // 1. Excepciones clínicas de consenso (Clinical Decision Limits)
  if (cleanName === 'hba1c' || cleanName.includes('hemoglobina glicada') || cleanName.includes('glicosilada')) {
    if (valNum >= 5.4 && valNum < 5.7) {
      return { isBorderline: true, reason: 'Límite preventivo prediabetes (5.4% - 5.6%)' };
    }
    return null;
  }
  if (cleanName.includes('ifcc')) {
    if (valNum >= 36.0 && valNum < 39.0) {
      return { isBorderline: true, reason: 'Límite preventivo prediabetes (36 - 38.9 mmol/mol)' };
    }
    return null;
  }
  if (cleanName === 'glucosa' || cleanName === 'glucosa basal' || cleanName.includes('glicemia')) {
    if (valNum >= 95.0) {
      return { isBorderline: true, reason: valNum > 100.0 ? 'Sobrepasa umbral ADA (>100 mg/dL)' : 'Próximo al límite ADA (95 - 100 mg/dL)' };
    }
    return null;
  }
  if (cleanName.includes('vitamina d') || cleanName.includes('25-oh')) {
    if (valNum >= 20.0 && valNum < 30.0) {
      return { isBorderline: true, reason: 'Insuficiencia / Límite de normalidad (20 - 29 ng/mL)' };
    }
    return null;
  }
  if (cleanName.includes('triglicéridos / hdl') || cleanName.includes('ratio tg/hdl') || cleanName === 'tg/hdl') {
    if (valNum >= 1.5 && valNum <= 2.0) {
      return { isBorderline: true, reason: 'Límite de riesgo cardiometabólico (1.5 - 2.0)' };
    }
    return null;
  }
  if (cleanName.includes('castelli ii') || cleanName.includes('ldl/hdl') || cleanName === 'cociente ldl/hdl') {
    if (valNum >= 3.0 && valNum <= 4.3) {
      return { isBorderline: true, reason: 'Límite intermedio riesgo vascular (3.0 - 4.3)' };
    }
    return null;
  }
  if (cleanName.includes('castelli i') || cleanName.includes('col/hdl') || cleanName === 'cociente col/hdl') {
    if (valNum >= 4.0 && valNum <= 5.0) {
      return { isBorderline: true, reason: 'Límite intermedio riesgo vascular (4.0 - 5.0)' };
    }
    return null;
  }

  // 2. Modelo matemático del 10% de ancho de banda relativo
  const bounds = parseReferenceBoundsClient(refStr);
  if (bounds.low === null && bounds.high === null) return null;

  // 2.1 Rango bilateral [L, H]
  if (bounds.low !== null && bounds.high !== null) {
    const w = bounds.high - bounds.low;
    if (w <= 0) return null;
    if (valNum < bounds.low - 1e-5 || valNum > bounds.high + 1e-5) return null; // Fuera de rango no es borderline

    const delta = 0.10 * w; // 10% del intervalo
    if (valNum >= bounds.high - delta) {
      return { isBorderline: true, reason: `Próximo al límite superior (${bounds.high})` };
    }
    if (valNum <= bounds.low + delta) {
      return { isBorderline: true, reason: `Próximo al límite inferior (${bounds.low})` };
    }
    return null;
  }

  // 2.2 Rango unilateral superior (< H o <= H)
  if (bounds.high !== null && bounds.low === null) {
    if (valNum > bounds.high + 1e-5) return null;
    const delta = 0.10 * bounds.high;
    if (valNum >= bounds.high - delta) {
      return { isBorderline: true, reason: `Próximo al límite superior (${bounds.high})` };
    }
    return null;
  }

  // 2.3 Rango unilateral inferior (> L o >= L)
  if (bounds.low !== null && bounds.high === null) {
    if (valNum < bounds.low - 1e-5) return null;
    const delta = 0.15 * bounds.low;
    if (valNum <= bounds.low + delta) {
      return { isBorderline: true, reason: `Próximo al límite inferior (${bounds.low})` };
    }
    return null;
  }

  return null;
}

function getCellFormatClient(name, v, ref = null) {
  if (v === null || v === undefined || v === '-') return { cls: 'text-slate-300', title: 'Sin dato' };
  let num = parseFloat(String(v).replace(',', '.'));
  if (isNaN(num)) return { cls: 'text-slate-800 font-medium', title: String(v) };
  if (!ref) return { cls: 'text-slate-800 font-medium', title: 'Normal' };
  const st = evaluateStatusClient(num, ref);
  if (st === 'Alto') return { cls: 'text-rose-800 bg-rose-50 border border-rose-300 font-bold px-1.5 py-0.5 rounded shadow-sm', title: `Alto (${ref})` };
  if (st === 'Bajo') return { cls: 'text-blue-800 bg-blue-50 border border-blue-300 font-bold px-1.5 py-0.5 rounded shadow-sm', title: `Bajo (${ref})` };
  const b = evaluateBorderlineClient(num, ref, name);
  if (b && b.isBorderline) return { cls: 'text-amber-900 bg-amber-50/80 border border-amber-200 font-medium px-1.5 py-0.5 rounded shadow-sm', title: `Límite (${b.reason})` };
  return { cls: 'text-slate-800 font-medium', title: 'Normal' };
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
        <th class="p-3 table-sticky-col-1">Parámetro</th>
        <th class="p-3 table-sticky-col-2 text-center">Unidad de medida</th>
        <th class="p-3 table-sticky-col-3 text-center" title="Rango de referencia oficial vigente según la analítica más reciente o consenso clínico">Referencia oficial</th>
    `;
    const infList = data.informes || [];
    data.dates.forEach((d, idx) => {
      let bgCls = 'bg-slate-700 hover:bg-slate-600';
      if (idx === data.dates.length - 1) bgCls = 'bg-emerald-800 hover:bg-emerald-700 font-bold';
      else if (idx === data.dates.length - 2) bgCls = 'bg-indigo-900 hover:bg-indigo-800 font-bold';
      else if (idx === data.dates.length - 3) bgCls = 'bg-blue-900 hover:bg-blue-800 font-bold';

      const inf = infList[idx];
      const refText = (inf && inf.referencia) ? inf.referencia : '-';
      if (inf && inf.id) {
        hHtml += `
          <th class="p-3 text-center min-w-[105px] whitespace-nowrap ${bgCls} cursor-pointer group transition-all select-none border-b-2 border-transparent hover:border-amber-400"
              onclick="openEditInformeModal(${inf.id})"
              title="Hacer clic para revisar o editar analítica del ${escapeHtml(inf.fecha)} (${escapeHtml(inf.laboratorio)}) - Ref: ${escapeHtml(refText)}">
            <div class="flex flex-col items-center justify-center">
              <div class="flex items-center justify-center gap-1.5">
                <span>${escapeHtml(d)}</span>
                <span class="text-[10px] opacity-70 group-hover:opacity-100 group-hover:scale-110 transition-transform" title="Editar este control">✏️</span>
              </div>
              <div class="text-[10px] font-normal text-slate-300 group-hover:text-amber-200 mt-0.5 tracking-tight" title="Referencia: ${escapeHtml(refText)}">Ref: ${escapeHtml(refText)}</div>
            </div>
          </th>`;
      } else {
        hHtml += `
          <th class="p-3 text-center min-w-[105px] whitespace-nowrap ${bgCls}">
            <div class="flex flex-col items-center justify-center">
              <span>${escapeHtml(d)}</span>
              <div class="text-[10px] font-normal text-slate-300 mt-0.5">Ref: -</div>
            </div>
          </th>`;
      }
    });
    hHtml += `
        <th class="p-3 text-center min-w-[140px] whitespace-nowrap bg-blue-800 font-extrabold text-white border-l-2 border-r-2 border-blue-400 shadow-inner">
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
            <span class="sticky left-4 inline-flex items-center gap-1.5 font-black">${escapeHtml(row.group)}</span>
          </td>
        `;
        tbody.appendChild(groupTr);
      }

      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-50 transition-colors';
      let cells = `
        <td class="p-3 font-bold table-sticky-col-1 text-slate-900">${escapeHtml(row.name)}</td>
        <td class="p-3 table-sticky-col-2 text-center text-slate-500 font-normal">${escapeHtml(row.unit || '-')}</td>
        <td class="p-3 table-sticky-col-3 text-center text-slate-600 font-medium text-[11px]" title="Rango oficial vigente: ${escapeHtml(row.ref)}">${escapeHtml(row.ref || '-')}</td>
      `;
      row.vals.forEach((v, idx) => {
        const cellObj = (row.cells && row.cells[idx]) ? row.cells[idx] : null;
        if (v === null || v === undefined) {
          cells += `<td class="p-3 text-center text-slate-300">-</td>`;
        } else {
          let cellCls = 'text-slate-800 font-medium';
          let title = `${row.name}: ${v} ${row.unit || ''}`;

          if (cellObj) {
            const cRef = cellObj.ref || row.ref || 'Sin referencia';
            let cStatus = cellObj.status || 'Normal';
            const numVal = parseFloat(String(v).replace(',', '.'));

            if ((!cStatus || cStatus === 'Normal') && !isNaN(numVal) && cRef) {
              const calcSt = evaluateStatusClient(numVal, cRef);
              if (calcSt !== 'Normal') {
                cStatus = calcSt;
              }
            }

            const isAltered = !!(cellObj.is_altered || cStatus === 'Alto' || cStatus === 'Bajo' || cStatus === 'Atencion' || cStatus === 'Alerta' || cStatus === 'Alérgeno');

            if (isAltered) {
              if (cStatus === 'Bajo') {
                cellCls = 'text-blue-800 bg-blue-50 border border-blue-300 font-bold px-1.5 py-0.5 rounded shadow-sm';
              } else if (cStatus === 'Alto' || cStatus === 'Atencion' || cStatus === 'Alerta' || cStatus === 'Alérgeno') {
                cellCls = 'text-rose-800 bg-rose-50 border border-rose-300 font-bold px-1.5 py-0.5 rounded shadow-sm';
              } else {
                if (!isNaN(numVal) && cRef) {
                  const bounds = parseReferenceBoundsClient(cRef);
                  if (bounds.low !== null && numVal < bounds.low) {
                    cellCls = 'text-blue-800 bg-blue-50 border border-blue-300 font-bold px-1.5 py-0.5 rounded shadow-sm';
                    cStatus = 'Bajo';
                  } else {
                    cellCls = 'text-rose-800 bg-rose-50 border border-rose-300 font-bold px-1.5 py-0.5 rounded shadow-sm';
                    cStatus = 'Alto';
                  }
                } else {
                  cellCls = 'text-rose-800 bg-rose-50 border border-rose-300 font-bold px-1.5 py-0.5 rounded shadow-sm';
                }
              }
            } else {
              const borderline = (!isNaN(numVal)) ? evaluateBorderlineClient(numVal, cRef, row.name) : null;
              if (borderline && borderline.isBorderline) {
                cellCls = 'text-amber-900 bg-amber-50/80 border border-amber-200 font-medium px-1.5 py-0.5 rounded shadow-sm';
                cStatus = `Límite (${borderline.reason})`;
              } else {
                cellCls = 'text-slate-800 font-medium';
              }
            }
            title = `${row.name}: ${v} ${row.unit || ''} | Rango del informe: ${cRef} (${cStatus}) | Ref. vigente: ${row.ref || '-'}`;
          } else {
            const num = parseFloat(String(v).replace(',', '.'));
            const st = (!isNaN(num) && row.ref) ? evaluateStatusClient(num, row.ref) : 'Normal';
            let stText = st;
            if (st === 'Bajo') {
              cellCls = 'text-blue-800 bg-blue-50 border border-blue-300 font-bold px-1.5 py-0.5 rounded shadow-sm';
            } else if (st === 'Alto') {
              cellCls = 'text-rose-800 bg-rose-50 border border-rose-300 font-bold px-1.5 py-0.5 rounded shadow-sm';
            } else {
              const borderline = (!isNaN(num) && row.ref) ? evaluateBorderlineClient(num, row.ref, row.name) : null;
              if (borderline && borderline.isBorderline) {
                cellCls = 'text-amber-900 bg-amber-50/80 border border-amber-200 font-medium px-1.5 py-0.5 rounded shadow-sm';
                stText = `Límite (${borderline.reason})`;
              } else {
                cellCls = 'text-slate-800 font-medium';
              }
            }
            title = `${row.name}: ${v} ${row.unit || ''} | Estado: ${stText} | Ref. vigente: ${row.ref || '-'}`;
          }

          cells += `<td class="p-3 text-center"><span class="${cellCls}" title="${escapeHtml(title)}">${v}</span></td>`;
        }
      });

      // Promedio 18 meses
      if (row.recentAvg && row.recentAvg !== '-') {
        const numAvg = parseFloat(String(row.recentAvg).replace(',', '.'));
        const avgSt = evaluateStatusClient(numAvg, row.ref);
        let avgCls = 'text-slate-800 text-xs font-bold';
        let avgTitle = `Promedio últimos 18 meses: ${row.recentAvg} ${row.unit || ''} (Ref. vigente: ${row.ref || '-'})`;
        if (avgSt === 'Alto') {
          avgCls = 'text-rose-800 bg-rose-50 border border-rose-300 font-bold px-1.5 py-0.5 rounded shadow-sm text-xs';
          avgTitle += ' - Alto';
        } else if (avgSt === 'Bajo') {
          avgCls = 'text-blue-800 bg-blue-50 border border-blue-300 font-bold px-1.5 py-0.5 rounded shadow-sm text-xs';
          avgTitle += ' - Bajo';
        } else {
          const avgBorder = evaluateBorderlineClient(numAvg, row.ref, row.name);
          if (avgBorder && avgBorder.isBorderline) {
            avgCls = 'text-amber-900 bg-amber-50/80 border border-amber-200 font-medium px-1.5 py-0.5 rounded shadow-sm text-xs';
            avgTitle += ` - Límite (${avgBorder.reason})`;
          }
        }
        cells += `
          <td class="p-3 text-center bg-blue-50/70 border-l border-r border-blue-200">
            <span class="${avgCls}" title="${escapeHtml(avgTitle)}">${row.recentAvg}</span>
          </td>
        `;
      } else {
        cells += `<td class="p-3 text-center bg-blue-50/40 border-l border-r border-blue-200 text-slate-300 font-normal">-</td>`;
      }

      tr.innerHTML = cells;
      tbody.appendChild(tr);
    });

    // Desplazar automáticamente al extremo derecho para ver el promedio y las analíticas más recientes
    setTimeout(() => {
      scrollTableToEnd();
    }, 60);
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
    list.innerHTML = '<div class="text-xs text-slate-400 py-4 text-center">Consultando y analizando registros de auditoría y rangos de referencia...</div>';
  }

  try {
    if (manualTrigger) {
      try {
        await fetch('/api/v1/ai/detectar', { method: 'POST' });
      } catch (e) {
        console.warn('Error al disparar escaneo de auditorías:', e);
      }
    }

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
    } else if (manualTrigger) {
      showAiAuditoriaAlert(`✓ Detección completada: ${items.length} criterio(s) de rangos identificados.`, 'success');
    }

    list.innerHTML = '';

    const pendientes = items.filter(a => {
      const st = a.estado || (a.aplicado_en_historico ? 'aplicado' : 'pendiente');
      return st === 'pendiente';
    });
    const revisados = items.filter(a => {
      const st = a.estado || (a.aplicado_en_historico ? 'aplicado' : 'pendiente');
      return st !== 'pendiente';
    });

    function createCardHtml(aud, isReviewed = false) {
      const safeAnalito = String(aud.analito).replace(/'/g, "\\'");
      const safeRangoNuevo = String(aud.rango_nuevo).replace(/'/g, "\\'");
      const estado = aud.estado || (aud.aplicado_en_historico ? 'aplicado' : 'pendiente');

      // Limpieza de referencias personales del paciente en la explicación clínica
      let expLimpia = aud.explicacion || 'El laboratorio ha actualizado el criterio de referencia.';
      if (expLimpia.includes('El valor de')) {
        expLimpia = expLimpia.split('El valor de')[0].trim();
      }

      let statusBadge = '';
      let actionButtons = '';

      if (!isReviewed) {
        // Tarjeta pendiente de revisión
        statusBadge = `
          <div class="flex items-center gap-1.5 px-2.5 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded-lg text-[11px] font-medium">
            <span>ℹ️</span>
            <span>Vigente en informes desde ${aud.fecha_analitica}</span>
          </div>
        `;
        actionButtons = `
          <div class="flex flex-wrap items-center gap-2">
            <button onclick="keepAuditHistorical(${aud.id}, '${safeAnalito}')" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-1.5 shadow-sm" title="Mantener los rangos de referencia originales de las analíticas pasadas">
              <span>🛡️</span> <span>Mantener rangos históricos</span> <span class="bg-indigo-700/90 text-indigo-100 text-[10px] font-medium px-1.5 py-0.2 rounded-full">(Recomendado)</span>
            </button>
            <button onclick="applyAuditCriteria(${aud.id}, '${safeAnalito}', '${safeRangoNuevo}')" class="px-3 py-1.5 bg-white hover:bg-slate-100 active:scale-95 text-slate-700 border border-slate-300 rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-1.5 shadow-xs" title="Homologar este nuevo rango a todas las analíticas anteriores">
              <span>⚡</span> <span>Aplicar a todo el historial</span>
            </button>
          </div>
        `;
      } else if (estado === 'mantenido') {
        // Tarjeta revisada con decisión: mantener histórico
        statusBadge = `
          <div class="flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 text-slate-700 border border-slate-200 rounded-lg text-[11px] font-medium">
            <span>🛡️</span>
            <span>Rangos históricos mantenidos (${aud.fecha_aplicacion || 'Revisado'})</span>
          </div>
        `;
        actionButtons = `
          <button onclick="applyAuditCriteria(${aud.id}, '${safeAnalito}', '${safeRangoNuevo}')" class="px-2.5 py-1.5 bg-white hover:bg-indigo-50 active:scale-95 text-indigo-700 border border-indigo-200 rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-1 shadow-xs" title="Cambiar decisión y homologar a todo el historial">
            <span>⚡</span> <span>Aplicar a todo el historial</span>
          </button>
        `;
      } else {
        // Tarjeta revisada con decisión: aplicado / homologado
        statusBadge = `
          <div class="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-[11px] font-medium">
            <span>✓</span>
            <span>Criterio homologado al historial (${aud.fecha_aplicacion || 'Activo'})</span>
          </div>
        `;
        actionButtons = `
          <div class="flex items-center gap-1.5">
            <button onclick="keepAuditHistorical(${aud.id}, '${safeAnalito}')" class="px-2.5 py-1.5 bg-white hover:bg-slate-100 active:scale-95 text-slate-600 border border-slate-200 rounded-lg text-[11px] font-medium transition-colors flex items-center gap-1 shadow-xs" title="Cambiar decisión y mantener rangos originales en analíticas pasadas">
              <span>🛡️</span> <span>Mantener histórico</span>
            </button>
            <button onclick="applyAuditCriteria(${aud.id}, '${safeAnalito}', '${safeRangoNuevo}')" class="px-2.5 py-1.5 bg-white hover:bg-slate-100 active:scale-95 text-slate-700 border border-slate-300 rounded-lg text-[11px] font-medium transition-colors flex items-center gap-1 shadow-xs">
              <span>🔄</span> <span>Reaplicar</span>
            </button>
          </div>
        `;
      }

      return `
        <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-2 hover:border-slate-300 transition-colors">
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

          <!-- Línea 3: Tarjeta informativa inferior con estado y botones de acción -->
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1.5 border-t border-slate-200/60">
            ${statusBadge}
            ${actionButtons}
          </div>
        </div>
      `;
    }

    // 1. Mostrar rangos pendientes en contenedor de altura limitada con scroll vertical
    if (pendientes.length > 0) {
      const pendingSection = document.createElement('div');
      pendingSection.className = 'space-y-2';

      const pendingHeader = document.createElement('div');
      pendingHeader.className = 'flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs px-1 text-slate-700 font-semibold';
      pendingHeader.innerHTML = `
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-purple-100 text-purple-700 text-[11px] font-bold">${pendientes.length}</span>
          <span>Cambios de rango pendientes de revisión</span>
        </div>
        ${pendientes.length > 1 ? `
          <div class="flex items-center gap-3 text-[11px]">
            <button onclick="keepAllAuditHistorical()" class="font-bold text-indigo-600 hover:text-indigo-800 hover:underline flex items-center gap-1" title="Mantener rangos históricos en todas las analíticas anteriores">
              <span>🛡️</span> <span>Mantener todos los históricos</span> <span class="text-[10px] font-medium text-indigo-500">(Recomendado)</span>
            </button>
            <span class="text-slate-300">|</span>
            <button onclick="applyAllAuditCriteria()" class="font-semibold text-slate-600 hover:text-slate-800 hover:underline flex items-center gap-1" title="Homologar los nuevos rangos a todas las analíticas pasadas">
              <span>⚡</span> <span>Aplicar y actualizar todo el historial</span>
            </button>
          </div>
        ` : ''}
      `;
      pendingSection.appendChild(pendingHeader);

      const scrollBox = document.createElement('div');
      scrollBox.className = 'max-h-[460px] overflow-y-auto pr-1.5 space-y-3 rounded-xl border border-slate-200/80 bg-slate-50/40 p-2.5';
      pendientes.forEach(aud => {
        const div = document.createElement('div');
        div.innerHTML = createCardHtml(aud, false);
        scrollBox.appendChild(div.firstElementChild);
      });
      pendingSection.appendChild(scrollBox);
      list.appendChild(pendingSection);
    } else {
      const emptyPending = document.createElement('div');
      emptyPending.className = 'p-3.5 bg-emerald-50/80 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2.5 font-medium';
      emptyPending.innerHTML = `
        <span class="text-emerald-600 text-base">✓</span>
        <span>Todos los cambios de rangos de laboratorio han sido revisados. No hay criterios pendientes de revisión.</span>
      `;
      list.appendChild(emptyPending);
    }

    // 2. Colapsar rangos ya revisados en un acordeón desplegable
    if (revisados.length > 0) {
      const numAplicados = revisados.filter(a => (a.estado || (a.aplicado_en_historico ? 'aplicado' : 'pendiente')) === 'aplicado').length;
      const numMantenidos = revisados.filter(a => (a.estado || (a.aplicado_en_historico ? 'aplicado' : 'pendiente')) === 'mantenido').length;

      const details = document.createElement('details');
      details.className = 'group bg-white border border-slate-200 rounded-xl overflow-hidden transition-all';
      
      const summary = document.createElement('summary');
      summary.className = 'p-3 cursor-pointer text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-50 flex items-center justify-between transition-colors select-none';
      summary.innerHTML = `
        <span class="flex items-center gap-2">
          <span class="text-slate-400 group-open:rotate-90 transition-transform inline-block text-[10px]">▶</span>
          <span>${revisados.length} criterio(s) de rangos de referencia ya revisado(s)</span>
        </span>
        <div class="flex items-center gap-1.5">
          ${numAplicados > 0 ? `<span class="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">${numAplicados} homologados</span>` : ''}
          ${numMantenidos > 0 ? `<span class="text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full font-bold">${numMantenidos} históricos mantenidos</span>` : ''}
        </div>
      `;
      details.appendChild(summary);

      const content = document.createElement('div');
      content.className = 'p-3 pt-0 border-t border-slate-100 mt-2';

      const reviewedScrollBox = document.createElement('div');
      reviewedScrollBox.className = 'max-h-[420px] overflow-y-auto pr-1.5 space-y-2.5 mt-2';
      revisados.forEach(aud => {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = createCardHtml(aud, true);
        reviewedScrollBox.appendChild(wrapper.firstElementChild);
      });
      content.appendChild(reviewedScrollBox);
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
    if (typeof loadTables === 'function') loadTables();
  } catch (err) {
    alert(`Error al aplicar criterio: ${err.message}`);
  }
}

// Opción 4: Mantener rangos de referencia históricos para un analito
async function keepAuditHistorical(auditId, analitoName) {
  const confirmMsg = `¿Deseas mantener los rangos de referencia históricos para ${analitoName}?\n\nEsta acción conservará los límites originales en las analíticas pasadas sin modificarlas y archivará la alerta como revisada.`;
  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch(`/api/v1/ai/mantener-historico/${auditId}`, { method: 'POST' });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Error al guardar decisión');
    }
    const data = await res.json();
    showAiAuditoriaAlert(`✓ ${data.message}`, 'success');
    await loadAiAuditorias(false);
    if (typeof loadSummary === 'function') loadSummary();
    if (typeof loadAllCategories === 'function') loadAllCategories();
    if (typeof loadTables === 'function') loadTables();
  } catch (err) {
    alert(`Error al mantener rangos históricos: ${err.message}`);
  }
}

// Opción 5: Mantener todos los criterios pendientes conservando históricos
async function keepAllAuditHistorical() {
  const confirmMsg = '¿Deseas mantener los rangos históricos para TODOS los criterios pendientes?\n\nEsto conservará los límites originales en todas las analíticas previas y archivará los cambios como revisados.';
  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch('/api/v1/ai/mantener-todos', { method: 'POST' });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Error al procesar criterios');
    }
    const data = await res.json();
    showAiAuditoriaAlert(`✓ ${data.message}`, 'success');
    await loadAiAuditorias(false);
    if (typeof loadSummary === 'function') loadSummary();
    if (typeof loadAllCategories === 'function') loadAllCategories();
    if (typeof loadTables === 'function') loadTables();
  } catch (err) {
    alert(`Error al mantener criterios históricos: ${err.message}`);
  }
}

// Opción 3: Aplicar todos los criterios al histórico
async function applyAllAuditCriteria() {
  const confirmMsg = '¿Deseas homologar TODOS los criterios de auditoría de rango a todo tu historial de analíticas pasadas?\n\nEsto actualizará los rangos de referencia de los analitos en todas las mediciones previas.';
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
    if (typeof loadTables === 'function') loadTables();
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

  const refEl = document.getElementById('previewReferenciaInput');
  if (refEl) refEl.value = data.referencia || '';

  const dictEl = document.getElementById('previewDictamenInput');
  if (dictEl) dictEl.value = data.dictamen_preliminar || '';

  const alertsContainer = document.getElementById('previewAlerts');
  alertsContainer.innerHTML = '';

  // Control de analítica duplicada
  const dupContainer = document.getElementById('previewDuplicateWarning');
  const dupTitle = document.getElementById('previewDuplicateTitle');
  const dupMsg = document.getElementById('previewDuplicateMessage');
  const mergeRadio = document.getElementById('duplicateActionMerge');
  const overwriteRadio = document.getElementById('duplicateActionOverwrite');

  if (data.es_duplicado && data.aviso_duplicado) {
    if (dupContainer) dupContainer.classList.remove('hidden');
    if (dupTitle) {
      dupTitle.innerHTML = data.tipo_duplicado === 'exacto_archivo'
        ? '📄 <strong>Documento PDF idéntico detectado en el historial</strong>'
        : '📅 <strong>Analítica con misma fecha registrada previamente</strong>';
    }
    if (dupMsg) {
      dupMsg.textContent = `${data.aviso_duplicado} Elige a continuación cómo deseas proceder:`;
    }
    if (mergeRadio) {
      mergeRadio.checked = true;
    } else if (overwriteRadio) {
      overwriteRadio.checked = true;
    }
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
  const referencia = document.getElementById('previewReferenciaInput')?.value.trim() || '';

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

  const mergeRadio = document.getElementById('duplicateActionMerge');
  const overwriteRadio = document.getElementById('duplicateActionOverwrite');
  let modoCoincidencia = 'fusionar';
  let sobrescribir = false;

  if (currentPreviewData.es_duplicado) {
    if (overwriteRadio && overwriteRadio.checked) {
      modoCoincidencia = 'reemplazar';
      sobrescribir = true;
    } else {
      modoCoincidencia = 'fusionar';
      sobrescribir = true;
    }
  }

  try {
    const payload = {
      temp_id: currentPreviewData.temp_id,
      fecha: fecha,
      laboratorio: laboratorio || 'Laboratorio Clínico',
      facultativo: facultativo || 'No especificado',
      referencia: referencia || null,
      mediciones: mediciones,
      dictamen_global: dictamen || 'Control favorable',
      sha256: currentPreviewData.sha256 || null,
      sobrescribir_existente: sobrescribir,
      informe_id_a_reemplazar: currentPreviewData.informe_existente_id || null,
      modo_coincidencia: modoCoincidencia
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
    const refInput = document.getElementById('editInformeReferencia');
    if (refInput) refInput.value = data.referencia || '';
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
  const referencia = document.getElementById('editInformeReferencia')?.value.trim() || '';
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
      referencia: referencia || null,
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
      btn.innerHTML = '<span>💾</span> Guardar datos';
    }
  }
}

function setAiStatus(message, tone = 'slate') {
  const status = document.getElementById('cfg-ai-status');
  if (!status) return;
  const colors = {
    slate: 'text-slate-600',
    success: 'text-emerald-600',
    error: 'text-rose-600',
    warning: 'text-amber-700'
  };
  status.textContent = message;
  status.className = `text-xs font-semibold ${colors[tone] || colors.slate}`;
}

function renderAiSlots(slots) {
  const container = document.getElementById('cfg-ai-slots');
  if (!container) return;
  const labels = ['Principal', 'Respaldo', 'Emergencia'];
  container.innerHTML = slots.map((slot, index) => {
    const number = index + 1;
    const managed = Boolean(slot.credential_managed_by_environment);
    return `
      <section class="cfg-ai-slot border border-violet-100 rounded-xl p-3 bg-violet-50/30" data-slot="${number}">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h4 class="font-bold text-slate-800 text-sm">Slot ${number}: ${labels[index]}</h4>
          <label class="flex items-center gap-2 text-xs text-slate-700 font-semibold"><input class="cfg-ai-enabled rounded border-slate-300 text-violet-600 focus:ring-violet-500" type="checkbox" ${slot.enabled ? 'checked' : ''}> Activar slot</label>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[minmax(8rem,0.75fr)_minmax(10rem,1fr)_minmax(12rem,1.6fr)_auto_auto_auto] gap-2.5 items-end text-xs">
          <div><label class="block font-semibold text-slate-700 mb-1">Proveedor</label><select class="cfg-ai-provider w-full border border-slate-300 rounded-xl p-2.5 bg-white focus:ring-2 focus:ring-violet-500 focus:outline-none"><option value="gemini" ${slot.provider === 'gemini' ? 'selected' : ''}>Gemini</option><option value="none" ${slot.provider === 'none' ? 'selected' : ''}>Sin IA</option></select></div>
          <div><label class="block font-semibold text-slate-700 mb-1">Modelo</label><input class="cfg-ai-model w-full border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-violet-500 focus:outline-none" type="text" maxlength="200" value="${escapeHtml(slot.model || '')}" placeholder="gemini-2.5-flash"></div>
          <div><label class="block font-semibold text-slate-700 mb-1">Token</label><input class="cfg-ai-key w-full border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-violet-500 focus:outline-none" type="password" autocomplete="new-password" placeholder="Clave o token" ${managed ? 'disabled' : ''}></div>
          <button onclick="saveAiCredential(${number})" ${managed ? 'disabled' : ''} class="px-3 py-2.5 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white font-bold rounded-xl text-xs whitespace-nowrap">Actualizar clave</button>
          <button onclick="deleteAiCredential(${number})" ${managed || !slot.credential_configured ? 'disabled' : ''} class="px-3 py-2.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 font-semibold border border-slate-300 rounded-xl text-xs whitespace-nowrap">Eliminar</button>
          <button onclick="testAiConnection(${number})" ${!slot.credential_configured || !slot.enabled || slot.provider !== 'gemini' ? 'disabled' : ''} class="px-3 py-2.5 bg-blue-50 hover:bg-blue-100 disabled:opacity-50 text-blue-700 border border-blue-200 font-semibold rounded-xl text-xs whitespace-nowrap">Comprobar</button>
        </div>
      </section>`;
  }).join('');
}

async function loadAiConfiguration() {
  try {
    const res = await fetch('/api/v1/settings/ai');
    if (!res.ok) throw new Error(await getErrorMessage(res, 'No se pudo consultar la configuración IA'));
    const ai = await res.json();
    const fallback = document.getElementById('cfg-ai-fallback');

    renderAiSlots(ai.slots || []);
    if (fallback) fallback.checked = Boolean(ai.fallback_enabled);
    const active = (ai.slots || []).filter(slot => slot.enabled && slot.credential_configured).length;
    setAiStatus(active ? `${active} slot(s) activo(s) con credencial` : 'No hay slots activos con credencial', active ? 'success' : 'warning');
  } catch (error) {
    setAiStatus(error.message, 'error');
  }
}

async function saveAiConfiguration() {
  const btn = document.getElementById('btn-save-ai-config');
  const payload = {
    slots: Array.from(document.querySelectorAll('.cfg-ai-slot')).map(slot => ({
      provider: slot.querySelector('.cfg-ai-provider').value,
      model: slot.querySelector('.cfg-ai-model').value.trim(),
      enabled: slot.querySelector('.cfg-ai-enabled').checked
    })),
    fallback_enabled: document.getElementById('cfg-ai-fallback').checked
  };
  try {
    if (btn) btn.disabled = true;
    const res = await fetch('/api/v1/settings/ai', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await getErrorMessage(res, 'No se pudieron guardar las preferencias'));
    const saved = await res.json();
    const resetSlots = payload.slots
      .map((slot, index) => slot.provider === 'gemini' && saved.slots?.[index]?.provider === 'none' ? index + 1 : null)
      .filter(Boolean);
    setAiStatus(
      resetSlots.length
        ? `Slot(s) ${resetSlots.join(', ')} guardado(s) como Sin IA: falta modelo o clave.`
        : 'Configuración guardada',
      resetSlots.length ? 'warning' : 'success'
    );
    await loadAiConfiguration();
    await loadSummary();
  } catch (error) {
    setAiStatus(error.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function saveAiCredential(slot) {
  const input = document.querySelector(`.cfg-ai-slot[data-slot="${slot}"] .cfg-ai-key`);
  const value = input ? input.value.trim() : '';
  if (!value) {
    setAiStatus('Introduce una clave antes de guardarla.', 'warning');
    return;
  }
  try {
    const res = await fetch(`/api/v1/settings/ai/credentials/${slot}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_key: value })
    });
    if (!res.ok) throw new Error(await getErrorMessage(res, 'No se pudo guardar la clave'));
    input.value = '';
    // No se recarga toda la configuración aquí: proveedor, modelo y activación
    // pueden estar todavía sin guardar en el formulario. Recargar los borraría
    // y haría que el usuario perdiese el slot justo después de guardar su clave.
    setAiStatus(`Credencial del slot ${slot} guardada. Ahora guarda la configuración de los tres slots.`, 'success');
  } catch (error) {
    setAiStatus(error.message, 'error');
  }
}

async function deleteAiCredential(slot) {
  if (!confirm(`¿Eliminar la credencial de Gemini del slot ${slot}?`)) return;
  try {
    const res = await fetch(`/api/v1/settings/ai/credentials/${slot}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await getErrorMessage(res, 'No se pudo eliminar la clave'));
    setAiStatus(`Credencial del slot ${slot} eliminada`, 'success');
    await loadAiConfiguration();
  } catch (error) {
    setAiStatus(error.message, 'error');
  }
}

async function testAiConnection(slot) {
  const btn = document.querySelector(`.cfg-ai-slot[data-slot="${slot}"] button:last-child`);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 25000);
  try {
    if (btn) btn.disabled = true;
    setAiStatus('Comprobando conexión…');
    const res = await fetch(`/api/v1/settings/ai/test/${slot}`, { method: 'POST', signal: controller.signal });
    if (!res.ok) throw new Error(await getErrorMessage(res, 'No se pudo comprobar Gemini'));
    setAiStatus(`Conexión del slot ${slot} verificada`, 'success');
  } catch (error) {
    const message = error.name === 'AbortError'
      ? 'La comprobación superó 25 segundos. Revisa la conectividad e inténtalo de nuevo.'
      : error.message;
    setAiStatus(message, 'error');
  } finally {
    window.clearTimeout(timeout);
    if (btn) btn.disabled = false;
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
      const refHtml = f.referencia
        ? `<div class="text-[11px] font-medium text-slate-500 font-mono mt-0.5">Ref: ${escapeHtml(f.referencia)}</div>`
        : `<div class="text-[11px] font-normal text-slate-400 font-mono mt-0.5">Ref: -</div>`;

      tr.innerHTML = `
        <td class="p-3">
          <div class="font-bold text-slate-900">${escapeHtml(f.fecha)}</div>
          ${refHtml}
        </td>
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

// ============================================================================
// Modal de Valoración Clínica Detallada
// ============================================================================
const clinicalModalMeta = {
  glucidico: {
    title: 'Metabolismo glucídico',
    badge: 'Prevención de diabetes'
  },
  lipidico: {
    title: 'Perfil lipídico',
    badge: 'Prevención cardiovascular'
  },
  renal: {
    title: 'Función renal',
    badge: 'Prevención enfermedad renal'
  },
  hepatico: {
    title: 'Función hepática',
    badge: 'Prevención hepática'
  },
  hemograma: {
    title: 'Hemograma / hierro',
    badge: 'Prevención general y anemia'
  },
  tiroideo: {
    title: 'Función tiroidea',
    badge: 'Prevención tiroidea'
  }
};

function openClinicalModal(key) {
  const modal = document.getElementById('evalClinicalModal');
  const tpl = document.getElementById(`eval-tpl-${key}`);
  if (!modal || !tpl) return;

  const titleEl = document.getElementById('evalModalTitle');
  const badgeEl = document.getElementById('evalModalBadge');
  const bodyEl = document.getElementById('evalModalBody');

  const meta = clinicalModalMeta[key];
  if (meta) {
    if (titleEl) titleEl.textContent = meta.title;
    if (badgeEl) badgeEl.textContent = meta.badge;
  }

  if (bodyEl) {
    bodyEl.innerHTML = '';
    bodyEl.appendChild(tpl.content.cloneNode(true));
  }

  // Prevenir scroll en el fondo mientras el modal está abierto
  document.body.classList.add('overflow-hidden');
  modal.showModal();
}

function closeClinicalModal() {
  const modal = document.getElementById('evalClinicalModal');
  if (modal && modal.open) {
    modal.close();
  }
}

// ============================================================================
// Modal de Información Completa de Tarjeta KPI
// ============================================================================
function openKpiModal(index) {
  if (!currentKpisData || currentKpisData.length === 0) return;
  if (index < 0) index = 0;
  if (index >= currentKpisData.length) index = currentKpisData.length - 1;
  activeKpiIndex = index;

  const kpi = currentKpisData[activeKpiIndex];
  if (!kpi) return;

  const modal = document.getElementById('kpiDetailModal');
  const titleEl = document.getElementById('kpiModalTitle');
  const bodyEl = document.getElementById('kpiModalBody');
  if (!modal || !bodyEl) return;

  if (titleEl) titleEl.textContent = kpi.title;

  const valColorClass = kpi.main_value_class ? kpi.main_value_class : (kpi.is_altered ? 'text-rose-600 font-semibold' : 'text-slate-900 font-semibold');

  let mainDotClass = 'bg-slate-300';
  let mainTrendTitle = 'Sin tendencia evaluable';
  if (kpi.main_clinical_trend === 'FAVORABLE') {
    mainDotClass = 'bg-emerald-500';
    mainTrendTitle = 'Tendencia favorable';
  } else if (kpi.main_clinical_trend === 'DESFAVORABLE') {
    mainDotClass = 'bg-rose-500';
    mainTrendTitle = 'Tendencia desfavorable';
  } else if (kpi.main_clinical_trend === 'ESTABLE') {
    mainDotClass = 'bg-blue-500';
    mainTrendTitle = 'Tendencia estable';
  }

  const mainTrendBadge = kpi.main_clinical_trend ? `
    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-white border border-slate-200 text-slate-700 shadow-2xs">
      <span class="w-2 h-2 rounded-full ${mainDotClass}"></span>
      ${mainTrendTitle}
    </span>
  ` : '';

  // Filas desglosadas con ancho cómodo sin recortes
  let rowsHtml = '';
  if (kpi.filas && kpi.filas.length > 0) {
    rowsHtml = `
      <div class="mt-3 pt-2.5 border-t border-slate-200">
        <div class="space-y-1.5">
          ${kpi.filas.map(f => {
            const isHistorical = f.es_historico;
            const varBadgeHtml = f.var_delta ? `
              <span class="inline-block px-2 py-0.5 rounded bg-slate-100 border border-slate-200/90 text-slate-900 font-mono font-bold text-xs shadow-2xs" title="Variación vs control anterior">
                ${f.var_delta}
              </span>
            ` : '';
            const isAltered = f.is_altered;
            const isUndetermined = f.val === '-' || !f.val;
            const valClass = isAltered 
              ? 'text-rose-600 font-bold' 
              : (isUndetermined ? 'text-slate-400 font-medium' : 'text-slate-900 font-semibold');
            
            let dotClass = 'bg-slate-300';
            let trendTitle = isUndetermined 
              ? 'No determinado' 
              : 'Sin tendencia';
            if (f.clinical_trend === 'FAVORABLE') {
              dotClass = 'bg-emerald-500';
              trendTitle = 'Favorable';
            } else if (f.clinical_trend === 'DESFAVORABLE') {
              dotClass = 'bg-rose-500';
              trendTitle = 'Desfavorable';
            } else if (f.clinical_trend === 'ESTABLE') {
              dotClass = 'bg-blue-500';
              trendTitle = 'Estable';
            }

            const tipoBadgeHtml = f.es_principal 
              ? `<span class="text-[10px] font-semibold text-blue-700 bg-blue-50 border border-blue-200/80 px-1.5 py-0.2 rounded shrink-0">Principal</span>`
              : (f.tipo_parametro === 'complementario'
                  ? `<span class="text-[10px] font-medium text-purple-700 bg-purple-50 border border-purple-200/80 px-1.5 py-0.2 rounded shrink-0">Complementario</span>`
                  : `<span class="text-[10px] font-medium text-slate-500 bg-slate-100 border border-slate-200/80 px-1.5 py-0.2 rounded shrink-0">Secundario</span>`);

            const rowContainerClass = isHistorical
              ? 'flex items-center justify-between gap-3 py-2 px-3 rounded-xl bg-amber-50/80 border border-amber-200/80 transition-colors'
              : 'flex items-center justify-between gap-3 py-2 px-3 rounded-xl bg-slate-50/70 border border-slate-100 hover:bg-slate-50 transition-colors';

            return `
              <div class="${rowContainerClass}">
                <div class="flex items-center gap-2 min-w-0 flex-1 flex-wrap sm:flex-nowrap pr-2">
                  <span class="w-1.5 h-1.5 rounded-full ${isAltered ? 'bg-rose-500' : 'bg-slate-400'} shrink-0"></span>
                  <span class="text-xs sm:text-sm font-semibold text-slate-800 leading-snug">${f.label}</span>
                  <div class="flex items-center gap-1.5 shrink-0">
                    ${tipoBadgeHtml}
                    ${isHistorical ? `<span class="text-[10px] font-semibold text-amber-800 bg-amber-100/90 px-1.5 py-0.2 rounded border border-amber-200 shrink-0">Histórico ${f.fecha_origen || ''}</span>` : ''}
                  </div>
                </div>
                <div class="flex items-center gap-2 sm:gap-3 shrink-0">
                  <span class="${valClass} text-xs sm:text-sm min-w-[55px] text-right">
                    ${f.val} <span class="text-[11px] font-normal text-slate-500">${f.unit || ''}</span>
                  </span>
                  <div class="min-w-[44px] flex justify-end">
                    ${varBadgeHtml}
                  </div>
                  <span class="inline-flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200/80 px-2.5 py-0.5 rounded shadow-2xs shrink-0" title="${trendTitle}">
                    <span class="w-2 h-2 rounded-full ${dotClass} inline-block"></span>
                    <span class="hidden sm:inline">${trendTitle}</span>
                  </span>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;
  } else {
    const subtitlesList = (kpi.subtitles && kpi.subtitles.length > 0)
      ? kpi.subtitles
      : [kpi.subtitle_1, kpi.subtitle_2, kpi.subtitle_3].filter(Boolean);

    rowsHtml = subtitlesList.length > 0
      ? `
        <div class="mt-3 pt-2.5 border-t border-slate-200">
          <h4 class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">Detalles complementarios</h4>
          <div class="space-y-1 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
            ${subtitlesList.map(sub => `
              <div class="text-xs sm:text-sm font-medium text-slate-700 flex items-start gap-2">
                <span class="text-blue-500 font-bold">•</span>
                <span>${sub}</span>
              </div>
            `).join('')}
          </div>
        </div>
      `
      : '';
  }

  const trendLabel = (kpi.trend_badge_text === 'SIN TENDENCIA' || kpi.trend_badge_text === 'Sin tendencia')
    ? 'Tendencia: Sin datos'
    : `Tendencia: ${kpi.trend_badge_text}`;

  const trendBadgeHtml = kpi.trend_badge_text ? `
    <span class="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${kpi.trend_badge_class || 'bg-slate-100 text-slate-600 border-slate-200'}">
      ${trendLabel}
    </span>
  ` : '';

  bodyEl.innerHTML = `
    <!-- Parámetro Principal Destacado -->
    <div class="bg-gradient-to-r from-slate-50 to-blue-50/40 border border-slate-200 rounded-2xl p-3.5 sm:p-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[11px] font-bold text-slate-500 uppercase tracking-wide block">
              ${kpi.main_label ? kpi.main_label : 'Parámetro Principal'}
            </span>
            <span class="text-[10px] font-bold text-blue-700 bg-blue-50 border border-blue-200/80 px-1.5 py-0.2 rounded shrink-0">Principal</span>
            ${kpi.main_is_historical ? `<span class="text-[10px] font-semibold text-amber-800 bg-amber-100/90 px-1.5 py-0.2 rounded border border-amber-200 shrink-0">Histórico ${kpi.main_fecha_origen || ''}</span>` : ''}
          </div>
          <div class="text-2xl sm:text-3xl ${valColorClass} mt-0.5 flex items-baseline flex-wrap">
            <span>${kpi.main_value}</span>
            <span class="text-sm font-semibold text-slate-500 ml-1.5">${kpi.unit}</span>
          </div>
        </div>
        <div class="flex items-center gap-2.5 flex-wrap">
          ${kpi.main_var_delta ? `
            <span class="inline-block px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200/90 text-slate-900 font-mono font-bold text-xs shadow-2xs" title="Variación vs control anterior">
              ${kpi.main_var_delta}
            </span>
          ` : ''}
          ${mainTrendBadge}
        </div>
      </div>
    </div>

    <!-- Filas secundarias y analitos -->
    ${rowsHtml}

    <!-- Dictamen y valoración de la tarjeta -->
    <div class="mt-3 pt-2.5 border-t border-slate-200 flex flex-wrap items-center justify-between gap-2.5">
      <div class="flex flex-wrap items-center gap-2">
        <div class="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold border ${kpi.badge_class}">
          ${kpi.badge_text}
        </div>
        ${trendBadgeHtml}
      </div>
    </div>
  `;

  document.body.classList.add('overflow-hidden');
  modal.showModal();
}

function closeKpiModal() {
  const modal = document.getElementById('kpiDetailModal');
  if (modal && modal.open) {
    modal.close();
  }
}

function openCreditsModal() {
  const modal = document.getElementById('creditsModal');
  if (!modal) return;
  document.body.classList.add('overflow-hidden');
  modal.showModal();
}

function closeCreditsModal() {
  const modal = document.getElementById('creditsModal');
  if (modal && modal.open) modal.close();
}

function openGoogleApiKeyModal() {
  const modal = document.getElementById('googleApiKeyModal');
  if (!modal) return;
  document.body.classList.add('overflow-hidden');
  modal.showModal();
}

function closeGoogleApiKeyModal() {
  const modal = document.getElementById('googleApiKeyModal');
  if (modal && modal.open) modal.close();
}

function navigateKpiModal(offset) {
  if (!currentKpisData || currentKpisData.length === 0) return;
  let newIndex = activeKpiIndex + offset;
  if (newIndex < 0) newIndex = currentKpisData.length - 1;
  if (newIndex >= currentKpisData.length) newIndex = 0;
  openKpiModal(newIndex);
}

// Configurar observadores y fallback de cierre para los diálogos modales
document.addEventListener('DOMContentLoaded', () => {
  const creditsModal = document.getElementById('creditsModal');
  if (creditsModal) {
    creditsModal.addEventListener('close', () => document.body.classList.remove('overflow-hidden'));
    creditsModal.addEventListener('cancel', () => document.body.classList.remove('overflow-hidden'));
  }

  const googleApiKeyModal = document.getElementById('googleApiKeyModal');
  if (googleApiKeyModal) {
    googleApiKeyModal.addEventListener('close', () => document.body.classList.remove('overflow-hidden'));
    googleApiKeyModal.addEventListener('cancel', () => document.body.classList.remove('overflow-hidden'));
  }

  const modal = document.getElementById('evalClinicalModal');
  if (modal) {
    modal.addEventListener('close', () => {
      document.body.classList.remove('overflow-hidden');
    });

    modal.addEventListener('cancel', () => {
      document.body.classList.remove('overflow-hidden');
    });

    // Fallback para navegadores sin soporte de closedby="any" (clic en el backdrop)
    if (!('closedBy' in HTMLDialogElement.prototype)) {
      modal.addEventListener('click', (event) => {
        if (event.target !== modal) return;
        const rect = modal.getBoundingClientRect();
        const isInside = (
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width
        );
        if (!isInside) {
          closeClinicalModal();
        }
      });
    }
  }

  // Modal de Detalle KPI
  const kpiModal = document.getElementById('kpiDetailModal');
  if (kpiModal) {
    kpiModal.addEventListener('close', () => {
      document.body.classList.remove('overflow-hidden');
    });

    kpiModal.addEventListener('cancel', () => {
      document.body.classList.remove('overflow-hidden');
    });

    if (!('closedBy' in HTMLDialogElement.prototype)) {
      kpiModal.addEventListener('click', (event) => {
        if (event.target !== kpiModal) return;
        const rect = kpiModal.getBoundingClientRect();
        const isInside = (
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width
        );
        if (!isInside) {
          closeKpiModal();
        }
      });
    }

    // Navegación con flechas del teclado cuando el modal está abierto
    window.addEventListener('keydown', (event) => {
      if (kpiModal.open) {
        if (event.key === 'ArrowLeft') {
          event.preventDefault();
          navigateKpiModal(-1);
        } else if (event.key === 'ArrowRight') {
          event.preventDefault();
          navigateKpiModal(1);
        }
      }
    });
  }
});


