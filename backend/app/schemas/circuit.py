from typing import Any

from pydantic import BaseModel, ConfigDict


class CircuitComponentPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class CircuitWirePayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class CircuitUpdateRequest(BaseModel):
    id: str
    name: str
    description: str
    category: str
    tags: list[str]
    components: list[CircuitComponentPayload]
    wires: list[CircuitWirePayload]

    model_config = ConfigDict(extra="allow")


class CircuitResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    tags: list[str]
    components: list[dict[str, Any]]
    wires: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)
