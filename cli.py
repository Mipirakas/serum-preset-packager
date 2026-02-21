#!/usr/bin/env python3
import sys, json, struct, pathlib, cbor2, zstandard as zstd, os, tempfile, subprocess
from typing import Any

MAGIC = b"XferJson\x00"
DECOMPRESSOR = zstd.ZstdDecompressor()
COMPRESSOR = zstd.ZstdCompressor(level=3)

def decodeFromSerumPreset(buf: bytes) -> dict[str, Any]:
    off = len(MAGIC)
    jlen, _ = struct.unpack_from("<II", buf, off); off += 8
    meta = json.loads(buf[off:off + jlen]); off += jlen
    clen, _ = struct.unpack_from("<II", buf, off); off += 8
    cbor = DECOMPRESSOR.decompress(buf[off:])
    assert len(cbor) == clen
    return {"metadata": meta, "data": cbor2.loads(cbor)}

def encodeToSerumPreset(obj: dict[str, Any]) -> bytes:
    m = json.dumps(obj["metadata"], separators=(",", ":")).encode()
    c = cbor2.dumps(obj["data"])
    z = COMPRESSOR.compress(c)
    out = bytearray()
    out += MAGIC
    out += struct.pack("<II", len(m), 0)
    out += m
    out += struct.pack("<II", len(c), 2)
    out += z
    return out

def unpack(src: pathlib.Path, dst: pathlib.Path):
    buf = src.read_bytes()
    data = decodeFromSerumPreset(buf)
    dst.write_text(json.dumps(data, indent=2))

def pack(src: pathlib.Path, dst: pathlib.Path):
    obj = json.loads(src.read_text())
    out = encodeToSerumPreset(obj)
    dst.write_bytes(out)

def edit(preset: pathlib.Path):
    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmp_path = pathlib.Path(tmp.name)

    try:
        # Unpack preset to temporary JSON file
        unpack(preset, tmp_path)

        # Open editor
        subprocess.run([editor, str(tmp_path)], check=True)

        # Pack modified JSON back to preset
        pack(tmp_path, preset)
    finally:
        # Clean up temporary file
        tmp_path.unlink(missing_ok=True)

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in {"unpack", "pack", "edit"}:
        print("usage: cli.py unpack <file.SerumPreset> <out.json>\n"
              "       cli.py pack   <in.json>         <out.SerumPreset>\n"
              "       cli.py edit   <file.SerumPreset>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "edit":
        if len(sys.argv) != 3:
            print("usage: cli.py edit <file.SerumPreset>")
            sys.exit(1)
        edit(pathlib.Path(sys.argv[2]))
    else:
        if len(sys.argv) != 4:
            print("usage: cli.py {} <input> <output>".format(cmd))
            sys.exit(1)
        (unpack if cmd == "unpack" else pack)(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]))
