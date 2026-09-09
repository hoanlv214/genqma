import { QmaAgent } from "../src/index.js";

async function main() {
  const agent = new QmaAgent();

  // Listen to ALL events generically
  const originalEmit = agent.emit;
  agent.emit = function (eventName: string, ...args: any[]) {
    // You could pipe this to Redis, SSE, or a Database here
    console.log(`[STREAM -> DB] Event: ${eventName}`);
    console.dir(args[0], { depth: null });
    return originalEmit.apply(agent, [eventName, ...args] as any);
  };

  await agent.run({
    task: "Event stream test",
    sessionBudgetUsdc: 10,
    maxPricePerReportUsdc: 5,
    maxPurchases: 1
  });
}

main().catch(console.error);
