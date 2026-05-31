export interface EVMCalculatedValues {
  ev: number;
  spi: number | null;
  cpi: number | null;
  hasData: boolean;
}

export function calculateEVMValues(
  budgetTotal: number,
  costToDate: number,
  percentCompleted: number,
  percentPlanned: number,
): EVMCalculatedValues {
  const ev = budgetTotal * percentCompleted;
  const spi = percentPlanned > 0 ? percentCompleted / percentPlanned : null;
  const cpi = costToDate > 0 ? ev / costToDate : null;
  return { ev, spi, cpi, hasData: budgetTotal > 0 };
}

const LEGACY_CURRENCY_MAP: Record<string, { code: string; locale: string }> = {
  euro: { code: 'EUR', locale: 'de-DE' },
  dollar: { code: 'USD', locale: 'en-US' },
};

const ISO_LOCALE_MAP: Record<string, string> = {
  EUR: 'de-DE',
  USD: 'en-US',
  GBP: 'en-GB',
  CHF: 'de-CH',
  JPY: 'ja-JP',
  AUD: 'en-AU',
  CAD: 'en-CA',
};

export function localeForCurrency(currency = 'euro'): { locale: string; code: string } {
  const legacy = LEGACY_CURRENCY_MAP[currency];
  const code = legacy ? legacy.code : (currency || 'EUR').toUpperCase();
  const locale = legacy ? legacy.locale : (ISO_LOCALE_MAP[code] ?? 'en-US');
  return { locale, code };
}

export function formatCurrency(value: number, currency = 'euro', decimals = 0): string {
  const { locale, code } = localeForCurrency(currency);
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: code,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatAmount(value: number, currency = 'euro', decimals = 2): string {
  const { locale } = localeForCurrency(currency);
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function getPerformanceColor(value: number): string {
  if (value >= 1) return 'text-score-green';
  if (value >= 0.9) return 'text-score-yellow';
  return 'text-score-red';
}

export function getPerformanceDotClass(value: number): string {
  if (value >= 1) return 'bg-aux-neon-grass';
  if (value >= 0.9) return 'bg-aux-yellow';
  return 'bg-aux-red';
}

export function getPerformanceLabel(value: number, metric: 'spi' | 'cpi'): string {
  if (metric === 'spi') {
    if (value > 1) return 'Ahead of schedule';
    if (value === 1) return 'On schedule';
    return 'Behind schedule';
  }
  if (value > 1) return 'Under budget';
  if (value === 1) return 'On budget';
  return 'Over budget';
}
