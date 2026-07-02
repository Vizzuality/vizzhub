import { describe, it, expect } from 'vitest';
import { barColor, BAD_COLOR, GOOD_COLOR, METRIC_CONFIG, formatAxisEur } from '../chart';

describe('formatAxisEur', () => {
  it('abbreviates millions and thousands with a euro sign', () => {
    expect(formatAxisEur(2_400_000)).toBe('€2.4M');
    expect(formatAxisEur(-450_000)).toBe('€-450k');
    expect(formatAxisEur(-42)).toBe('€-42');
  });
});

describe('METRIC_CONFIG axis + value formatters carry the unit', () => {
  it('profit formats as euro on both axis and tooltip', () => {
    expect(METRIC_CONFIG.profit_eur.axisFormat(-450_000)).toBe('€-450k');
    expect(METRIC_CONFIG.profit_eur.valueFormat(1_234_567)).toBe('€1,234,567');
  });

  it('margin always carries the percent sign', () => {
    expect(METRIC_CONFIG.margin_pct.axisFormat(-45)).toBe('-45%');
    expect(METRIC_CONFIG.margin_pct.valueFormat(52.4)).toBe('52.4%');
  });

  it('delay carries a signed month unit', () => {
    expect(METRIC_CONFIG.delay_months.axisFormat(3)).toBe('+3mo');
    expect(METRIC_CONFIG.delay_months.valueFormat(-1)).toBe('-1mo');
  });
});

describe('barColor semantics', () => {
  it('paints profit/margin green when positive, red when negative', () => {
    expect(barColor(1000, 'profit_eur')).toBe(GOOD_COLOR);
    expect(barColor(-1000, 'profit_eur')).toBe(BAD_COLOR);
    expect(barColor(20, 'margin_pct')).toBe(GOOD_COLOR);
    expect(barColor(-20, 'margin_pct')).toBe(BAD_COLOR);
  });

  it('inverts for delay: late (positive) is bad, on-time/early is good', () => {
    expect(barColor(3, 'delay_months')).toBe(BAD_COLOR);
    expect(barColor(0, 'delay_months')).toBe(GOOD_COLOR);
    expect(barColor(-2, 'delay_months')).toBe(GOOD_COLOR);
  });
});
