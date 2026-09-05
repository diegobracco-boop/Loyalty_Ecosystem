// Manual Loyalty Ecosystem · Despegar — Apps Script Backend
// Landing de solo lectura: sirve manual.html estático. Sin doPost, sin formularios.
function doGet() {
  return HtmlService.createHtmlOutputFromFile('manual')
    .setTitle('Manual · Loyalty Ecosystem · Despegar')
    .addMetaTag('viewport', 'width=device-width,initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
