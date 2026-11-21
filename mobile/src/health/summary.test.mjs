import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createSummaries,
  groupSleepIntervals,
  latestValuesPerDay,
} from './summary.ts';

const localDate = (day, hour = 0, minute = 0) =>
  new Date(2026, 0, day, hour, minute);

test('selects the most recent sample for each local day', () => {
  const values = latestValuesPerDay([
    { date: localDate(1, 8), value: 61 },
    { date: localDate(1, 21), value: 54 },
    { date: localDate(2, 9), value: 59 },
  ]);

  assert.deepEqual(Array.from(values), [
    ['2026-01-01', 54],
    ['2026-01-02', 59],
  ]);
});

test('groups sleep stages, removes overlaps, and separates distant sessions', () => {
  const sessions = groupSleepIntervals([
    { start: localDate(1, 22), end: localDate(1, 23) },
    { start: localDate(1, 22, 30), end: localDate(1, 23, 30) },
    { start: localDate(1, 23), end: localDate(2, 0) },
    { start: localDate(2, 0, 30), end: localDate(2, 1, 30) },
    { start: localDate(2, 5), end: localDate(2, 5, 30) },
    { start: localDate(2, 8), end: localDate(2, 7) },
  ]);

  assert.deepEqual(
    sessions.map(({ date, value }) => [date, value]),
    [
      [localDate(2, 1, 30), 180],
      [localDate(2, 5, 30), 30],
    ],
  );
});

test('builds sparse daily summaries without inventing missing metrics', () => {
  const summaries = createSummaries({
    hrv: [
      { date: localDate(1, 8), value: 44.26 },
      { date: localDate(1, 21), value: 49.65 },
    ],
    restingHeartRate: [{ date: localDate(2, 7), value: 58 }],
    sleepMinutes: [
      { date: localDate(2, 6), value: 430 },
      { date: localDate(2, 6), value: 450 },
    ],
  });

  assert.deepEqual(summaries, [
    { date: '2026-01-01', hrvRmssdMs: 49.7 },
    {
      date: '2026-01-02',
      restingHeartRateBpm: 58,
      sleepHours: 7.5,
    },
  ]);
  assert.deepEqual(createSummaries({}), []);
});
