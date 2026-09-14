// cac-elrocho: Frontend Application Logic

let currentPreviewData = null;
let chartsRendered = false;
let chartInstances = {};

// Inicialización al cargar la página
document.addEventListener('DOMContentLoaded', () => {
  loadSummary();
  loadTables();
  setupDragAndDrop();
});

// 1. Gestión de Pestañas
function setTab(tabId) {
  const tabs = ['eval', 'charts', 'table', 'panels', 'audit', 'ai', 'config'];
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

  if (tabId === 'charts' && !chartsRendered) {
    loadCharts();
  } else if (tabId === 'ai') {
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
    document.getElementById('paciente-nombre').textContent = 'Panel de Gestión Analítica: ' + (data.paciente.nombre || 'Paciente');
    document.getElementById('paciente-detalles').innerHTML = 'F. Nacimiento: <strong>' + (data.paciente.nacimiento || '-') + '</strong> • DNI: <strong>' + (data.paciente.dni || '-') + '</strong> • ' + (data.paciente.centro || '-');
    document.getElementById('dictamen-titulo').textContent = data.dictamen_global;
    document.getElementById('dictamen-sub').textContent = data.dictamen_subtitulo;

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
  if (name === 'Cociente Col/HDL') {
    if (num > 4.5) return { cls: 'text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded', title: 'Riesgo Alto (>4.5)' };
    if (num >= 3.5) return { cls: 'text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded', title: 'Bueno (Óptimo <3.5)' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo (<3.5)' };
  }
  if (name === 'Cociente LDL/HDL') {
    if (num > 3.0) return { cls: 'text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded', title: 'Riesgo Alto (>3.0)' };
    if (num >= 2.0) return { cls: 'text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded', title: 'Bueno (Óptimo <2.0)' };
    return { cls: 'text-emerald-700 font-semibold', title: 'Óptimo (<2.0)' };
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
    data.dates.forEach((d, idx) => {
      let bgCls = 'bg-slate-700';
      if (idx === data.dates.length - 1) bgCls = 'bg-emerald-800 font-bold';
      else if (idx === data.dates.length - 2) bgCls = 'bg-indigo-900 font-bold';
      else if (idx === data.dates.length - 3) bgCls = 'bg-blue-900 font-bold';
      hHtml += `<th class="p-3 text-center ${bgCls}">${d}</th>`;
    });
    hHtml += `
        <th class="p-3 text-center bg-blue-800 font-extrabold text-white border-l-2 border-r-2 border-blue-400 shadow-inner">
          Promedio Reciente<br><span class="text-[10px] font-normal text-blue-200">1.5 años (2025-26)</span>
        </th>
        <th class="p-3 text-center bg-slate-800 text-slate-400 font-normal">
          Promedio Total<br><span class="text-[10px] text-slate-500 font-light">Histórico (2022-26)</span>
        </th>
      </tr>
    `;
    thead.innerHTML = hHtml;

    // 4.2 Filas Bioquímica
    const tbody = document.getElementById('tableBodyRows');
    tbody.innerHTML = '';
    data.bioquimica.forEach(row => {
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

      // Promedio Reciente
      if (row.recentAvg && row.recentAvg !== '-') {
        let fmt = getCellFormatClient(row.name, row.recentAvg);
        cells += `
          <td class="p-3 text-center bg-blue-50/70 border-l border-r border-blue-200">
            <span class="${fmt.cls} text-xs font-bold" title="Promedio reciente (2025-26): ${fmt.title}">${row.recentAvg}</span>
          </td>
        `;
      } else {
        cells += `<td class="p-3 text-center bg-blue-50/40 border-l border-r border-blue-200 text-slate-300 font-normal">-</td>`;
      }

      // Promedio Total
      cells += `<td class="p-3 text-center text-[11px] text-slate-400 font-normal bg-slate-50/50">${row.avg}</td>`;
      tr.innerHTML = cells;
      tbody.appendChild(tr);
    });

    // 4.3 Paneles Especiales
    populateSimplePanel('hemogramaRows', data.hemograma);
    populateSimplePanel('coagRows', data.coagulacion);
    populateSimplePanel('enzimasRows', data.enzimas);

  } catch (err) {
    console.error('Fallo al cargar tablas:', err);
  }
}

function populateSimplePanel(tbodyId, rows) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  tbody.innerHTML = '';
  rows.forEach(r => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-50';
    let statusClass = 'text-emerald-700 font-semibold';
    if (r[11] && (r[11].includes('Bajo') || r[11].includes('Ligeramente'))) {
      statusClass = 'text-blue-900 bg-blue-100 border border-blue-300 font-bold px-2 py-0.5 rounded inline-block';
    } else if (r[11] && (r[11].includes('Atención') || r[11].includes('Límite'))) {
      statusClass = 'text-amber-800 bg-amber-100 border border-amber-300 font-bold px-2 py-0.5 rounded inline-block';
    }
    tr.innerHTML = `
      <td class="p-3 font-semibold">${r[0]}</td>
      <td class="p-3 text-slate-500">${r[1]}</td>
      <td class="p-3 text-center">${r[2]}</td>
      <td class="p-3 text-center">${r[3]}</td>
      <td class="p-3 text-center">${r[4]}</td>
      <td class="p-3 text-center">${r[5]}</td>
      <td class="p-3 text-center">${r[6]}</td>
      <td class="p-3 text-center bg-blue-50 font-bold">${r[7]}</td>
      <td class="p-3 text-center bg-slate-50">${r[8]}</td>
      <td class="p-3 text-center bg-emerald-50 font-bold text-emerald-900">${r[9]}</td>
      <td class="p-3 text-center text-slate-500">${r[10]}</td>
      <td class="p-3 text-center"><span class="${statusClass}">${r[11]}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// 5. Cargar Gráficos Evolutivos
async function loadCharts() {
  try {
    const res = await fetch('/api/v1/analiticas/charts');
    if (!res.ok) throw new Error('Error al cargar charts');
    const cData = await res.json();
    chartsRendered = true;

    // Destruir instancias previas si existen
    Object.values(chartInstances).forEach(c => c && c.destroy());

    // 1. Glucosa
    chartInstances['glucosa'] = new Chart(document.getElementById('chartGlucosa'), {
      type: 'line',
      data: cData.glucosa,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { min: 85, max: 115 } }
      }
    });

    // 2. Lípidos
    chartInstances['lipidos'] = new Chart(document.getElementById('chartLipidos'), {
      type: 'line',
      data: cData.lipidos,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 40, max: 200 } }
      }
    });

    // 3. Castelli
    chartInstances['castelli'] = new Chart(document.getElementById('chartCastelli'), {
      type: 'line',
      data: cData.castelli,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0.5, max: 4.8 } }
      }
    });

    // 4. Ratios Lipídicos
    chartInstances['ratios'] = new Chart(document.getElementById('chartRatiosLipidos'), {
      type: 'line',
      data: cData.ratios_tg,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0.1, max: 0.8 } }
      }
    });

    // 5. Renal
    chartInstances['renal'] = new Chart(document.getElementById('chartRenal'), {
      type: 'line',
      data: cData.renal,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { type: 'linear', position: 'left', min: 20, max: 60, title: { display: true, text: 'Urea (mg/dL)' } },
          y1: { type: 'linear', position: 'right', min: 0.6, max: 1.3, grid: { drawOnChartArea: false }, title: { display: true, text: 'Creatinina (mg/dL)' } }
        }
      }
    });

    // 6. Ácido Úrico
    chartInstances['urico'] = new Chart(document.getElementById('chartUrico'), {
      type: 'line',
      data: cData.urico,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { min: 4.5, max: 8.0 } }
      }
    });

    // 7. PSA
    chartInstances['psa'] = new Chart(document.getElementById('chartPSA'), {
      type: 'line',
      data: cData.psa,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { min: 0.3, max: 1.0, title: { display: true, text: 'PSA Total (ng/mL)' } },
          y1: { min: 20, max: 80, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Ratio (%)' } }
        }
      }
    });

    // 8. TSH
    chartInstances['tsh'] = new Chart(document.getElementById('chartTSH'), {
      type: 'line',
      data: cData.tsh,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0.8, max: 3.0 } }
      }
    });

  } catch (err) {
    console.error('Fallo al cargar gráficos:', err);
  }
}

// 6. Cargar Auditorías de Rango con IA
async function loadAiAuditorias() {
  const list = document.getElementById('ai-auditorias-list');
  list.innerHTML = '<div class="text-xs text-slate-400 py-4 text-center">Cargando registros de auditoría de rangos...</div>';

  try {
    const res = await fetch('/api/v1/ai/auditorias');
    if (!res.ok) throw new Error('Error al obtener auditorías');
    const items = await res.json();

    if (items.length === 0) {
      list.innerHTML = '<div class="text-xs text-slate-500 py-4">No se han registrado modificaciones de rangos de laboratorio todavía.</div>';
      return;
    }

    list.innerHTML = '';
    items.forEach(aud => {
      const card = document.createElement('div');
      card.className = 'p-4 bg-slate-50 border border-slate-200 rounded-2xl text-xs space-y-2';
      card.innerHTML = `
        <div class="flex justify-between items-center">
          <div class="font-bold text-slate-900 text-sm flex items-center gap-2">
            <span>🔬</span> ${aud.analito}
            <span class="px-2 py-0.5 bg-purple-100 text-purple-800 text-[10px] font-bold rounded-full">Auditoría IA</span>
          </div>
          <span class="text-slate-400 text-[11px]">${aud.fecha_analitica}</span>
        </div>
        <div class="grid grid-cols-2 gap-3 pt-1">
          <div class="bg-white p-2 rounded-xl border border-slate-200">
            <span class="text-slate-400 block text-[10px] uppercase">Rango Anterior:</span>
            <span class="font-semibold text-slate-700">${aud.rango_anterior || 'No especificado'}</span>
          </div>
          <div class="bg-purple-50 p-2 rounded-xl border border-purple-200">
            <span class="text-purple-600 block text-[10px] uppercase font-bold">Nuevo Rango Detectado:</span>
            <span class="font-bold text-purple-900">${aud.rango_nuevo}</span>
          </div>
        </div>
        <p class="text-slate-600 leading-relaxed pt-1 bg-white p-2.5 rounded-xl border border-slate-100">
          💡 <strong>Criterio Clínico IA:</strong> ${aud.explicacion}
        </p>
      `;
      list.appendChild(card);
    });
  } catch (err) {
    list.innerHTML = `<div class="text-xs text-rose-600 py-2">Error al consultar auditorías: ${err.message}</div>`;
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
      const err = await res.json();
      throw new Error(err.detail || 'Error al procesar el archivo');
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

  document.getElementById('previewLabDate').textContent = `${data.fecha} • ${data.laboratorio}`;
  document.getElementById('previewDictamen').textContent = data.dictamen_preliminar;
  document.getElementById('previewParamCount').textContent = data.total_parametros;

  const alertsContainer = document.getElementById('previewAlerts');
  alertsContainer.innerHTML = '';
  if (data.alertas_ia && data.alertas_ia.length > 0) {
    data.alertas_ia.forEach(al => {
      const div = document.createElement('div');
      div.className = 'flex items-center gap-1.5';
      div.innerHTML = `<span>⚠️</span> <span>${al}</span>`;
      alertsContainer.appendChild(div);
    });
  }

  const tbody = document.getElementById('previewTableBody');
  tbody.innerHTML = '';
  data.mediciones.forEach(m => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-50';
    tr.innerHTML = `
      <td class="p-2.5 font-semibold text-slate-800">${m.nombre}</td>
      <td class="p-2.5 text-center font-bold text-slate-900">${m.valor}</td>
      <td class="p-2.5 text-center text-slate-500">${m.unidad}</td>
      <td class="p-2.5 text-center text-slate-400 text-[11px]">${m.rango_referencia}</td>
      <td class="p-2.5 text-center">
        <span class="px-2 py-0.5 bg-emerald-50 text-emerald-700 font-semibold rounded text-[10px]">${m.estado_estimado || 'Normal'}</span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function confirmUploadData() {
  if (!currentPreviewData) return;

  const btn = document.getElementById('btnConfirmUpload');
  btn.disabled = true;
  btn.textContent = 'Guardando en base de datos...';

  try {
    const payload = {
      temp_id: currentPreviewData.temp_id,
      fecha: currentPreviewData.fecha,
      laboratorio: currentPreviewData.laboratorio,
      facultativo: currentPreviewData.facultativo,
      mediciones: currentPreviewData.mediciones,
      dictamen_global: currentPreviewData.dictamen_preliminar
    };

    const res = await fetch('/api/v1/upload/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error al confirmar analítica');
    }

    alert('¡Analítica incorporada con éxito al historial!');
    closeUploadModal();
    
    // Recargar componentes dinámicamente
    await loadSummary();
    await loadTables();
    chartsRendered = false;
    if (!document.getElementById('tab-charts').classList.contains('hidden')) {
      await loadCharts();
    }

  } catch (err) {
    alert(`Error al confirmar: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = '✅ Confirmar e Incorporar al Historial';
  }
}

// 8. Filtro en Vivo de la Tabla Bioquímica
function filterTable() {
  const query = document.getElementById('tableFilter').value.toLowerCase();
  const rows = document.getElementById('tableBodyRows').getElementsByTagName('tr');
  for (let i = 0; i < rows.length; i++) {
    const text = rows[i].textContent.toLowerCase();
    rows[i].style.display = text.includes(query) ? '' : 'none';
  }
}

// 9. Funciones del Panel de Gestión y Respaldo de Datos (Tab 7)
async function downloadBackup() {
  const pass = document.getElementById('exportPassphrase').value.trim();
  let url = '/api/v1/backup/export';
  if (pass) {
    url += '?passphrase=' + encodeURIComponent(pass);
  }

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Error al generar la copia de seguridad');

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition');
    let filename = pass ? 'cac-elrocho-backup.enc.json' : 'cac-elrocho-backup.json';
    if (disposition && disposition.includes('filename=')) {
      filename = disposition.split('filename=')[1].replace(/"/g, '');
    }

    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);

    alert(`¡Copia de seguridad descargada correctamente! (${filename})`);
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

async function uploadBackupFile() {
  const fileInput = document.getElementById('importFileInput');
  const passInput = document.getElementById('importPassphrase');

  if (!fileInput.files || fileInput.files.length === 0) {
    alert('Por favor, selecciona un archivo JSON de copia de seguridad.');
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
    chartsRendered = false;
    setTab('eval');
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

async function confirmResetDemo() {
  const confirm1 = confirm('¿Deseas restaurar los datos demostrativos sintéticos de prueba?');
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
    chartsRendered = false;
    setTab('eval');
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

