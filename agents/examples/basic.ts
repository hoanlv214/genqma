import { QmaAgent } from "../src/index.js";

async function main() {
  const agent = new QmaAgent(); // Uses default QMA API URL and Dry-run (no wallet)

  console.log("Starting autonomous session...");
  
  agent.on("session_started", (e) => console.log(`[STARTED] Session ${e.session_id}`));
  agent.on("decision", (e) => console.log(`[DECISION] Evaluating ${e.selected_candidate_id}...`));
  agent.on("wait", (e) => console.log(`[WAIT] ${e.reason}`));
  agent.on("session_finished", (e) => console.log(`[FINISHED] Reason: ${e.stop_reason}`));

  const report = await agent.run({
    task: "Find undervalued AI tokens with high momentum",
    sessionBudgetUsdc: 10,
    maxPricePerReportUsdc: 5,
    durationSeconds: 120, // Run for 2 minutes
    executionMode: "dry_run" // Do not execute real purchases
  });

  console.log("\nFinal Session Report:");
  console.log(JSON.stringify(report, null, 2));
}

main().catch(console.error);
