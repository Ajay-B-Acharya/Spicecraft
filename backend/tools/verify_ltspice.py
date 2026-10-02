"""Verify exported ASC connectivity using LTspice's real, non-simulated netlist.

This does not build source nets or interpret wire intersections. Callers supply
an expected partition of canonical ``Component.Pin`` strings, including singleton
sets for unwired pins. Node names are deliberately irrelevant to partition
comparison. Use ``parse_netlist(asc_text, netlist_text)`` to obtain the independent
actual mapping; stock ASY SpiceOrder is matched to canonical pin_maps geometry.

CLI: python backend/tools/verify_ltspice.py input.asc --artifacts TEMP_DIRECTORY
     [--expected expected_pin_groups.json] [--executable /path/to/LTspice]
Expected JSON is a list of pin lists or an object mapping group names to pin lists.
Only the explicitly supplied artifacts directory receives LTspice output.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable, Mapping, Sequence

# Also support direct execution from outside the backend working directory.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.pin_maps import COMPONENT_LIBRARY, ComponentDefinition


def discover_ltspice_executable() -> Path | None:
    """Find a runnable LTspice binary; an invalid explicit override is an error."""
    override = os.environ.get("LTSPICE_EXECUTABLE")
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"LTSPICE_EXECUTABLE is not a file: {path}")
        return path.resolve()
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
    candidates = [local / "Programs/ADI/LTspice/LTspice.exe"]
    for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if root:
            candidates.extend(Path(root) / suffix for suffix in (
                "ADI/LTspice/LTspice.exe", "Analog Devices/LTspice/LTspice.exe",
                "LTC/LTspiceXVII/XVIIx64.exe", "LTC/LTspiceXVII/XVIIx86.exe",
                "LTC/LTspiceIV/scad3.exe",
            ))
    candidates.extend([
        Path("/Applications/LTspice.app/Contents/MacOS/LTspice"),
        home / "Applications/LTspice.app/Contents/MacOS/LTspice",
    ])
    for name in ("LTspice.exe", "XVIIx64.exe", "ltspice", "LTspice"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    return next((path.resolve() for path in candidates if path.is_file()), None)


def discover_symbol_roots(executable: str | Path | None = None) -> list[Path]:
    """Existing stock symbol directories for modern Windows, legacy, and macOS."""
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
    candidates = [local / "LTspice/lib/sym", home / "Documents/LTspice/lib/sym",
                  home / "Documents/LTspiceXVII/lib/sym",
                  home / "Library/Application Support/LTspice/lib/sym",
                  home / ".local/share/LTspice/lib/sym",
                  Path("/Applications/LTspice.app/Contents/Resources/lib/sym"),
                  Path("/Applications/LTspice.app/Contents/lib/sym")]
    exe = Path(executable) if executable else discover_ltspice_executable()
    if exe:
        candidates[:0] = [exe.parent / "lib/sym", exe.parent.parent / "Resources/lib/sym"]
    return list(dict.fromkeys(path.resolve() for path in candidates if path.is_dir()))


def read_ltspice_text(path: str | Path) -> str:
    """Read UTF-8, BOM-marked UTF-16, or legacy Windows ANSI LTspice files."""
    data = Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def run_ltspice_netlist(
    asc_path: str | Path,
    artifacts_dir: str | Path,
    *,
    executable: str | Path | None = None,
    timeout: float = 30,
) -> Path:
    """Copy ASC into caller-owned artifacts, run ``-netlist <absolute.asc>``.

    No simulation, system settings, or libraries are changed. The input ASC and
    adjacent outputs are untouched unless they already reside in artifacts_dir.
    Nonzero exits, missing/empty output, and timeouts are failures, not a pass.
    """
    source = Path(asc_path).expanduser().resolve(strict=True)
    if source.suffix.lower() != ".asc":
        raise ValueError("LTspice netlisting requires an .asc input")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    exe = Path(executable).expanduser() if executable else discover_ltspice_executable()
    if exe is None or not exe.is_file():
        raise FileNotFoundError("LTspice not found; set LTSPICE_EXECUTABLE")
    directory = Path(artifacts_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / source.name
    if source != target:
        shutil.copy2(source, target)
    output = target.with_suffix(".net")
    # Never allow stale output to turn a failed invocation into success.
    output.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            [str(exe.resolve()), "-netlist", str(target)], cwd=directory,
            capture_output=True, text=True, errors="replace", timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"LTspice netlisting timed out after {timeout}s: {target}") from exc
    if result.returncode != 0:
        raise RuntimeError(f"LTspice exited {result.returncode}: "
                           f"{result.stderr.strip() or result.stdout.strip()}")
    if not output.is_file() or not output.stat().st_size:
        raise RuntimeError(f"LTspice did not produce a nonempty netlist: {output}")
    return output


@dataclass(frozen=True)
class _Symbol:
    instance: str
    definition: ComponentDefinition
    path: Path


def _symbol_path(name: str, roots: Sequence[Path]) -> Path:
    relative = Path(name.replace("\\", "/") + ".asy")
    for root in roots:
        candidate = root / relative
        if candidate.is_file():
            return candidate
        # Stock LED.asy versus ASC 'led': case-sensitive installations also work.
        current = root
        for part in relative.parts:
            if not current.is_dir():
                break
            current = next((p for p in current.iterdir() if p.name.casefold() == part.casefold()),
                           current / part)
        if current.is_file():
            return current
    raise FileNotFoundError(f"Stock symbol {relative} not found in {list(roots)}")


def _asc_symbols(asc_text: str, roots: Sequence[Path]) -> list[_Symbol]:
    lookup = {definition.symbol.replace("\\", "/").casefold(): definition
              for definition in COMPONENT_LIBRARY.values()}
    blocks: list[tuple[str, dict[str, str]]] = []
    for raw in asc_text.splitlines():
        fields = raw.strip().split(maxsplit=2)
        if not fields:
            continue
        if fields[0].upper() == "SYMBOL":
            if len(raw.split()) != 5:
                raise ValueError(f"Malformed ASC SYMBOL: {raw}")
            blocks.append((fields[1], {}))
        elif fields[0].upper() == "SYMATTR" and blocks and len(fields) == 3:
            blocks[-1][1][fields[1].casefold()] = fields[2]
    symbols = []
    seen = set()
    for name, attrs in blocks:
        instance = attrs.get("instname", "").strip()
        if not instance or len(instance.split()) != 1:
            raise ValueError(f"Missing/invalid InstName for SYMBOL {name}")
        if instance.casefold() in seen:
            raise ValueError(f"Duplicate ASC instance: {instance}")
        seen.add(instance.casefold())
        definition = lookup.get(name.replace("\\", "/").casefold())
        if definition is None:
            raise ValueError(f"Unsupported ASC symbol: {name}; cannot verify its pins")
        symbols.append(_Symbol(instance, definition, _symbol_path(name, roots)))
    if not symbols:
        raise ValueError("ASC contains no supported component instances")
    return symbols


def _spice_orders(symbol: _Symbol) -> dict[str, int]:
    # Match physical ASY pins to canonical definitions, not guessed token counts
    # or PinName aliases (e.g. NE555 uses THRS, RST, CV in the stock symbol).
    coordinates: dict[tuple[int, int], int] = {}
    position = None
    for raw in read_ltspice_text(symbol.path).splitlines():
        fields = raw.split()
        if fields and fields[0].upper() == "PIN":
            position = (int(fields[1]), int(fields[2]))
        elif len(fields) == 3 and fields[:2] == ["PINATTR", "SpiceOrder"]:
            if position is None or position in coordinates:
                raise ValueError(f"Invalid/duplicate ASY SpiceOrder: {symbol.path}")
            coordinates[position] = int(fields[2])
    orders = {}
    for pin in symbol.definition.pins:
        order = coordinates.get((pin.x, pin.y))
        if order is None or order < 1:
            raise ValueError(f"No ASY SpiceOrder for {symbol.instance}.{pin.id}")
        orders[pin.id] = order
    if len(set(orders.values())) != len(orders):
        raise ValueError(f"Duplicate ASY terminal orders: {symbol.path}")
    return orders


def _device_lines(netlist_text: str) -> list[list[str]]:
    logical: list[str] = []
    for raw in netlist_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        line = line.split(";", 1)[0].strip()
        if line.startswith("+"):
            if not logical:
                raise ValueError("Netlist continuation without preceding line")
            logical[-1] += " " + line[1:].strip()
        elif line:
            logical.append(line)
    devices = []
    depth = 0
    for line in logical:
        tokens = line.split()
        command = tokens[0].casefold()
        if command == ".subckt":
            depth += 1
        elif command == ".ends":
            depth -= 1
            if depth < 0:
                raise ValueError("Unmatched .ends in netlist")
        elif not depth and not command.startswith("."):
            devices.append(tokens)
    if depth:
        raise ValueError("Unterminated .subckt in netlist")
    return devices


def parse_netlist(
    asc_text: str,
    netlist_text: str,
    *,
    symbol_roots: Iterable[str | Path] | None = None,
) -> dict[str, str]:
    """Map actual exported pins to LTspice node tokens, in ASC/canonical order.

    Reads ASC SYMBOL/InstName, then real stock ASY PINATTR SpiceOrder. Handles
    case-insensitive device names and LTspice's X§U1/subcircuit prefix spelling.
    BJT fourth substrate terminals are NOT canonical component pins. Unknown
    symbols, missing/duplicate devices, or truncated lines fail explicitly.
    Call with read_ltspice_text(path), not filenames, for the two text arguments.
    """
    roots = ([Path(root) for root in symbol_roots] if symbol_roots is not None
             else discover_symbol_roots())
    devices = _device_lines(netlist_text)
    actual: dict[str, str] = {}
    for symbol in _asc_symbols(asc_text, roots):
        orders = _spice_orders(symbol)
        instance = symbol.instance.casefold()
        aliases = {instance, "x" + instance}
        matches = [tokens for tokens in devices
                   if tokens[0].casefold() in aliases
                   or ("§" in tokens[0] and tokens[0].split("§", 1)[1].casefold() == instance)]
        if len(matches) != 1:
            raise ValueError(f"Expected one netlist device for {symbol.instance}; found {len(matches)}")
        tokens = matches[0]
        if len(tokens) < max(orders.values()) + 2:
            raise ValueError(f"Truncated netlist device: {' '.join(tokens)}")
        for pin, order in orders.items():
            actual[f"{symbol.instance}.{pin}"] = tokens[order]
    return actual


@dataclass(frozen=True)
class PartitionReport:
    """Deterministic differences; shorts merge groups, opens split one group."""
    shorts: tuple[dict, ...]
    opens: tuple[dict, ...]
    missing_pins: tuple[str, ...]
    unexpected_pins: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (self.shorts or self.opens or self.missing_pins or self.unexpected_pins)

    def to_dict(self) -> dict:
        return {"ok": self.ok, **asdict(self)}


def compare_partitions(
    expected: Mapping[str, Iterable[str]] | Iterable[Iterable[str]],
    actual: Mapping[str, str],
) -> PartitionReport:
    """Compare supplied canonical pin sets to independently netlisted node sets.

    Does not consult source wires, exporter geometry, or NetBuilder. Supply all
    canonical pins, including unwired singleton groups, for a complete check.
    Group and LTspice node names need not match; their membership must match.
    A pin absent from LTspice is missing, not silently dropped from comparison.
    """
    groups = ({str(name): set(pins) for name, pins in expected.items()}
              if isinstance(expected, Mapping)
              else {f"group-{index}": set(pins) for index, pins in enumerate(expected, 1)})
    owner: dict[str, str] = {}
    for name, pins in groups.items():
        for pin in pins:
            if not isinstance(pin, str) or "." not in pin:
                raise ValueError(f"Expected canonical Component.Pin, got {pin!r}")
            if pin in owner:
                raise ValueError(f"Expected partition repeats pin {pin}")
            owner[pin] = name
    nodes: dict[str, list[str]] = {}
    for pin, node in actual.items():
        if not isinstance(node, str) or not node.strip():
            raise ValueError(f"Invalid actual node for {pin}: {node!r}")
        nodes.setdefault(node.casefold(), []).append(pin)
    shorts = []
    for node, pins in sorted(nodes.items()):
        names = sorted({owner[pin] for pin in pins if pin in owner})
        if len(names) > 1:
            shorts.append({"actual_node": node, "expected_groups": names, "pins": sorted(pins)})
    opens = []
    for name, pins in sorted(groups.items()):
        fragments = {node: sorted(set(members) & pins) for node, members in sorted(nodes.items())
                     if set(members) & pins}
        if len(fragments) > 1:
            opens.append({"expected_group": name, "actual_fragments": fragments})
    return PartitionReport(tuple(shorts), tuple(opens), tuple(sorted(set(owner) - set(actual))),
                           tuple(sorted(set(actual) - set(owner))))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asc", type=Path)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--symbol-root", action="append", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        output = run_ltspice_netlist(args.asc, args.artifacts, executable=args.executable,
                                    timeout=args.timeout)
        roots = args.symbol_root or discover_symbol_roots(args.executable)
        actual = parse_netlist(read_ltspice_text(output.with_suffix(".asc")),
                               read_ltspice_text(output), symbol_roots=roots)
        result = {"netlist": str(output), "pin_nodes": actual}
        if args.expected:
            report = compare_partitions(json.loads(args.expected.read_text(encoding="utf-8")), actual)
            result["verification"] = report.to_dict()
        print(json.dumps(result, indent=2))
        return 1 if args.expected and not report.ok else 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        parser.exit(2, f"LTspice verification failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
