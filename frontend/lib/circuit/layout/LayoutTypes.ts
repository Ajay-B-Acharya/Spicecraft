/**
 * Layout engine type contracts.
 *
 * Defines configuration, analysis results, and placement metadata for the
 * intelligent auto-layout system. The layout engine operates exclusively on
 * Circuit objects without requiring UI or exporter dependencies.
 */
import { Component } from "../models/Component";
import { Net } from "../models/Net";

export interface GridConfig {
  spacingX: number;
  spacingY: number;
  marginX: number;
  marginY: number;
  originX?: number;
  originY?: number;
}

export interface GridPosition {
  col: number;
  row: number;
}

export interface ComponentClassification {
  inputs: string[];
  outputs: string[];
  grounds: string[];
  supplies: string[];
  active: string[];
  passive: string[];
  coupling: string[];
  decoupling: string[];
}

export interface ComponentAnalysis {
  componentId: string;
  degree: number;
  connectedNets: string[];
  isInput: boolean;
  isOutput: boolean;
  isGround: boolean;
  isSupply: boolean;
  isActive: boolean;
  isPassive: boolean;
  isCoupling: boolean;
  isDecoupling: boolean;
  groupId?: string;
  groupRole?: string;
}

export type ComponentGroup =
  | { type: "voltage_divider"; components: string[] }
  | { type: "rc_filter"; components: string[]; isHighPass: boolean }
  | { type: "bias_network"; components: string[]; target: string }
  | { type: "amplifier_stage"; components: string[]; transistor: string }
  | {
      type: "differential_pair";
      components: string[];
      transistors: [string, string];
    };

export interface CircuitAnalysis {
  classification: ComponentClassification;
  componentAnalyses: Map<string, ComponentAnalysis>;
  netDegrees: Map<string, number>;
  signalFlow: Map<string, number>;
}

export interface PlacementHint {
  componentId: string;
  preferredCol?: number;
  preferredRow?: number;
  anchor?: "left" | "right" | "top" | "bottom" | "center";
  weight: number;
}

export interface PlacementResult {
  componentId: string;
  gridPosition: GridPosition;
  absolutePosition: { x: number; y: number };
  rotation: number;
  mirror: boolean;
}

export interface LayoutConfig {
  grid: GridConfig;
  enableOptimization: boolean;
  preserveUserPositions: boolean;
  alignToSignalFlow: boolean;
}

export interface LayoutResult {
  placements: Map<string, PlacementResult>;
  bounds: {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    width: number;
    height: number;
  };
  gridBounds: {
    minCol: number;
    maxCol: number;
    minRow: number;
    maxRow: number;
    cols: number;
    rows: number;
  };
}

export const DEFAULT_GRID_CONFIG: GridConfig = {
  spacingX: 128,
  spacingY: 96,
  marginX: 128,
  marginY: 128,
  originX: 0,
  originY: 0,
};

export const DEFAULT_LAYOUT_CONFIG: LayoutConfig = {
  grid: DEFAULT_GRID_CONFIG,
  enableOptimization: true,
  preserveUserPositions: false,
  alignToSignalFlow: true,
};
