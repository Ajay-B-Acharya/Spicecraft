import logging
import re
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.schemas.circuit import CircuitResponse, CircuitUpdateRequest
from app.services.asc_validation import ERROR, AscExportError
from app.services.connectivity import validate_connectivity
from app.services.ltspice_exporter import generate_asc
from app.services.input_safety import validate_input
from app.services.production import Execution, PipelineLimits, execution_context
from circuits.repository import CircuitRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/circuits", tags=["circuits"])
repository = CircuitRepository()


def _pipeline_error(exc: AscExportError, default_stage: str) -> HTTPException:
    diagnostics = [asdict(d) for d in exc.diagnostics if d.severity == ERROR]
    stage = getattr(exc, "stage", None) or next(
        (d.get("stage") for d in diagnostics if d.get("stage")), default_stage
    )
    for diagnostic in diagnostics:
        diagnostic['stage'] = diagnostic.get('stage') or stage
    codes = {d["code"] for d in diagnostics}
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    if "PIPELINE_TIMEOUT" in codes:
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
    elif "RESOURCE_LIMIT" in codes:
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if stage == "input_validation" else status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(status_code=status_code, detail={
        "message": "Circuit processing failed",
        "stage": stage,
        "retryable": status_code == status.HTTP_504_GATEWAY_TIMEOUT,
        "diagnostics": diagnostics,
    })


def _internal_error(stage: str, message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
        "message": message, "stage": stage, "code": "INTERNAL_ERROR", "retryable": False,
    })


def _get_circuit(circuit_id: str):
    try:
        return repository.get_circuit_by_id(circuit_id)
    except Exception as exc:
        logger.exception("Failed to read circuit %s", circuit_id)
        raise _internal_error("load", "Failed to load circuit") from exc


@router.get("", response_model=list[CircuitResponse])
def list_circuits() -> list[CircuitResponse]:
    logger.info("GET /circuits")
    try:
        return [CircuitResponse.model_validate(circuit) for circuit in repository.get_all_circuits()]
    except Exception as exc:
        logger.exception("Failed to list circuits")
        raise _internal_error("load", "Failed to load circuits") from exc


@router.get("/{circuit_id}", response_model=CircuitResponse)
def get_circuit(circuit_id: str) -> CircuitResponse:
    logger.info("GET /circuits/%s", circuit_id)
    circuit = _get_circuit(circuit_id)
    if not circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Circuit not found", "code": "CIRCUIT_NOT_FOUND", "stage": "load", "retryable": False},
        )
    try:
        return CircuitResponse.model_validate(circuit)
    except Exception as exc:
        logger.exception("Invalid stored circuit %s", circuit_id)
        raise _internal_error("load", "Failed to load circuit") from exc


@router.get("/{circuit_id}/export/asc")
def export_circuit_asc(circuit_id: str) -> Response:
    """Export a circuit as a downloadable LTspice ASC schematic file."""
    logger.info("GET /circuits/%s/export/asc", circuit_id)

    circuit = _get_circuit(circuit_id)
    if not circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Circuit not found", "code": "CIRCUIT_NOT_FOUND", "stage": "load", "retryable": False},
        )

    try:
        asc_content = generate_asc(circuit)
    except AscExportError as exc:
        logger.warning("ASC export blocked for %s: %s", circuit_id, exc)
        raise _pipeline_error(exc, "export_validation") from exc
    except Exception as exc:
        logger.exception("Unexpected ASC export failure for %s", circuit_id)
        raise _internal_error("export", "Failed to export circuit") from exc

    # Build a safe filename from the circuit name
    safe_name = re.sub(r"[^A-Za-z0-9_\-]", "_", str(circuit.get("name", circuit_id)))[:120] or "circuit"
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
            detail={"message": "Circuit ID in payload must match the route parameter",
                    "code": "CIRCUIT_ID_MISMATCH", "stage": "input_validation", "retryable": False},
        )

    existing_circuit = _get_circuit(circuit_id)
    if not existing_circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Circuit not found", "code": "CIRCUIT_NOT_FOUND", "stage": "load", "retryable": False},
        )

    try:
        circuit_data = payload.model_dump(mode="json")
        execution = Execution(PipelineLimits.from_environment(), circuit_id=circuit_id)
        with execution_context(execution):
            validate_input(circuit_data, execution)
            execution.transition('net_building')
            logical_errors = [d for d in validate_connectivity(circuit_data) if d.severity == ERROR]
            execution.check()
            if logical_errors:
                raise AscExportError(logical_errors)
    except AscExportError as exc:
        raise _pipeline_error(exc, "connectivity") from exc
    except Exception as exc:
        logger.exception("Unexpected circuit validation failure for %s", circuit_id)
        raise _internal_error("input_validation", "Failed to validate circuit") from exc

    try:
        updated_circuit = repository.update_circuit(
            circuit_id,
            circuit_data,
        )
        if updated_circuit is not None:
            updated_circuit = CircuitResponse.model_validate(updated_circuit)
    except Exception as exc:
        logger.exception("Failed to write circuit file for %s", circuit_id)
        raise _internal_error("save", "Failed to save circuit") from exc

    if not updated_circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Circuit not found", "code": "CIRCUIT_NOT_FOUND", "stage": "load", "retryable": False},
        )

    return updated_circuit
