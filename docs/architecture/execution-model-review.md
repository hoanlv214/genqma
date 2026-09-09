# Execution Model Architecture Review

Assuming `agents/src` becomes the single source of truth for the autonomous runtime, we must decide how the Python FastAPI backend orchestrates the Node.js execution. 

Below is an evaluation of four potential execution models tailored for QMA's current scale (tens of users, long-running sessions, Supabase Postgres).

---

## 1. Tradeoff Matrix

| Metric | A. RPC Node Service | B. Sidecar Process | C. Queue-based Worker | D. Session-per-process |
| :--- | :--- | :--- | :--- | :--- |
| **Complexity** | Medium (Network I/O) | Low (Subprocess I/O) | Medium (DB Polling) | High (Orchestration API) |
| **Operational Burden** | Medium (2 Services) | Low (1 Container) | Low-Medium (DB schema) | High (Infra as Code) |
| **Deploy: Render** | 2 Web Services ($$) | 1 Web Service ($) | 1 Web + 1 Worker ($$) | Dynamic APIs (Hard) |
| **Deploy: Railway** | 2 Services | 1 Service | 2 Services | Dynamic APIs (Hard) |
| **Deploy: VPS** | 2 Containers | 1 Container | 2 Containers | Docker socket access |
| **Persistence Need** | Medium | Low (Python handles it) | **High** (Worker reads DB) | Medium |
| **Failure Recovery** | Hard (State in memory) | Easy (Python restarts it) | **Robust** (Heartbeats) | Easy (Docker restarts) |
| **Horizontal Scaling**| Hard (Stateful routing) | Easy (Tied to Web scaling)| **Trivial** (Any worker) | Infinite |
| **Cost** | Medium | Lowest | Medium | Highest |

---

## 2. Deep Dive by Model

### A. Dedicated Node Worker Service (RPC)
FastAPI sends a `POST /start` request to a persistent Node.js Express server.
- **Pros:** Clean separation of concerns over HTTP.
- **Cons:** If the Node service restarts, all in-memory sessions are lost unless they were checkpointed. Routing HTTP requests to the *specific* worker holding a running session's memory is complex if you scale past 1 node.

### B. Node Sidecar Process (Child Process)
FastAPI spawns `node agents/dist/cli.js` using Python's `subprocess.Popen` for each session.
- **Pros:** Absolute lowest cost. Deployable as a single container anywhere. Python can read `stdout` JSON events and write them to Supabase synchronously.
- **Cons:** Managing child process lifecycles (PIDs, zombie processes, SIGTERM propagation) in Python is notoriously brittle. If FastAPI restarts, all sidecars are orphaned or killed.

### C. Queue-based Worker (DB Polling / PubSub)
FastAPI simply writes `status = 'queued'` to the `agent_sessions` table in Supabase. A separate Node.js worker process polls the database (or uses Postgres `LISTEN`), picks up the job, and updates `status = 'running'`.
- **Pros:** Extremely robust. If the worker crashes, another worker (or the same one upon restart) can pick up the session because state is in the DB. Trivial horizontal scaling.
- **Cons:** Requires rigorous DB state syncing (`initialState` hydration, heartbeats).

### D. Session-per-process (Fargate/ECS/K8s Jobs)
FastAPI calls a Cloud Provider API to spin up a brand-new container for every session.
- **Pros:** Perfect isolation.
- **Cons:** Complete overkill for tens of users. High latency to start. Very expensive (paying for container overhead per session).

---

## 3. Recommended Approach

**Recommendation: C. Queue-based Worker (using Supabase)**

For a system with tens of users running sessions that last for *hours*, **reliability and failure recovery are paramount**. If a user's 3-hour session dies at hour 2 because of a deployment or a memory spike, it is a catastrophic UX failure.

A Queue-based Worker architecture solves this cleanly without requiring heavy infrastructure (like Kafka or RabbitMQ) because we already have Supabase.

**Why it fits QMA:**
- **Simplest Queue:** You don't need Redis. The Node.js worker can just poll `SELECT * FROM agent_sessions WHERE status = 'queued'` or use Supabase Realtime/Postgres LISTEN.
- **Resumption:** By forcing the Node worker to periodically flush `SessionState` to Supabase, we solve the "Resume" problem. If the worker restarts, it simply reads the last state and continues.
- **Cost-effective:** You deploy exactly 1 FastAPI Web Service and 1 Node.js Background Worker on Render/Railway. 

---

## 4. Architecture Diagrams

### Recommended Architecture (Queue-based DB Worker)

```mermaid
flowchart TD
    UI[React Dashboard] --> |POST /sessions| API[FastAPI Web Service]
    API --> |INSERT (status='queued')| DB[(Supabase Postgres)]
    
    subgraph Node.js Worker Service
    Poller[DB Poller / Listener] --> |Pulls Job & State| Runtime[agents/src/runAutonomousSession]
    Runtime --> |Flushes state periodically| DB
    Runtime --> |onEvent (writes logs)| DB
    end
    
    UI --> |SSE or Supabase Realtime| DB
```

---

## 5. Migration Plan

**Phase 1: Database Schema (Supabase)**
- Create `agent_sessions` table (`status`, `policy`, `state_snapshot`).
- Create `agent_events` table (append-only log).

**Phase 2: SDK Refactoring (`agents/src`)**
- Modify `runAutonomousSession` to accept an optional `initialState: SessionState`.
- Add a periodic `onStateChange` callback to `SessionDeps` so the worker knows when to flush state to the DB.

**Phase 3: Worker Harness**
- Create a simple Node.js script (`worker.mjs`) that connects to Supabase via `@supabase/supabase-js`.
- Implement a polling loop looking for `queued` or `running` (but stale heartbeat) sessions.
- Wire the DB results into `runAutonomousSession`.

**Phase 4: API & Deployment**
- FastAPI stops executing local logic and simply creates rows in `agent_sessions`.
- Deploy `worker.mjs` as a "Background Worker" service on Render/Railway alongside the existing FastAPI Web Service.
