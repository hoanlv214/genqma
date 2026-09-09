import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import fs from "node:fs";

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packageJson = JSON.parse(fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"));
const cliPath = path.join(packageRoot, "bin", "qma.js");

function run(args) {
  return spawnSync(process.execPath, [cliPath, ...args], {
    cwd: packageRoot,
    encoding: "utf8",
    env: { ...process.env, QMA_DEBUG: "0" },
  });
}

const version = run(["--version"]);
assert.equal(version.status, 0);
assert.equal(version.stdout.trim(), packageJson.version);

const help = run(["agent", "run", "--help"]);
assert.equal(help.status, 0);
for (const option of ["--duration", "--max-attempts", "--json", "--event-log", "--llm-provider"]) {
  assert.match(help.stdout, new RegExp(option));
}

const unknown = run(["--not-a-real-option"]);
assert.equal(unknown.status, 2);
assert.match(unknown.stderr, /Unknown option/);

const missingValue = run(["--budget", "--live"]);
assert.equal(missingValue.status, 2);
assert.match(missingValue.stderr, /--budget requires a value/);

const invalidDuration = run(["--duration", "forever"]);
assert.equal(invalidDuration.status, 1);
assert.match(invalidDuration.stderr, /--duration must be/);

const circleAutoDeposit = run([
  "--executor", "circle-agent-wallet",
  "--wallet", "0x1111111111111111111111111111111111111111",
  "--auto-deposit",
]);
assert.equal(circleAutoDeposit.status, 1);
assert.match(circleAutoDeposit.stderr, /does not support automatic Gateway deposits/);

console.log("CLI parsing and help smoke PASS");
