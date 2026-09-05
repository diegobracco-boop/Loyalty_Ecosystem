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
  ssp:      'loyalty_ssp.json'
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

function getRawAcumCY()   { return _load(LOYALTY_FOLDER_ID,  FILES.acum_cy,  'acum_cy');  }
function getRawAcumLY()   { return _load(LOYALTY_FOLDER_ID,  FILES.acum_ly,  'acum_ly');  }
function getRawRedenCY()  { return _load(LOYALTY_FOLDER_ID,  FILES.reden_cy, 'reden_cy'); }
function getRawRedenLY()  { return _load(LOYALTY_FOLDER_ID,  FILES.reden_ly, 'reden_ly'); }
function getRawBreakage() { return _load(LOYALTY_FOLDER_ID,  FILES.breakage, 'breakage'); }
function getRawMiembros() { return _load(LOYALTY_FOLDER_ID,  FILES.miembros, 'miembros'); }
function getRawClub()     { return _load(LOYALTY_FOLDER_ID,  FILES.club,     'club');     }
function getRawIfood()    { return _load(LOYALTY_FOLDER_ID,  FILES.ifood,    'ifood');    }
function getRawDict()     { return _load(LOYALTY_FOLDER_ID,  FILES.dict, 'dict'); }
function getRawSsp()      { return _load(LOYALTY_FOLDER_ID,  FILES.ssp,  'ssp');  }

// P&L Contable: mismos JSON canónicos que consumen las landings B2B
// (Inputs_Planning_PnL). Se filtran a las líneas de loyalty server-side para
// mandar ~4k filas al cliente en vez de ~70k.
function getLoyBaseline() { return _loyPnl('baseline_actuals+projections.json', 'loy_baseline'); }
function getLoyBudget()   { return _loyPnl('budget.json',   'loy_budget');   }
function getLoyForecast() { return _loyPnl('forecast.json', 'loy_forecast'); }

// ---- Internal helpers ----

function _loyPnl(filename, baseKey) {
  var folder = DriveApp.getFolderById(BASELINE_FOLDER_ID);
  var files  = folder.getFilesByName(filename);
  if (!files.hasNext()) throw new Error('No encontrado en Drive: ' + filename);
  var file   = files.next();
  var key    = baseKey + '_' + file.getLastUpdated().getTime();
  var cached = cacheGet_(key);
  if (cached) return JSON.parse(cached);
  var raw = JSON.parse(file.getBlob().getDataAsString());
  // Acople cross-repo: estas columnas las define Inputs_Planning_PnL (repo B2B).
  // Si renombran alguna, sin este guard el P&L Contable quedaría vacío sin error.
  ['P&L N1', 'Pais', 'Fecha', 'Monto USD'].forEach(function(c) {
    if (raw.cols.indexOf(c) === -1) throw new Error(
      'Esquema P&L cambió en ' + filename + ': falta la columna "' + c + '". ' +
      'Revisar los nombres de columna en Inputs_Planning_PnL (repo B2B_Ecosystem).');
  });
  var n1i = raw.cols.indexOf('P&L N1');
  var rows = [];
  for (var i = 0; i < raw.rows.length; i++) {
    var v = raw.rows[i][n1i];
    if (v && String(v).toLowerCase().indexOf('loyalty') !== -1) rows.push(raw.rows[i]);
  }
  if (rows.length === 0) throw new Error(
    'Cero filas "loyalty" en ' + filename + '. El filtro dejó de matchear — ' +
    'probablemente cambió el string del LOB en Inputs_Planning_PnL.');
  var result = { meta: raw.meta, cols: raw.cols, rows: rows };
  cachePut_(key, JSON.stringify(result));
  return result;
}

function _load(folderId, filename, baseKey) {
  var folder = DriveApp.getFolderById(folderId);
  var files  = folder.getFilesByName(filename);
  if (!files.hasNext()) throw new Error('No encontrado en Drive: ' + filename);
  var file   = files.next();
  var key    = baseKey + '_' + file.getLastUpdated().getTime();
  var cached = cacheGet_(key);
  if (cached) return JSON.parse(cached);
  var raw = file.getBlob().getDataAsString();
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
