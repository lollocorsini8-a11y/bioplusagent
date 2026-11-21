import {
  getSdkStatus,
  initialize,
  readRecords,
  requestPermission,
  SdkAvailabilityStatus,
  SleepStageType,
  type Permission,
  type RecordType,
} from 'react-native-health-connect';
import { createSummaries, getDateWindow } from './summary';
import type { TimedValue } from './types';

const PERMISSIONS: Permission[] = [
  { accessType: 'read', recordType: 'HeartRateVariabilityRmssd' },
  { accessType: 'read', recordType: 'RestingHeartRate' },
  { accessType: 'read', recordType: 'OxygenSaturation' },
  { accessType: 'read', recordType: 'SleepSession' },
];

const ASLEEP_STAGES = new Set<number>([
  SleepStageType.SLEEPING,
  SleepStageType.LIGHT,
  SleepStageType.DEEP,
  SleepStageType.REM,
]);

export async function connectAndReadHealthData() {
  const status = await getSdkStatus();
  if (status !== SdkAvailabilityStatus.SDK_AVAILABLE) {
    throw new Error(
      'Health Connect non è disponibile. Verifica che sia installato o aggiornato sul dispositivo.',
    );
  }

  if (!(await initialize())) {
    throw new Error('Impossibile inizializzare Health Connect.');
  }

  const grants = await requestPermission(PERMISSIONS);
  const grantedTypes = new Set(
    grants
      .filter((grant) => grant.accessType === 'read')
      .map((grant) => grant.recordType),
  );

  if (grantedTypes.size === 0) {
    throw new Error('Non è stato concesso alcun permesso di lettura.');
  }

  const { start, end } = getDateWindow(28);
  const timeRangeFilter = {
    operator: 'between' as const,
    startTime: start.toISOString(),
    endTime: end.toISOString(),
  };

  const readAll = async <T extends RecordType>(recordType: T) => {
    const records: Awaited<ReturnType<typeof readRecords<T>>>['records'] = [];
    let pageToken: string | undefined;

    do {
      const page = await readRecords(recordType, {
        timeRangeFilter,
        pageSize: 1000,
        pageToken,
      });
      records.push(...page.records);
      pageToken = page.pageToken;
    } while (pageToken);

    return records;
  };

  const [hrvRecords, restingHeartRateRecords, oxygenRecords, sleepRecords] =
    await Promise.all([
      grantedTypes.has('HeartRateVariabilityRmssd')
        ? readAll('HeartRateVariabilityRmssd')
        : Promise.resolve([]),
      grantedTypes.has('RestingHeartRate')
        ? readAll('RestingHeartRate')
        : Promise.resolve([]),
      grantedTypes.has('OxygenSaturation')
        ? readAll('OxygenSaturation')
        : Promise.resolve([]),
      grantedTypes.has('SleepSession')
        ? readAll('SleepSession')
        : Promise.resolve([]),
    ]);

  const hrv: TimedValue[] = hrvRecords.map((record) => ({
    date: new Date(record.time),
    value: record.heartRateVariabilityMillis,
  }));
  const restingHeartRate: TimedValue[] = restingHeartRateRecords.map((record) => ({
    date: new Date(record.time),
    value: record.beatsPerMinute,
  }));
  const oxygenSaturation: TimedValue[] = oxygenRecords.map((record) => ({
    date: new Date(record.time),
    value: record.percentage <= 1 ? record.percentage * 100 : record.percentage,
  }));
  const sleepMinutes: TimedValue[] = sleepRecords.flatMap((record) => {
    if (!record.stages?.length) return [];

    const minutes = record.stages
      .filter((stage) => ASLEEP_STAGES.has(stage.stage))
      .reduce(
        (total, stage) =>
          total +
          (new Date(stage.endTime).getTime() -
            new Date(stage.startTime).getTime()) /
            60_000,
        0,
      );

    return minutes > 0
      ? [{ date: new Date(record.endTime), value: minutes }]
      : [];
  });

  return createSummaries({ hrv, restingHeartRate, oxygenSaturation, sleepMinutes });
}
