#!/usr/bin/env node
/**
 * Universal Studio Director v7.1 — Web-Cinema Parallel RGBA & Alpha MOV Engine
 * ============================================================================
 * Zero-dependency Node.js v22+ renderer driving Chrome Headless via native
 * `globalThis.WebSocket` CDP (`Emulation.setDefaultBackgroundColorOverride`
 * alpha=0 + `Page.captureScreenshot({ format: "png", omitBackground: true,
 * optimizeForSpeed: true, captureBeyondViewport: false })`).
 *
 * v7.1 Upgrades:
 *   - Multi-Tab Parallel Worker Pool (`--concurrency <1..4>`, default 4 in
 *     `--batch-json` mode) sharing ONE Chrome instance via `Target.createTarget`
 *     + `Target.attachToTarget({ flatten: true })` per job.
 *   - Fast Screenshot (`optimizeForSpeed: true`) + dual alpha codecs:
 *       * `prores4444` (default): `prores_ks -profile:v 4444 -pix_fmt yuva444p10le -threads 2`
 *       * `qtrle`               : `qtrle -pix_fmt argb -threads 2`
 *   - Supersampled `scale` (`deviceScaleFactor`, e.g. 1.5 / 2.0) with automatic
 *     Lanczos downscale (`-vf scale=W:H:flags=lanczos`) to logical `width x height`.
 *   - Default `fps = 60` for razor-sharp kinetic typography & studio motion.
 *   - Clean `DBUS_SESSION_BUS_ADDRESS=/dev/null`, `detached: true`, and
 *     `process.kill(-chrome.pid, "SIGKILL")` process-group teardown in `finally`.
 */

import { spawn } from "node:child_process";
import { once } from "node:events";
import fs from "node:fs";
import fsp from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const CHROME_CANDIDATES = [
  process.env.CHROME_BIN,
  path.join(os.homedir(), ".local/bin/google-chrome"),
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean);

function resolveChromeBinary() {
  for (const candidate of CHROME_CANDIDATES) {
    try {
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    } catch {
      // ignore
    }
  }
  throw new Error(
    `Chrome binary not found. Checked: ${CHROME_CANDIDATES.join(", ")}`
  );
}

function normalizeAlphaCodec(raw) {
  const v = String(raw || "prores4444")
    .trim()
    .toLowerCase();
  if (v === "qtrle") return "qtrle";
  if (
    v === "prores4444" ||
    v === "prores" ||
    v === "prores_ks" ||
    v === "4444"
  ) {
    return "prores4444";
  }
  throw new Error(
    `Unsupported alpha codec '${raw}'. Expected 'prores4444' or 'qtrle'.`
  );
}

function parseCliArgs(argv) {
  const args = {
    mode: "auto",
    width: 1080,
    height: 1920,
    scale: 1,
    downscaleToLogical: true,
    fps: 60,
    fpsExplicit: false,
    frames: 60,
    duration: null,
    frameIdx: null,
    alphaCodec: "prores4444",
    alphaCodecExplicit: false,
    concurrency: 4,
    concurrencyExplicit: false,
    html: null,
    url: null,
    out: null,
    batchJson: null,
    ffmpegBin: process.env.FFMPEG_BIN || "ffmpeg",
    timeoutMs: 60000,
    quiet: false,
  };

  for (let i = 2; i < argv.length; i++) {
    const token = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) {
        throw new Error(`Missing value after ${token}`);
      }
      return argv[++i];
    };
    switch (token) {
      case "--html":
        args.html = next();
        break;
      case "--url":
        args.url = next();
        break;
      case "--out":
      case "-o":
        args.out = next();
        break;
      case "--mode":
        args.mode = next();
        break;
      case "--width":
      case "-w":
        args.width = Number.parseInt(next(), 10);
        break;
      case "--height":
      case "-h":
        args.height = Number.parseInt(next(), 10);
        break;
      case "--scale":
      case "--dpr":
        args.scale = Number.parseFloat(next());
        break;
      case "--no-downscale":
        args.downscaleToLogical = false;
        break;
      case "--fps":
        args.fps = Number.parseFloat(next());
        args.fpsExplicit = true;
        break;
      case "--frames":
        args.frames = Number.parseInt(next(), 10);
        break;
      case "--duration":
        args.duration = Number.parseFloat(next());
        break;
      case "--frame-idx":
        args.frameIdx = Number.parseInt(next(), 10);
        break;
      case "--alpha-codec":
        args.alphaCodec = normalizeAlphaCodec(next());
        args.alphaCodecExplicit = true;
        break;
      case "--concurrency":
      case "-c": {
        const cVal = Number.parseInt(next(), 10);
        args.concurrency = Math.max(1, Math.min(4, Number.isFinite(cVal) ? cVal : 4));
        args.concurrencyExplicit = true;
        break;
      }
      case "--batch-json":
        args.batchJson = next();
        break;
      case "--ffmpeg":
        args.ffmpegBin = next();
        break;
      case "--timeout-ms":
        args.timeoutMs = Number.parseInt(next(), 10);
        break;
      case "--quiet":
        args.quiet = true;
        break;
      case "--help":
        printHelp();
        process.exit(0);
        break;
      default:
        throw new Error(`Unknown CLI flag: ${token}`);
    }
  }
  return args;
}

function printHelp() {
  console.log(`Usage:
  node web_cinema_plate_engine.mjs --html <plate.html> --out <plate.png|clip.mov> [options]
  node web_cinema_plate_engine.mjs --batch-json <jobs.json> [--concurrency 4]

Options:
  --mode <auto|still|mov|sequence>      Render mode (auto-inferred from --out extension)
  --width <px>                          Logical viewport width (default: 1080)
  --height <px>                         Logical viewport height (default: 1920)
  --scale <dpr>                         deviceScaleFactor (default: 1; >1 Lanczos downscales to logical WxH)
  --no-downscale                        Keep physical scaled resolution when --scale > 1
  --fps <num>                           Frame rate for mov/sequence (default: 60)
  --frames <int>                        Total frames for mov/sequence (default: 60)
  --duration <sec>                      Duration in seconds (overrides --frames = round(duration*fps))
  --frame-idx <int>                     Optional frame index for still snapshot
  --alpha-codec <prores4444|qtrle>      Alpha video codec for .mov (default: prores4444)
  --concurrency <1..4>                  Parallel CDP tabs in --batch-json mode (default: 4)
  --batch-json <file>                   JSON array (or {jobs, concurrency}) sharing one Chrome session
  --quiet                               Suppress progress logs
`);
}

class CDPBrowserClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
    this.closed = false;
  }

  async connect(timeoutMs = 15000) {
    if (typeof globalThis.WebSocket !== "function") {
      throw new Error(
        `globalThis.WebSocket is unavailable in Node ${process.version}. Requires Node v22+.`
      );
    }
    this.ws = new globalThis.WebSocket(this.wsUrl);

    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`Timed out connecting to CDP WebSocket: ${this.wsUrl}`));
      }, timeoutMs);

      this.ws.onopen = () => {
        clearTimeout(timer);
        resolve();
      };
      this.ws.onerror = (err) => {
        clearTimeout(timer);
        reject(
          new Error(`CDP WebSocket connection error: ${err?.message || "unknown"}`)
        );
      };
    });

    this.ws.onmessage = (event) => {
      let text;
      if (typeof event.data === "string") {
        text = event.data;
      } else if (event.data instanceof ArrayBuffer) {
        text = Buffer.from(event.data).toString("utf8");
      } else {
        text = String(event.data);
      }

      let msg;
      try {
        msg = JSON.parse(text);
      } catch {
        return;
      }

      if (typeof msg.id === "number") {
        const entry = this.pending.get(msg.id);
        if (entry) {
          this.pending.delete(msg.id);
          clearTimeout(entry.timer);
          if (msg.error) {
            entry.reject(
              new Error(
                `CDP ${entry.method} failed: ${
                  msg.error.message || JSON.stringify(msg.error)
                }`
              )
            );
          } else {
            entry.resolve(msg.result || {});
          }
        }
      }
    };

    this.ws.onclose = () => {
      this.closed = true;
      for (const [, entry] of this.pending) {
        clearTimeout(entry.timer);
        entry.reject(
          new Error(`CDP WebSocket closed while awaiting ${entry.method}`)
        );
      }
      this.pending.clear();
    };
  }

  send(method, params = {}, sessionId = undefined, timeoutMs = 35000) {
    if (!this.ws || this.closed) {
      return Promise.reject(
        new Error(`Cannot send ${method}: CDP WebSocket closed`)
      );
    }
    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) {
      payload.sessionId = sessionId;
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout (${timeoutMs}ms) on ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer, method });
      this.ws.send(JSON.stringify(payload));
    });
  }

  close() {
    if (this.ws && !this.closed) {
      try {
        this.ws.close();
      } catch {
        // ignore
      }
      this.closed = true;
    }
  }
}

async function launchHeadlessChrome(timeoutMs = 20000) {
  const chromeBin = resolveChromeBinary();
  const userDataDir = await fsp.mkdtemp(
    path.join(os.tmpdir(), "usd-v71-chrome-")
  );

  const chromeArgs = [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--hide-scrollbars",
    "--allow-file-access-from-files",
    "--font-render-hinting=none",
    "--force-color-profile=srgb",
    "--password-store=basic",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${userDataDir}`,
    "--remote-debugging-port=0",
    "about:blank",
  ];

  const chrome = spawn(chromeBin, chromeArgs, {
    detached: true,
    stdio: ["ignore", "ignore", "pipe"],
    env: {
      ...process.env,
      DBUS_SESSION_BUS_ADDRESS: "/dev/null",
    },
  });

  const killChromeGroupSync = () => {
    try {
      process.kill(-chrome.pid, "SIGKILL");
    } catch {
      // ignore
    }
    try {
      chrome.kill("SIGKILL");
    } catch {
      // ignore
    }
  };

  const onSigInt = () => {
    killChromeGroupSync();
    process.exit(130);
  };
  const onSigTerm = () => {
    killChromeGroupSync();
    process.exit(143);
  };
  process.once("SIGINT", onSigInt);
  process.once("SIGTERM", onSigTerm);

  let stderrTail = "";
  const activePortFile = path.join(userDataDir, "DevToolsActivePort");

  let browserWsUrl;
  try {
    browserWsUrl = await new Promise((resolve, reject) => {
      let settled = false;
      const finish = (fn, val) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeoutTimer);
        clearInterval(pollTimer);
        fn(val);
      };

      const timeoutTimer = setTimeout(() => {
        finish(
          reject,
          new Error(
            `Timed out waiting for Chrome DevTools WebSocket. Stderr:\n${stderrTail}`
          )
        );
      }, timeoutMs);

      chrome.stderr.setEncoding("utf8");
      // Continuously drain stderr so Chrome never blocks on full pipe buffer
      chrome.stderr.on("data", (chunk) => {
        if (stderrTail.length < 8192) {
          stderrTail += chunk;
        }
        const match =
          chunk.match(/DevTools listening on (ws:\/\/[^\s\r\n]+)/) ||
          stderrTail.match(/DevTools listening on (ws:\/\/[^\s\r\n]+)/);
        if (match) {
          finish(resolve, match[1].trim());
        }
      });

      chrome.once("error", (err) => {
        finish(reject, new Error(`Failed to spawn Chrome: ${err.message}`));
      });

      chrome.once("exit", (code, sig) => {
        finish(
          reject,
          new Error(
            `Chrome exited prematurely (code=${code}, sig=${sig}). Stderr:\n${stderrTail}`
          )
        );
      });

      const pollTimer = setInterval(async () => {
        try {
          const raw = await fsp.readFile(activePortFile, "utf8");
          const lines = raw
            .split(/\r?\n/)
            .map((s) => s.trim())
            .filter(Boolean);
          if (lines.length >= 2) {
            const port = Number.parseInt(lines[0], 10);
            const wsPath = lines[1];
            if (port > 0 && wsPath.startsWith("/")) {
              finish(resolve, `ws://127.0.0.1:${port}${wsPath}`);
            }
          }
        } catch {
          // DevToolsActivePort not written yet
        }
      }, 40);
    });

    await new Promise((r) => setTimeout(r, 120));

    const cdp = new CDPBrowserClient(browserWsUrl);
    await cdp.connect(timeoutMs);

    let closedOnce = false;
    const close = async () => {
      if (closedOnce) return;
      closedOnce = true;
      process.removeListener("SIGINT", onSigInt);
      process.removeListener("SIGTERM", onSigTerm);
      cdp.close();
      try {
        chrome.stderr.removeAllListeners();
        chrome.stderr.destroy();
      } catch {
        // ignore
      }
      killChromeGroupSync();
      await fsp.rm(userDataDir, { recursive: true, force: true }).catch(() => {});
    };

    return { chrome, userDataDir, browserWsUrl, cdp, close };
  } catch (err) {
    process.removeListener("SIGINT", onSigInt);
    process.removeListener("SIGTERM", onSigTerm);
    killChromeGroupSync();
    await fsp.rm(userDataDir, { recursive: true, force: true }).catch(() => {});
    throw err;
  }
}

function normalizeMode(rawMode, outPath) {
  const m = String(rawMode || "auto").toLowerCase();
  if (m !== "auto") {
    return m;
  }
  const ext = path.extname(String(outPath || "")).toLowerCase();
  if (ext === ".mov") return "mov";
  if (ext === ".png") return "still";
  return "sequence";
}

function resolveTargetUrl(job) {
  if (job.url) {
    return job.url;
  }
  if (job.html) {
    const absHtml = path.resolve(job.html);
    if (!fs.existsSync(absHtml)) {
      throw new Error(`HTML file does not exist: ${absHtml}`);
    }
    return pathToFileURL(absHtml).href;
  }
  throw new Error("Either `html` or `url` must be specified for render job.");
}

async function waitForPageReady(cdp, sessionId, timeoutMs = 30000) {
  const evalRes = await cdp.send(
    "Runtime.evaluate",
    {
      expression: `(async () => {
        while (document.readyState !== "complete") {
          await new Promise((r) => setTimeout(r, 12));
        }
        if (document.fonts && document.fonts.ready) {
          await document.fonts.ready;
        }
        const imgs = Array.from(document.images || []);
        await Promise.all(imgs.map((img) => {
          if (img.complete) return Promise.resolve();
          return new Promise((res) => {
            img.addEventListener("load", res, { once: true });
            img.addEventListener("error", res, { once: true });
          });
        }));
        await new Promise((r) => {
          let done = false;
          const finish = () => { if (!done) { done = true; r(true); } };
          requestAnimationFrame(() => requestAnimationFrame(finish));
          setTimeout(finish, 32);
        });
        return {
          fontsStatus: document.fonts ? document.fonts.status : "unknown",
          imageCount: imgs.length,
          hasSetFrame: typeof window.__setFrame === "function"
        };
      })()`,
      awaitPromise: true,
      returnByValue: true,
    },
    sessionId,
    timeoutMs
  );

  if (evalRes.exceptionDetails) {
    throw new Error(
      `Page readiness evaluation failed: ${JSON.stringify(
        evalRes.exceptionDetails
      )}`
    );
  }
  return evalRes.result?.value || {};
}

async function applyFrameState(cdp, sessionId, frameIdx, totalFrames, fps) {
  const evalRes = await cdp.send(
    "Runtime.evaluate",
    {
      expression: `(async () => {
        if (typeof window.__setFrame === "function") {
          await window.__setFrame(${Number(frameIdx)}, ${Number(totalFrames)}, ${Number(fps)});
        }
        if (document.body) {
          void document.body.offsetHeight;
        }
        await new Promise((r) => {
          let done = false;
          const finish = () => { if (!done) { done = true; r(true); } };
          requestAnimationFrame(finish);
          setTimeout(finish, 16);
        });
        return true;
      })()`,
      awaitPromise: true,
      returnByValue: true,
    },
    sessionId
  );
  if (evalRes.exceptionDetails) {
    throw new Error(
      `window.__setFrame(${frameIdx}, ${totalFrames}, ${fps}) threw: ${JSON.stringify(
        evalRes.exceptionDetails
      )}`
    );
  }
}


// v7.9.0: in-page text probes. TEXT_SIZE_PROBE_JS returns every text-bearing element with its computed font size times its screen
// scale (the size it is DRAWN at, before the plate scale). WORD_GAP_PROBE_JS measures, on the current frame, the INK gap between
// adjacent words of the guarded lines ([data-ws-nat0] / [data-pfd-line], or the ids given) minus the screen-space blur of both
// neighbours, against 0.25 em (motion_gate.check_word_gaps).
const PROBE_COMMON_JS = String.raw`
  const __pfdSkip = new Set(["SCRIPT", "STYLE", "TITLE", "DEFS", "NOSCRIPT", "TEMPLATE"]);
  function __pfdMatScale(el) {
    let m = new DOMMatrix();
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const t = getComputedStyle(n).transform;
      if (t && t !== "none") m = new DOMMatrix(t).multiply(m);
    }
    return Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
  }
  function __pfdBoxScale(el) {
    const r = el.getBoundingClientRect();
    if (el instanceof SVGElement) {
      let bb = null;
      try { bb = el.getBBox(); } catch (e) { bb = null; }
      if (!bb || !(bb.width > 0) || !(bb.height > 0)) return null;
      return Math.min(r.width / bb.width, r.height / bb.height);
    }
    const sz = __pfdLayoutSize(el);
    if (!sz) return null;
    const rr = sz[2].getBoundingClientRect();
    return Math.min(rr.width / sz[0], rr.height / sz[1]);
  }
  // Untransformed border-box size in FRACTIONAL px of el, or of its nearest non-inline ancestor for an inline box (CSS transforms do
  // not apply to inline boxes). offsetWidth / offsetHeight are rounded to whole px: a 42.6 px box read as 43 gave a 0.99x "scale".
  function __pfdLayoutSize(el) {
    for (let n = el; n && n.nodeType === 1 && !(n instanceof SVGElement); n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (!cs.width.endsWith("px") || !cs.height.endsWith("px")) continue;
      let w = parseFloat(cs.width), h = parseFloat(cs.height);
      if (cs.boxSizing !== "border-box") {
        const px = (k) => parseFloat(cs[k]) || 0;
        w += px("paddingLeft") + px("paddingRight") + px("borderLeftWidth") + px("borderRightWidth");
        h += px("paddingTop") + px("paddingBottom") + px("borderTopWidth") + px("borderBottomWidth");
      }
      if (!(w > 0) || !(h > 0) || Math.abs(w - n.offsetWidth) > 1 || Math.abs(h - n.offsetHeight) > 1) return null;
      return [w, h, n];
    }
    return null;
  }
  function __pfdScale(el) {
    const m = el instanceof SVGElement ? null : __pfdMatScale(el);
    const b = __pfdBoxScale(el);
    if (m == null) return b == null ? 1 : b;
    return b == null ? m : Math.min(m, b);
  }
  function __pfdBlurPx(el) {
    const f = getComputedStyle(el).filter;
    if (!f || f === "none") return 0;
    let s = 0;
    for (const m of f.matchAll(/blur\(\s*([\d.]+)px\s*\)/g)) s += Number(m[1]);
    return s;
  }
  function __pfdLabel(el) {
    return el.id ? "#" + el.id : (el.getAttribute("class") || el.tagName.toLowerCase()).split(/\s+/)[0].replace(/^/, ".");
  }
`;

const TEXT_SIZE_PROBE_JS = `(() => {
  ${PROBE_COMMON_JS}
  const out = [];
  for (const el of document.querySelectorAll("body *")) {
    if (__pfdSkip.has(el.tagName.toUpperCase())) continue;
    let txt = "";
    for (const c of el.childNodes) if (c.nodeType === 3) txt += c.textContent;
    txt = txt.replace(/\\s+/g, " ").trim();
    if (!txt) continue;
    if (el.getClientRects().length === 0) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize) || 0;
    const sc = __pfdScale(el);
    let box = null;
    for (const c of el.childNodes) {
      if (c.nodeType !== 3 || !c.textContent.trim()) continue;
      const rg = document.createRange();
      rg.selectNodeContents(c);
      const r = rg.getBoundingClientRect();
      if (!(r.width > 0)) continue;
      box = box ? [Math.min(box[0], r.left), Math.min(box[1], r.top), Math.max(box[2], r.right), Math.max(box[3], r.bottom)]
                : [r.left, r.top, r.right, r.bottom];
    }
    out.push({ label: __pfdLabel(el), text: txt.slice(0, 48), fontPx: +fs.toFixed(2), scale: +sc.toFixed(4), effPx: +(fs * sc).toFixed(2),
               box: box ? box.map((v) => +v.toFixed(1)) : null, view: [window.innerWidth, window.innerHeight] });
  }
  return out;
})()`;

function wordGapProbeJs(ids) {
  return `(() => {
  ${PROBE_COMMON_JS}
  ${TEXT_PATH_COMMON_JS}
  const ids = ${JSON.stringify(ids || null)};
  // "*" = EVERY drawn text line of the page (the nearest non-inline ancestor of each non-empty text node, glow / echo copies included),
  // so a line the page guard does not know about is measured too
  const all = ids === "*";
  const rootOf = (node) => {
    let n = node.parentElement;
    if (!n || !node.textContent.trim() || n.closest("script, style, title, defs, noscript, template")) return null;
    if (n instanceof SVGElement) return n.closest("text") || n;
    while (n.parentElement && n !== document.body && getComputedStyle(n).display.startsWith("inline")) n = n.parentElement;
    return n;
  };
  const allRoots = () => {
    const set = new Set();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) { const r = rootOf(node); if (r && !r.closest("[data-pfd-glow]")) set.add(r); }
    return Array.from(set);
  };
  const roots = all ? allRoots() : ids ? ids.map((i) => document.getElementById(i)).filter(Boolean)
                    : Array.from(document.querySelectorAll("[data-ws-nat0], [data-pfd-line]"));
  const ctx = document.createElement("canvas").getContext("2d");
  const derot = [];
  const fix = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const t = getComputedStyle(n).transform;
      if (!t || t === "none") continue;
      const m = new DOMMatrix(t);
      if (Math.abs(m.b) < 1e-6 && Math.abs(m.c) < 1e-6) continue;
      const s = Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
      derot.push([n, n.style.transform]);
      n.style.transform = "matrix(" + s + ",0,0," + s + "," + m.e + "," + m.f + ")";
    }
  };
  roots.forEach(fix);
  const opacityOf = (el) => { let o = 1; for (let n = el; n && n.nodeType === 1; n = n.parentElement) { const cs = getComputedStyle(n);
    if (cs.visibility === "hidden" || cs.display === "none") return 0; o *= parseFloat(cs.opacity); } return o; };
  const blurOf = (el) => { let b = 0; for (let n = el; n && n.nodeType === 1; n = n.parentElement) { const v = __pfdBlurPx(n); if (v) b += v * __pfdScale(n); } return b; };
  const ink = (el, ch) => {
    const cs = getComputedStyle(el);
    ctx.font = cs.fontStyle + " " + cs.fontWeight + " " + cs.fontSize + " " + cs.fontFamily;
    if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";
    const m = ctx.measureText(ch);
    return { l: m.actualBoundingBoxLeft, r: m.actualBoundingBoxRight };
  };
  const out = [];
  const rect = (c) => { const r = document.createRange(); r.setStart(c.node, c.i); r.setEnd(c.node, c.i + c.g.length); return r.getBoundingClientRect(); };
  for (const root of roots) {
    const chars = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const host = node.parentElement;
      if (!host || (!all && host.closest("[data-pfd-glow]"))) continue;
      if (all && rootOf(node) !== root) continue;  // a nested block line is its own root
      const seg = typeof Intl !== "undefined" && Intl.Segmenter ? Array.from(new Intl.Segmenter("vi", { granularity: "grapheme" }).segment(node.textContent), (x) => [x.index, x.segment]) : Array.from(node.textContent).map((c, i) => [i, c]);
      for (const [i, g] of seg) chars.push({ node, i, g, host, space: /^\\s+$/.test(g) });
    }
    let worst = null;
    for (let k = 1; k < chars.length - 1; k++) {
      if (!chars[k].space || chars[k - 1].space) continue;
      let j = k; while (j < chars.length && chars[j].space) j++;
      if (j >= chars.length) break;
      const a = chars[k - 1], b = chars[j];
      const opA = opacityOf(a.host), opB = opacityOf(b.host);
      if (Math.min(opA, opB) < 0.15) continue;
      const ra = rect(a), rb = rect(b);
      if (Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top) < 0.5 * Math.min(ra.height, rb.height)) continue;  // line break
      let sa = __pfdScale(a.host), sb = __pfdScale(b.host);
      const ia = ink(a.host, a.g), ib = ink(b.host, b.g);
      let gap = (rb.left - ib.l * sb) - (ra.left + ia.r * sa);
      if (a.host === b.host && a.node === b.node && a.host instanceof SVGTextContentElement && typeof a.host.getSubStringLength === "function") {
        // text on a path (kt11 arc): glyphs are rotated, so measure the ink gap ALONG the path (advance offsets from the DOM, which
        // include letter- / word-spacing) and scale it to the screen; text above a convex arc only fans out, so this is the narrowest
        const ctm = a.host.getScreenCTM();
        const k = ctm ? Math.sqrt(Math.abs(ctm.a * ctm.d - ctm.b * ctm.c)) : 1;
        const ua = a.host.getSubStringLength(0, a.i), ub = a.host.getSubStringLength(0, b.i);
        sa = sb = k;
        gap = ((ub - ib.l) - (ua + ia.r)) * k;
      }
      const blur = blurOf(a.host) + blurOf(b.host);
      const fa = parseFloat(getComputedStyle(a.host).fontSize) * sa, fb = parseFloat(getComputedStyle(b.host).fontSize) * sb;
      const need = 0.25 * Math.max(fa, fb);
      const eff = gap - blur;
      const rec = { pair: a.g + "|" + b.g, gapPx: +gap.toFixed(2), blurPx: +blur.toFixed(2), effPx: +eff.toFixed(2), needPx: +need.toFixed(2),
                    emPx: +Math.max(fa, fb).toFixed(2), opacity: +Math.min(opA, opB).toFixed(3) };
      if (!worst || eff - need < worst.effPx - worst.needPx) worst = rec;
    }
    // rows = laid-out text lines of the root (a line that reflows while its spacing widens changes this count)
    const centers = chars.filter((c) => !c.space).map((c) => rect(c)).filter((r) => r.height > 0)
                         .map((r) => [(r.top + r.bottom) / 2, r.height]).sort((x, y) => x[0] - y[0]);
    let rows = 0, lastY = -1e9;
    for (const [cy, hh] of centers) if (cy - lastY > 0.5 * hh) { rows++; lastY = cy; }
    // text on a path is one line by construction (row centres along an arc mean nothing); report whether every glyph is still drawn
    const tps = root instanceof SVGElement ? Array.from(root.querySelectorAll("textPath")) : [];
    const onPath = tps.length ? tps.map((tp) => { const i = __pfdTextPathInfo(tp); return { rendered: i.rendered, chars: i.chars, overflow: i.overflow }; }) : undefined;
    out.push({ id: root.id || __pfdLabel(root), wordSpacing: getComputedStyle(root).wordSpacing, rows: tps.length ? tps.length : rows, worst, onPath });
  }
  for (const [n, t] of derot.reverse()) n.style.transform = t;
  return out;
})()`;
}

// v7.9.0 repair: an SVG <textPath> silently drops every glyph whose advance midpoint falls off its path (the long kt11 arc lost
// its first / last words while every size audit passed). TEXT_PATH_COMMON_JS lays each textPath out along its path from the DOM
// metrics (getComputedTextLength / getSubStringLength vs getTotalLength, startOffset, text-anchor) and returns the screen extents of
// the glyphs that are actually drawn (getExtentOfChar through getScreenCTM), so the content box measures real ink, never the bbox
// Chrome reports for the dropped glyphs.
const TEXT_PATH_COMMON_JS = String.raw`
  function __pfdTextPathInfo(tp) {
    const href = tp.getAttribute("href") || tp.getAttribute("xlink:href") || "";
    const path = href.startsWith("#") ? document.getElementById(href.slice(1)) : null;
    const text = tp.closest("text");
    const n = tp.getNumberOfChars();
    const rec = { id: tp.id || (path && path.id) || "textPath", text: (tp.textContent || "").replace(/\s+/g, " ").trim().slice(0, 64),
                  chars: n, rendered: 0, textLen: 0, pathLen: 0, start: 0, end: 0, overflow: true, inkBox: null, glyphBoxes: [] };
    if (!path || !text || typeof path.getTotalLength !== "function") { rec.error = "textPath without a path"; return rec; }
    const pathLen = path.getTotalLength();
    const textLen = tp.getComputedTextLength();
    const so = String(tp.getAttribute("startOffset") || "0").trim();
    const off = so.endsWith("%") ? parseFloat(so) / 100 * pathLen : (parseFloat(so) || 0);
    const anchor = getComputedStyle(tp).textAnchor || getComputedStyle(text).textAnchor;
    const start = anchor === "middle" ? off - textLen / 2 : (anchor === "end" ? off - textLen : off);
    const ctm = text.getScreenCTM();
    let ink = null;
    for (let i = 0; i < n; i++) {
      const adv = tp.getSubStringLength(i, 1);
      const mid = start + tp.getSubStringLength(0, i) + adv / 2;
      if (mid < 0 || mid > pathLen) continue;  // the SVG rule: a glyph whose midpoint is off the path is not rendered
      rec.rendered++;
      if (!ctm) continue;
      let e = null;
      try { e = text.getExtentOfChar(i); } catch (err) { e = null; }
      if (!e || !(e.width > 0 || e.height > 0)) continue;
      const pts = [[e.x, e.y], [e.x + e.width, e.y], [e.x, e.y + e.height], [e.x + e.width, e.y + e.height]]
        .map(([x, y]) => new DOMPoint(x, y).matrixTransform(ctm));
      const b = [Math.min(...pts.map((q) => q.x)), Math.min(...pts.map((q) => q.y)), Math.max(...pts.map((q) => q.x)), Math.max(...pts.map((q) => q.y))];
      rec.glyphBoxes.push(b);
      ink = ink ? [Math.min(ink[0], b[0]), Math.min(ink[1], b[1]), Math.max(ink[2], b[2]), Math.max(ink[3], b[3])] : b;
    }
    rec.textLen = +textLen.toFixed(2); rec.pathLen = +pathLen.toFixed(2); rec.start = +start.toFixed(2); rec.end = +(start + textLen).toFixed(2);
    rec.overflow = rec.rendered < n || start < -0.5 || start + textLen > pathLen + 0.5;
    rec.inkBox = ink ? ink.map((v) => +v.toFixed(1)) : null;
    return rec;
  }
`;

const TEXT_PATH_PROBE_JS = `(() => {
  ${TEXT_PATH_COMMON_JS}
  return Array.from(document.querySelectorAll("textPath")).map((tp) => { const r = __pfdTextPathInfo(tp); delete r.glyphBoxes; return r; });
})()`;

// Union screen box [left, top, right, bottom] of everything a kinetic plate draws that must stay inside it: every visible text run
// (range boxes, after transforms) and every optional pill. Used to grow a default-height kt plate to its content.
const CONTENT_BOX_PROBE_JS = `(() => {
  ${TEXT_PATH_COMMON_JS}
  const vis = (el) => { let o = 1; for (let n = el; n && n.nodeType === 1; n = n.parentElement) { const cs = getComputedStyle(n);
    if (cs.visibility === "hidden" || cs.display === "none") return 0; o *= parseFloat(cs.opacity); } return o; };
  let box = null;
  const add = (r) => { if (!(r.width > 0) || !(r.height > 0)) return;
    box = box ? [Math.min(box[0], r.left), Math.min(box[1], r.top), Math.max(box[2], r.right), Math.max(box[3], r.bottom)] : [r.left, r.top, r.right, r.bottom]; };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const host = node.parentElement;
    if (!host || !node.textContent.trim() || ["SCRIPT", "STYLE", "TITLE"].includes(host.tagName.toUpperCase()) || vis(host) < 0.02) continue;
    if (host.closest("textPath")) continue;  // measured per drawn glyph below
    const rg = document.createRange(); rg.selectNodeContents(node); add(rg.getBoundingClientRect());
  }
  document.querySelectorAll("textPath").forEach((tp) => { if (vis(tp) < 0.02) return;
    for (const b of __pfdTextPathInfo(tp).glyphBoxes) add({ left: b[0], top: b[1], right: b[2], bottom: b[3], width: b[2] - b[0], height: b[3] - b[1] }); });
  document.querySelectorAll(".kt-opt-pill").forEach((el) => { if (vis(el) >= 0.02) add(el.getBoundingClientRect()); });
  return box;
})()`;

async function evalValue(cdp, sessionId, expression) {
  const res = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  if (res.exceptionDetails) {
    throw new Error(`probe evaluation failed: ${JSON.stringify(res.exceptionDetails)}`);
  }
  return res.result?.value;
}

// Settled state (what a still renders) -> every drawn text with its on-plate size.
async function probeSettledTextSizes(cdp, sessionId, fps, hasSetFrame) {
  if (hasSetFrame) await applyFrameState(cdp, sessionId, 0, 1, fps);
  return evalValue(cdp, sessionId, TEXT_SIZE_PROBE_JS);
}

async function captureRgbaPngBuffer(cdp, sessionId) {
  const shot = await cdp.send(
    "Page.captureScreenshot",
    {
      format: "png",
      omitBackground: true,
      optimizeForSpeed: true,
      captureBeyondViewport: false,
    },
    sessionId
  );
  if (!shot || !shot.data) {
    throw new Error("Page.captureScreenshot returned empty payload");
  }
  return Buffer.from(shot.data, "base64");
}

async function downscalePngToLogical(ffmpegBin, pngBuf, width, height, outPath) {
  const ffArgs = [
    "-y",
    "-loglevel",
    "error",
    "-f",
    "image2pipe",
    "-vcodec",
    "png",
    "-i",
    "-",
    "-vf",
    `scale=${width}:${height}:flags=lanczos`,
    "-pix_fmt",
    "rgba",
    "-frames:v",
    "1",
    "-map_metadata",
    "-1",
    outPath,
  ];
  const ffProc = spawn(ffmpegBin, ffArgs, {
    stdio: ["pipe", "ignore", "pipe"],
  });
  let ffStderr = "";
  ffProc.stderr.setEncoding("utf8");
  ffProc.stderr.on("data", (chunk) => {
    ffStderr += chunk;
  });
  let ffSpawnErr = null;
  ffProc.once("error", (err) => {
    ffSpawnErr = err;
  });
  if (ffSpawnErr) {
    throw new Error(`ffmpeg spawn error: ${ffSpawnErr.message}`);
  }
  ffProc.stdin.end(pngBuf);
  const [exitCode] = await once(ffProc, "close");
  if (exitCode !== 0) {
    throw new Error(
      `ffmpeg PNG Lanczos downscale exited with code ${exitCode}: ${ffStderr.trim()}`
    );
  }
}

async function renderSingleJob(
  cdp,
  job,
  defaults = {}
) {
  const startedAt = Date.now();
  const width = Math.max(16, Number.parseInt(job.width ?? 1080, 10));
  const height = Math.max(16, Number.parseInt(job.height ?? 1920, 10));
  const deviceScaleFactor =
    Number.parseFloat(job.scale ?? job.deviceScaleFactor ?? defaults.scale ?? 1) || 1;
  const downscaleToLogical =
    job.downscaleToLogical !== undefined
      ? Boolean(job.downscaleToLogical)
      : defaults.downscaleToLogical !== false;
  const shouldDownscale = deviceScaleFactor > 1.0 && downscaleToLogical;
  const outWidth = shouldDownscale
    ? width
    : Math.round(width * deviceScaleFactor);
  const outHeight = shouldDownscale
    ? height
    : Math.round(height * deviceScaleFactor);

  const fps = Number.parseFloat(job.fps ?? defaults.fps ?? 60) || 60;
  const totalFrames =
    job.duration != null
      ? Math.max(1, Math.round(Number(job.duration) * fps))
      : Math.max(1, Number.parseInt(job.frames ?? job.totalFrames ?? 60, 10));
  const alphaCodec = normalizeAlphaCodec(
    job.alphaCodec ?? job.alpha_codec ?? defaults.alphaCodec ?? "prores4444"
  );
  const outPath = path.resolve(String(job.out));
  const mode = normalizeMode(job.mode, outPath);
  const targetUrl = resolveTargetUrl(job);
  const ffmpegBin = job.ffmpegBin || defaults.ffmpegBin || "ffmpeg";
  const quiet = Boolean(defaults.quiet);

  const { targetId } = await cdp.send("Target.createTarget", {
    url: "about:blank",
  });
  const { sessionId } = await cdp.send("Target.attachToTarget", {
    targetId,
    flatten: true,
  });

  try {
    await cdp.send("Page.enable", {}, sessionId);
    await cdp.send("Runtime.enable", {}, sessionId);

    await cdp.send(
      "Emulation.setDeviceMetricsOverride",
      {
        width,
        height,
        deviceScaleFactor,
        mobile: false,
      },
      sessionId
    );
    await cdp.send(
      "Emulation.setDefaultBackgroundColorOverride",
      {
        color: { r: 0, g: 0, b: 0, a: 0 },
      },
      sessionId
    );

    await cdp.send("Page.navigate", { url: targetUrl }, sessionId);

    const readyInfo = await waitForPageReady(
      cdp,
      sessionId,
      job.timeoutMs ?? defaults.timeoutMs ?? 30000
    );

    if (mode === "probe") {
      // v7.9.0: no pixels written. Steps frames [probeFrom, probeTo] of a `totalFrames` clip and returns the word-gap probe per frame.
      const from = Math.max(0, Number.parseInt(job.probeFrom ?? 0, 10));
      const to = Math.min(totalFrames - 1, Number.parseInt(job.probeTo ?? totalFrames - 1, 10));
      const frames = [];
      for (let frameIdx = from; frameIdx <= to; frameIdx++) {
        if (readyInfo.hasSetFrame) await applyFrameState(cdp, sessionId, frameIdx, totalFrames, fps);
        frames.push({ frameIdx, lines: await evalValue(cdp, sessionId, wordGapProbeJs(job.probeIds || null)) });
      }
      // `contentBoxFrames` (frame indices of this clip, null = the settled still): union box of what the plate draws on those frames
      let contentBox = null;
      if (Array.isArray(job.contentBoxFrames)) {
        for (const f of job.contentBoxFrames) {
          if (readyInfo.hasSetFrame) await applyFrameState(cdp, sessionId, f == null ? 0 : Number(f), f == null ? 1 : totalFrames, fps);
          const b = await evalValue(cdp, sessionId, CONTENT_BOX_PROBE_JS);
          if (b) contentBox = contentBox ? [Math.min(contentBox[0], b[0]), Math.min(contentBox[1], b[1]), Math.max(contentBox[2], b[2]), Math.max(contentBox[3], b[3])] : b;
        }
      }
      const textSizes = await probeSettledTextSizes(cdp, sessionId, fps, readyInfo.hasSetFrame);
      const textPaths = await evalValue(cdp, sessionId, TEXT_PATH_PROBE_JS);
      return { ok: true, mode: "probe", fps, frames: totalFrames, wordGaps: frames, textSizes, textPaths, contentBox, elapsedMs: Date.now() - startedAt };
    }

    if (mode === "still") {
      await fsp.mkdir(path.dirname(outPath), { recursive: true });
      if (readyInfo.hasSetFrame) {
        const heroFrame =
          job.frameIdx != null ? Number(job.frameIdx) : Math.max(0, totalFrames - 1);
        const stillTotal = job.frameIdx != null ? totalFrames : 1;
        await applyFrameState(cdp, sessionId, heroFrame, stillTotal, fps);
      }
      const pngBuf = await captureRgbaPngBuffer(cdp, sessionId);
      let finalBytes = pngBuf.length;
      if (shouldDownscale) {
        await downscalePngToLogical(ffmpegBin, pngBuf, width, height, outPath);
        const st = await fsp.stat(outPath);
        finalBytes = st.size;
      } else {
        await fsp.writeFile(outPath, pngBuf);
      }
      const textSizes = await probeSettledTextSizes(cdp, sessionId, fps, readyInfo.hasSetFrame);
      const textPaths = await evalValue(cdp, sessionId, TEXT_PATH_PROBE_JS);
      const elapsedMs = Date.now() - startedAt;
      if (!quiet) {
        console.error(
          `[web-cinema-engine] STILL ${outWidth}x${outHeight} (dpr=${deviceScaleFactor}) -> ${outPath} (${finalBytes} bytes, ${elapsedMs}ms)`
        );
      }
      return {
        ok: true,
        mode: "still",
        textSizes,
        textPaths,
        out: outPath,
        width: outWidth,
        height: outHeight,
        scale: deviceScaleFactor,
        bytes: finalBytes,
        elapsedMs,
      };
    }

    const writesMov =
      mode === "mov" ||
      (mode === "sequence" && path.extname(outPath).toLowerCase() === ".mov");

    if (writesMov) {
      await fsp.mkdir(path.dirname(outPath), { recursive: true });
      const ffArgs = [
        "-y",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-r",
        String(fps),
        "-i",
        "-",
      ];

      if (shouldDownscale) {
        ffArgs.push("-vf", `scale=${width}:${height}:flags=lanczos`);
      }

      let codecTag;
      if (alphaCodec === "qtrle") {
        ffArgs.push("-c:v", "qtrle", "-pix_fmt", "argb", "-threads", "2");
        codecTag = "qtrle_argb";
      } else {
        ffArgs.push(
          "-c:v",
          "prores_ks",
          "-profile:v",
          "4444",
          "-pix_fmt",
          "yuva444p10le",
          "-vendor",
          "apl0",
          "-threads",
          "2"
        );
        codecTag = "prores_ks_4444_yuva444p10le";
      }

      ffArgs.push("-map_metadata", "-1", outPath);

      const ffProc = spawn(ffmpegBin, ffArgs, {
        stdio: ["pipe", "ignore", "pipe"],
      });

      let ffStderr = "";
      ffProc.stderr.setEncoding("utf8");
      ffProc.stderr.on("data", (chunk) => {
        ffStderr += chunk;
      });

      let ffSpawnErr = null;
      ffProc.once("error", (err) => {
        ffSpawnErr = err;
      });

      try {
        for (let frameIdx = 0; frameIdx < totalFrames; frameIdx++) {
          if (ffSpawnErr) {
            throw new Error(`ffmpeg spawn error: ${ffSpawnErr.message}`);
          }
          await applyFrameState(cdp, sessionId, frameIdx, totalFrames, fps);
          const pngBuf = await captureRgbaPngBuffer(cdp, sessionId);
          if (!ffProc.stdin.write(pngBuf)) {
            await once(ffProc.stdin, "drain");
          }
        }
        ffProc.stdin.end();
      } catch (loopErr) {
        try {
          ffProc.kill("SIGKILL");
        } catch {
          // ignore
        }
        throw loopErr;
      }

      const [exitCode] = await once(ffProc, "close");
      if (exitCode !== 0) {
        throw new Error(`ffmpeg exited with code ${exitCode}: ${ffStderr.trim()}`);
      }

      const textSizes = await probeSettledTextSizes(cdp, sessionId, fps, readyInfo.hasSetFrame);
      const textPaths = await evalValue(cdp, sessionId, TEXT_PATH_PROBE_JS);
      const stat = await fsp.stat(outPath);
      const elapsedMs = Date.now() - startedAt;
      if (!quiet) {
        console.error(
          `[web-cinema-engine] MOV ${alphaCodec} (${totalFrames}f @ ${fps}fps, ${outWidth}x${outHeight}, dpr=${deviceScaleFactor}) -> ${outPath} (${stat.size} bytes, ${elapsedMs}ms)`
        );
      }
      return {
        ok: true,
        mode: "mov",
        textSizes,
        textPaths,
        codec: codecTag,
        alphaCodec,
        out: outPath,
        frames: totalFrames,
        fps,
        width: outWidth,
        height: outHeight,
        scale: deviceScaleFactor,
        bytes: stat.size,
        elapsedMs,
      };
    }

    if (mode === "sequence") {
      await fsp.mkdir(outPath, { recursive: true });
      const framePaths = [];
      for (let frameIdx = 0; frameIdx < totalFrames; frameIdx++) {
        await applyFrameState(cdp, sessionId, frameIdx, totalFrames, fps);
        const pngBuf = await captureRgbaPngBuffer(cdp, sessionId);
        const frameFile = path.join(
          outPath,
          `frame_${String(frameIdx).padStart(5, "0")}.png`
        );
        if (shouldDownscale) {
          await downscalePngToLogical(ffmpegBin, pngBuf, width, height, frameFile);
        } else {
          await fsp.writeFile(frameFile, pngBuf);
        }
        framePaths.push(frameFile);
      }
      const textSizes = await probeSettledTextSizes(cdp, sessionId, fps, readyInfo.hasSetFrame);
      const textPaths = await evalValue(cdp, sessionId, TEXT_PATH_PROBE_JS);
      const elapsedMs = Date.now() - startedAt;
      if (!quiet) {
        console.error(
          `[web-cinema-engine] SEQUENCE (${totalFrames} PNGs @ ${fps}fps) -> ${outPath} (${elapsedMs}ms)`
        );
      }
      return {
        ok: true,
        mode: "sequence",
        textSizes,
        textPaths,
        out: outPath,
        frames: totalFrames,
        fps,
        width: outWidth,
        height: outHeight,
        framePaths,
        elapsedMs,
      };
    }

    throw new Error(
      `Unsupported mode '${mode}'. Expected 'still', 'mov', or 'sequence'.`
    );
  } finally {
    await cdp.send("Target.closeTarget", { targetId }).catch(() => {});
  }
}

async function main() {
  const batchStartedAt = Date.now();
  const args = parseCliArgs(process.argv);
  let jobs = [];
  let parsedConcurrency = null;
  let parsedAlphaCodec = null;

  if (args.batchJson) {
    const raw = await fsp.readFile(path.resolve(args.batchJson), "utf8");
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      jobs = parsed;
    } else {
      jobs = parsed.jobs || [];
      if (parsed.concurrency != null) {
        parsedConcurrency = Number.parseInt(parsed.concurrency, 10);
      }
      if (parsed.alphaCodec || parsed.alpha_codec) {
        parsedAlphaCodec = normalizeAlphaCodec(
          parsed.alphaCodec || parsed.alpha_codec
        );
      }
    }
    if (jobs.length === 0) {
      throw new Error(`No render jobs found in ${args.batchJson}`);
    }
  } else {
    if (!args.out) {
      throw new Error("Missing required --out <path>");
    }
    jobs = [args];
  }

  const rawConcurrency = args.batchJson
    ? args.concurrencyExplicit
      ? args.concurrency
      : parsedConcurrency ?? args.concurrency ?? 4
    : 1;
  const workerCount = Math.max(
    1,
    Math.min(Number.isFinite(rawConcurrency) ? rawConcurrency : 4, 4, jobs.length)
  );

  const sharedDefaults = {
    fps: args.fpsExplicit ? args.fps : 60,
    alphaCodec: args.alphaCodecExplicit
      ? args.alphaCodec
      : parsedAlphaCodec ?? "prores4444",
    scale: args.scale,
    downscaleToLogical: args.downscaleToLogical,
    ffmpegBin: args.ffmpegBin,
    timeoutMs: args.timeoutMs,
    quiet: args.quiet,
  };

  const session = await launchHeadlessChrome(args.timeoutMs);
  try {
    const results = new Array(jobs.length);
    let nextIdx = 0;
    let firstError = null;

    const runWorker = async () => {
      while (true) {
        if (firstError) return;
        const idx = nextIdx++;
        if (idx >= jobs.length) return;
        try {
          results[idx] = await renderSingleJob(
            session.cdp,
            jobs[idx],
            sharedDefaults
          );
        } catch (err) {
          if (!firstError) {
            firstError = err;
          }
          return;
        }
      }
    };

    const workers = Array.from({ length: workerCount }, () => runWorker());
    await Promise.allSettled(workers);
    if (firstError) {
      throw firstError;
    }

    const totalElapsedMs = Date.now() - batchStartedAt;
    // a pipe write is asynchronous: wait for it to flush before process.exit (a multi-MB probe result was cut at ~3.9 MB)
    await new Promise((resolve) => process.stdout.write(
      `${JSON.stringify(
        args.batchJson
          ? { ok: true, concurrency: workerCount, totalElapsedMs, results }
          : results[0]
      )}\n`,
      resolve
    ));
  } finally {
    await session.close();
  }
  process.exit(0);
}

main().catch((err) => {
  console.error(
    `[web-cinema-engine] FATAL: ${err?.stack || err?.message || err}`
  );
  process.exit(1);
});
