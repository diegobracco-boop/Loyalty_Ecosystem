// Manual Loyalty Ecosystem · Despegar — Apps Script Backend
// Landing de solo lectura: sirve manual.html estático. Sin doPost, sin formularios.
// ?page=presentacion sirve presentacion.html (presentación animada de 4 min del ecosistema).
function doGet(e) {
  if (e && e.parameter && e.parameter.page === 'presentacion') {
    return HtmlService.createHtmlOutputFromFile('presentacion')
      .setTitle('Presentación · Loyalty Ecosystem · Despegar')
      .addMetaTag('viewport', 'width=device-width,initial-scale=1')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  }
  return HtmlService.createHtmlOutputFromFile('manual')
    .setTitle('Manual · Loyalty Ecosystem · Despegar')
    .addMetaTag('viewport', 'width=device-width,initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
