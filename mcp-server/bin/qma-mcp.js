#!/usr/bin/env node
import { run } from "../dist/index.js";

run().catch((error) => {
  console.error("qma-mcp failed:", error);
  process.exit(1);
});
