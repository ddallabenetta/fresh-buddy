# Fresh Buddy — 80s Futuristic Face System Specification

## Overview

Transform Fresh Buddy's face into a stunning 80s sci-fi movie aesthetic — think Blade Runner terminal interfaces, Tron light cycles, and retrofuturistic computer displays. The system must maintain full backward compatibility while delivering a visually striking experience.

---

## Visual Style Guide

### Color Palette
- **Primary**: Matrix green `#39FF14` (classic terminal green)
- **Secondary**: Cyan `#00FFFF` (Tron-style)
- **Accent**: Magenta/Hot Pink `#FF00FF` (synthwave)
- **Accent 2**: Electric Blue `#00D4FF`
- **Background**: Pure black `#000000`
- **Warning/Alert**: Amber `#FFB000`

### Typography
- Retro LED/terminal font aesthetic
- All caps for status indicators
- Monospace for data displays

### Display Composition
- BMO-style rounded rectangle body (existing)
- Screen area with scanline overlay effect
- Glowing edges with subtle bloom
- CRT screen curvature hint (via corner shading)

---

## Animation System

### Expression Transitions
- All expression changes use **smooth interpolation** (not instant snap)
- Transition duration: **200-400ms**
- Easing: **ease-in-out** or **ease-out-expo** for that premium feel

### Per-Expression Animations

#### NEUTRAL
- Gentle idle breathing: subtle vertical float over time
- Eyes: animated pupil radar reticles, glints, eyelid shutter sweep
- Mouth: minimal smile with CRT post-processing shimmer

#### HAPPY
- Eyes: sparkle effect (small bright dots orbit)
- Mouth: wide smile with corner accents
- Body: slight bounce animation
- Cheek indicators (small blinking LED dots)

#### EXCITED
- Eyes: starburst effect, rapid color shift cyan↔magenta
- Mouth: open smile with tongue hint
- Body: energetic bounce, faster pulse
- Particle effects: starburst rays plus mouth equalizer bars

#### SAD
- Eyes: droopy, tears animation (vertical streaks)
- Mouth: pronounced frown
- Body: slow breathing, desaturated colors
- Effect: subtle rain/static on screen edges

#### CONFUSED
- Eyes: one open, one closed, eyebrow tilt
- Mouth: wavy/uncertain shape
- Effect: question mark icon with wobble animation
- Background: subtle static/interference pattern

#### LISTENING
- Eyes: attentive, iris follows subtle "movement"
- Mouth: small "o" shape
- Ear indicator: sound wave rings emanating
- Face overlay: pupil radar and mouth equalizer bars

#### SPEAKING
- Mouth: smooth open/close synced to speech
- Jaw movement: animated phase cycle with equalizer bars
- Eyes: slight blink suppression, focused pupil radar
- Tongue visible for "th" and "l" sounds (optional)

#### THINKING
- Eyes: look to side with dots animation
- Expression: concentrated frown
- Background: loading bar or circular spinner
- Effect: "PROCESSING" text flicker

#### SLEEPING
- Eyes: closed (horizontal lines with lashes)
- Mouth: small "o" or flat line
- Z's: animated floating Z characters
- Body: slow breathing (scale 1.0 → 1.03 → 1.0, 4s cycle)
- Effect: soft snore indicator

#### RECORDING
- Red dot: pulsing record indicator
- Eyes: alert, scanning motion
- Body: slight shake/vibration effect
- Text: "REC" flashing
- Face overlay: horizontal eye scan beam

### Idle Animations
- Scanline overlay (horizontal lines scrolling slowly)
- Glow/bloom post-processing around lit edges
- Occasional glitch effect (1-2 per minute, very subtle)

### Transition Effects
- Expression change: brief flash/white-out
- Type-in text: retro terminal typewriter effect
- Loading: progress bar with percentage

---

## Technical Requirements

### Smooth Animation Pipeline
- Frame rate: 30fps minimum for animations
- Double-buffering to prevent flicker
- Interrupt-driven animation thread

### Easing Functions (minimum)
```python
def ease_out_expo(t):        # Quick start, slow end
def ease_in_out_quad(t):     # Smooth in and out
def ease_out_bounce(t):      # Bounce effect for excited states
```

### Expression Blending
- Support intermediate expression states (e.g., 60% happy, 40% neutral)
- Blend factors interpolate over transition duration

---

## Display Layers (rendering order)

1. **Background**: Pure black
2. **Scanline overlay**: Semi-transparent horizontal lines
3. **Body glow**: Outer glow effect
4. **Body**: Rounded rectangle outline
5. **Screen background**: Slightly lighter black `#0a0a0a`
6. **Face elements**: Eyes, mouth, accessories
7. **Effects layer**: Particles, Z's, indicators
8. **Text/Status**: Labels, percentages

---

## Display Specification

**Hardware**: Waveshare 5" HDMI LCD (800×480)
- No I2C/SPI — HDMI connection, display is framebuffer-driven
- High resolution allows detailed animations
- Full RGB output, not 1-bit like OLED

### Previous OLED Reference (128×64)
- Kept as fallback/simulation mode
- Used only when no HDMI display detected

### Face Dimensions (800×480 display)
- **Body**: ~440×240 pixels, rounded corners (radius 40)
- **Screen**: ~380×180 pixels, inset from body by 30px
- **Eye diameter**: ~80px each, 90px apart (center to center)
- **Pupil**: ~40px with highlight dot
- **Mouth**: ~120px wide, 60px tall when open
- **Overall face position**: Centered horizontally, slightly above vertical center

### Face Dimensions (128x64 display - legacy)
- Body: 88x48 pixels, rounded corners (radius 8)
- Screen: 76x36 pixels, inset from body by 6px
- Eye spacing: ~22px apart (center to center)
- Mouth position: centered below eyes
- Status text: bottom of screen area

---

## Preview Server Enhancements

- [x] Real-time expression preview with auto-refresh
- [x] Expression transition smoothness visualization
- [x] Color scheme switcher (green/cyan/magenta/amber themes)
- [x] Animation speed slider
- [x] Frame rate display
- [x] Scanline toggle
- [x] Glow toggle

---

## Deliverables Checklist

- [x] Updated expressions.py with 80s visual style (800×480 native)
- [x] Smooth transition system between expressions
- [x] Easing function library
- [x] Animation timing controller
- [x] Scanline overlay effect (1px every 3px)
- [x] Glow/bloom effect on edges
- [x] Enhanced preview_server with debug controls
- [x] HDMI display driver (framebuffer-based, not I2C)
- [x] Unit tests for animation system
- [x] Documentation: Animation System API

## Hardware Notes

**IMPORTANT**: Display is HDMI-connected, NOT I2C/SPI!
- Driver must use framebuffer (`/dev/fb0`) or DRM/HDMI output
- No SSD1306 OLED driver needed for actual hardware
- Simulation mode still uses 128×64 for dev console preview
- Resolution switching: detect HDMI and use 800×480, fallback to OLED simulation

---

## Color Scheme Variants (for future)

1. **Matrix Green** (default): `#39FF14` on black
2. **Tron Cyan**: `#00FFFF` on `#001a1a`
3. **Synthwave**: `#FF00FF` / `#00D4FF` gradient on `#1a001a`
4. **Amber Retro**: `#FFB000` on `#0a0800`
