import { describe, it, expect } from 'vitest';
import { formatCurrency, calculateEVMValues } from '../evmCalculations';

describe('formatCurrency', () => {
  it('renders the legacy "euro" key as EUR de-DE', () => {
    const out = formatCurrency(1000, 'euro');
    expect(out).toContain('€');
    expect(out).toMatch(/1\.000/);
  });

  it('renders the legacy "dollar" key as USD en-US', () => {
    const out = formatCurrency(1000, 'dollar');
    expect(out).toContain('$');
    expect(out).toMatch(/1,000/);
  });

  it('renders an ISO-4217 USD code as USD en-US', () => {
    const out = formatCurrency(1000, 'USD');
    expect(out).toContain('$');
    expect(out).toMatch(/1,000/);
  });

  it('renders an ISO-4217 GBP code as GBP en-GB', () => {
    const out = formatCurrency(1000, 'GBP');
    expect(out).toContain('£');
    expect(out).toMatch(/1,000/);
  });

  it('renders an ISO-4217 EUR code as EUR de-DE', () => {
    const out = formatCurrency(1000, 'EUR');
    expect(out).toContain('€');
    expect(out).toMatch(/1\.000/);
  });

  it('renders a lowercase ISO code (defensive uppercase)', () => {
    const out = formatCurrency(1000, 'usd');
    expect(out).toContain('$');
  });

  it('falls back to EUR when currency is undefined / empty string', () => {
    const fromUndefined = formatCurrency(1000);
    const fromEmpty = formatCurrency(1000, '');
    expect(fromUndefined).toContain('€');
    expect(fromEmpty).toContain('€');
  });

  it('respects decimals parameter', () => {
    const out = formatCurrency(1234.5, 'USD', 2);
    expect(out).toMatch(/1,234\.50/);
  });

  it('handles an unknown ISO code with a fallback locale (no throw)', () => {
    const out = formatCurrency(1000, 'NOK');
    expect(out).toMatch(/1[,.]000/);
    expect(out).toMatch(/NOK|kr/);
  });
});

describe('calculateEVMValues', () => {
  it('returns null SPI when percentPlanned is 0', () => {
    const r = calculateEVMValues(1000, 500, 0.5, 0);
    expect(r.spi).toBeNull();
  });

  it('returns null CPI when costToDate is 0', () => {
    const r = calculateEVMValues(1000, 0, 0.5, 0.5);
    expect(r.cpi).toBeNull();
  });

  it('computes EV, SPI, CPI for the happy path', () => {
    const r = calculateEVMValues(1000, 400, 0.5, 0.4);
    expect(r.ev).toBe(500);
    expect(r.spi).toBeCloseTo(1.25);
    expect(r.cpi).toBeCloseTo(1.25);
  });
});
