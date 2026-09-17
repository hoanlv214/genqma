import { randomBytes } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { registerEntitySecretCiphertext } from "@circle-fin/developer-controlled-wallets";
import * as path from "node:path";
import { loadEnvFile } from "./load-env.js";

// Load .env from parent directory
const envPath = path.resolve(process.cwd(), "..", ".env");
loadEnvFile(envPath);

const apiKey: string | undefined = process.env.CIRCLE_CONSOLE_API_KEY;
if (!apiKey) {
  throw new Error("CIRCLE_CONSOLE_API_KEY is required. Set it in .env first.");
}

// Refuse to overwrite an existing entity secret in .env.
const existingEnv: string = existsSync(envPath)
  ? readFileSync(envPath, "utf8")
  : "";
if (/^CIRCLE_ENTITY_SECRET=/m.test(existingEnv)) {
  throw new Error(
    "CIRCLE_ENTITY_SECRET already exists in .env. Refusing to overwrite it.",
  );
}

// Generate a 32-byte entity secret.
const entitySecret: string = randomBytes(32).toString("hex");
const recoveryFilePath: string = "./recovery";

mkdirSync(recoveryFilePath, { recursive: true });

await registerEntitySecretCiphertext({
  apiKey,
  entitySecret,
  recoveryFileDownloadPath: recoveryFilePath,
});

// Append to the root .env
appendFileSync(envPath, `\nCIRCLE_ENTITY_SECRET=${entitySecret}\n`);

console.log("Entity secret registered.");
console.log(`Recovery file saved to a new file in: ${recoveryFilePath}`);
console.log("CIRCLE_ENTITY_SECRET added to .env");
