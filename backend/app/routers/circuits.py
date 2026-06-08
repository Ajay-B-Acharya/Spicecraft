import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.circuit import CircuitResponse, CircuitUpdateRequest
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
