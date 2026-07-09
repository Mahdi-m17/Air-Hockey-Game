# Air Hockey 🏒

A keyboard-controlled Air Hockey game built with [pygame](https://www.pygame.org/), featuring
a resizable / full-screen window, a single-player mode against a predictive AI, and a local
two-player mode.

## Features

- Realistic puck physics — friction, wall bounces, and momentum transfer from paddle hits
- Predictive AI opponent that anticipates the puck's path (including wall bounces) instead
  of just mirroring its position
- Single Player (vs Computer) and Two Player (local, same keyboard) modes
- Resizable and full-screen window — the table, walls, and goals rescale automatically
- Simple main menu and win screen

## Requirements

- Python 3.8+
- [pygame](https://www.pygame.org/)

## Install & Run

```bash
git clone https://github.com/<your-username>/air-hockey.git
cd air-hockey
pip install -r requirements.txt
python air_hockey.py
```

## Controls

**Menu**

| Key       | Action                        |
|-----------|--------------------------------|
| `1`       | Start Single Player (vs AI)    |
| `2`       | Start Two Player                |
| `F11` / `F` | Toggle full screen            |
| `ESC`     | Quit                            |

**In-game**

| Key            | Action                                   |
|----------------|-------------------------------------------|
| `W A S D`      | Player 1 (blue) movement                  |
| Arrow keys     | Player 2 (red) movement — Two Player mode only |
| `F11` / `F`    | Toggle full screen                        |
| `R`            | Reset the score                           |
| `ESC`          | Back to menu                              |
| `SPACE`        | Play again (after a win)                  |

First to **7 goals** wins.

## Roadmap / Ideas for future versions

- [ ] Difficulty levels for the AI (easy / medium / hard)
- [ ] Sound effects and background music
- [ ] Best-of-N match format
- [ ] Online multiplayer
- [ ] Paddle/puck skins or table themes
- [ ] Local high-score tracking

## License

MIT — feel free to fork and modify.
