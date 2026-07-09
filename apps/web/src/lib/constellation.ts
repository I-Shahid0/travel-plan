/**
 * Deterministic constellation sigils.
 *
 * Every listing in the atlas gets its own tiny constellation, derived from a
 * hash of its id: star positions, the line-path connecting them, and a hue
 * pair tinted by the listing's leading category. The same listing always
 * renders the same sky — pure function, server-renderable, no assets.
 */

export interface ConstellationSpec {
  stars: { x: number; y: number; r: number; bright: boolean }[];
  /** Index pairs into `stars`, forming the constellation lines. */
  edges: [number, number][];
  hueA: number;
  hueB: number;
}

/** FNV-1a — small, stable, good scatter for short ids. */
export function fnv1a(input: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/** Mulberry32 PRNG — deterministic stream from one seed. */
function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const CATEGORY_HUES: [RegExp, number][] = [
  [/coffee|tea|cafe|bakery|dessert|donut|ice cream/i, 32],
  [/restaurant|food|pizza|sushi|burger|bbq|noodle|taco|deli|breakfast|brunch/i, 350],
  [/bar|brewer|wine|pub|cocktail|nightlife|lounge/i, 268],
  [/park|hik|trail|outdoor|beach|garden|nature|camp/i, 152],
  [/museum|art|galler|theater|theatre|music|venue|festival/i, 210],
  [/hotel|travel|tour|resort|bed & breakfast/i, 190],
  [/spa|massage|salon|yoga|fitness|gym|wellness/i, 300],
  [/shop|store|market|boutique|mall/i, 48],
];

export function categoryHue(categories: string[]): number {
  const joined = categories.join(" ");
  for (const [pattern, hue] of CATEGORY_HUES) {
    if (pattern.test(joined)) return hue;
  }
  return 226; // default: deep sky violet-blue
}

/**
 * Build a constellation inside a 100×62.5 viewBox (16:10).
 * Stars are scattered with margin, then connected in a single
 * angular-sorted path so lines never tangle into a scribble.
 */
export function constellationFor(id: string, categories: string[] = []): ConstellationSpec {
  const seed = fnv1a(id);
  const rand = mulberry32(seed);

  const count = 5 + Math.floor(rand() * 4); // 5–8 stars
  const stars: ConstellationSpec["stars"] = [];
  for (let i = 0; i < count; i++) {
    stars.push({
      x: 10 + rand() * 80,
      y: 9 + rand() * 44,
      r: 0.7 + rand() * 1.1,
      bright: rand() > 0.62,
    });
  }

  // connect stars sorted by angle around their centroid — an open ring
  const cx = stars.reduce((s, p) => s + p.x, 0) / count;
  const cy = stars.reduce((s, p) => s + p.y, 0) / count;
  const order = stars
    .map((p, i) => ({ i, a: Math.atan2(p.y - cy, p.x - cx) }))
    .sort((m, n) => m.a - n.a)
    .map((m) => m.i);

  const edges: [number, number][] = [];
  for (let k = 0; k < order.length - 1; k++) {
    const from = order[k];
    const to = order[k + 1];
    if (from !== undefined && to !== undefined) edges.push([from, to]);
  }
  // occasionally close the ring or add a cross-strut for variety
  const first = order[0];
  const last = order[order.length - 1];
  if (first !== undefined && last !== undefined && rand() > 0.5) {
    edges.push([last, first]);
  }

  const hueA = categoryHue(categories);
  // analogous companion hue — stays in the same family so sigils never clash
  const hueB = (hueA + 18 + Math.floor(rand() * 22)) % 360;

  return { stars, edges, hueA, hueB };
}
