#!/usr/bin/env python3
"""
Civilization V Save File Map Extractor

Extracts and renders the game map from a .Civ5Save file.
Decompresses the zlib game state and parses per-tile terrain data.

Usage:
    python3 civ5_map.py <savefile.Civ5Save>
    python3 civ5_map.py <savefile.Civ5Save> --json
    python3 civ5_map.py <savefile.Civ5Save> <savefile2.Civ5Save>  # two saves for better accuracy

The two-save mode uses consecutive turns of the same game to precisely
locate tile boundaries via binary diffing.
"""

import struct
import sys
import zlib
import json
import argparse
from pathlib import Path


# --- Constants ---

TERRAIN_TYPES = {
    0: "TERRAIN_GRASS",
    1: "TERRAIN_PLAINS",
    2: "TERRAIN_DESERT",
    3: "TERRAIN_TUNDRA",
    4: "TERRAIN_SNOW",
    5: "TERRAIN_COAST",
    6: "TERRAIN_OCEAN",
}

TERRAIN_CHARS = {
    0: 'G',  # Grassland
    1: 'P',  # Plains
    2: 'D',  # Desert
    3: 'T',  # Tundra
    4: 'S',  # Snow
    5: '~',  # Coast
    6: '.',  # Ocean
}

PLOT_TYPES = {
    0: "PLOT_LAND",
    1: "PLOT_HILLS",
    2: "PLOT_MOUNTAIN",
    3: "PLOT_OCEAN",
}


# --- Decompression ---

def find_zlib_offset(data: bytes) -> int:
    """Find the first valid zlib stream (magic 0x78 0x9C)."""
    search_from = 0
    while True:
        idx = data.find(b'\x78\x9c', search_from)
        if idx == -1:
            return -1
        try:
            zlib.decompress(data[idx:], 15)
            return idx
        except zlib.error:
            pass
        search_from = idx + 1
    return -1


def decompress_game_state(data: bytes) -> bytes:
    """Find and decompress the zlib game state from a save file."""
    zlib_offset = find_zlib_offset(data)
    if zlib_offset < 0:
        raise ValueError("No zlib stream found in save file")

    decompressor = zlib.decompressobj()
    result = b''
    chunk_size = 4096
    pos = zlib_offset
    while pos < len(data):
        end = min(pos + chunk_size, len(data))
        chunk = data[pos:end]
        try:
            result += decompressor.decompress(chunk)
        except zlib.error:
            break
        if decompressor.unused_data:
            break
        pos = end
    return result


# --- Map Header ---

def find_map_header(data: bytes) -> tuple:
    """Find the map header (gridFlag=1, width, height, numPlots) in decompressed data."""
    for i in range(len(data) - 16):
        vals = struct.unpack_from('<iiii', data, i)
        if vals[0] == 1 and 20 <= vals[1] <= 200 and 10 <= vals[2] <= 100:
            expected_plots = vals[1] * vals[2]
            # numPlots (field 4) should be less than total tiles
            if 0 < vals[3] <= expected_plots:
                return i, vals[1], vals[2]
    raise ValueError("Map header not found in decompressed data")


# --- Tile Detection ---

def find_first_tile(data: bytes, header_offset: int) -> int:
    """Find the first tile after the map header."""
    # First tile starts with 0x01 followed by zeros, then 80 FF bytes at +118
    for pos in range(header_offset + 32, header_offset + 2000):
        if data[pos] == 0x01 and all(data[pos + j] == 0 for j in range(1, 118)):
            if all(data[pos + 118 + j] == 0xFF for j in range(80)):
                return pos
    raise ValueError("First tile not found")


def find_tile_ff_blocks(data: bytes, start: int, end: int) -> list:
    """
    Find the first visibility FF block in each tile.

    Each tile contains an 80-byte block of 0xFF bytes (revealed owner array)
    preceded by a long run of zeros (the tile's fixed fields, mostly zero
    for unexplored tiles).

    Returns list of FF block positions.
    """
    blocks = []
    pos = start + 50

    while pos < end - 200:
        if data[pos] == 0xFF:
            # Count consecutive FFs
            ff_count = 0
            while pos + ff_count < end and data[pos + ff_count] == 0xFF:
                ff_count += 1

            # First FF block per tile is ~80 bytes (not 160+)
            if 78 <= ff_count <= 84:
                # Check preceded by mostly zeros
                pre_zeros = sum(1 for j in range(1, 80) if data[pos - j] == 0)
                if pre_zeros >= 60:
                    blocks.append(pos)
                    pos += 1000  # skip past this tile
                    continue
            pos += max(ff_count, 1)
        else:
            pos += 1

    return blocks


def find_anchor_tiles(data1: bytes, data2: bytes, ft1: int, ft2: int) -> list:
    """
    Find tile positions using two saves from consecutive turns.

    The builder AI scratch pad turn field changes by exactly 928 between
    consecutive turns. This gives precise tile positions.

    Returns list of (relative_offset, terrain, plot_type) tuples.
    """
    markers = []
    i = 0
    end = min(len(data1) - ft1, len(data2) - ft2) - 3

    while i < end:
        v1 = struct.unpack_from('<H', data1, ft1 + i)[0]
        v2 = struct.unpack_from('<H', data2, ft2 + i)[0]

        if v2 - v1 == 928:
            before_same = (i == 0) or (data1[ft1 + i - 1] == data2[ft2 + i - 1])
            after_same = (i + 2 >= end) or (data1[ft1 + i + 2] == data2[ft2 + i + 2])

            if before_same and after_same:
                terrain = data1[ft1 + i + 21]
                plot = data1[ft1 + i + 20]
                owner = data1[ft1 + i + 19]
                if terrain <= 6 and plot <= 3:
                    markers.append((i, terrain, plot, owner))
                i += 500
                continue
        i += 1

    return markers


# --- Map Extraction ---

# The terrain byte is located at a fixed offset from the first FF block
# in each tile: FF_block_position + 930 = owner byte, +931 = plot type,
# +932 = terrain type. This corresponds to approximately +1048 from tile start.
TERRAIN_DELTA = 930  # offset from FF block to owner/plot/terrain triplet


def extract_map_single(save_path: str) -> dict:
    """Extract map from a single save file."""
    raw = Path(save_path).read_bytes()
    decompressed = decompress_game_state(raw)

    header_off, width, height = find_map_header(decompressed)
    total_tiles = width * height

    # Find replay data as end boundary
    replay_off = decompressed.find(b'REPLAYDATASET_SCORE')
    end_boundary = replay_off if replay_off > 0 else len(decompressed)

    # Find FF blocks (tile markers)
    first_tile = find_first_tile(decompressed, header_off)
    ff_blocks = find_tile_ff_blocks(decompressed, first_tile - 10, end_boundary)

    # Extract terrain from found tiles, interpolate gaps
    tiles = _build_tile_array(decompressed, ff_blocks, total_tiles)

    return {
        'width': width,
        'height': height,
        'tiles': tiles,
        'tiles_found': len(ff_blocks),
        'tiles_total': total_tiles,
    }


def extract_map_dual(save_path1: str, save_path2: str) -> dict:
    """Extract map using two consecutive saves for better accuracy."""
    raw1 = Path(save_path1).read_bytes()
    raw2 = Path(save_path2).read_bytes()
    dec1 = decompress_game_state(raw1)
    dec2 = decompress_game_state(raw2)

    h1_off, width, height = find_map_header(dec1)
    h2_off, _, _ = find_map_header(dec2)
    total_tiles = width * height

    ft1 = find_first_tile(dec1, h1_off)
    ft2 = find_first_tile(dec2, h2_off)

    replay_off = dec1.find(b'REPLAYDATASET_SCORE')
    end_boundary = replay_off if replay_off > 0 else len(dec1)

    # Find anchor tiles from binary diff
    anchors = find_anchor_tiles(dec1, dec2, ft1, ft2)

    # Find FF blocks for non-anchor tiles
    ff_blocks = find_tile_ff_blocks(dec1, ft1 - 10, end_boundary)

    # Build tile array combining anchors and FF blocks
    tiles = _build_tile_array_with_anchors(dec1, ff_blocks, anchors, ft1, total_tiles)

    return {
        'width': width,
        'height': height,
        'tiles': tiles,
        'tiles_found': len(ff_blocks),
        'anchor_tiles': len(anchors),
        'tiles_total': total_tiles,
    }


def _build_tile_array(data: bytes, ff_blocks: list, total_tiles: int) -> list:
    """Build terrain array from FF block positions, interpolating gaps."""
    tiles = []

    for i, ff in enumerate(ff_blocks):
        terrain = data[ff + TERRAIN_DELTA] if ff + TERRAIN_DELTA < len(data) else -1
        plot = data[ff + TERRAIN_DELTA + 1] if ff + TERRAIN_DELTA + 1 < len(data) else -1
        owner = data[ff + TERRAIN_DELTA - 1] if ff + TERRAIN_DELTA - 1 < len(data) else -1

        tiles.append({
            'terrain': terrain if terrain <= 6 else -1,
            'plotType': plot if plot <= 3 else -1,
            'owner': owner,
        })

        # Fill gaps between this and next FF block
        if i < len(ff_blocks) - 1:
            spacing = ff_blocks[i + 1] - ff
            num_in_gap = round(spacing / 1569)
            for j in range(1, num_in_gap):
                interp_ff = ff + j * 1569
                t = data[interp_ff + TERRAIN_DELTA] if interp_ff + TERRAIN_DELTA < len(data) else -1
                p = data[interp_ff + TERRAIN_DELTA + 1] if interp_ff + TERRAIN_DELTA + 1 < len(data) else -1
                o = data[interp_ff + TERRAIN_DELTA - 1] if interp_ff + TERRAIN_DELTA - 1 < len(data) else -1
                tiles.append({
                    'terrain': t if t <= 6 else -1,
                    'plotType': p if p <= 3 else -1,
                    'owner': o,
                })

    # Extrapolate remaining tiles
    while len(tiles) < total_tiles:
        last_ff = ff_blocks[-1] if ff_blocks else 0
        n = len(tiles) - len(ff_blocks) + 1
        ext_ff = last_ff + n * 1569
        t = data[ext_ff + TERRAIN_DELTA] if ext_ff + TERRAIN_DELTA < len(data) else -1
        p = data[ext_ff + TERRAIN_DELTA + 1] if ext_ff + TERRAIN_DELTA + 1 < len(data) else -1
        o = data[ext_ff + TERRAIN_DELTA - 1] if ext_ff + TERRAIN_DELTA - 1 < len(data) else -1
        tiles.append({
            'terrain': t if t <= 6 else -1,
            'plotType': p if p <= 3 else -1,
            'owner': o,
        })

    return tiles[:total_tiles]


def _build_tile_array_with_anchors(data: bytes, ff_blocks: list,
                                    anchors: list, ft1: int,
                                    total_tiles: int) -> list:
    """Build terrain array using both FF blocks and anchor positions."""
    # First build from FF blocks
    tiles = _build_tile_array(data, ff_blocks, total_tiles)

    # Override with anchor data where available
    # Build calibration from anchors
    if anchors:
        # Assign tile indices to anchors
        anchor_indices = [0]
        for j in range(1, len(anchors)):
            spacing = anchors[j][0] - anchors[j - 1][0]
            num_tiles = round(spacing / 1569)
            anchor_indices.append(anchor_indices[-1] + num_tiles)

        for j, (offset, terrain, plot, owner) in enumerate(anchors):
            idx = anchor_indices[j]
            if 0 <= idx < total_tiles:
                tiles[idx] = {
                    'terrain': terrain,
                    'plotType': plot,
                    'owner': owner,
                }

    return tiles


# --- Rendering ---

def render_ascii(map_data: dict) -> str:
    """Render map as ASCII art."""
    width = map_data['width']
    height = map_data['height']
    tiles = map_data['tiles']

    lines = []
    lines.append(f"=== Civilization V Map ({width}x{height}) ===")
    lines.append(f"Tiles: {map_data.get('tiles_found', '?')}/{map_data['tiles_total']}")
    lines.append(f"Legend: G=Grass P=Plains D=Desert T=Tundra S=Snow ~=Coast .=Ocean ?=Unknown")
    lines.append("")

    for y in range(height - 1, -1, -1):
        row = ''
        for x in range(width):
            idx = y * width + x
            if idx < len(tiles):
                t = tiles[idx]['terrain']
                row += TERRAIN_CHARS.get(t, '?')
            else:
                row += ' '
        lines.append(f"{y:2d} {row}")

    return '\n'.join(lines)


def map_to_json(map_data: dict) -> dict:
    """Convert map data to JSON-serializable format."""
    result = {
        'width': map_data['width'],
        'height': map_data['height'],
        'tilesFound': map_data.get('tiles_found', 0),
        'tilesTotal': map_data['tiles_total'],
        'terrain': [],
        'plotTypes': [],
    }

    for tile in map_data['tiles']:
        result['terrain'].append(tile['terrain'])
        result['plotTypes'].append(tile['plotType'])

    # Add terrain type counts
    from collections import Counter
    terrain_counts = Counter(t['terrain'] for t in map_data['tiles'])
    result['terrainCounts'] = {
        TERRAIN_TYPES.get(t, f'UNKNOWN({t})'): c
        for t, c in sorted(terrain_counts.items())
    }

    return result


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description='Extract and render maps from Civilization V save files'
    )
    parser.add_argument('savefile', help='Path to .Civ5Save file')
    parser.add_argument('savefile2', nargs='?', default=None,
                        help='Optional second save (consecutive turn) for better accuracy')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output as JSON')
    args = parser.parse_args()

    if args.savefile2:
        print(f"Extracting map using dual-save mode...", file=sys.stderr)
        map_data = extract_map_dual(args.savefile, args.savefile2)
    else:
        print(f"Extracting map from {args.savefile}...", file=sys.stderr)
        map_data = extract_map_single(args.savefile)

    if args.json:
        print(json.dumps(map_to_json(map_data), indent=2))
    else:
        print(render_ascii(map_data))


if __name__ == '__main__':
    main()
