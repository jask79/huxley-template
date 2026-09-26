#!/usr/bin/env node
/**
 * Veo 3.1 Video Generator via OAuth
 * Uses gemini-cli's stored OAuth credentials to call the Veo API directly.
 * This bypasses the GEMINI_API_KEY requirement for nano-banana.
 *
 * Usage:
 *   node veo-oauth-generate.mjs "prompt text" --output /path/to/out.mp4 [--fast] [--duration 8]
 */

import { GoogleGenAI } from "/opt/homebrew/lib/node_modules/@the-focus-ai/nano-banana/node_modules/@google/genai/dist/node/index.mjs";
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { homedir } from "node:os";
import https from "node:https";

// ─── OAuth helpers ────────────────────────────────────────────────────────────

const CLIENT_ID = process.env.GOOGLE_OAUTH_CLIENT_ID;
const CLIENT_SECRET = process.env.GOOGLE_OAUTH_CLIENT_SECRET;
if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error("Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in the environment.");
  process.exit(1);
}
const TOKEN_URI = "https://oauth2.googleapis.com/token";

async function refreshToken(refreshToken) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams({
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      refresh_token: refreshToken,
      grant_type: "refresh_token",
    }).toString();

    const req = https.request(
      TOKEN_URI,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          try {
            const parsed = JSON.parse(data);
            if (parsed.error) reject(new Error(parsed.error_description || parsed.error));
            else resolve(parsed.access_token);
          } catch (e) {
            reject(e);
          }
        });
      }
    );
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

async function getAccessToken() {
  const credsPath = `${homedir()}/.gemini/oauth_creds.json`;
  const creds = JSON.parse(readFileSync(credsPath, "utf8"));

  // Check if existing token is still valid (5 min buffer)
  const now = Date.now();
  const expiry = creds.expiry_date || 0;
  if (creds.access_token && expiry > now + 5 * 60 * 1000) {
    return creds.access_token;
  }

  // Refresh
  console.log("Refreshing OAuth token...");
  const newToken = await refreshToken(creds.refresh_token);
  // Update stored creds
  creds.access_token = newToken;
  creds.expiry_date = Date.now() + 55 * 60 * 1000; // assume 1hr expiry
  writeFileSync(credsPath, JSON.stringify(creds, null, 2));
  return newToken;
}

// ─── Video generation ─────────────────────────────────────────────────────────

async function waitForVideoCompletion(ai, operation) {
  const startTime = Date.now();
  let elapsed = 0;

  while (!operation.done) {
    await new Promise((r) => setTimeout(r, 10000)); // poll every 10s
    elapsed = Math.floor((Date.now() - startTime) / 1000);
    process.stdout.write(`\r  Generating... ${elapsed}s elapsed`);

    operation = await ai.operations.getVideosOperation({
      operation: operation,
    });
  }
  process.stdout.write("\n");
  return operation;
}

async function generateVideo(opts) {
  const {
    prompt,
    outputPath,
    model = "veo-3.1-fast-generate-001",
    duration = 8,
    aspectRatio = "16:9",
    resolution = "1080p",
    noAudio = false,
  } = opts;

  const token = await getAccessToken();

  // Build GoogleGenAI client with OAuth Bearer token
  const ai = new GoogleGenAI({
    apiKey: "placeholder", // required by SDK but overridden by header
    httpOptions: {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  });

  const request = {
    model,
    prompt,
    config: {
      aspectRatio,
      durationSeconds: duration,
      resolution,
    },
  };

  console.log(`Model: ${model}`);
  console.log(`Prompt: ${prompt.substring(0, 80)}...`);
  console.log(`Duration: ${duration}s | Aspect: ${aspectRatio} | Res: ${resolution}`);
  if (noAudio) console.log("Audio: disabled");
  console.log("Starting generation (takes 2-4 minutes)...");

  let operation = await ai.models.generateVideos(request);
  operation = await waitForVideoCompletion(ai, operation);

  if (operation.error) {
    throw new Error(`Generation failed: ${operation.error.message}`);
  }

  const video = operation.response?.generatedVideos?.[0]?.video;
  if (!video) throw new Error("No video in response");

  // Save output
  mkdirSync(dirname(outputPath), { recursive: true });

  if (video.videoBytes) {
    const buffer = Buffer.from(video.videoBytes, "base64");
    writeFileSync(outputPath, buffer);
  } else if (video.uri) {
    // Download from URI
    execSync(`curl -sL "${video.uri}" -o "${outputPath}"`);
    // Save URI for potential extension
    writeFileSync(outputPath + ".uri", video.uri, "utf8");
  } else {
    throw new Error("Video has no bytes or URI");
  }

  const stats = readFileSync(outputPath);
  const sizeMB = (stats.length / 1024 / 1024).toFixed(2);
  console.log(`\nSaved: ${outputPath} (${sizeMB} MB)`);
  return outputPath;
}

// ─── CLI parsing ──────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const opts = {
  prompt: null,
  outputPath: null,
  model: "veo-3.1-fast-generate-001",
  duration: 8,
  aspectRatio: "16:9",
  resolution: "1080p",
  noAudio: false,
};

for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === "--output" || a === "-o") opts.outputPath = args[++i];
  else if (a === "--fast") opts.model = "veo-3.1-fast-generate-001";
  else if (a === "--model") opts.model = args[++i];
  else if (a === "--duration") opts.duration = parseInt(args[++i]);
  else if (a === "--aspect") opts.aspectRatio = args[++i];
  else if (a === "--resolution") opts.resolution = args[++i];
  else if (a === "--no-audio") opts.noAudio = true;
  else if (!a.startsWith("--")) opts.prompt = a;
}

if (!opts.prompt || !opts.outputPath) {
  console.error('Usage: veo-oauth-generate.mjs "prompt" --output /path/to/out.mp4 [--fast] [--duration 8] [--aspect 16:9] [--resolution 1080p] [--no-audio]');
  process.exit(1);
}

generateVideo(opts)
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("Error:", err.message);
    process.exit(1);
  });
