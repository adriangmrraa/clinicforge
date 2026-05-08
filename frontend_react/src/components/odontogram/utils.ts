/**
 * DLD-73: Conditional path resolution for mesial/distal based on quadrant.
 *
 * Mesial ALWAYS points toward the midline (center of the mouth).
 * - Q1 (11-18) and Q4 (41-48): mesial is visually on the RIGHT side
 * - Q2 (21-28) and Q3 (31-38): mesial is visually on the LEFT side
 *
 * The SVG paths are defined with mesial=LEFT, distal=RIGHT.
 * For Q1/Q4, we swap the path assignment so the visual matches anatomy.
 * Surface NAMES stay semantic — only the visual path changes.
 */
export function getPathForSurface(
  toothId: number,
  surfaceName: string,
  paths: Record<string, string>,
): string {
  const quadrant = Math.floor(toothId / 10);
  // Q1/Q4 = permanent right side, Q5/Q8 = deciduous right side (same anatomy)
  if (
    (quadrant === 1 || quadrant === 4 || quadrant === 5 || quadrant === 8) &&
    (surfaceName === 'mesial' || surfaceName === 'distal')
  ) {
    return surfaceName === 'mesial' ? paths['distal'] : paths['mesial'];
  }
  return paths[surfaceName];
}

/**
 * Returns true if mesial/distal paths should be visually swapped for this tooth.
 * Useful for swapping labels ("M" and "D") on the zoomed SVG.
 */
export function shouldSwapMesialDistal(toothId: number): boolean {
  const quadrant = Math.floor(toothId / 10);
  return quadrant === 1 || quadrant === 4 || quadrant === 5 || quadrant === 8;
}
