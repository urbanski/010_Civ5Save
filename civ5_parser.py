#!/usr/bin/env python3
"""
Civilization V Save File Parser (.Civ5Save)

Parses the uncompressed header sections and can decompress
the zlib-compressed game state from a Civ5 save file.

Usage:
    python3 civ5_parser.py <savefile.Civ5Save> [--dump-compressed <outfile>]
"""

import struct
import sys
import zlib
import json
import argparse
from pathlib import Path

# Section delimiter: 0x40000000 in little-endian
SECTION_DELIMITER = b'\x40\x00\x00\x00'

# Player status enum
PLAYER_STATUS = {
    1: "AI",
    2: "Dead",
    3: "Human",
    4: "None",
}

# Game mode enum
GAME_MODE = {
    0: "Single Player",
    1: "Multiplayer",
    2: "Hotseat",
}


class BinaryReader:
    """Simple binary reader with position tracking."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read_bytes(self, n: int) -> bytes:
        result = self.data[self.pos:self.pos + n]
        self.pos += n
        return result

    def read_int32(self) -> int:
        val = struct.unpack_from('<i', self.data, self.pos)[0]
        self.pos += 4
        return val

    def read_uint32(self) -> int:
        val = struct.unpack_from('<I', self.data, self.pos)[0]
        self.pos += 4
        return val

    def read_byte(self) -> int:
        val = self.data[self.pos]
        self.pos += 1
        return val

    def read_c5string(self) -> str:
        length = self.read_int32()
        if length <= 0:
            return ""
        raw = self.read_bytes(length)
        return raw.decode('utf-8', errors='replace')

    def read_c5string_array(self, count: int) -> list:
        return [self.read_c5string() for _ in range(count)]

    def skip(self, n: int):
        self.pos += n

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def peek_bytes(self, n: int) -> bytes:
        return self.data[self.pos:self.pos + n]


def find_section_offsets(data: bytes) -> list:
    """Find all section delimiter offsets in the file."""
    offsets = []
    search_from = 0
    while True:
        idx = data.find(SECTION_DELIMITER, search_from)
        if idx == -1:
            break
        offsets.append(idx)
        search_from = idx + 4
    return offsets


def find_zlib_offset(data: bytes) -> int:
    """Find the first zlib stream (magic 0x78 0x9C) in the data."""
    search_from = 0
    while True:
        idx = data.find(b'\x78\x9c', search_from)
        if idx == -1:
            return -1
        # Verify it's actually zlib by trying to decompress a small chunk
        try:
            zlib.decompress(data[idx:idx + 256], 15)
            return idx
        except zlib.error:
            pass
        # Try with more data
        try:
            zlib.decompress(data[idx:], 15)
            return idx
        except zlib.error:
            pass
        search_from = idx + 1
    return -1


def decompress_zlib_stream(data: bytes, offset: int) -> bytes:
    """Decompress a zlib stream starting at offset."""
    decompressor = zlib.decompressobj()
    result = b''
    chunk_size = 4096
    pos = offset
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


def parse_header(reader: BinaryReader) -> dict:
    """Parse Section 1: File header."""
    header = {}

    magic = reader.read_bytes(4)
    header['magic'] = magic.decode('ascii', errors='replace')
    if magic != b'CIV5':
        print(f"WARNING: Expected 'CIV5' magic, got {magic!r}", file=sys.stderr)

    header['saveGameVersion'] = reader.read_int32()
    header['gameVersion'] = reader.read_c5string()
    header['gameBuild'] = reader.read_c5string()
    header['currentTurn'] = reader.read_int32()
    mode = reader.read_byte()
    header['gameMode'] = GAME_MODE.get(mode, f"Unknown({mode})")
    header['gameModeRaw'] = mode
    header['player1Civilization'] = reader.read_c5string()
    header['difficulty'] = reader.read_c5string()
    header['startingEra'] = reader.read_c5string()
    header['currentEra'] = reader.read_c5string()
    header['gamePace'] = reader.read_c5string()
    header['mapSize'] = reader.read_c5string()
    header['mapFile'] = reader.read_c5string()

    return header


def parse_dlc(reader: BinaryReader) -> list:
    """Parse DLC/expansion entries."""
    num_dlc = reader.read_int32()
    dlcs = []
    for _ in range(num_dlc):
        dlc_id = reader.read_bytes(16)
        dlc_version = reader.read_int32()
        dlc_name = reader.read_c5string()
        dlcs.append({
            'id': dlc_id.hex(),
            'version': dlc_version,
            'name': dlc_name,
        })
    return dlcs


def parse_mods(reader: BinaryReader) -> list:
    """Parse mod entries."""
    num_mods = reader.read_int32()
    mods = []
    for _ in range(num_mods):
        mod_id = reader.read_bytes(16)
        mod_version = reader.read_int32()
        mod_name = reader.read_c5string()
        mods.append({
            'id': mod_id.hex(),
            'version': mod_version,
            'name': mod_name,
        })
    return mods


def parse_player_data(reader: BinaryReader) -> dict:
    """Parse player-related sections (names, statuses, civs, leaders, etc.)."""
    players = {}

    # Two unknown strings
    players['_postModStr1'] = reader.read_c5string()
    players['_postModStr2'] = reader.read_c5string()

    # Player 1 color
    players['player1Color'] = reader.read_c5string()

    # Unknown block (41 bytes)
    reader.skip(41)

    # 4 unknown ints
    reader.skip(4 * 4)

    # Map file path (repeated)
    players['mapFilePath'] = reader.read_c5string()

    # Player names section (preceded by section delimiter often)
    # We look for the int count
    num_players = reader.read_int32()
    if num_players < 0 or num_players > 128:
        # Might have hit a section delimiter, adjust
        print(f"WARNING: Unexpected numPlayers={num_players}, may need format adjustment", file=sys.stderr)
        players['playerNames'] = []
    else:
        players['playerNames'] = reader.read_c5string_array(num_players)

    # Player statuses (64 slots)
    num_statuses = reader.read_int32()
    statuses = []
    for _ in range(min(num_statuses, 64)):
        raw = reader.read_int32()
        statuses.append(PLAYER_STATUS.get(raw, f"Unknown({raw})"))
    players['playerStatuses'] = statuses

    # Regions
    num_regions = reader.read_int32()
    players['regions'] = [reader.read_int32() for _ in range(num_regions)]

    # Teams
    num_teams = reader.read_int32()
    players['teams'] = [reader.read_int32() for _ in range(num_teams)]

    # Difficulties
    num_diffs = reader.read_int32()
    players['difficulties'] = [reader.read_int32() for _ in range(num_diffs)]

    # Civilizations
    num_civs = reader.read_int32()
    players['civilizations'] = reader.read_c5string_array(num_civs)

    # Leaders
    num_leaders = reader.read_int32()
    players['leaders'] = reader.read_c5string_array(num_leaders)

    return players


def parse_save(filepath: str, dump_compressed: str = None) -> dict:
    """Parse a Civ5 save file and return structured data."""
    data = Path(filepath).read_bytes()
    reader = BinaryReader(data)
    result = {}

    # Parse header
    result['header'] = parse_header(reader)

    # Parse DLC
    result['dlc'] = parse_dlc(reader)

    # Parse mods
    result['mods'] = parse_mods(reader)

    # Parse player data
    result['players'] = parse_player_data(reader)

    # Section delimiter analysis
    section_offsets = find_section_offsets(data)
    result['_sectionDelimiters'] = {
        'count': len(section_offsets),
        'offsets': [f"0x{off:X}" for off in section_offsets],
    }

    # Find and optionally decompress zlib data
    zlib_offset = find_zlib_offset(data)
    if zlib_offset >= 0:
        result['_compressedData'] = {
            'zlibOffset': f"0x{zlib_offset:X}",
            'zlibOffsetDecimal': zlib_offset,
            'compressedSize': len(data) - zlib_offset,
        }
        if dump_compressed:
            decompressed = decompress_zlib_stream(data, zlib_offset)
            Path(dump_compressed).write_bytes(decompressed)
            result['_compressedData']['decompressedSize'] = len(decompressed)
            result['_compressedData']['dumpedTo'] = dump_compressed
            print(f"Decompressed {len(decompressed)} bytes -> {dump_compressed}", file=sys.stderr)
    else:
        result['_compressedData'] = None

    result['_fileSize'] = len(data)
    result['_parseEndOffset'] = f"0x{reader.pos:X}"

    return result


def main():
    parser = argparse.ArgumentParser(description='Parse Civilization V save files')
    parser.add_argument('savefile', help='Path to .Civ5Save file')
    parser.add_argument('--dump-compressed', '-d', metavar='OUTFILE',
                        help='Decompress and dump the zlib game state to a file')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output as JSON (default)')
    parser.add_argument('--summary', '-s', action='store_true',
                        help='Print a human-readable summary')
    args = parser.parse_args()

    result = parse_save(args.savefile, args.dump_compressed)

    if args.summary:
        h = result['header']
        print(f"=== Civilization V Save File ===")
        print(f"Game Version:  {h['gameVersion']} (build {h['gameBuild']})")
        print(f"Save Version:  {h['saveGameVersion']}")
        print(f"Turn:          {h['currentTurn']}")
        print(f"Game Mode:     {h['gameMode']}")
        print(f"Player 1 Civ:  {h['player1Civilization']}")
        print(f"Difficulty:    {h['difficulty']}")
        print(f"Starting Era:  {h['startingEra']}")
        print(f"Current Era:   {h['currentEra']}")
        print(f"Game Pace:     {h['gamePace']}")
        print(f"Map Size:      {h['mapSize']}")
        print(f"Map File:      {h['mapFile']}")
        print()

        if result['dlc']:
            print(f"DLC ({len(result['dlc'])}):")
            for d in result['dlc']:
                print(f"  - {d['name']}")
            print()

        if result['mods']:
            print(f"Mods ({len(result['mods'])}):")
            for m in result['mods']:
                print(f"  - {m['name']}")
            print()

        p = result['players']
        if p.get('playerNames'):
            print(f"Players:")
            for i, name in enumerate(p['playerNames']):
                status = p['playerStatuses'][i] if i < len(p.get('playerStatuses', [])) else '?'
                civ = p['civilizations'][i] if i < len(p.get('civilizations', [])) else '?'
                leader = p['leaders'][i] if i < len(p.get('leaders', [])) else '?'
                if name or (isinstance(status, str) and status not in ('None',)):
                    print(f"  [{i}] {name or '(unnamed)'} | {status} | {civ} | {leader}")
            print()

        cd = result['_compressedData']
        if cd:
            print(f"Compressed Data: offset {cd['zlibOffset']}, {cd['compressedSize']} bytes")
        print(f"Section Delimiters: {result['_sectionDelimiters']['count']} found")
        print(f"File Size: {result['_fileSize']} bytes")
    else:
        print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
