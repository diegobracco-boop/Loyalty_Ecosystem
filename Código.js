// ============================================================
// Código.js — Loyalty Dashboard  v2
// GAS serves raw JSON only. All compute runs in the browser.
// ============================================================

var LOYALTY_FOLDER_ID  = '1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb';
var BASELINE_FOLDER_ID = '1XqQPL_rlS0NRIPUnPfj5nALBTn7kAOQV';

// Los nombres de acum/reden llevan el año en el nombre — se derivan de la fecha
// para no romper el 1-ene (el pipeline usa date.today().year).
var _CY = new Date().getFullYear();
var _LY = _CY - 1;
var FILES = {
  acum_cy:  'loyalty_acumulaciones_' + _CY + '.json',
  acum_ly:  'loyalty_acumulaciones_' + _LY + '.json',
  reden_cy: 'loyalty_redenciones_' + _CY + '.json',
  reden_ly: 'loyalty_redenciones_' + _LY + '.json',
  breakage: 'loyalty_breakage.json',
  miembros: 'loyalty_miembros.json',
  club:     'loyalty_club_despegar.json',
  ifood:    'loyalty_ifood_enroll.json',
  dict:     'loyalty_dict.json',
  ssp:      'loyalty_ssp.json',
  ratio_acum: 'loyalty_ratio_acumulacion.json',
  ratio_acum_tier: 'loyalty_ratio_acum_tier.json',
  acum_tier:  'loyalty_acum_tier.json',
  penet:      'loyalty_penetracion_gb.json',
  acum_channel: 'loyalty_acum_channel.json',
  stock_ifood: 'loyalty_stock_ifood.json',
  proy:       'loyalty_proyecciones.json',
  inputs_real: 'loyalty_inputs_real.json'
};

var CACHE_TTL   = 21600;  // 6 h
var CACHE_CHUNK = 90000;

// ---- Entry point ----

function doGet() {
  return HtmlService.createHtmlOutputFromFile('dashboard')
    .setTitle('Loyalty Dashboard — Despegar')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// ---- Public API ----

function getRawAcumCY()         { return _load(LOYALTY_FOLDER_ID,  FILES.acum_cy,    'acum_cy');    }
function getRawAcumLY()         { return _load(LOYALTY_FOLDER_ID,  FILES.acum_ly,    'acum_ly');    }
function getRawRedenCY()        { return _load(LOYALTY_FOLDER_ID,  FILES.reden_cy,   'reden_cy');   }
function getRawRedenLY()        { return _load(LOYALTY_FOLDER_ID,  FILES.reden_ly,   'reden_ly');   }
function getRawBreakage()       { return _load(LOYALTY_FOLDER_ID,  FILES.breakage,   'breakage');   }
function getRawMiembros()       { return _load(LOYALTY_FOLDER_ID,  FILES.miembros,   'miembros');   }
function getRawClub()           { return _load(LOYALTY_FOLDER_ID,  FILES.club,       'club');       }
function getRawIfood()          { return _load(LOYALTY_FOLDER_ID,  FILES.ifood,      'ifood');      }
function getRawDict()           { return _load(LOYALTY_FOLDER_ID,  FILES.dict,       'dict');       }
function getRawSsp()            { return _load(LOYALTY_FOLDER_ID,  FILES.ssp,        'ssp');        }
function getRawRatioAcum()      { return _load(LOYALTY_FOLDER_ID,  FILES.ratio_acum, 'ratio_acum'); }
function getRawRatioAcumTier()  { return _load(LOYALTY_FOLDER_ID,  FILES.ratio_acum_tier, 'ratio_acum_tier'); }
function getRawAcumTier()       { return _load(LOYALTY_FOLDER_ID,  FILES.acum_tier,  'acum_tier');  }
function getRawPenetracionGb()  { return _load(LOYALTY_FOLDER_ID,  FILES.penet,      'penet');      }
function getRawAcumChannel()    { return _load(LOYALTY_FOLDER_ID,  FILES.acum_channel, 'acum_channel'); }
function getRawStockIfood()     { return _load(LOYALTY_FOLDER_ID,  FILES.stock_ifood, 'stock_ifood'); }
function getRawInputsReal()     { return _load(LOYALTY_FOLDER_ID,  FILES.inputs_real, 'inputs_real'); }
function getRawProyecciones()   { return _load(LOYALTY_FOLDER_ID,  FILES.proy,       'proy');       }

// Carga TODO en una sola ejecución server-side (secuencial), en vez de que el
// cliente dispare ~18 google.script.run en paralelo — eso es lo que agotaba
// la cuota de ráfaga de Drive (18 ejecuciones concurrentes, cada una con sus
// propias llamadas a DriveApp, ya no era cuestión de reintentar: todas
// competían por la misma ventana de cuota a la vez). Con una sola ejecución
// las llamadas a Drive son secuenciales, no concurrentes, y _withDriveRetry_
// alcanza para absorber cualquier hiccup transitorio real.
function getAllRaw() {
  var out = {};
  var getters = {
    acum_cy: getRawAcumCY, acum_ly: getRawAcumLY,
    reden_cy: getRawRedenCY, reden_ly: getRawRedenLY,
    breakage: getRawBreakage, miembros: getRawMiembros,
    club: getRawClub, ifood: getRawIfood,
    dict: getRawDict, ssp: getRawSsp,
    ratio_acum: getRawRatioAcum, ratio_acum_tier: getRawRatioAcumTier, acum_tier: getRawAcumTier,
    penet: getRawPenetracionGb, acum_channel: getRawAcumChannel,
    stock_ifood: getRawStockIfood, proy: getRawProyecciones, inputs_real: getRawInputsReal,
    baseline: getLoyBaseline, budget: getLoyBudget, forecast: getLoyForecast,
    runrate: getLoyRunrate, pnl_prev: getLoyPnlPrev
  };
  Object.keys(getters).forEach(function(k) {
    try { out[k] = { ok: true, data: getters[k]() }; }
    catch (e) { out[k] = { ok: false, error: String(e && e.message || e) }; }
  });
  return out;
}

// P&L Contable (12-oct): vista de Loyalty SOLO MARCA DESPEGAR —
// loyalty_pnl_<escenario>.json en el folder de Loyalty, armados por
// inputs_contables_loyalty.py desde las planas de Inputs_Planning_PnL (ya vienen
// recortados a líneas loyalty + Drivers B2C). Los canónicos de B2B suman todas las
// marcas (Best Day = 44% del GB B2C de MX). Si el JSON de Loyalty no está, cae al
// canónico de B2B filtrado por _loyPnl (todas las marcas) — degradado, no roto.
function _loyPnlDespegar(esc, canonical) {
  try { return _load(LOYALTY_FOLDER_ID, 'loyalty_pnl_' + esc + '.json', 'loy_pnl_' + esc); }
  catch (e) { return _loyPnl(canonical, 'loy_' + esc + '_v2'); }
}
function getLoyBaseline() { return _loyPnlDespegar('baseline', 'baseline_actuals+projections.json'); }
function getLoyBudget()   { return _loyPnlDespegar('budget',   'budget.json'); }
function getLoyForecast() { return _loyPnlDespegar('forecast', 'forecast.json'); }
// Run Rate: runrate.json de Inputs_Planning_PnL (12 meses del FY), misma vista Despegar.
// loyalty_runrate.json (armado a mano el 22-sep, solo LE NA) queda en Drive sin uso.
function getLoyRunrate()  { return _loyPnlDespegar('runrate',  'runrate.json'); }
// FY anterior (actuals, solo Despegar): para la evolución de "Reglas One Revenue".
function getLoyPnlPrev()  { return _load(LOYALTY_FOLDER_ID, 'loyalty_pnl_actuals_prev.json', 'loy_pnl_prev'); }

// ---- Internal helpers ----

// El dashboard dispara ~18 llamadas google.script.run simultáneas al cargar,
// cada una con su propio DriveApp.getFolderById/getFilesByName — bajo carga
// concurrente eso puede pasar la cuota de Drive por usuario/100s y tira
// "Error de servicio: Drive" (transitorio, no un problema de datos). Retry
// con backoff exponencial absorbe eso.
function _withDriveRetry_(fn) {
  var lastErr;
  for (var attempt = 0; attempt < 5; attempt++) {
    try {
      return fn();
    } catch (e) {
      lastErr = e;
      if (String(e).indexOf('Drive') === -1) throw e;
      Utilities.sleep(300 * Math.pow(2, attempt) + Math.floor(Math.random() * 200));
    }
  }
  throw lastErr;
}

function _loyPnl(filename, baseKey) {
  var folder = _withDriveRetry_(function() { return DriveApp.getFolderById(BASELINE_FOLDER_ID); });
  var files  = _withDriveRetry_(function() { return folder.getFilesByName(filename); });
  if (!files.hasNext()) throw new Error('No encontrado en Drive: ' + filename);
  var file   = files.next();
  var key    = baseKey + '_' + _withDriveRetry_(function() { return file.getLastUpdated().getTime(); });
  var cached = cacheGet_(key);
  if (cached) return JSON.parse(cached);
  var raw = JSON.parse(_withDriveRetry_(function() { return file.getBlob().getDataAsString(); }));
  // Acople cross-repo: estas columnas las define Inputs_Planning_PnL (repo B2B).
  // Si renombran alguna, sin este guard el P&L Contable quedaría vacío sin error.
  ['P&L N1', 'Pais', 'Fecha', 'Monto USD'].forEach(function(c) {
    if (raw.cols.indexOf(c) === -1) throw new Error(
      'Esquema P&L cambió en ' + filename + ': falta la columna "' + c + '". ' +
      'Revisar los nombres de columna en Inputs_Planning_PnL (repo B2B_Ecosystem).');
  });
  var n1i = raw.cols.indexOf('P&L N1');
  var lobi = raw.cols.indexOf('LoB');
  // Drivers B2C (GB, Orders, Up Front + Fees) — solo LoB='b2c', mismo alcance
  // que Loyalty (todas sus líneas ya son B2C). Los muestra el bloque "Drivers
  // B2C" del P&L Contable (PNL_DRIVERS en dashboard.html), que NO los suma al
  // TOTAL LOYALTY. El resto de filtros (Marca, exclusiones de negocio) ya vienen
  // aplicados upstream en Inputs_Planning_PnL.
  var GB_ORDERS_N1 = ['gross bookings domestic', 'gross bookings international',
                       'orders domestic', 'orders international',
                       'up front incentives', 'fees', 'commercial discounts'];
  var rows = [], loyCount = 0;
  for (var i = 0; i < raw.rows.length; i++) {
    var v = raw.rows[i][n1i];
    var vLower = v ? String(v).toLowerCase() : '';
    var isLoy = vLower.indexOf('loyalty') !== -1;
    if (isLoy) loyCount++;
    var isGbOrdersB2c = GB_ORDERS_N1.indexOf(vLower) !== -1
      && lobi !== -1 && String(raw.rows[i][lobi]).toLowerCase() === 'b2c';
    if (isLoy || isGbOrdersB2c) rows.push(raw.rows[i]);
  }
  if (loyCount === 0) throw new Error(
    'Cero filas "loyalty" en ' + filename + '. El filtro dejó de matchear — ' +
    'probablemente cambió el string del LOB en Inputs_Planning_PnL.');
  var result = { meta: raw.meta, cols: raw.cols, rows: rows };
  cachePut_(key, JSON.stringify(result));
  return result;
}

function _load(folderId, filename, baseKey) {
  var folder = _withDriveRetry_(function() { return DriveApp.getFolderById(folderId); });
  var files  = _withDriveRetry_(function() { return folder.getFilesByName(filename); });
  if (!files.hasNext()) throw new Error('No encontrado en Drive: ' + filename);
  var file   = files.next();
  var key    = baseKey + '_' + _withDriveRetry_(function() { return file.getLastUpdated().getTime(); });
  var cached = cacheGet_(key);
  if (cached) return JSON.parse(cached);
  var raw = _withDriveRetry_(function() { return file.getBlob().getDataAsString(); });
  cachePut_(key, raw);
  return JSON.parse(raw);
}

function cachePut_(key, raw) {
  try {
    var cache = CacheService.getScriptCache();
    var n = Math.ceil(raw.length / CACHE_CHUNK);
    cache.put(key + '_n', String(n), CACHE_TTL);
    var BATCH = 90;
    for (var s = 0; s < n; s += BATCH) {
      var obj = {}, e = Math.min(s + BATCH, n);
      for (var i = s; i < e; i++)
        obj[key + '_' + i] = raw.substring(i * CACHE_CHUNK, (i + 1) * CACHE_CHUNK);
      cache.putAll(obj, CACHE_TTL);
    }
  } catch(ex) {}
}

function cacheGet_(key) {
  try {
    var cache = CacheService.getScriptCache();
    var nStr = cache.get(key + '_n');
    if (!nStr) return null;
    var n = parseInt(nStr), parts = [];
    for (var i = 0; i < n; i++) {
      var c = cache.get(key + '_' + i);
      if (!c) return null;
      parts.push(c);
    }
    return parts.join('');
  } catch(ex) { return null; }
}
