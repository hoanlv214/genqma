import { rmSync } from "node:fs";

rmSync(new URL("../dist", import.meta.url), { recursive: true, force: true });
rmSync(new URL("../agents.tsbuildinfo", import.meta.url), { force: true });
