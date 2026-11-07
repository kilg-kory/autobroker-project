import type { Quotation } from './types';

const NANO = 1_000_000_000;

/** 300.25 -> { units: 300, nano: 250000000 } — как в T-Invest API. */
export function toQuotation(value: number): Quotation {
  const scaled = Math.round(value * NANO);
  return { units: Math.trunc(scaled / NANO), nano: scaled % NANO };
}

/** Обратное преобразование для графиков. */
export function quotationToNumber(quotation: Quotation): number {
  return quotation.units + quotation.nano / NANO;
}
