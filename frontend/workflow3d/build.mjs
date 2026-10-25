// ACCESSPATH audit line — an isometric "machine" figure of the 9-step audit workflow.
// Built with the anatomy kit (github.com/wheresryan22/anatomy, MIT, see kit/LICENSE).
//
// The object is the explanation: a website cartridge rides a carriage along a bench
// past eight stations (one per workflow step). Station 9 is a turntable that sends the
// cartridge back along the return belt to station 1: the retest loop.
// The dashboard drives it from the real audit: the carriage parks at the running
// step, each station's lamp shows that step's status, and the dial reads the score.
//
// Run:  node frontend/workflow3d/build.mjs   -> writes frontend/workflow3d.js
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./kit/iso-kit.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "..", "workflow3d.js");
const DEMO = process.argv.includes("--demo") ? join(HERE, "demo.html") : null;

const WIDTH = 1000;
const HEIGHT = 300;
const AZIMUTH = 70;

// ---------------------------------------------------------------- world plan
const PLATE = { x: -392, y: -100, w: 784, d: 186, r: 10 };
const PLATE_H = 12, FOOT_H = 6;
const RAIL_Y = [4, 28], RAIL_X = [-352, 300], RAIL_H = 4;
const TRACK_Y = 16;
const STATION_X = [-300, -222, -144, -66, 12, 90, 168, 246];
const PED = (sx) => ({ x: sx - 30, y: -86, w: 60, d: 46, r: 4 });
const PED_H = 9;
const TURN = [334, TRACK_Y], TURN_R = 32, TURN_Z = 2;
const BELT = { x: -360, y: 50, w: 694, d: 18, r: 3 };
const CART = { w: 44, d: 36 };
const STOPS = [...STATION_X, TURN[0]];
const LAMP = (sx) => [sx + 21, -46];

const P = k.fitProjection(
  [...k.boxCorners(PLATE, -PLATE_H - FOOT_H, 0), [STATION_X[1], TRACK_Y, 78], [STATION_X[3], TRACK_Y, 82], [-300, -70, 60], [246, -70, 60]],
  WIDTH, HEIGHT, { pad: 8, azimuth: AZIMUTH },
);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (pts, style) => k.dotsSvg(pts, style);
const depth = (x, y, z = 0) => k.depthOf([x, y, z], P);
const plateText = (x, y, z, text, size = 6, tone = "mid") =>
  k.faceTextSvg(k.sideMatrix([x, y], z, P, "left"), text, { size, tone, anchor: "middle" });
const slab = (plan, z, h, steps = 4, bevel = 0.6) => k.slabOf(plan, z, h, P, steps, bevel);
const screwRow = (plan, z, inset = 5) => {
  const pts = k.corners(plan, inset);
  return L(pts.map(([x, y]) => k.ring(x, y, 1.8, z, P, 14)).join(""), { tone: "lo" }) + D(pts.map(([x, y]) => at([x, y, z])), { size: 0.45 });
};

// ---------------------------------------------------------------- bench
function bench() {
  const out = [`<path class="iso-halo" d="${k.haloOf(PLATE, -PLATE_H - FOOT_H, PLATE_H, P)}"/>`];
  const feet = k.corners(PLATE, 26).sort((a, b) => depth(...a) - depth(...b));
  for (const [x, y] of feet) {
    out.push(S(k.cylinder(x, y, 9, -PLATE_H - FOOT_H, 2, P, 28), { tone: "lo" }));
    out.push(S(k.cylinder(x, y, 7, -PLATE_H - FOOT_H + 2, FOOT_H - 2, P, 28), { tone: "mid" }));
  }
  out.push(S(slab(PLATE, -PLATE_H, PLATE_H, 8, 1.6), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(PLATE, 6), 0, P), { tone: "lo" }));
  out.push(screwRow(PLATE, 0, 12));
  // ruler strip along the front edge: one major tick per station
  const strip = { x: -370, y: 74, w: 704, d: 7, r: 1 };
  out.push(S(slab(strip, 0, 0.6, 3, 0), { tone: "lo", crease: "none" }));
  const ticks = k.topTicks(strip.x + 6, strip.x + strip.w - 6, 6.5, 6, strip.y + 0.8, 0.6, [2, 3.8], P);
  out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
  // maker's plate on the front face
  out.push(plateText(-330, PLATE.y + PLATE.d, -4.5, "ACCESSPATH · AUDIT LINE", 4.2, "lo"));
  return out.join("");
}

function rails() {
  const out = [];
  for (const y of RAIL_Y) {
    out.push(S(slab({ x: RAIL_X[0], y: y - 2.5, w: RAIL_X[1] - RAIL_X[0], d: 5, r: 1 }, 0, RAIL_H, 3, 0.4), { tone: "mid" }));
    out.push(D(STATION_X.map((x) => at([x + 36, y, RAIL_H])), { size: 0.4, tone: "lo" }));
  }
  // end stop at the start of the line
  const stop = { x: RAIL_X[0] - 8, y: RAIL_Y[0] - 6, w: 8, d: RAIL_Y[1] - RAIL_Y[0] + 12, r: 1.4 };
  out.push(S(slab(stop, 0, 9, 3, 0.5), { tone: "mid" }));
  out.push(D([at([stop.x + 4, RAIL_Y[0] - 2, 9]), at([stop.x + 4, RAIL_Y[1] + 2, 9])], { size: 0.45 }));
  return out.join("");
}

// ---------------------------------------------------------------- stations (bases, drawn behind the carriage)
function pedestal(sx, n) {
  const p = PED(sx);
  const out = [S(slab(p, 0, PED_H, 5, 0.8), { tone: "mid" })];
  out.push(L(k.planOutline(k.insetPlan(p, 3.5), PED_H, P), { tone: "faint" }));
  out.push(D(k.corners(p, 4).map(([x, y]) => at([x, y, PED_H])), { size: 0.4, tone: "lo" }));
  out.push(plateText(sx - 18, p.y + p.d, 6.6, String(n), 5.6, "hi"));
  return out.join("");
}

function lamp(sx, n) {
  const [x, y] = LAMP(sx);
  return `<g class="ap3d-lamp" data-lamp="${n}" data-status="pending">` +
    S(k.cylinder(x, y, 4.2, PED_H, 1.4, P, 24), { tone: "mid" }) +
    S(k.cylinder(x, y, 3, PED_H + 1.4, 3.4, P, 24, 0.4), { tone: "hi", crease: "none" }) +
    `<circle class="ap3d-glow" cx="${at([x, y, PED_H + 4.8])[0].toFixed(1)}" cy="${at([x, y, PED_H + 4.8])[1].toFixed(1)}" r="7"/>` +
    `</g>`;
}

function box(sx, w, d, h, y0 = -78) {
  const plan = { x: sx - w / 2 - 4, y: y0, w, d, r: 2.5 };
  return { plan, svg: S(slab(plan, PED_H, h, 4, 0.8), { tone: "mid" }) };
}

// 1 · URL terminal: keyboard tray + upright screen with an address bar
function s1(sx) {
  const out = [];
  const { plan, svg } = box(sx, 46, 34, 10);
  out.push(svg);
  const top = PED_H + 10;
  for (let r = 0; r < 3; r++) for (let c = 0; c < 7; c++) {
    const key = { x: plan.x + 4 + c * 5.6, y: plan.y + 15 + r * 5.4, w: 4.4, d: 4.2, r: 0.8 };
    out.push(S(slab(key, top, 1.6, 2, 0.3), { tone: r === 2 && c > 1 && c < 5 ? "hi" : "mid", crease: "none" }));
  }
  const scr = { x: plan.x + 3, y: plan.y + 3, w: 40, d: 4, r: 1 };
  out.push(S(slab(scr, top, 24, 3, 0.5), { tone: "mid" }));
  const fy = scr.y + scr.d;
  out.push(`<path class="ap3d-screen" d="${k.pathOf([at([scr.x + 3, fy, top + 21]), at([scr.x + 37, fy, top + 21]), at([scr.x + 37, fy, top + 3]), at([scr.x + 3, fy, top + 3])], true)}"/>`);
  out.push(L(k.segment([scr.x + 6, fy, top + 17], [scr.x + 34, fy, top + 17], P), { tone: "hi" }));
  out.push(L(k.segment([scr.x + 6, fy, top + 12], [scr.x + 26, fy, top + 12], P), { tone: "lo", free: "both" }));
  out.push(L(k.segment([scr.x + 6, fy, top + 8], [scr.x + 30, fy, top + 8], P), { tone: "lo", free: "both" }));
  out.push(D([at([scr.x + 32, fy, top + 6])], { size: 0.8, tone: "hi", pulse: true }));
  return out.join("");
}

// 2 · Inspect: magnifier post (the arm and lens hang over the track, drawn later)
const POST2 = (sx) => [sx - 6, -72];
function s2(sx) {
  const [px, py] = POST2(sx);
  const base = { x: px - 9, y: py - 9, w: 18, d: 18, r: 3 };
  return S(slab(base, PED_H, 5, 4, 0.6), { tone: "mid" }) +
    S(k.cylinder(px, py, 3.4, PED_H + 5, 60, P, 24), { tone: "mid", crease: "none" }) +
    L([30, 46, 62].map((z) => k.sideArc(px, py, 3.4, z, P, 14)).join(""), { tone: "faint" }) +
    S(k.cylinder(px, py, 4.4, PED_H + 63, 4, P, 24), { tone: "mid" }) +
    L(k.knurl(px, py, 4.4, PED_H + 63, PED_H + 67, 20, P), { tone: "lo" });
}
function s2Top(sx) {
  const [px, py] = POST2(sx);
  const z = PED_H + 58;
  const arm = { x: px - 2.5, y: py, w: 5, d: TRACK_Y - py, r: 1.5 };
  const lens = [px, TRACK_Y];
  return S(slab(arm, z, 4, 3, 0.4), { tone: "mid" }) +
    D([at([px, py + 8, z + 4]), at([px, TRACK_Y - 16, z + 4])], { size: 0.45 }) +
    `<g class="ap3d-lens" data-part="lens">` +
    S(k.cylinder(lens[0], lens[1], 13, z - 3, 3, P, 40, 0.5), { tone: "hi", crease: "lo" }) +
    `<path class="ap3d-glass" d="${k.ring(lens[0], lens[1], 10.5, z, P, 40)}"/>` +
    L(k.ring(lens[0], lens[1], 10.5, z, P, 40), { tone: "mid" }) +
    `</g>`;
}

// 3 · Conditions: three selector knobs (keyboard, screen reader, mobile)
const KNOBS = (sx) => [sx - 18, sx - 4, sx + 10].map((x) => [x, -62]);
function s3(sx) {
  const out = [];
  const { plan, svg } = box(sx, 50, 30, 8);
  out.push(svg);
  const top = PED_H + 8;
  out.push(L(k.planOutline(k.insetPlan(plan, 2.5), top, P), { tone: "faint" }));
  KNOBS(sx).forEach(([x, y], i) => {
    const t = k.radialTicks(x, y, 8.5, 12, 3, top, [1, 2], P, -Math.PI * 0.75, Math.PI * 1.5);
    out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
    out.push(`<g class="ap3d-knob" data-knob="${i}" data-on="1">` +
      S(k.cylinder(x, y, 5, top, 5, P, 28, 0.5), { tone: "hi", crease: "lo" }) +
      L(k.knurl(x, y, 5, top + 1, top + 4.4, 22, P), { tone: "lo" }) +
      `<path class="iso-line ap3d-pointer" data-tone="lit" data-free="start" d="${k.lineOnTop([x, y], [x + 4, y - 0.01], top + 5, P)}" data-on-d="${k.lineOnTop([x, y], [x + 3, y + 3], top + 5, P)}" data-off-d="${k.lineOnTop([x, y], [x - 3, y + 3], top + 5, P)}"/>` +
      `</g>`);
  });
  return out.join("");
}

// 4 · TinyFish agent: gantry post with an arm; the probe drops onto the cartridge
const POST4 = (sx) => [sx + 4, -72];
function s4(sx) {
  const [px, py] = POST4(sx);
  const base = { x: px - 11, y: py - 9, w: 22, d: 18, r: 3 };
  return S(slab(base, PED_H, 6, 4, 0.6), { tone: "mid" }) +
    S(slab({ x: px - 4, y: py - 4, w: 8, d: 8, r: 1.2 }, PED_H + 6, 62, 3, 0.4), { tone: "mid" }) +
    L([0, 1, 2].map((i) => k.segment([px - 4, py + 4, PED_H + 20 + i * 14], [px + 4, py + 4, PED_H + 20 + i * 14], P)).join(""), { tone: "faint" }) +
    S(slab({ x: px - 6, y: py - 6, w: 12, d: 12, r: 1.6 }, PED_H + 66, 5, 3, 0.4), { tone: "mid" });
}
const PROBE_TOP = PED_H + 70;
function s4Top(sx) {
  const [px, py] = POST4(sx);
  const z = PED_H + 66;
  const arm = { x: px - 3, y: py, w: 6, d: TRACK_Y - py + 4, r: 1.5 };
  const head = { x: px - 7, y: TRACK_Y - 7, w: 14, d: 14, r: 2 };
  return S(slab(arm, z, 5, 3, 0.4), { tone: "mid" }) +
    D([at([px, py + 10, z + 5]), at([px, TRACK_Y - 12, z + 5])], { size: 0.45 }) +
    k.faceTextSvg(k.sideMatrix([px - 2, py + 18], z + 3.6, P, "left"), "TINYFISH", { size: 2.4, tone: "lo" }) +
    `<g data-part="probe">` +
    S(k.cylinder(px, TRACK_Y, 2, z - 26, 26, P, 18), { tone: "hi", crease: "none", lit: true }) +
    S(k.cylinder(px, TRACK_Y, 3.6, z - 30, 4, P, 20, 0.4), { tone: "hi", lit: true }) +
    `</g>` +
    S(slab(head, z - 4, 9, 3, 0.6), { tone: "mid" }) +
    D([at([head.x + 2.5, head.y + head.d, z + 2])], { size: 0.45 });
}

// 5 · Record: tape deck with two reels that spin while recording
const REELS = (sx) => [[sx - 15, -62], [sx + 9, -62]];
function s5(sx) {
  const out = [];
  const { plan, svg } = box(sx, 50, 32, 12);
  out.push(svg);
  const top = PED_H + 12;
  out.push(L(k.planOutline(k.insetPlan(plan, 2.5), top, P), { tone: "faint" }));
  REELS(sx).forEach(([x, y], i) => {
    out.push(S(k.cylinder(x, y, 10, top, 2.4, P, 36, 0.4), { tone: "hi", crease: "lo" }));
    out.push(L(k.ring(x, y, 3.2, top + 2.4, P, 20), { tone: "mid" }));
    out.push(`<path class="iso-line" data-tone="mid" data-part="spokes${i}" d=""/>`);
  });
  const [a, b] = REELS(sx);
  out.push(L(k.lineOnTop([a[0], a[1] + 10], [b[0], b[1] + 10], top + 1.2, P), { tone: "hi" }));
  out.push(S(k.cylinder(plan.x + plan.w - 6, plan.y + plan.d - 5, 2, top, 2, P, 16), { tone: "mid" }));
  out.push(D([at([plan.x + 5, plan.y + plan.d - 4, top])], { size: 0.9, tone: "lo", pulse: false }));
  return out.join("");
}

// 6 · Analyse: dial gauge; the needle reads the accessibility score 0–100
const DIAL = (sx) => [sx - 4, -62];
const DIAL_R = 17, DIAL_Z = PED_H + 6;
function s6(sx) {
  const out = [];
  const [x, y] = DIAL(sx);
  const base = { x: x - 22, y: y - 20, w: 44, d: 40, r: 4 };
  out.push(S(slab(base, PED_H, 6, 4, 0.6), { tone: "mid" }));
  out.push(S(k.cylinder(x, y, DIAL_R, DIAL_Z, 7, P, 64, 0.8), { tone: "hi", crease: "lo" }));
  const top = DIAL_Z + 7;
  out.push(L(k.knurl(x, y, DIAL_R, top - 3, top, 72, P, 0.3), { tone: "lo" }));
  out.push(L(k.ring(x, y, DIAL_R - 2, top, P, 60), { tone: "lo" }));
  const t = k.radialTicks(x, y, DIAL_R - 3, 40, 5, top, [1.2, 2.6], P, -Math.PI * 0.75, Math.PI * 1.5);
  out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
  out.push(L(k.ring(x, y, 1.6, top, P, 16), { tone: "mid" }));
  out.push(k.faceTextSvg(k.topMatrix([x, y + 8], top, P, "x"), "A11Y", { size: 2.4, tone: "lo", anchor: "middle" }));
  out.push(`<path class="iso-line" data-tone="lit" data-free="start" data-part="needle" d="${needleD(sx, 0)}" style="stroke-width:1.1"/>`);
  return out.join("");
}
function needleD(sx, score) {
  const [x, y] = DIAL(sx);
  const a = -Math.PI * 0.75 + (Math.max(0, Math.min(100, score)) / 100) * Math.PI * 1.5;
  const r = DIAL_R - 4;
  return k.lineOnTop([x - Math.sin(a) * 3, y + Math.cos(a) * 3], [x + Math.sin(a) * r, y - Math.cos(a) * r], DIAL_Z + 7.2, P);
}

// 7 · Explain: printer that feeds out the fix ticket
function s7(sx) {
  const out = [];
  const { plan, svg } = box(sx, 46, 32, 16);
  out.push(svg);
  const top = PED_H + 16;
  const slot = { x: plan.x + 8, y: plan.y + 9, w: 30, d: 3, r: 1 };
  out.push(S(slab(slot, top - 0.4, 0.4, 2, 0), { tone: "lo", flat: true, crease: "none" }));
  out.push(L(k.planOutline(slot, top, P, 2), { tone: "lo" }));
  out.push(`<g data-part="ticket" class="ap3d-ticket">` +
    S(slab({ x: slot.x + 3, y: slot.y + 1, w: 24, d: 1, r: 0.3 }, top, 20, 2, 0), { tone: "hi", lit: true, crease: "none" }) +
    [16, 12.5, 9, 5.5].map((dz, i) => L(k.segment([slot.x + 6, slot.y + 2, top + dz], [slot.x + (i % 2 ? 20 : 24), slot.y + 2, top + dz], P), { tone: "lo", free: "both" })).join("") +
    `</g>`);
  out.push(S(k.cylinder(plan.x + plan.w - 7, plan.y + plan.d - 7, 2.6, top, 2.4, P, 18), { tone: "mid" }));
  out.push(D([at([plan.x + 6, plan.y + plan.d - 5, top])], { size: 0.45 }));
  return out.join("");
}

// 8 · Report: upright board with a bar chart
function s8(sx) {
  const out = [];
  const board = { x: sx - 30, y: -74, w: 54, d: 4, r: 1 };
  for (const fx of [board.x + 8, board.x + board.w - 8]) {
    out.push(S(slab({ x: fx - 5, y: board.y - 6, w: 10, d: 16, r: 2 }, PED_H, 4, 3, 0.5), { tone: "mid" }));
  }
  out.push(S(slab(board, PED_H + 4, 46, 3, 0.6), { tone: "mid" }));
  const fy = board.y + board.d, z0 = PED_H + 4;
  out.push(`<path class="ap3d-screen" d="${k.pathOf([at([board.x + 4, fy, z0 + 42]), at([board.x + board.w - 4, fy, z0 + 42]), at([board.x + board.w - 4, fy, z0 + 4]), at([board.x + 4, fy, z0 + 4])], true)}"/>`);
  out.push(L(k.segment([board.x + 8, fy, z0 + 37], [board.x + 30, fy, z0 + 37], P), { tone: "hi", free: "both" }));
  [18, 26, 12, 30, 22].forEach((h, i) => {
    const bx = board.x + 10 + i * 8;
    out.push(`<path class="ap3d-bar" data-bar="${i}" d="${k.pathOf([at([bx, fy, z0 + 8]), at([bx + 5, fy, z0 + 8]), at([bx + 5, fy, z0 + 8 + h]), at([bx, fy, z0 + 8 + h])], true)}"/>`);
  });
  out.push(L(k.segment([board.x + 8, fy, z0 + 8], [board.x + board.w - 8, fy, z0 + 8], P), { tone: "mid" }));
  out.push(D([at([board.x + 3, fy, z0 + 44]), at([board.x + board.w - 3, fy, z0 + 44])], { size: 0.45 }));
  return out.join("");
}

// 9 · Fix and rerun: turntable at the end of the line + return belt along the front
function turntable() {
  const [x, y] = TURN;
  const base = { x: x - 38, y: y - 38, w: 76, d: 76, r: 8 };
  const out = [S(slab(base, 0, TURN_Z, 6, 0.6), { tone: "mid" })];
  out.push(`<g data-part="turntable">` + S(k.cylinder(x, y, TURN_R, TURN_Z, 4, P, 72, 0.8), { tone: "hi", crease: "lo" }) +
    L(k.ring(x, y, TURN_R - 5, TURN_Z + 4, P, 64), { tone: "faint" }) + `</g>`);
  const t = k.radialTicks(x, y, TURN_R - 1.5, 36, 9, TURN_Z + 4, [1.2, 3], P);
  out.push(`<g data-part="turnticks">` + L(t.minor, { tone: "lo" }) + L(t.major, { tone: "mid" }) + `</g>`);
  for (const ry of RAIL_Y) out.push(S(slab({ x: x - 20, y: ry - 2.5, w: 40, d: 5, r: 1 }, TURN_Z + 4, 2, 3, 0.3), { tone: "mid" }));
  out.push(lampAt(base.x + base.w - 8, base.y + 8, TURN_Z, 9));
  out.push(plateText(x - 26, base.y + base.d, 1.4, "9", 3.2, "hi"));
  return out.join("");
}
function lampAt(x, y, z, n) {
  return `<g class="ap3d-lamp" data-lamp="${n}" data-status="pending">` +
    S(k.cylinder(x, y, 4.2, z, 1.4, P, 24), { tone: "mid" }) +
    S(k.cylinder(x, y, 3, z + 1.4, 3.4, P, 24, 0.4), { tone: "hi", crease: "none" }) +
    `<circle class="ap3d-glow" cx="${at([x, y, z + 4.8])[0].toFixed(1)}" cy="${at([x, y, z + 4.8])[1].toFixed(1)}" r="7"/></g>`;
}
function belt() {
  const out = [];
  for (const ex of [BELT.x, BELT.x + BELT.w]) {
    out.push(S(k.cylinder(ex, BELT.y + BELT.d / 2, BELT.d / 2 + 1, 0, 6, P, 28), { tone: "mid" }));
  }
  out.push(S(slab(BELT, 0, 5, 3, 0.4), { tone: "mid" }));
  const chev = [];
  for (let x = BELT.x + BELT.w - 40; x > BELT.x + 20; x -= 34) {
    chev.push(k.onTop([[x + 6, BELT.y + 4], [x, BELT.y + BELT.d / 2], [x + 6, BELT.y + BELT.d - 4]], 5, P));
  }
  out.push(`<path class="iso-line ap3d-chevrons" data-tone="lo" d="${chev.join("")}"/>`);
  out.push(`<path class="iso-line ap3d-flow" data-tone="lo" d="${k.lineOnTop([BELT.x + BELT.w - 8, BELT.y + BELT.d / 2], [BELT.x + 8, BELT.y + BELT.d / 2], 5, P)}"/>`);
  // the riser that carries the cartridge from the turntable down onto the belt
  out.push(S(slab({ x: TURN[0] - 14, y: BELT.y - 6, w: 28, d: 6, r: 1 }, 0, 3, 3, 0.3), { tone: "lo" }));
  return out.join("");
}

// ---------------------------------------------------------------- the cartridge (the subject)
function cartridge() {
  const plan = { x: -CART.w / 2, y: TRACK_Y - CART.d / 2, w: CART.w, d: CART.d, r: 3 };
  const z = RAIL_H;
  const out = [`<path class="iso-halo" d="${k.haloOf(k.insetPlan(plan, 3), z, 0.1, P)}" style="filter:blur(4px)"/>`];
  for (const [bx, by] of [[-15, RAIL_Y[0]], [15, RAIL_Y[0]], [-15, RAIL_Y[1]], [15, RAIL_Y[1]]]) {
    out.push(S(slab({ x: bx - 5, y: by - 3.5, w: 10, d: 7, r: 1 }, z, 2.6, 2, 0.3), { tone: "mid", crease: "none" }));
  }
  out.push(S(slab(plan, z + 2.6, 4, 5, 0.6), { tone: "mid" }));
  const top = z + 6.6;
  out.push(L(k.lineOnTop([plan.x, plan.y + 4], [plan.x + plan.w, plan.y + 4], top, P), { tone: "faint" }));
  out.push(D([-16, -6, 6, 16].map((x) => at([x, plan.y + plan.d - 3, top])), { size: 0.4, tone: "lo" }));
  // the website: an upright tablet in a stand, screen facing the viewer
  const tab = { x: -18, y: TRACK_Y - 4, w: 36, d: 4, r: 1.2 };
  out.push(S(slab({ x: -12, y: TRACK_Y - 8, w: 24, d: 10, r: 1.5 }, top, 3, 3, 0.4), { tone: "mid" }));
  out.push(S(slab(tab, top + 3, 30, 3, 0.6), { tone: "hi", lit: true }));
  const fy = tab.y + tab.d, z0 = top + 3;
  out.push(`<path class="ap3d-site" d="${k.pathOf([at([tab.x + 2.5, fy, z0 + 27]), at([tab.x + tab.w - 2.5, fy, z0 + 27]), at([tab.x + tab.w - 2.5, fy, z0 + 3]), at([tab.x + 2.5, fy, z0 + 3])], true)}"/>`);
  out.push(L(k.segment([tab.x + 5, fy, z0 + 23.5], [tab.x + tab.w - 5, fy, z0 + 23.5], P), { tone: "lit" }));
  out.push(D([at([tab.x + 5.5, fy, z0 + 20]), at([tab.x + 8, fy, z0 + 20]), at([tab.x + 10.5, fy, z0 + 20])], { size: 0.55, tone: "hi" }));
  out.push(`<path class="ap3d-sitebar" d="${k.pathOf([at([tab.x + 5, fy, z0 + 15]), at([tab.x + 21, fy, z0 + 15]), at([tab.x + 21, fy, z0 + 7]), at([tab.x + 5, fy, z0 + 7])], true)}"/>`);
  out.push(L(k.segment([tab.x + 24, fy, z0 + 14], [tab.x + 31, fy, z0 + 14], P), { tone: "mid", free: "both" }));
  out.push(L(k.segment([tab.x + 24, fy, z0 + 10.5], [tab.x + 31, fy, z0 + 10.5], P), { tone: "mid", free: "both" }));
  out.push(L(k.segment([tab.x + 24, fy, z0 + 7], [tab.x + 29, fy, z0 + 7], P), { tone: "mid", free: "both" }));
  return out.join("");
}

// ---------------------------------------------------------------- assemble
const BASES = [s1, s2, s3, s4, s5, s6, s7, s8];
const stationsBack = STATION_X.map((sx, i) => ({ d: depth(sx, -60), svg: pedestal(sx, i + 1) + BASES[i](sx) + lamp(sx, i + 1) }))
  .sort((a, b) => a.d - b.d).map((s) => s.svg).join("");
const overTrack = [s2Top(STATION_X[1]), s4Top(STATION_X[3])].join("");

const startX = STOPS[0];
const svg = k.figureSvg({
  width: WIDTH,
  height: HEIGHT,
  label: "The ACCESSPATH audit line. A website cartridge rides a carriage past eight stations: 1 URL terminal, 2 magnifier, 3 condition knobs, 4 TinyFish probe, 5 tape recorder, 6 score dial, 7 fix printer, 8 report board. Station 9, a turntable, sends it back along the return belt to retest.",
  body: [
    bench(),
    rails(),
    stationsBack,
    turntable(),
    `<g data-part="cart" transform="${k.translateAlong(P, [startX, 0, 0])}">${cartridge()}</g>`,
    overTrack,
    `<g data-part="belt">${belt()}</g>`,
  ],
});

const plate = k.plateHtml({
  fig: "Fig 1",
  title: "Audit line",
  hint: "Follows the live audit",
  readout: "1 · Enter website URL",
  body: `<div class="iso-stage ap3d-stage" tabindex="0" role="img" aria-label="Audit workflow machine; the carriage stops at the step that is running">${svg}</div>`,
});

// ---------------------------------------------------------------- page CSS (dashboard palette) + runtime
const CSS = k.ISO_CSS + `
.ap3d.iso{--anatomy-page:transparent;--anatomy-card:#0d1a3a;--anatomy-text:#9fb0d6;--anatomy-strong:#e8eefc;--anatomy-muted:#6f82b0;
 --anatomy-paper:#10204a;--anatomy-face:#172a57;--anatomy-top:#1c3266;
 --anatomy-shade-0:#0b1633;--anatomy-shade-1:#0f1d42;--anatomy-shade-2:#13244f;--anatomy-shade-3:#182c5c;
 --anatomy-lit-top:#2c4c92;--anatomy-lit-shade:#203b76;
 --anatomy-hi:#dbe5ff;--anatomy-mid:#7189c2;--anatomy-lo:#3f5b95;--anatomy-faint:#2b4376;--anatomy-lit:#ffffff;
 --anatomy-halo:#020612;--anatomy-halo-opacity:.9;--anatomy-dot:#e8eefc;
 --ap-run:#38bdf8;--ap-done:#22c55e;--ap-fail:#ef4444;--ap-skip:#64748b;--ap-ready:#3b82f6}
.ap3d .iso-figure{margin:0}
.ap3d .iso-plate{background:linear-gradient(180deg,#0e1c40,#0b1633);border:1px solid #26407a;box-shadow:none;border-radius:14px;padding:40px 10px 42px}
.ap3d .iso-plate-corners{inset:14px 16px}
.ap3d .iso-plate-corner{color:var(--anatomy-muted)}
.ap3d .iso-plate-corner[data-readout]{color:var(--anatomy-strong)}
.ap3d .ap3d-stage{outline:none}
.ap3d .ap3d-stage:focus-visible{outline:3px solid #38bdf8;outline-offset:4px;border-radius:8px}
.ap3d-glow{fill:transparent;opacity:0;transition:opacity .4s}
.ap3d-lamp[data-status="running"] .ap3d-glow{fill:var(--ap-run);opacity:.35;filter:blur(3px)}
.ap3d-lamp[data-status="done"] .ap3d-glow{fill:var(--ap-done);opacity:.28;filter:blur(3px)}
.ap3d-lamp[data-status="failed"] .ap3d-glow{fill:var(--ap-fail);opacity:.35;filter:blur(3px)}
.ap3d-lamp[data-status="ready"] .ap3d-glow{fill:var(--ap-ready);opacity:.35;filter:blur(3px)}
.ap3d-lamp[data-status="running"] .iso-solid:last-of-type>.iso-top,.ap3d-lamp[data-status="running"] .iso-solid:last-of-type>.iso-shade{fill:var(--ap-run)}
.ap3d-lamp[data-status="done"] .iso-solid:last-of-type>.iso-top,.ap3d-lamp[data-status="done"] .iso-solid:last-of-type>.iso-shade{fill:var(--ap-done)}
.ap3d-lamp[data-status="failed"] .iso-solid:last-of-type>.iso-top,.ap3d-lamp[data-status="failed"] .iso-solid:last-of-type>.iso-shade{fill:var(--ap-fail)}
.ap3d-lamp[data-status="skipped"] .iso-solid:last-of-type>.iso-top{fill:var(--ap-skip)}
.ap3d-lamp[data-status="ready"] .iso-solid:last-of-type>.iso-top,.ap3d-lamp[data-status="ready"] .iso-solid:last-of-type>.iso-shade{fill:var(--ap-ready)}
.ap3d-lamp[data-status="running"] .ap3d-glow{animation:ap3dPulse 1.2s ease-in-out infinite}
@keyframes ap3dPulse{50%{opacity:.08}}
.ap3d-screen{fill:#0a1736;stroke:var(--anatomy-lo);stroke-width:.6}
.ap3d-site{fill:#0b1a3e;stroke:var(--anatomy-mid);stroke-width:.6}
.ap3d-sitebar{fill:#1e3a8a}
.ap3d[data-task="failed"] .ap3d-sitebar{fill:#7f1d1d}
.ap3d[data-task="passed"] .ap3d-sitebar{fill:#14532d}
.ap3d-glass{fill:#38bdf8;opacity:.08}
.ap3d-bar{fill:var(--anatomy-lo);transition:fill .5s}
.ap3d[data-reported="1"] .ap3d-bar{fill:#3b82f6}
.ap3d[data-reported="1"] .ap3d-bar[data-bar="1"],.ap3d[data-reported="1"] .ap3d-bar[data-bar="3"]{fill:#38bdf8}
.ap3d-ticket{opacity:0;transition:opacity .6s}
.ap3d[data-printed="1"] .ap3d-ticket{opacity:1}
.ap3d-knob[data-on="0"] .iso-top{fill:var(--anatomy-top)}
.ap3d-knob[data-on="1"] .iso-solid>.iso-top{fill:#1e3a8a}
.ap3d-flow{stroke-dasharray:3 9;opacity:.0;transition:opacity .4s}
.ap3d[data-loop="1"] .ap3d-flow{opacity:1;stroke:var(--ap-ready);animation:ap3dFlow 1s linear infinite}
.ap3d[data-loop="1"] .ap3d-chevrons{stroke:var(--ap-ready)}
@keyframes ap3dFlow{to{stroke-dashoffset:-12}}
@media (prefers-reduced-motion:reduce){.ap3d *{animation:none!important;transition:none!important}}
`;

const kitSource = readFileSync(join(HERE, "kit", "iso-kit.mjs"), "utf8").replace(/^export /gm, "");

const runtime = `
const P = ${JSON.stringify(P)};
const STOPS = ${JSON.stringify(STOPS)};
const STATION_X = ${JSON.stringify(STATION_X)};
const REELS = ${JSON.stringify(STATION_X.map((sx) => REELS(sx))[4])};
const DIAL_C = ${JSON.stringify(DIAL(STATION_X[5]))}, DIAL_R = ${DIAL_R}, DIAL_TOP = ${DIAL_Z + 7.2};
const REEL_TOP = ${PED_H + 12 + 2.4};
const PROBE_UP = 14, PROBE_DOWN = 0; // tip rests 14 above the cartridge, drops to touch it
const TITLES = ["Enter website URL","Inspect the site","Select conditions","Attempt journey","Record interactions","Analyse findings","Explain & recommend","Show audit report","Fix and rerun"];
const needleD = (score) => {
  const [x, y] = DIAL_C;
  const a = -Math.PI * 0.75 + (Math.max(0, Math.min(100, score)) / 100) * Math.PI * 1.5;
  const r = DIAL_R - 4;
  return lineOnTop([x - Math.sin(a) * 3, y + Math.cos(a) * 3], [x + Math.sin(a) * r, y - Math.cos(a) * r], DIAL_TOP, P);
};
const spokes = ([cx, cy], turn) => [0, 1, 2].map((i) => {
  const a = turn + i * Math.PI * 2 / 3;
  return lineOnTop([cx + Math.cos(a) * 3.4, cy + Math.sin(a) * 3.4], [cx + Math.cos(a) * 8.6, cy + Math.sin(a) * 8.6], REEL_TOP, P);
}).join("");

function mount(host) {
  if (!document.getElementById("ap3d-css")) {
    const st = document.createElement("style"); st.id = "ap3d-css"; st.textContent = CSS; document.head.appendChild(st);
  }
  host.classList.add("iso", "ap3d");
  host.innerHTML = PLATE;
  const svg = host.querySelector("svg");
  const q = (s) => svg.querySelector(s);
  const cart = q('[data-part="cart"]'), probe = q('[data-part="probe"]'), needle = q('[data-part="needle"]');
  const sp = [q('[data-part="spokes0"]'), q('[data-part="spokes1"]')];
  const lamps = [...svg.querySelectorAll(".ap3d-lamp")];
  const knobs = [...svg.querySelectorAll(".ap3d-knob")];
  const readout = host.querySelector("[data-readout]");
  const still = matchMedia("(prefers-reduced-motion: reduce)");
  let x = STOPS[0], target = STOPS[0], probeZ = 14, probeT = 0, score = 0, scoreT = 0, reel = 0;
  let mode = "idle", runStep = 0, frame = 0, last = 0, clock = 0, visible = true, alive = true;
  const io = new IntersectionObserver((e) => { visible = e[e.length - 1].isIntersecting; if (visible) run(); });
  io.observe(host);

  function draw() {
    cart.setAttribute("transform", translateAlong(P, [x, 0, 0]));
    probe.setAttribute("transform", translateAlong(P, [0, 0, probeZ]));
    needle.setAttribute("d", needleD(score));
    sp[0].setAttribute("d", spokes(REELS[0], reel));
    sp[1].setAttribute("d", spokes(REELS[1], reel * 1.3));
  }
  function tick(now) {
    const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60;
    last = now;
    const calm = still.matches;
    if (mode === "idle") {
      clock += dt;
      const i = Math.floor(clock / 1.6) % STOPS.length;
      target = STOPS[i];
      setLamps(STOPS.map((_, j) => (j < i ? "done" : j === i ? "running" : "pending")));
      probeT = i === 3 ? 1 : 0;
      scoreT = i >= 5 ? 72 : 0;
      setReadout((i + 1) + " · " + TITLES[i]);
    }
    x = calm ? target : x + (target - x) * (1 - Math.exp(-dt / 0.35));
    if (Math.abs(target - x) < 0.05) x = target;
    const atAgent = Math.abs(x - STATION_X[3]) < 2;
    const want = probeT && atAgent ? PROBE_DOWN : PROBE_UP;
    probeZ = calm ? want : probeZ + (want - probeZ) * (1 - Math.exp(-dt / 0.18));
    score = calm ? scoreT : score + (scoreT - score) * (1 - Math.exp(-dt / 0.5));
    const recording = (mode === "idle" ? Math.floor(clock / 1.6) % STOPS.length === 4 : runStep === 5);
    if (recording && !calm) reel += dt * 3.2;
    draw();
    const moving = Math.abs(target - x) > 0.01 || Math.abs(want - probeZ) > 0.01 || Math.abs(scoreT - score) > 0.05 || recording;
    frame = alive && visible && (mode === "idle" || moving) && !calm ? requestAnimationFrame(tick) : 0;
    if (calm) { x = target; probeZ = want; score = scoreT; draw(); }
  }
  function run() { if (!frame && visible && alive) { last = 0; frame = requestAnimationFrame(tick); } }
  function setLamps(states) { lamps.forEach((l, i) => { const s = states[i] || "pending"; if (l.dataset.status !== s) l.dataset.status = s; }); }
  function setReadout(t) { if (readout && readout.textContent !== t) readout.textContent = t; }

  function update(audit) {
    if (!audit || !audit.progress) { mode = "idle"; host.dataset.task = ""; host.dataset.loop = "0"; host.dataset.printed = "0"; host.dataset.reported = "0"; run(); return; }
    mode = "live";
    const prog = audit.progress;
    const running = prog.find((p) => p.status === "running");
    const done = audit.status === "done";
    let step = running ? running.n : done ? 9 : (audit.current_step || 1);
    if (audit.status === "error") { const f = prog.find((p) => p.status === "failed"); step = f ? f.n : step; }
    runStep = running ? running.n : 0;
    target = STOPS[step - 1];
    setLamps(prog.map((p) => p.status));
    probeT = runStep === 4 ? 1 : 0;
    const s = (audit.result && typeof audit.result.score === "number") ? audit.result.score : (typeof audit.score === "number" ? audit.score : null);
    const analysed = prog[5] && prog[5].status === "done";
    scoreT = s == null || !analysed ? 0 : s;
    knobs.forEach((kn, i) => {
      const key = ["keyboard", "screen_reader", "mobile"][i];
      const on = !audit.conditions || audit.conditions[key] !== false;
      kn.dataset.on = on ? "1" : "0";
      const ptr = kn.querySelector(".ap3d-pointer");
      ptr.setAttribute("d", ptr.getAttribute(on ? "data-on-d" : "data-off-d"));
    });
    host.dataset.task = done ? (audit.task_status || "") : "";
    host.dataset.printed = prog[6] && prog[6].status === "done" ? "1" : "0";
    host.dataset.reported = prog[7] && prog[7].status === "done" ? "1" : "0";
    host.dataset.loop = prog[8] && prog[8].status === "ready" ? "1" : "0";
    const cur = prog[step - 1] || { title: TITLES[step - 1], status: "" };
    let text = step + " · " + cur.title + (cur.status && cur.status !== "done" ? " · " + cur.status : "");
    if (done) text = "9 · Fix and rerun · " + (audit.task_status || "") + (s != null ? " · score " + Math.round(s) + "/100" : "");
    setReadout(text);
    run();
  }
  run();
  return { update, destroy() { alive = false; io.disconnect(); cancelAnimationFrame(frame); } };
}
window.APWorkflow3D = { mount };
`;

const bundle = `/* Generated by frontend/workflow3d/build.mjs — do not edit by hand.
 * Isometric audit-line figure drawn with the anatomy kit (MIT, © 2026 Ryan, github.com/wheresryan22/anatomy). */
(function () {
${kitSource}
const CSS = ${JSON.stringify(CSS)};
const PLATE = ${JSON.stringify(plate)};
${runtime}
})();
`;
writeFileSync(OUT, bundle);
console.log("wrote", OUT, (bundle.length / 1024).toFixed(0) + " KB");

if (DEMO) {
  writeFileSync(DEMO, `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Audit line</title>
<style>body{margin:0;background:#0a1430;font:14px system-ui;color:#e8eefc}main{max-width:1100px;margin:24px auto;padding:0 16px}</style></head>
<body><main><div id="fig"></div></main><script src="../workflow3d.js"></script><script>
const api = APWorkflow3D.mount(document.getElementById("fig"));
const q = new URLSearchParams(location.search);
if (q.get("step")) {
  const n = +q.get("step"); const done = n > 9;
  const progress = Array.from({length: 9}, (_, i) => ({ n: i + 1, title: ["Enter website URL","Inspect the site","Select conditions","Attempt journey","Record interactions","Analyse findings","Explain & recommend","Show audit report","Fix and rerun"][i],
    status: done ? (i === 8 ? "ready" : i === 3 ? "skipped" : "done") : i + 1 < n ? "done" : i + 1 === n ? "running" : "pending" }));
  api.update({ status: done ? "done" : "running", task_status: q.get("task") || "failed", score: done ? 43 : null, progress, conditions: { keyboard: true, screen_reader: true, mobile: q.get("mobile") !== "0" } });
}
</script></body></html>`);
  console.log("wrote", DEMO);
}
