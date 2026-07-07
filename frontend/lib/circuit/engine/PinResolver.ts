/**
 * Pin resolver engine.
 *
 * Converts component-relative pin coordinates into absolute schematic-space
 * coordinates. This module is renderer-agnostic and supports rotation plus
 * horizontal mirroring so future exporters, routers, ERC, and simulation tooling
 * can operate on the same electrical geometry.
 */
import { Component } from "../models/Component";
import { Pin } from "../models/Pin";
import { PinDirection, ResolvedPinLike } from "../types";

export interface ResolvedPin extends ResolvedPinLike {}

const directionOrder: PinDirection[] = ["right", "bottom", "left", "top"];

function normalizeRotation(rotation: number): number {
  return ((rotation % 360) + 360) % 360;
}

function rotateDirection(
  direction: PinDirection | undefined,
  rotation: number,
): PinDirection | undefined {
  if (!direction) {
    return undefined;
  }

  const normalized = normalizeRotation(rotation);

  if (normalized % 90 !== 0) {
    return direction;
  }

  const quarterTurns = normalized / 90;
  const currentIndex = directionOrder.indexOf(direction);

  return directionOrder[(currentIndex + quarterTurns) % directionOrder.length];
}

function mirrorDirection(
  direction: PinDirection | undefined,
): PinDirection | undefined {
  if (direction === "left") {
    return "right";
  }

  if (direction === "right") {
    return "left";
  }

  return direction;
}

export function resolvePin(component: Component, pin: Pin): ResolvedPin {
  const mirroredX = component.mirror ? -pin.x : pin.x;
  const mirroredDirection = component.mirror
    ? mirrorDirection(pin.direction)
    : pin.direction;
  const radians = (normalizeRotation(component.rotation) * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  const rotatedX = mirroredX * cos - pin.y * sin;
  const rotatedY = mirroredX * sin + pin.y * cos;

  return {
    ...pin,
    direction: rotateDirection(mirroredDirection, component.rotation),
    componentId: component.id,
    componentName: component.name,
    absoluteX: component.position.x + rotatedX,
    absoluteY: component.position.y + rotatedY,
  };
}

export function resolvePins(component: Component): ResolvedPin[] {
  return component.pins.map((pin) => resolvePin(component, pin));
}
