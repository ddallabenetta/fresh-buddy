# Hardware Setup Guide

This guide covers the hardware assembly for BMO Companion.

## Required Components

### Core Computing
- **NVIDIA Jetson Orin Nano** (8GB recommended)
  - Orin Nano 8GB: ~$599
  - Orin NX 16GB: ~$699
- **MicroSD Card** (64GB+ for OS and models)
- **Power Supply** (5V/4A USB-C for Orin Nano)

### Display System
- **Primary Display**: Small CRT monitor (optional, for retro aesthetic)
- **OLED Display**: SSD1306 128x64 I2C OLED (~$10)
  - Adafruit SSD1306 or equivalent
  - Pins: SDA, SCL, VCC (3.3V), GND
- **I2C wiring**: Connect to Jetson I2C bus (pins 3/SDA, 5/SCL)

### Audio
- **Microphone**: I2S microphone array or USB mic
  - Recommended: ReSpeaker 4-Mic Array (~$30)
  - Or: USB omnidirectional microphone
- **Speakers**: 3W speaker or headphones
  - Connects to 3.5mm audio jack

### Housing
- Old small CRT monitor
- 3D printed case (optional, see STL files in assets/)
- Mounting hardware, cables

## Wiring Diagram

```
Jetson Orin Nano     OLED Display
----------------     ------------
Pin 3 (I2C SDA)  →  SDA
Pin 5 (I2C SCL)  →  SCL
3.3V              →  VCC
GND               →  GND

Jetson Orin Nano     Microphone Array
----------------     -----------------
Pin 3 (I2C SDA)  →  SDA (if I2S)
Pin 5 (I2C SCL)  →  SCL (if I2S)
3.3V              →  3.3V
GND               →  GND
                  Or
USB               →  USB mic (simpler)
```

## I2C Setup

1. Check I2C bus is available:
```bash
ls /dev/i2c-*
```

2. Install I2C tools:
```bash
sudo apt install i2c-tools
```

3. Scan for devices:
```bash
sudo i2cdetect -y -r 1
```

4. You should see `3c` for the SSD1306 display

## Audio Setup

1. Check audio devices:
```bash
arecord -l
aplay -l
```

2. Set default audio device in `config.json`:
```json
{
    "audio_device": 0
}
```

## Software Installation

After hardware assembly, run:
```bash
./scripts/install.sh
```

## Testing

Test the display:
```bash
python -m bmo.main --test-face
```

Test audio:
```bash
python -m bmo.main --test-audio
```

## Troubleshooting

### Display not showing
- Check I2C address (should be 0x3C)
- Verify wiring connections
- Run `i2cdetect` to confirm device detection

### Audio not working
- Check microphone permissions: `arecord --dummy`
- Install pulse audio: `sudo apt install pulseaudio`
- Verify default device in system settings

### Jetson won't boot
- Use official NVIDIA JetPack image
- Ensure power supply provides sufficient current
- Check SD card is properly inserted
