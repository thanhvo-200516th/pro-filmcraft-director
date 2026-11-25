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
      const elapsedMs = Date.now() - startedAt;
      if (!quiet) {
        console.error(
          `[web-cinema-engine] STILL ${outWidth}x${outHeight} (dpr=${deviceScaleFactor}) -> ${outPath} (${finalBytes} bytes, ${elapsedMs}ms)`
        );
      }
      return {
        ok: true,
        mode: "still",
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
      const elapsedMs = Date.now() - startedAt;
      if (!quiet) {
        console.error(
          `[web-cinema-engine] SEQUENCE (${totalFrames} PNGs @ ${fps}fps) -> ${outPath} (${elapsedMs}ms)`
        );
      }
      return {
        ok: true,
        mode: "sequence",
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
    process.stdout.write(
      `${JSON.stringify(
        args.batchJson
          ? { ok: true, concurrency: workerCount, totalElapsedMs, results }
          : results[0]
      )}\n`
    );
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
