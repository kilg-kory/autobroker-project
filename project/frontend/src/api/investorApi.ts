import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type {
  AnalysisResponse,
  GetAllCandlesArgs,
  GetAnalysisArgs,
  GetPerformanceArgs,
  HistoricCandle,
  PerformanceResponse,
} from './types';

/**
 * REST-клиент backend: GET /api/candles.
 *
 * Цепочка: frontend -> backend (FastAPI, TTL-кэш 5 с) -> investor (PostgreSQL;
 * в T-Invest ходит только его фоновый цикл) -> обратно. Префикс /api снимает прокси Vite (vite.config.ts),
 * поэтому в dev запросы идут на тот же origin и CORS не нужен.
 */
export const investorApi = createApi({
  reducerPath: 'investorApi',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  tagTypes: ['Candles', 'Analysis', 'Performance'],
  endpoints: (builder) => ({
    getAllCandles: builder.query<HistoricCandle[], GetAllCandlesArgs>({
      query: ({ instrumentId, interval = 'CANDLE_INTERVAL_HOUR', days = 30 }) => ({
        url: '/candles',
        params: {
          instrument_id: instrumentId,
          interval,
          days,
        },
      }),
      providesTags: ['Candles'],
    }),
    getAnalysis: builder.query<AnalysisResponse, GetAnalysisArgs>({
      query: ({ instrumentId, interval = 'CANDLE_INTERVAL_HOUR', days = 30 }) => ({
        url: '/analysis',
        params: {
          instrument_id: instrumentId,
          interval,
          days,
        },
      }),
      providesTags: ['Analysis'],
    }),
    getPerformance: builder.query<PerformanceResponse, GetPerformanceArgs>({
      query: ({ instrumentId, interval = 'CANDLE_INTERVAL_HOUR', days = 30, patterns }) => ({
        url: '/performance',
        params: {
          instrument_id: instrumentId,
          interval,
          days,
          // `undefined` — не отправляем параметр (считать все паттерны),
          // пустой массив — отправляем `patterns=` (не выбран ни один)
          ...(patterns === undefined ? {} : { patterns: patterns.join(',') }),
        },
      }),
      providesTags: ['Performance'],
    }),
  }),
});

export const { useGetAllCandlesQuery, useGetAnalysisQuery, useGetPerformanceQuery } =
  investorApi;
