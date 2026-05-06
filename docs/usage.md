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

Fresh Buddy mostra diverse espressioni con stile robot futuristico anni 80: glow CRT, scanline, reticoli pupilla, sweep palpebre, LED sulle guance e barre equalizer quando parla o ascolta.

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

## Dev Console

Per provare l'interfaccia in browser durante lo sviluppo:

```bash
PYTHONPATH=src PREVIEW_PORT=8088 python3 -c "from bmo.face.display import OLEDDisplay; from bmo.face.expressions import ExpressionEngine; from bmo.face.preview_server import configure; import time; d=OLEDDisplay(); e=ExpressionEngine(d); configure(expressions=e); e.show_expression('neutral'); time.sleep(3600)"
```

Apri `http://localhost:8088/`. Puoi testare tutte le espressioni, cambiare schema colore, regolare transizione e velocità, attivare/disattivare scanline e glow, e lanciare il glitch test.

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

Oppure usa un file `.env` nella directory del progetto per impostare variabili come `FIRST_MESSAGE`.

### Impostazioni Voce
```json
{
    "piper_voice": "it_IT-riccardo-x_low",
    "piper_speaker": null,
    "piper_length_scale": 1.0,
    "tts_volume": 0.3
}
```

### Impostazioni LLM
```json
{
    "llm_temperature": 0.7,
    "llm_max_tokens": 512,
    "llm_top_p": 0.9
}
```

### Wake Word
```json
{
    "wake_word": "ciao buddy",
    "wake_word_sensitivity": 0.5
}
```

### STT Tuning
```json
{
    "stt_main_timeout": 12.0,
    "stt_followup_timeout": 6.0,
    "stt_energy_threshold": 500,
    "stt_end_silence_timeout": 0.45,
    "stt_followup_end_silence_timeout": 0.35,
    "stt_pre_roll_chunks": 3,
    "stt_chunk_frames": 512,
    "stt_beam_size": 1,
    "stt_best_of": 1,
    "stt_temperature": 0.0,
    "stt_vad_filter": true,
    "stt_condition_on_previous_text": false
}
```

Per ridurre la latenza, i valori consigliati sono quelli sopra: `beam_size=1`, `best_of=1`, `vad_filter=true`, `condition_on_previous_text=false` e `stt_chunk_frames=512`. Se vuoi più accuratezza al costo di più tempo, aumenta `beam_size` o disattiva `vad_filter`.

### Messaggio Iniziale
```json
{
    "first_message": "Ciao! Sono Fresh Buddy. Come posso aiutarti?"
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
