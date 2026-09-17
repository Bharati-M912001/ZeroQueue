// ZeroQueue keeps ONE .env file, at the repo root. This loader reads the
// NEXT_PUBLIC_* values out of it so the web page needs no env file of its own.
const fs = require("fs");
const path = require("path");

const envPath = path.resolve(__dirname, "../../.env");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && m[1].startsWith("NEXT_PUBLIC_") && process.env[m[1]] === undefined) {
      process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
    }
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = { reactStrictMode: true };

module.exports = nextConfig;
