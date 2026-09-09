import assert from "node:assert/strict";
import { SessionTaskPool } from "../dist/workerPool.js";

const pool = new SessionTaskPool(2);
const releases = new Map();
let running = 0;
let maxObserved = 0;

function deferredTask(sessionId) {
  return async () => {
    running += 1;
    maxObserved = Math.max(maxObserved, running);
    await new Promise((resolve) => releases.set(sessionId, resolve));
    running -= 1;
  };
}

assert.equal(pool.tryStart("session-a", deferredTask("session-a")), true);
assert.equal(pool.tryStart("session-b", deferredTask("session-b")), true);
assert.equal(pool.tryStart("session-c", deferredTask("session-c")), false);
assert.equal(pool.tryStart("session-a", deferredTask("session-a-duplicate")), false);

await new Promise((resolve) => setImmediate(resolve));
assert.equal(pool.activeCount, 2);
assert.equal(pool.availableSlots, 0);
assert.equal(running, 2);
assert.equal(maxObserved, 2);

releases.get("session-a")();
await pool.waitForCapacity(1000);
await new Promise((resolve) => setImmediate(resolve));

assert.equal(pool.activeCount, 1);
assert.equal(pool.tryStart("session-c", deferredTask("session-c")), true);
await new Promise((resolve) => setImmediate(resolve));
assert.equal(pool.activeCount, 2);
assert.equal(maxObserved, 2);

releases.get("session-b")();
releases.get("session-c")();
await pool.waitForCapacity(1000);
await new Promise((resolve) => setImmediate(resolve));

assert.equal(pool.activeCount, 0);
assert.equal(running, 0);
console.log("worker concurrency smoke PASS");
