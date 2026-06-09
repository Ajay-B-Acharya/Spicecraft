import logging
import re

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.schemas.circuit import CircuitResponse, CircuitUpdateRequest
from app.services.ltspice_exporter import generate_asc
from circuits.repository import CircuitRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/circuits", tags=["circuits"])
repository = CircuitRepository()


@router.get("", response_model=list[CircuitResponse])
def list_circuits() -> list[CircuitResponse]:
    logger.info("GET /circuits")
    return repository.get_all_circuits()


@router.get("/{circuit_id}", response_model=CircuitResponse)
def get_circuit(circuit_id: str) -> CircuitResponse:
    logger.info("GET /circuits/%s", circuit_id)
    circuit = repository.get_circuit_by_id(circuit_id)
    if not circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circuit not found",
        )
    return circuit



@router.get("/{circuit_id}/export/asc")
def export_circuit_asc(circuit_id: str) -> Response:
    """Export a circuit as a downloadable LTspice ASC schematic file."""
    logger.info("GET /circuits/%s/export/asc", circuit_id)

    circuit = repository.get_circuit_by_id(circuit_id)
    if not circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circuit not found",
        )

    asc_content = generate_asc(circuit)

    # Build a safe filename from the circuit name
    safe_name = re.sub(r"[^\w\-]", "_", str(circuit.get("name", circuit_id)))
    filename = f"{safe_name}.asc"

    return Response(
        content=asc_content.encode("utf-8"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/{circuit_id}", response_model=CircuitResponse)
def update_circuit(
    circuit_id: str,
    payload: CircuitUpdateRequest,
) -> CircuitResponse:
    logger.info("PUT /circuits/%s", circuit_id)

    if payload.id != circuit_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Circuit ID in payload must match the route parameter",
        )

    existing_circuit = repository.get_circuit_by_id(circuit_id)
    if not existing_circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circuit not found",
        )

    try:
        updated_circuit = repository.update_circuit(
            circuit_id,
            payload.model_dump(mode="json"),
        )
    except OSError as exc:
        logger.exception("Failed to write circuit file for %s", circuit_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save circuit",
        ) from exc

    if not updated_circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circuit not found",
        )

    return updated_circuit
