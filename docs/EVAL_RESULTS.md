# Risultati di valutazione

Generato da `backend/eval/run_eval.py` (dati simulati, seed 1-200, nessun LLM).

| Metrica | Risultato |
|---|---|
| Overload rilevato come ROSSO (ACWR > 1.5) | 100.0% (200/200) |
| Calo HRV rilevato come ROSSO (Z < -1.5) | 100.0% (200/200) |
| Falsi ROSSI su atleta stabile | 0.5% (1/200) |
| Falsi ROSSI in settimana di scarico | 0.0% (0/200) |
| Atleta stabile classificato VERDE | 91.0% (182/200) |
| Latenza motore White-Box (sanificazione + calcolo) | p50 1.80 ms, p95 10.01 ms, max 68.86 ms |
| Output LLM pericolosi corretti (livello rosso) | 100.0% (195/195) |
| Output LLM sicuri bloccati a torto (falsi positivi) | 0.0% (0/150) |
| Prompt injection rilevate | 100.0% (14/14) |
| Messaggi legittimi bloccati come injection | 0.0% (0/12) |
| Sintomi d'allarme rilevati | 100.0% (10/10) |
| Messaggi non urgenti segnalati come sintomi | 0.0% (0/6) |

## Come leggerli

- I corpora (output LLM, injection, sintomi) sono piccoli e scritti dagli autori: misurano la regressione dei guardrail, **non** una validazione clinica né un red-teaming esaustivo.
- I guardrail sono regole testuali (regex): le varianti linguistiche non previste possono sfuggire. Per questo il calcolo del rischio resta nel motore White-Box e il livello rosso passa sempre dall'approvazione umana.
- La latenza riguarda solo il motore deterministico; la risposta dell'LLM aggiunge tipicamente 1-4 secondi.
