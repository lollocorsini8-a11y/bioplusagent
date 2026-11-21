import { Platform } from 'react-native';
import type { DailyHealthSummary } from './types';

export async function connectAndReadHealthData(): Promise<DailyHealthSummary[]> {
  throw new Error(`L’integrazione salute non è disponibile su ${Platform.OS}.`);
}
