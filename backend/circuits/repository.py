import json
import os
from pathlib import Path
import tempfile
from typing import Any


class CircuitRepository:
    def __init__(self, circuits_dir: Path | None = None) -> None:
        self.circuits_dir = circuits_dir or Path(__file__).resolve().parent

    def _load_circuit_file(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _iter_circuit_files(self) -> list[Path]:
        return sorted(self.circuits_dir.glob("*.json"))

    def _get_circuit_path(self, circuit_id: str) -> Path | None:
        for path in self._iter_circuit_files():
            circuit = self._load_circuit_file(path)
            if str(circuit.get("id")) == str(circuit_id):
                return path
        return None

    def get_all_circuits(self) -> list[dict[str, Any]]:
        return [self._load_circuit_file(path) for path in self._iter_circuit_files()]

    def get_circuit_by_id(self, circuit_id: str) -> dict[str, Any] | None:
        circuit_path = self._get_circuit_path(circuit_id)
        if not circuit_path:
            return None
        return self._load_circuit_file(circuit_path)

    def update_circuit(
        self,
        circuit_id: str,
        circuit_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        circuit_path = self._get_circuit_path(circuit_id)
        if not circuit_path:
            return None

        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=circuit_path.parent,
                                             prefix=".circuit-", suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                json.dump(circuit_data, file, indent=2, allow_nan=False)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, circuit_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

        return circuit_data

    def search_circuits(self, query: str) -> list[dict[str, Any]]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return self.get_all_circuits()

        results: list[dict[str, Any]] = []
        for circuit in self.get_all_circuits():
            name = str(circuit.get("name", "")).lower()
            category = str(circuit.get("category", "")).lower()
            tags = [str(tag).lower() for tag in circuit.get("tags", [])]

            if (
                normalized_query in name
                or normalized_query in category
                or any(normalized_query in tag for tag in tags)
            ):
                results.append(circuit)

        return results
