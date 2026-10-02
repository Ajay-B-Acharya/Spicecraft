from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.pin_maps import COMPONENT_LIBRARY
from tools.verify_ltspice import (
    compare_partitions,
    discover_ltspice_executable,
    discover_symbol_roots,
    parse_netlist,
    read_ltspice_text,
    run_ltspice_netlist,
)


def resistor(name: str, pin1: tuple[int, int]) -> str:
    # Stock res.asy at R0: anchor (-16,-16) gives pin1 (0,0), pin2 (0,80).
    x, y = pin1
    return f"SYMBOL res {x - 16} {y - 16} R0\nSYMATTR InstName {name}\nSYMATTR Value 1k\n"


def schematic(wires: list[str], pin2: tuple[int, int], flags: list[str] | None = None) -> str:
    return ("Version 4\nSHEET 1 1024 768\n" + "\n".join(wires + (flags or [])) + "\n"
            + resistor("R1", (0, 0)) + resistor("R2", pin2))


# These are interpreted by LTspice, never by a Python geometry/network builder.
# Boolean says whether the measured R1.1 and R2.1 join. Opposite resistor pins
# lie outside all wires, so they must remain separate singleton nets.
JUNCTION_CASES = {
    "unsplit_interior_x": (schematic([
        "WIRE 0 0 256 0", "WIRE 128 -128 128 128",
    ], (128, 128)), False),
    "endpoint_interior_t": (schematic([
        "WIRE 0 0 256 0", "WIRE 128 128 128 0",
    ], (128, 128)), True),
    "shared_endpoints": (schematic([
        "WIRE 0 0 128 0", "WIRE 128 0 128 128",
    ], (128, 128)), True),
    "collinear_overlap": (schematic([
        "WIRE 0 0 192 0", "WIRE 128 0 256 0",
    ], (256, 0)), True),
    "foreign_pin_on_interior": (schematic([
        "WIRE 0 0 256 0",
    ], (128, 0)), True),
    "foreign_flag_on_interior": (schematic([
        "WIRE 0 0 256 0",
    ], (384, 0), ["FLAG 128 0 FOREIGN", "FLAG 384 0 FOREIGN"]), True),
    "same_flag_disconnected": (schematic([], (384, 0), [
        "FLAG 0 0 SAME", "FLAG 384 0 SAME",
    ]), True),
    "split_interior_x_control": (schematic([
        "WIRE 0 0 128 0", "WIRE 128 0 256 0", "WIRE 128 -128 128 128",
    ], (128, 128)), True),
}


class NetlistParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Synthetic stock-shaped files remove any executable/library dependency
        # from parser tests. Reverse physical listing order and LED terminal order
        # to prove SpiceOrder, not .asy listing or canonical tuple order, is used.
        for definition in COMPONENT_LIBRARY.values():
            path = self.root / definition.asy_file
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = ["Version 4", "SymbolType CELL"]
            for index, pin in reversed(list(enumerate(definition.pins, 1))):
                order = 3 - index if definition.kind == "led" else index
                lines.extend([f"PIN {pin.x} {pin.y} NONE 0", f"PINATTR PinName {pin.name}",
                              f"PINATTR SpiceOrder {order}"])
            path.write_text("\n".join(lines), encoding="utf-8")

    def parse(self, asc: str, netlist: str) -> dict[str, str]:
        return parse_netlist(asc, netlist, symbol_roots=[self.root])

    def test_device_nodes_substrate_prefix_aliases_and_continuations(self) -> None:
        asc = "\n".join([
            "Version 4", "SHEET 1 1000 800", "SYMBOL npn 0 0 R0",
            "SYMATTR InstName Q1", "SYMATTR Value BC547", "SYMBOL res -16 -16 R0",
            "SYMATTR InstName R1", "SYMATTR Value 1k", "SYMBOL cap 200 0 R90",
            "SYMATTR InstName C1", "SYMBOL led 400 0 M0", "SYMATTR InstName D1",
            "SYMBOL diode 600 0 R0", "SYMATTR InstName D2",
            "SYMBOL Misc\\NE555 800 256 R0", "SYMATTR InstName U1",
            "SYMATTR Value NE555", "SYMATTR Value2 NE555",
        ])
        netlist = "\n".join([
            "* synthetic LTspice netlist", "q1 COL BASE EMIT 0 BC547", "r1 COL Vin 1k ; comment",
            "C1 Vin 0 10µF", "D1 CATH ANODE LED", "D2 DA DK 1N4148",
            "X§u1 0 trig out reset", "+ ctrl thr dis vcc NE555",
            ".subckt NE555 1 2 3 4 5 6 7 8", "R1 1 2 100", ".ends NE555",
            ".model BC547 NPN", ".backanno", ".end",
        ])
        actual = self.parse(asc, netlist)
        self.assertEqual(actual, {
            "Q1.C": "COL", "Q1.B": "BASE", "Q1.E": "EMIT",
            "R1.1": "COL", "R1.2": "Vin", "C1.1": "Vin", "C1.2": "0",
            "D1.A": "ANODE", "D1.K": "CATH", "D2.1": "DA", "D2.2": "DK",
            **{f"U1.{i}": node for i, node in enumerate(
                ["0", "trig", "out", "reset", "ctrl", "thr", "dis", "vcc"], 1)},
        })
        self.assertNotIn("Q1.4", actual)
        self.assertEqual(list(actual)[:3], ["Q1.C", "Q1.B", "Q1.E"])

    def test_subcircuit_name_aliases(self) -> None:
        asc = "SYMBOL Misc/NE555 0 0 R0\nSYMATTR InstName U1\nSYMATTR Value2 NE555\n"
        for name in ("U1", "XU1", "X§U1", "x§u1"):
            with self.subTest(name=name):
                actual = self.parse(asc, f"{name} a b c d e f g h NE555")
                self.assertEqual(actual["U1.6"], "f")
                self.assertEqual(len(actual), 8)

    def test_parser_fails_closed_on_missing_duplicate_and_truncated_devices(self) -> None:
        asc = resistor("R1", (0, 0))
        for netlist, message in (("R2 a b 1k", "found 0"),
                                 ("R1 a b 1k\nr1 c d 2k", "found 2"),
                                 ("R1 a 1k", "Truncated")):
            with self.subTest(netlist=netlist), self.assertRaisesRegex(ValueError, message):
                self.parse(asc, netlist)
        with self.assertRaisesRegex(ValueError, "Unsupported ASC symbol"):
            self.parse("SYMBOL unknown 0 0 R0\nSYMATTR InstName Z1", "Z1 a b x")
        with self.assertRaisesRegex(ValueError, "Duplicate ASC"):
            self.parse(asc + resistor("r1", (256, 0)), "R1 a b 1k")
        with self.assertRaisesRegex(ValueError, "InstName"):
            self.parse("SYMBOL res 0 0 R0", "R1 a b 1k")
        with self.assertRaises(FileNotFoundError):
            parse_netlist(asc, "R1 a b 1k", symbol_roots=[])

    def test_stock_geometry_mismatch_and_duplicate_orders_are_errors(self) -> None:
        path = self.root / "res.asy"
        path.write_text("PIN 17 16 NONE 0\nPINATTR SpiceOrder 1\n"
                        "PIN 16 96 NONE 0\nPINATTR SpiceOrder 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "No ASY SpiceOrder"):
            self.parse(resistor("R1", (0, 0)), "R1 a b 1k")
        path.write_text("PIN 16 16 NONE 0\nPINATTR SpiceOrder 1\n"
                        "PIN 16 96 NONE 0\nPINATTR SpiceOrder 1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate ASY terminal"):
            self.parse(resistor("R1", (0, 0)), "R1 a b 1k")

    def test_ltspice_text_encodings(self) -> None:
        for encoding in ("utf-8-sig", "utf-16", "cp1252"):
            with self.subTest(encoding=encoding):
                path = self.root / "encoding.net"
                path.write_bytes("X§U1 a b NE555\nC1 a b 10µF".encode(encoding))
                self.assertEqual(read_ltspice_text(path), "X§U1 a b NE555\nC1 a b 10µF")


class PartitionTests(unittest.TestCase):
    def test_equivalence_ignores_names_order_and_node_case(self) -> None:
        report = compare_partitions([{"R1.1", "Q1.C"}, {"R1.2"}],
                                    {"R1.2": "0", "Q1.C": "n123", "R1.1": "N123"})
        self.assertTrue(report.ok)
        self.assertTrue(report.to_dict()["ok"])
        json.dumps(report.to_dict())

    def test_short_is_not_a_successful_expected_source_match(self) -> None:
        expected = {"supply": {"R1.1"}, "bias": {"R1.2", "Q1.B"}, "collector": {"Q1.C"}}
        report = compare_partitions(expected, {pin: "0" for pins in expected.values() for pin in pins})
        self.assertFalse(report.ok)
        self.assertEqual(len(report.shorts), 1)
        self.assertEqual(report.shorts[0]["expected_groups"], ["bias", "collector", "supply"])
        self.assertFalse(report.opens)

    def test_opens_missing_and_unexpected_pins(self) -> None:
        report = compare_partitions({"bias": {"R1.2", "Q1.B", "R2.1"}},
                                    {"R1.2": "a", "Q1.B": "b", "C1.1": "b"})
        self.assertFalse(report.ok)
        self.assertEqual(report.opens[0]["actual_fragments"], {"a": ["R1.2"], "b": ["Q1.B"]})
        self.assertEqual(report.missing_pins, ("R2.1",))
        self.assertEqual(report.unexpected_pins, ("C1.1",))
        with self.assertRaisesRegex(ValueError, "repeats pin"):
            compare_partitions([{"R1.1"}, {"R1.1"}], {"R1.1": "a"})
        with self.assertRaisesRegex(ValueError, "Component.Pin"):
            compare_partitions([{ "VCC" }], {})


class InvocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source/input.asc"
        self.source.parent.mkdir()
        self.source.write_text(resistor("R1", (0, 0)), encoding="utf-8")
        self.exe = self.root / "LTspice.exe"
        self.exe.touch()
        self.artifacts = self.root / "outputs"

    def test_explicit_executable_discovery(self) -> None:
        with patch.dict(os.environ, {"LTSPICE_EXECUTABLE": str(self.exe)}):
            self.assertEqual(discover_ltspice_executable(), self.exe.resolve())
        with patch.dict(os.environ, {"LTSPICE_EXECUTABLE": str(self.root / "absent.exe")}):
            with self.assertRaises(FileNotFoundError):
                discover_ltspice_executable()

    def test_runner_absolute_argument_timeout_and_artifact_isolation(self) -> None:
        def netlist(command, **kwargs):
            self.assertEqual(command, [str(self.exe.resolve()), "-netlist",
                                       str((self.artifacts / "input.asc").resolve())])
            self.assertEqual(kwargs["cwd"], self.artifacts.resolve())
            self.assertEqual(kwargs["timeout"], 4)
            self.assertTrue(kwargs["capture_output"])
            Path(command[2]).with_suffix(".net").write_text("R1 a b 1k", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")
        with patch("tools.verify_ltspice.subprocess.run", side_effect=netlist):
            result = run_ltspice_netlist(self.source, self.artifacts, executable=self.exe, timeout=4)
        self.assertEqual(result, self.artifacts / "input.net")
        self.assertEqual(list(self.source.parent.iterdir()), [self.source])
        self.assertTrue((self.artifacts / "input.asc").is_file())

    def test_failures_do_not_accept_stale_netlist(self) -> None:
        self.artifacts.mkdir()
        stale = self.artifacts / "input.net"
        stale.write_text("R1 a b 1k", encoding="utf-8")
        with patch("tools.verify_ltspice.subprocess.run", return_value=subprocess.CompletedProcess(
                [], 0, "", "")), self.assertRaisesRegex(RuntimeError, "nonempty netlist"):
            run_ltspice_netlist(self.source, self.artifacts, executable=self.exe)
        self.assertFalse(stale.exists())
        with patch("tools.verify_ltspice.subprocess.run", return_value=subprocess.CompletedProcess(
                [], 2, "", "bad input")), self.assertRaisesRegex(RuntimeError, "exited 2"):
            run_ltspice_netlist(self.source, self.artifacts, executable=self.exe)
        with patch("tools.verify_ltspice.subprocess.run", side_effect=subprocess.TimeoutExpired([], 0.1)), \
                self.assertRaisesRegex(TimeoutError, "timed out"):
            run_ltspice_netlist(self.source, self.artifacts, executable=self.exe, timeout=0.1)


class RealLtspiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.executable = discover_ltspice_executable()
        if cls.executable is None:
            raise unittest.SkipTest("LTspice unavailable; set LTSPICE_EXECUTABLE to run electrical checks")
        cls.symbol_roots = discover_symbol_roots(cls.executable)
        if not cls.symbol_roots:
            raise unittest.SkipTest("Stock LTspice symbol library unavailable")

    def netlist(self, asc: str, name: str) -> tuple[dict[str, str], str]:
        with tempfile.TemporaryDirectory(prefix="spicecraft-ltspice-") as directory:
            root = Path(directory)
            source = root / f"{name}.asc"
            source.write_text(asc, encoding="utf-8")
            output = run_ltspice_netlist(source, root / "artifacts", executable=self.executable,
                                        timeout=30)
            text = read_ltspice_text(output)
            return parse_netlist(asc, text, symbol_roots=self.symbol_roots), text

    def test_real_junction_semantics_matrix(self) -> None:
        for name, (asc, joins) in JUNCTION_CASES.items():
            with self.subTest(junction=name):
                actual, text = self.netlist(asc, name)
                groups = ([{"R1.1", "R2.1"}] if joins else [{"R1.1"}, {"R2.1"}])
                report = compare_partitions(groups + [{"R1.2"}, {"R2.2"}], actual)
                print(f"LTspice junction {name}: "
                      f"R1.1={actual['R1.1']} R2.1={actual['R2.1']} "
                      f"joined={actual['R1.1'].casefold() == actual['R2.1'].casefold()}")
                self.assertTrue(report.ok, f"{name}: {report.to_dict()}\n{text}")

    def test_real_ne555_value2_and_subcircuit_pin_order(self) -> None:
        definition = COMPONENT_LIBRARY["ne555"]
        asc = "Version 4\nSHEET 1 1024 768\n"
        asc += "".join(f"FLAG {512 + pin.x} {256 + pin.y} PIN{pin.id}\n" for pin in definition.pins)
        asc += ("SYMBOL Misc\\NE555 512 256 R0\nSYMATTR InstName U1\n"
                "SYMATTR Value NE555\nSYMATTR Value2 NE555\n")
        actual, text = self.netlist(asc, "ne555")
        self.assertEqual(actual, {f"U1.{i}": f"PIN{i}" for i in range(1, 9)}, text)
        self.assertTrue(compare_partitions([{key} for key in actual], actual).ok)

    def test_actual_negative_common_emitter_baseline_reports_shorts(self) -> None:
        baseline = BACKEND_ROOT / "tests/artifacts/phase_6_5/common_emitter_before.asc"
        if not baseline.is_file():
            self.skipTest("Phase6.5 negative ASC artifact not available")
        actual, text = self.netlist(read_ltspice_text(baseline), "common_emitter_before")
        # Explicitly provided intended groups, not a copy of NetBuilder or an
        # exporter self-check. This baseline MUST fail electrical verification.
        expected = {
            "VCC": {"R1.1", "R3.2"},
            "bias": {"R1.2", "Q1.B", "R2.1"},
            "ground": {"R2.2", "C1.2"},
            "collector": {"Q1.C", "R3.1", "C2.1"},
            "emitter": {"Q1.E", "C1.1"},
            "output": {"C2.2"},
        }
        report = compare_partitions(expected, actual)
        self.assertFalse(report.ok, text)
        self.assertEqual(len(report.shorts), 1, report.to_dict())
        self.assertEqual(report.shorts[0]["actual_node"], "0", text)
        self.assertEqual(report.shorts[0]["expected_groups"],
                         ["VCC", "bias", "collector", "emitter", "ground"])
        self.assertEqual(actual["C2.2"], "VOUT", text)
        self.assertEqual(len(actual), 13)  # NOT Q1's extra fourth/substrate node.
        self.assertFalse(report.missing_pins)
        self.assertFalse(report.unexpected_pins)
        print("LTspice negative baseline: short joins VCC, bias, collector, emitter, ground on 0")


if __name__ == "__main__":
    unittest.main()
