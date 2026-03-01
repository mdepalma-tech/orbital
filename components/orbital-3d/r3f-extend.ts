/**
 * Extend R3F with THREE.Line under the "threeLine" alias.
 * The "line" element conflicts with SVG, so R3F types use "threeLine" in ThreeElements.
 * R3F looks up catalogue[toPascalCase(type)], so we must use "ThreeLine" as the key.
 */
import { extend } from "@react-three/fiber";
import * as THREE from "three";

extend({ ThreeLine: THREE.Line });
