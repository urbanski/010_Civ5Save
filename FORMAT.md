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

### Decompressed Payload Serialization Order

The compressed payload serializes game objects in this order (from SDK `CvGame::Read`, `CvMap::Read`, etc.):

1. **CvGame** — game-level state (turns, scores, random seeds, replay messages, deals)
2. **CvBarbarians** + **CvGoodyHuts** — supporting class data
3. **CvMap** — map header, all plots, areas, landmasses
4. **CvTeam[]** — all teams
5. **CvPlayer[]** — all players (each containing cities, units, AI subsystems)
6. **Embedded SQLite DB** — `Civ5SavedGameDatabase.db` (size-prefixed raw bytes)

Each class begins with a `uint uiVersion` for backward compatibility. There is **no tagged serialization** — fields are written/read in fixed order with no type markers or field IDs.

### CvMap Serialization (version = 1)

```
uint uiVersion          // = 1
int  m_iGridWidth       // Map width in tiles
int  m_iGridHeight      // Map height in tiles
int  m_iLandPlots       // Number of land plots
int  m_iOwnedPlots      // Number of owned plots
int  m_iNumNaturalWonders
int  m_iTopLatitude     // e.g. 90
int  m_iBottomLatitude  // e.g. -90
bool m_bWrapX           // Horizontal wrapping
bool m_bWrapY           // Vertical wrapping (always false)
GUID (16 bytes)         // Map GUID
HashedArray m_paiNumResource
HashedArray m_paiNumResourceOnLand
CvPlot[width×height]    // All tiles in row-major order (index = y*width + x)
CvArea[]                // Area containers
CvLandmass[]            // Landmass containers
int  m_iAIMapHints
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

### CvPlot Serialization (version = 8)

Each tile is a serialized `CvPlot` object (~1569 bytes for unexplored ocean, variable for land). Fields are written in this exact order with their precise C++ types:

```
uint   uiVersion                         // 4 bytes, = 8
short  m_iX                              // 2 bytes: tile X coordinate
short  m_iY                              // 2 bytes: tile Y coordinate
int    m_iArea                           // 4 bytes: area ID
char   m_iFeatureVariety                 // 1 byte: feature visual variant
short  m_iOwnershipDuration              // 2 bytes: turns owned
short  m_iImprovementDuration            // 2 bytes: turns improved
short  m_iUpgradeProgress                // 2 bytes: improvement upgrade progress
short  m_iCulture                        // 2 bytes: culture value
char   m_iNumMajorCivsRevealed           // 1 byte
char   m_iCityRadiusCount                // 1 byte
char   m_iReconCount                     // 1 byte
char   m_iRiverCrossingCount             // 1 byte
char   m_iResourceNum                    // 1 byte: resource quantity
char   m_cBuilderAIScratchPadPlayer      // 1 byte: AI scratch: which player
short  m_sBuilderAIScratchPadTurn        // 2 bytes: AI scratch: turn (changes by 928/turn)
short  m_sBuilderAIScratchPadValue       // 2 bytes: AI scratch: value (v6+)
int    m_eBuilderAIScratchPadRoute       // 4 bytes: AI scratch: route type (v6+)
int    m_iLandmass                       // 4 bytes: landmass ID
uint   m_uiTradeRouteBitFlags            // 4 bytes: trade route flags

bool   m_bStartingPlot                   // 1 byte
bool   m_bHills                          // 1 byte
bool   m_bNEOfRiver                      // 1 byte: river adjacency
bool   m_bWOfRiver                       // 1 byte
bool   m_bNWOfRiver                      // 1 byte
bool   m_bPotentialCityWork              // 1 byte
bool   m_bImprovementPillaged            // 1 byte
bool   m_bRoutePillaged                  // 1 byte
bool   m_bBarbCampNotConverting          // 1 byte
bool   m_bRoughFeature                   // 1 byte
bool   m_bResourceLinkedCityActive       // 1 byte
bool   m_bImprovedByGiftFromMajor        // 1 byte (v7+)

char   m_eOwner                          // 1 byte: 0xFF = unowned
char   m_ePlotType                       // 1 byte: 0=Land, 1=Hills, 2=Mountain, 3=Ocean
char   m_eTerrainType                    // 1 byte: 0=Grass..6=Ocean
hash   m_eFeatureType                    // 4+ bytes: hashed (v8+)
hash   m_eResourceType                   // 4+ bytes: hashed (v8+)
hash   m_eImprovementType               // 4+ bytes: hashed
hash   m_eImprovementTypeUnderConstruction // 4+ bytes: hashed
char   m_ePlayerBuiltImprovement         // 1 byte
char   m_ePlayerResponsibleForImprovement // 1 byte
char   m_ePlayerResponsibleForRoute      // 1 byte
char   m_ePlayerThatClearedBarbCampHere  // 1 byte
char   m_eRouteType                      // 1 byte
char   m_eWorldAnchor                    // 1 byte
char   m_cWorldAnchorData                // 1 byte
char   m_eRiverEFlowDirection            // 1 byte
char   m_eRiverSEFlowDirection           // 1 byte
char   m_eRiverSWFlowDirection           // 1 byte

// City references (owner:char + ID:int = 5 bytes each):
IDInfo m_plotCity                         // 5 bytes: city on this plot
IDInfo m_workingCity                      // 5 bytes: city working this plot
IDInfo m_workingCityOverride             // 5 bytes
IDInfo m_ResourceLinkedCity              // 5 bytes
IDInfo m_purchaseCity                    // 5 bytes

// Per-type arrays (MAX_TEAMS = MAX_PLAYERS = 64):
short  m_aiYield[6]                      // 12 bytes (food, prod, gold, sci, culture, faith)
int    m_aiFoundValue[64]                // 256 bytes: AI city founding value per player
char   m_aiPlayerCityRadiusCount[64]     // 64 bytes
short  m_aiVisibilityCount[64]           // 128 bytes: visibility per team
char   m_aiRevealedOwner[64]             // 64 bytes (0xFF = unknown) ← FF block

char   m_cRiverCrossing                  // 1 byte
DWORD  m_bfRevealed[4]                   // 16 bytes: packed bitfield (128 bits for 64 teams)

bool   m_abResourceForceReveal[64]       // 64 bytes
hash   m_aeRevealedImprovementType[64]   // variable: hashed per team
short  m_aeRevealedRouteType[64]         // 128 bytes
bool   m_abNoSettling[64]                // 64 bytes

// Variable-length fields:
bool   hasScriptData                     // 1 byte; if true: length-prefixed string follows
int    buildProgressCount                // 4 bytes; if > 0: hashed array follows
int[][]  m_apaiInvisibleVisibilityCount  // 2D array (MAX_TEAMS × NUM_INVISIBLE_TYPES)
uint   numUnits                          // 4 bytes: units on this plot
  for each: [char eOwner] [int iID]      // 5 bytes per unit
char   m_cContinentType                  // 1 byte
// m_kArchaeologyData                    // variable (BNW only)
```

Constants: `MAX_TEAMS` = `MAX_PLAYERS` = 64, `NUM_YIELD_TYPES` = 6 (BNW).

#### Tile Landmarks for Binary Parsing

Key landmarks within each tile for practical binary parsing:

##### FF Block (Revealed Owner + Revealed Bitfield) — offset ~+118 from tile start

```
[64 bytes: m_aiRevealedOwner]  // per-team, 0xFF for unrevealed
[1 byte:   m_cRiverCrossing]
[16 bytes: m_bfRevealed]       // 4 DWORDs packed bitfield
```

For unexplored tiles, the `m_aiRevealedOwner` entries are all `0xFF`, creating a distinctive ~80-byte run of `0xFF` bytes (64 + padding from adjacent zero fields) that serves as a reliable tile marker.

##### Builder AI Scratch Pad — offset ~+30 from tile start

```
[char:  m_cBuilderAIScratchPadPlayer]
[short: m_sBuilderAIScratchPadTurn]     // Changes by exactly 928 between consecutive turns
```

Useful for cross-save tile alignment (see Two-Save Method below).

##### Terrain Fields — offset ~+1048 from tile start (FF block + 930)

```
[char: m_eOwner]         // 0xFF = unowned, 0-22 = player index
[char: m_ePlotType]      // 0=Land, 1=Hills, 2=Mountain, 3=Ocean
[char: m_eTerrainType]   // 0=Grass, 1=Plains, 2=Desert, 3=Tundra, 4=Snow, 5=Coast, 6=Ocean
[uint: m_eFeatureType]   // Hashed feature (forest, jungle, etc.)
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
| Land with features | 1600–2066+ bytes | Variable: units, improvements, routes, script data |

The variable-length fields (script data, build progress, units on plot) cause tile size to vary. This means fixed-stride parsing loses alignment after encountering tiles with extra data.

### CvLandmass Serialization (version = 1)

```
uint uiVersion     // = 1
int  m_iID
int  m_iNumTiles
int  m_iCentroidX
int  m_iCentroidY
bool m_bWater
char m_cContinentType
```

### Two-Save Extraction Method

For higher accuracy, two saves from **consecutive turns of the same game** can be compared:

1. Decompress both saves
2. Align first-tile offsets
3. Scan for 2-byte positions where `save2_value - save1_value == 928` (the builder AI scratch pad increment)
4. These positions precisely mark tile boundaries
5. Read terrain at known offset from each anchor point

This method finds ~1358 tiles (tiles the AI has evaluated). Remaining tiles use FF-block detection with stride-1569 interpolation to fill gaps.

### Hashed Data Arrays

Later format versions (v8+ for CvPlot) serialize game info types by string hash rather than raw index. This makes saves resilient to XML/mod changes. Format:

```
[int32: count]
  repeated count times:
    [uint32: hash]    // Hash of the type's string key (e.g. hash of "RESOURCE_IRON")
    [value]           // The associated value (type depends on context)
```

Used for: `m_eFeatureType`, `m_eResourceType`, `m_eImprovementType`, and various arrays in CvCity, CvPlayer, and CvGame.

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
