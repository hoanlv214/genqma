export function AgentBuyerDemo() {
  return (
    <aside className="panel agent-panel">
      <h2>Agent Buyer Demo</h2>
      <p>Browser judge mode calls `/api/v1/agent/recommendations`, applies budget policy, then creates an agent invoice.</p>
      <button type="button">Run Agent Decision</button>
    </aside>
  );
}
