// Find the row with the given label in column A
function findRowByLabel_(sheet, label) {
  const last = sheet.getLastRow();
  const colA = sheet.getRange(1, 1, last, 1).getValues();
  for (let i = 0; i < colA.length; i++) {
    if (String(colA[i][0]).trim() === label) return i + 1; // 1-based row
  }
  return 0;
}

// Write value in col B of the row with `label` (must exist in template)
function setMetric_(sheet, label, value, format) {
  const row = findRowByLabel_(sheet, label);
  if (row === 0) throw new Error(`Label not found in sheet: ${label}`);
  const cell = sheet.getRange(row, 2);
  if (format) cell.setNumberFormat(format);
  cell.setValue(value);
}