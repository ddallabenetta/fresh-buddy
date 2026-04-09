# Guida Hardware — Fresh Buddy

Questa guida copre l'assemblaggio hardware per Fresh Buddy.

## Componenti Necessari

### Calcolo Principale
- **NVIDIA Jetson Orin Nano** (8GB consigliato)
  - Orin Nano 8GB: ~€550
  - Orin NX 16GB: ~€650
- **MicroSD Card** (64GB+ per OS e modelli)
- **Alimentatore** (5V/4A USB-C per Orin Nano)

### Sistema Display
- **Display OLED**: SSD1306 128x64 I2C (~$10)
  - Adafruit SSD1306 o equivalente
  - Pin: SDA, SCL, VCC (3.3V), GND
- **Cablaggio I2C**: Collega ai pin I2C del Jetson (3/SDA, 5/SCL)

### Audio
- **Microfono**: Array microfonico I2S o USB
  - Consigliato: ReSpeaker 4-Mic Array (~$30)
  - Oppure: Microfono USB omnidirezionale
- **Speaker**: Speaker 3W o cuffie
  - Collega al jack audio 3.5mm

### Case
- Piccolo monitor CRT (opzionale, per estetica retro)
- Case stampato in 3D (opzionale)
- Cavi e viti di montaggio

## Schema dei Cablaggi

```
Jetson Orin Nano     Display OLED
----------------     ------------
Pin 3 (I2C SDA)  →  SDA
Pin 5 (I2C SCL)  →  SCL
3.3V              →  VCC
GND               →  GND

Jetson Orin Nano     Array Microfonico
----------------     -----------------
Pin 3 (I2C SDA)  →  SDA (se I2S)
Pin 5 (I2C SCL)  →  SCL (se I2S)
3.3V              →  3.3V
GND               →  GND
                  Or
USB               →  USB mic (più semplice)
```

## Configurazione I2C

1. Verifica che il bus I2C sia disponibile:
```bash
ls /dev/i2c-*
```

2. Installa gli strumenti I2C:
```bash
sudo apt install i2c-tools
```

3. Scansiona i dispositivi:
```bash
sudo i2cdetect -y -r 1
```

4. Dovresti vedere `3c` per il display SSD1306

## Configurazione Audio

1. Verifica i dispositivi audio:
```bash
arecord -l
aplay -l
```

2. Imposta il dispositivo audio predefinito in `config.json`:
```json
{
    "audio_device": 0
}
```

## Installazione Software

Dopo l'assemblaggio hardware, esegui:
```bash
./scripts/install.sh
```

## Test

Testa il display:
```bash
python -m bmo.main --test-face
```

Testa l'audio:
```bash
python -m bmo.main --test-audio
```

## Risoluzione Problemi

### Display non funziona
- Verifica l'indirizzo I2C (dovrebbe essere 0x3C)
- Controlla i collegamenti
- Esegui `i2cdetect` per confermare il rilevamento

### Audio non funziona
- Verifica i permessi del microfono: `arecord --dummy`
- Installa pulse audio: `sudo apt install pulseaudio`
- Controlla il dispositivo audio predefinito

### Jetson non si avvia
- Usa l'immagine ufficiale NVIDIA JetPack
- Assicurati che l'alimentazione sia sufficiente
- Verifica che la SD sia inserita correttamente
