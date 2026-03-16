# Civilization V Save File Format (.Civ5Save)

Reverse-engineered binary format documentation for Civilization V save files.

## Overview

| Property | Value |
|----------|-------|
| Magic | `CIV5` (4 bytes ASCII) |
| Byte order | Little-endian |
| String encoding | UTF-8, length-prefixed |
| Section delimiter | `0x40000000` (LE: `40 00 00 00`) |
| Sections | 32 (base game) or 33 (builds ≥ 395070) |
| Compression | zlib (final section, magic `78 9C`) |

## Primitive Types

### Integer (`int32`)
4-byte signed little-endian integer.

### Byte (`uint8`)
Single unsigned byte.

### c5string (Length-Prefixed String)
```
[4 bytes: length N as int32 LE] [N bytes: UTF-8 string data]
```
Example: `05 00 00 00 48 65 6C 6C 6F` → "Hello"

A length of 0 means an empty string (no data bytes follow).

### GUID
16-byte binary identifier (used for DLC and mod IDs).

## File Structure

The file is divided into sections separated by the delimiter `40 00 00 00`. The first section (header) starts immediately without a delimiter. All subsequent sections are preceded by this 4-byte marker.

```
[HEADER (Section 1)]
[40 00 00 00] [Section 2 data]
[40 00 00 00] [Section 3 data]
...
[40 00 00 00] [Section N: zlib compressed game state]
```

### Important: The delimiter `0x40000000` can appear as a false positive in player color hex data for builds < 310700. Parsers should account for this.

---

## Section 1: Header

| Offset | Type | Field | Description |
|--------|------|-------|-------------|
| 0x00 | char[4] | magic | File signature, must be `"CIV5"` |
| 0x04 | int32 | saveGameVersion | Format version (4–8) |
| 0x08 | c5string | gameVersion | e.g. `"1.0.3.18 (379995)"` |
| var | c5string | gameBuild | e.g. `"379995"` |
| var | int32 | currentTurn | Current game turn number |
| var | uint8 | gameMode | 0=Single Player, 1=Multiplayer, 2=Hotseat |
| var | c5string | player1Civilization | e.g. `"CIVILIZATION_ROME"` |
| var | c5string | difficulty | e.g. `"HANDICAP_PRINCE"` |
| var | c5string | startingEra | e.g. `"ERA_ANCIENT"` |
| var | c5string | currentEra | e.g. `"ERA_CLASSICAL"` |
| var | c5string | gamePace | e.g. `"GAMESPEED_STANDARD"` |
| var | c5string | mapSize | e.g. `"WORLDSIZE_SMALL"` |
| var | c5string | mapFile | e.g. `"Assets\\Maps\\Continents.lua"` |

### Save Game Version Reference

| saveGameVersion | Introduced in Build | Notes |
|-----------------|---------------------|-------|
| 4 | Early versions | Base format |
| 5 | ~230620 | Added gameVersion and gameBuild |
| 6 | ~310700 | Player colors changed from hex to strings |
| 7 | ~395070 | Added section 33 |
| 8 | ~403694 | Latest known format |

## DLC Section (follows header)

```
[int32: numDLC]
  repeated numDLC times:
    [16 bytes: GUID]
    [int32: version]
    [c5string: dlcName]
```

Known DLC names include:
- `Expansion - Gods and Kings`
- `Expansion - Brave New World`
- Various civilization/scenario packs

## Mod Section (follows DLC)

```
[int32: numMods]
  repeated numMods times:
    [16 bytes: GUID]
    [int32: version]
    [c5string: modName]
```

## Sections 2–9: Player Metadata

After mods, the file contains player-related data. The exact boundaries depend on section delimiters.

### Section 2–3: Pre-Player Data
- 2 unknown c5strings
- Player 1 color (c5string)
- 41 bytes unknown
- 4 unknown int32s
- Map file path (c5string, repeated)

### Section 3: Player Names
```
[int32: numPlayers]
  [c5string × numPlayers: player names]
```

### Section 4: Player Statuses
```
[int32: numStatuses]  (always 64 slots)
  [int32 × 64: status values]
```

| Status Value | Meaning |
|-------------|---------|
| 1 | AI |
| 2 | Dead |
| 3 | Human |
| 4 | None (empty slot) |

### Section 5: Regions
```
[int32: count]
  [int32 × count: region IDs]
```

### Section 6: Teams
```
[int32: count]
  [int32 × count: team assignments]
```

### Section 7: Difficulty Per Player
```
[int32: count]
  [int32 × count: difficulty level indices]
```

### Section 8: Civilizations
```
[int32: numCivs]
  [c5string × numCivs: civilization keys]
```
Values like `"CIVILIZATION_ROME"`, `"CIVILIZATION_RANDOM"`, empty string for unused slots.

### Section 9: Leaders
```
[int32: numLeaders]
  [c5string × numLeaders: leader keys]
```
Values like `"LEADER_AUGUSTUS"`, empty for unused slots.

## Sections 10–18: Game Configuration

These sections contain various game settings with many unknown fields:

| Data | Description |
|------|-------------|
| `currentPlayerIndex` (int32) | Index of the active player |
| Passwords section | `[int32: count] [c5string × count]` |
| `startingEraIndex` (int32) | Numeric era index |
| 68 unknown int32s | Game configuration values |
| 8 unknown c5strings | Configuration strings |
| 11 unknown int32s | More config values |

## Sections 19–23: Game State Metadata

| Data | Description |
|------|-------------|
| 64 player slot strings | Player color/config strings |
| `gameName` (c5string) | Lobby/save name |
| `timeOffset` (int32) | Time-related value |
| `gameStarted` (uint8) | Whether game has started |
| `turnNumber` (int32) | Turn number (repeated) |
| `randomSeed` (int32) | Random number generator seed |
| `numCityStates` (int32) | Number of city-states in game |

### Section 19: Max Turns
```
[int32: maxTurns]
```

### Section 21–23: Turn Timer
```
[int32: turnTimerLength]
```

## Sections 24–25: Player Colors and Multiplayer

```
[int32: count]
  [c5string × 64: player colour strings]
[uint8: privateGame]  (multiplayer only)
```

**Note**: For builds < 310700, player colors were stored as raw hex values (4 bytes each) instead of strings. This means the section delimiter `0x40000000` could appear as a valid color value, causing parsing issues.

## Sections 27–29: Victory Conditions

After some skip data and timer strings:

| Offset (from section start) | Type | Field |
|-----|------|-------|
| var | uint8 | timeVictory |
| var | uint8 | scienceVictory |
| var | uint8 | dominationVictory |
| var | uint8 | culturalVictory |
| var | uint8 | diplomaticVictory |

Each is a boolean (0 = disabled, 1 = enabled).

## Sections 28–30: Map and Game Options

Contains map size strings, help text keys, and a game options map:

```
[c5string: mapSize1]
[c5string: txtKeyMapHelp]
[8 bytes skip]
[c5string: mapSize2]
[c5string: txtKeyMapSize]
[c5string: mapSize3]
[bytes: worldInfo]
[gameOptionsMap: string→bool mapping]
```

The game options map uses keys like:
- `GAMEOPTION_NO_BARBARIANS`
- `GAMEOPTION_RAGING_BARBARIANS`
- `GAMEOPTION_COMPLETE_KILLS`
- `GAMEOPTION_NO_CITY_RAZING`
- `GAMEOPTION_NO_ESPIONAGE`
- etc.

## Section 32/33: Compressed Game State

The final section contains the full game state compressed with zlib.

### Identification
- Preceded by bytes `01 00` before the zlib magic `78 9C`
- The zlib magic bytes `0x78 0x9C` mark the start of the compressed stream

### Decompression
Standard zlib inflate. The decompressed data contains:
- Complete map/tile data
- Unit positions and state
- City data
- Diplomatic relationships
- Research progress
- Score history / replay data
- Game notes
- Great person notifications
- Histogram/replay datasets

### Decompressed Payload Structure

The decompressed data (~21 MB typical) contains sequential fields:

| Order | Type | Field | Notes |
|-------|------|-------|-------|
| 1 | int32 | unknown | Typically 1 |
| 2 | int32 | unknown | Typically 0 |
| 3 | int32 | currentTurn | Duplicate of header field |
| 4–5 | int32 | unknown | Zeros |
| 6 | int32 | startingYear | e.g. -4000 for 4000 BC |
| 7–8 | int32 | maxTurnCount | e.g. 500 |
| 9 | int32 | playTime | Deciseconds (with appended digit) |
| 10 | int32 | unknown | Zero |
| — | bytes | skip | 90 bytes |
| — | counted array | notes | [int32: count] + c5strings |
| — | counted array | cityNotifications | [int32: count] + c5strings |
| — | counted array | greatPersonNotifs | [int32: count] + c5strings |
| — | string-prefixed | replayData | Prefixed with `"REPLAYDATASET_SCORE"` |
| — | SQLite DB | gameDatabase | Standard SQLite, 1024-byte page size |

The map data appears in at least 3 duplicate locations within the decompressed payload.

### Map Header

Located within the decompressed payload (observed at offset `0x3851`). Identified by scanning for the pattern `[gridFlag=1] [valid_width] [valid_height]`.

```
[int32: gridFlag]       // Always 1
[int32: width]          // Map width in tiles (e.g. 80 for WORLDSIZE_SMALL)
[int32: height]         // Map height in tiles (e.g. 52)
[int32: numPlots]       // Number of special plots (≤ width×height)
[int32: numAreas]       // Number of distinct areas (e.g. 226)
[int32: numLandmasses]  // Number of landmasses (e.g. 6)
[int32: unknown]        // Observed: 90
[int32: unknown]        // Observed: -90
```

#### Map Sizes

| WORLDSIZE | Width | Height | Total Tiles |
|-----------|-------|--------|-------------|
| DUEL      | 40    | 24     | 960         |
| TINY      | 56    | 36     | 2016        |
| SMALL     | 66    | 42     | 2772        |
| STANDARD  | 80    | 52     | 4160        |
| LARGE     | 104   | 64     | 6656        |
| HUGE      | 128   | 80     | 10240       |

### Tile Data

Tile data follows the map header after approximately 1276 bytes of intervening data. Tiles are stored in row-major order (y=0 at south, increasing northward), left to right (x=0 at west).

Each tile occupies approximately **1569 bytes** for unexplored ocean tiles. Explored and land tiles with features, units, or improvements are larger (1569–2066+ bytes) due to variable-length fields.

#### Tile Structure (CvPlot)

Each tile corresponds to a serialized `CvPlot` object from the game engine. The structure contains 76+ fields, many of which are variable-length. Key landmarks within each tile:

##### First FF Block (Visibility Data) — offset ~+118 from tile start

```
[80 bytes: m_aiRevealedOwner[64] + m_bfRevealed[16]]
```

- 64 bytes: `m_aiRevealedOwner` — per-team revealed owner (0xFF = no owner, 0-22 = player index)
- 16 bytes: `m_bfRevealed` — bitfield, 2 bits per team (explored/visible flags)
- This block is identifiable as ~80 consecutive `0xFF` bytes for unexplored tiles

##### Builder AI Scratch Pad — offset ~+1027 from tile start

```
[int16: turnEvaluated]
```

- Updated by the AI each turn; increases by exactly **928** between consecutive turns
- Only present (non-zero) in tiles the AI has evaluated
- Useful for cross-save tile alignment (see Two-Save Method below)

##### Terrain Triplet — offset ~+1048 from tile start (FF block + 930)

```
[uint8: owner]          // 0xFF = unowned, 0-22 = owning player index
[uint8: plotType]       // 0=Land, 1=Hills, 2=Mountain, 3=Ocean
[uint8: terrainType]    // 0=Grass, 1=Plains, 2=Desert, 3=Tundra, 4=Snow, 5=Coast, 6=Ocean
[4 bytes: featureHash]  // Hashed feature type (forest, jungle, marsh, etc.)
```

#### Terrain Types

| Value | Constant | Description |
|-------|----------|-------------|
| 0 | TERRAIN_GRASS | Grassland |
| 1 | TERRAIN_PLAINS | Plains |
| 2 | TERRAIN_DESERT | Desert |
| 3 | TERRAIN_TUNDRA | Tundra |
| 4 | TERRAIN_SNOW | Snow |
| 5 | TERRAIN_COAST | Coastal water |
| 6 | TERRAIN_OCEAN | Deep ocean |

#### Plot Types

| Value | Constant | Description |
|-------|----------|-------------|
| 0 | PLOT_LAND | Flat land |
| 1 | PLOT_HILLS | Hills |
| 2 | PLOT_MOUNTAIN | Mountain (impassable) |
| 3 | PLOT_OCEAN | Water tile |

#### Tile Size Variability

Tile size varies based on content:

| Tile Type | Approximate Size | Notes |
|-----------|-----------------|-------|
| Unexplored ocean | 1569 bytes | Minimum tile size, all fixed fields |
| Explored ocean | ~1569 bytes | Same size, visibility fields populated |
| Explored land (empty) | ~1577 bytes | +8 bytes for exploration data |
| Land with features | 1600–2066+ bytes | Variable: units, improvements, routes |

The 8-byte expansion for explored land tiles causes cumulative offset drift when using fixed-stride parsing.

### Two-Save Extraction Method

For higher accuracy, two saves from **consecutive turns of the same game** can be compared:

1. Decompress both saves
2. Align first-tile offsets
3. Scan for 2-byte positions where `save2_value - save1_value == 928` (the builder AI scratch pad increment)
4. These positions precisely mark tile boundaries
5. Read terrain at known offset from each anchor point

This method finds ~1358 tiles (tiles the AI has evaluated). Remaining tiles use FF-block detection with stride-1569 interpolation to fill gaps.

### File Terminator
The file ends with the 4-byte sequence: `00 00 FF FF`.

## Build Version History

| Build | Version | Notable Format Changes |
|-------|---------|----------------------|
| 98650 | 1.0.0.0 | Initial release |
| 230620 | 1.0.1.135 | Major format changes, added version/build strings |
| 310700 | 1.0.2.x | Player colors changed from hex to strings |
| 341540 | 1.0.2.13 | |
| 395070 | 1.0.3.x | Added section 33 (now 33 sections total) |
| 403694 | 1.0.3.279 | Latest known format |

## Tools

| File | Description |
|------|-------------|
| `civ5.bt` | 010 Editor binary template for visual inspection |
| `civ5_parser.py` | Python parser that extracts header, player, and metadata |
| `civ5_map.py` | Map extractor — renders terrain from decompressed tile data |

## References

- [bmaupin/js-civ5save](https://github.com/bmaupin/js-civ5save) — JavaScript library with detailed property definitions
- [rivarolle/civ5-saveparser](https://github.com/rivarolle/civ5-saveparser) — Python parser with zlib decompression
- [pydt/civ5-save-parser](https://github.com/pydt/civ5-save-parser) — TypeScript parser for Play Your Damn Turn
- [bmaupin/civ5save-editor](https://github.com/bmaupin/civ5save-editor) — Web-based save editor
