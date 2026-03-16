# Civ5 Save File Reverse Engineering

Tools and documentation for reverse engineering Civilization V `.Civ5Save` files.

## Contents

| File | Description |
|------|-------------|
| [`FORMAT.md`](FORMAT.md) | Comprehensive binary format documentation |
| [`civ5.bt`](civ5.bt) | 010 Editor binary template for visual inspection |
| [`civ5_parser.py`](civ5_parser.py) | Python parser for extracting save file data |
| [`civ5_map.py`](civ5_map.py) | Map extractor — renders terrain as ASCII or JSON |

## Quick Start

```bash
# Parse a save file and print JSON
python3 civ5_parser.py game.Civ5Save

# Print a human-readable summary
python3 civ5_parser.py game.Civ5Save --summary

# Extract the compressed game state
python3 civ5_parser.py game.Civ5Save --dump-compressed gamestate.bin

# Render the game map as ASCII
python3 civ5_map.py game.Civ5Save

# Export map as JSON
python3 civ5_map.py game.Civ5Save --json

# Two-save mode for better accuracy (consecutive turns of the same game)
python3 civ5_map.py turn12.Civ5Save turn13.Civ5Save
```

## Format Summary

Civ5 saves are binary files with:
- **Magic**: `CIV5` (4 bytes)
- **32–33 sections** separated by `0x40000000` delimiters
- **Length-prefixed strings** (4-byte LE int + UTF-8 data)
- **zlib-compressed game state** in the final section

See [`FORMAT.md`](FORMAT.md) for the full specification.
