import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { connectAndReadHealthData } from './src/health/connector';
import type { DailyHealthSummary } from './src/health/types';

const platformName = Platform.OS === 'ios' ? 'Apple Health' : 'Health Connect';

export default function App() {
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summaries, setSummaries] = useState<DailyHealthSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connect = async () => {
    setLoading(true);
    setError(null);
    setSummaries(null);
    try {
      setSummaries(await connectAndReadHealthData());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Connessione non riuscita.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.screen}>
      <StatusBar style="light" />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.eyebrow}>BIOPULSE AGENT</Text>
          <Text style={styles.title}>I tuoi dati,{'\n'}le tue scelte.</Text>
          <Text style={styles.subtitle}>
            Collega {platformName} per visualizzare un riepilogo dei dati
            disponibili sul dispositivo.
          </Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Cosa leggeremo</Text>
          <Text style={styles.body}>
            Solo frequenza cardiaca a riposo, variabilità cardiaca (RMSSD),
            saturazione di ossigeno e segmenti del sonno, se disponibili.
            L’accesso è in sola lettura e puoi negare singoli permessi.
          </Text>
          <View style={styles.divider} />
          <Text style={styles.cardTitle}>Dove vanno i dati</Text>
          <Text style={styles.body}>
            In questa versione restano solo in memoria sul dispositivo per
            mostrarli qui. Non vengono salvati né inviati a un server o a un
            modello AI.
          </Text>
          <Text style={styles.notice}>
            Questo riepilogo non è una valutazione medica e non fornisce
            diagnosi o consigli terapeutici.
          </Text>
        </View>

        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: consent }}
          onPress={() => setConsent((accepted) => !accepted)}
          style={styles.consentRow}
        >
          <View style={[styles.checkbox, consent && styles.checkboxChecked]}>
            {consent ? <Text style={styles.checkmark}>✓</Text> : null}
          </View>
          <Text style={styles.consentText}>
            Ho letto l’informativa e acconsento alla lettura locale dei dati
            selezionati.
          </Text>
        </Pressable>

        <Pressable
          accessibilityRole="button"
          accessibilityState={{ disabled: !consent || loading }}
          disabled={!consent || loading}
          onPress={connect}
          style={[styles.button, (!consent || loading) && styles.buttonDisabled]}
        >
          {loading ? (
            <ActivityIndicator color="#081a1d" />
          ) : (
            <Text style={styles.buttonText}>Collega {platformName}</Text>
          )}
        </Pressable>

        {error ? (
          <Text accessibilityRole="alert" style={styles.error}>
            {error}
          </Text>
        ) : null}

        {summaries ? (
          <View style={styles.results}>
            <Text style={styles.cardTitle}>Ultimi 28 giorni</Text>
            {summaries.length === 0 ? (
              <Text style={styles.body}>
                Nessun dato disponibile per i permessi concessi. Puoi
                modificare le autorizzazioni nelle impostazioni di {platformName}.
              </Text>
            ) : (
              summaries
                .slice()
                .sort((a, b) => b.date.localeCompare(a.date))
                .map((summary) => (
                  <View key={summary.date} style={styles.dayRow}>
                    <Text style={styles.day}>{summary.date}</Text>
                    <Text style={styles.values}>
                      {formatMetrics(summary)}
                    </Text>
                  </View>
                ))
            )}
          </View>
        ) : null}

        <Text style={styles.footer}>
          Puoi revocare l’accesso in qualsiasi momento dalle impostazioni di
          salute del dispositivo.
        </Text>
      </ScrollView>
    </View>
  );
}

function formatMetrics(summary: DailyHealthSummary) {
  const metrics = [
    summary.restingHeartRateBpm !== undefined
      ? `FC riposo ${summary.restingHeartRateBpm} bpm`
      : null,
    summary.hrvRmssdMs !== undefined ? `HRV ${summary.hrvRmssdMs} ms` : null,
    summary.oxygenSaturationPercent !== undefined
      ? `SpO₂ ${summary.oxygenSaturationPercent}%`
      : null,
    summary.sleepHours !== undefined ? `Sonno ${summary.sleepHours} h` : null,
  ].filter((metric): metric is string => metric !== null);

  return metrics.join(' · ') || 'Nessun dato per questo giorno';
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#071719',
  },
  content: {
    width: '100%',
    maxWidth: 620,
    alignSelf: 'center',
    paddingHorizontal: 24,
    paddingTop: 72,
    paddingBottom: 48,
  },
  header: {
    marginBottom: 28,
  },
  eyebrow: {
    color: '#67e8c1',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 2,
    marginBottom: 14,
  },
  title: {
    color: '#f4fbf8',
    fontSize: 38,
    fontWeight: '700',
    lineHeight: 44,
  },
  subtitle: {
    color: '#b7cbc5',
    fontSize: 16,
    lineHeight: 24,
    marginTop: 14,
  },
  card: {
    backgroundColor: '#102426',
    borderColor: '#244144',
    borderRadius: 18,
    borderWidth: 1,
    padding: 20,
  },
  cardTitle: {
    color: '#f4fbf8',
    fontSize: 17,
    fontWeight: '700',
    marginBottom: 8,
  },
  body: {
    color: '#b7cbc5',
    fontSize: 14,
    lineHeight: 21,
  },
  divider: {
    backgroundColor: '#244144',
    height: 1,
    marginVertical: 18,
  },
  notice: {
    color: '#9eb6af',
    fontSize: 12,
    lineHeight: 18,
    marginTop: 16,
  },
  consentRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    marginTop: 22,
  },
  checkbox: {
    alignItems: 'center',
    borderColor: '#6f8d86',
    borderRadius: 5,
    borderWidth: 1,
    height: 22,
    justifyContent: 'center',
    width: 22,
  },
  checkboxChecked: {
    backgroundColor: '#67e8c1',
    borderColor: '#67e8c1',
  },
  checkmark: {
    color: '#081a1d',
    fontSize: 15,
    fontWeight: '700',
  },
  consentText: {
    color: '#d8e6e1',
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
  },
  button: {
    alignItems: 'center',
    backgroundColor: '#67e8c1',
    borderRadius: 12,
    justifyContent: 'center',
    marginTop: 20,
    minHeight: 52,
  },
  buttonDisabled: {
    backgroundColor: '#38534e',
  },
  buttonText: {
    color: '#081a1d',
    fontSize: 15,
    fontWeight: '700',
  },
  error: {
    color: '#ff9b9b',
    fontSize: 14,
    lineHeight: 20,
    marginTop: 16,
  },
  results: {
    backgroundColor: '#102426',
    borderColor: '#244144',
    borderRadius: 18,
    borderWidth: 1,
    marginTop: 24,
    padding: 20,
  },
  dayRow: {
    borderTopColor: '#244144',
    borderTopWidth: 1,
    paddingVertical: 12,
  },
  day: {
    color: '#67e8c1',
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 5,
  },
  values: {
    color: '#d8e6e1',
    fontSize: 13,
    lineHeight: 19,
  },
  footer: {
    color: '#829d95',
    fontSize: 12,
    lineHeight: 18,
    marginTop: 22,
  },
});
