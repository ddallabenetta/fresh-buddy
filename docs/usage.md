# Guida Utilizzo — Fresh Buddy

## Avviare Fresh Buddy

```bash
source venv/bin/activate
python -m bmo.main
```

Fresh Buddy:
1. Inizializza tutti i componenti hardware
2. Mostra animazione di avvio sul display OLED
3. Ti saluta con voce: "Ciao! Sono Fresh Buddy. Come posso aiutarti?"
4. Ascolta i comandi vocali

## Comandi Vocali

### Interazione Base
- Dì "**Ciao Buddy**" per attirare l'attenzione di Fresh Buddy
- Dopo la wake word, parla la tua domanda o comando
- Fresh Buddy risponderà con voce ed espressioni

### Comandi Meeting

| Comando | Descrizione |
|---------|-------------|
| "Ciao Buddy, avvia meeting" | Inizia registrazione meeting |
| "Ciao Buddy, termina meeting" | Ferma registrazione e genera riepilogo |
| "Ciao Buddy, riepiloga meeting" | Ottieni riepilogo dell'ultimo meeting |

### Esempi

**Avviare un meeting:**
```
Tu: "Ciao Buddy, avvia meeting"
Fresh Buddy: "Registrazione meeting iniziata."
(Indicatore rosso sul display)
```

**Avere una conversazione:**
```
Tu: "Ciao Buddy, qual è la capitale della Francia?"
Fresh Buddy: (espressione pensante)
Fresh Buddy: "La capitale della Francia è Parigi."
```

**Terminare un meeting:**
```
Tu: "Ciao Buddy, termina meeting"
Fresh Buddy: "Registrazione meeting terminata. Sto generando il riepilogo..."
Fresh Buddy: (legge il riepilogo ad alta voce)
```

## Espressioni del Display

Fresh Buddy mostra diverse espressioni:

| Espressione | Quando |
|-------------|--------|
| 😊 Felice | Risposte positive |
| 😢 Triste | Scuse o notizie tristi |
| 🤔 Pensante | Elaborazione query complesse |
| 😮 Eccitato | Info molto positive o sorprendenti |
| 😕 Confuso | Input non chiaro o frainteso |
| 😴 Addormentato | Stato idle/inattivo |
| 🔴 Registrazione | Meeting in registrazione |
| 👂 Ascolto | Modalità ascolto attivo |

## Meeting

### Flusso Meeting

1. **Avvio**: "Ciao Buddy, avvia meeting"
2. **Durante**: Tutto il contenuto parlato viene trascritto
3. **Termine**: "Ciao Buddy, termina meeting"
4. **Riepilogo**: Fresh Buddy genera e legge il riepilogo

### Dati Meeting Salvati

I meeting vengono salvati nella directory `meetings/`:

```
meetings/
├── 20260408_143000_minutes.json  # Riepilogo strutturato
└── 20260408_143000_transcript.txt # Trascrizione completa
```

### Formato Riepilogo Meeting

```json
{
    "meeting_id": "20260408_143000",
    "date": "2026-04-08T14:30:00",
    "duration_seconds": 1800,
    "summary": "Il team ha discusso il roadmap Q2...",
    "action_items": [
        {"task": "Rivedi PR #123", "assignee": "Alice", "deadline": "Venerdì"}
    ],
    "decisions": ["Approvato aumento budget"],
    "participants": ["Alice", "Bob", "Charlie"]
}
```

## Configurazione

Modifica `config.json` per personalizzare:

### Impostazioni Voce
```json
{
    "piper_voice": "it_IT-riccardo-x_low",
    "piper_speaker": null,
    "piper_length_scale": 1.0
}
```

### Impostazioni LLM
```json
{
    "llm_temperature": 0.7,
    "llm_max_tokens": 512
}
```

### Wake Word
```json
{
    "wake_word": "ciao buddy",
    "wake_word_sensitivity": 0.5
}
```

## Risoluzione Problemi

### Fresh Buddy non risponde alla wake word
- Verifica che il microfono funzioni: `python -m bmo.main --test-audio`
- Abbassa la sensibilità della wake word nel config
- Avvicinati al microfono

### Le risposte sono lente
- Il modello Nemotron potrebbe necessitare quantizzazione
- Controlla thermal throttling del Jetson
- Riduci `llm_max_tokens`

### Qualità audio scarsa
- Usa un microfono di qualità superiore
- Regola il gain di input audio nelle impostazioni di sistema
- Prova microfono USB invece di I2S

## Uso Programmatico

Fresh Buddy può essere usato programmaticamente:

```python
from bmo.main import FreshBuddy
from bmo.config import Config

# Carica config
config = Config.load()

# Crea istanza Fresh Buddy
buddy = FreshBuddy(config)

# Query senza voce
response = buddy.run_headless("Che ore sono?")
print(response)

# Ottieni riepilogo meeting
summary = buddy.meeting.get_summary()
print(summary)
```
