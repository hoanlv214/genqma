import { describe, expect, it, mock, beforeEach, afterEach } from "bun:test";
import React from "react";
import { render, act, cleanup, fireEvent, screen } from "@testing-library/react";
import { NotificationDropdown } from "../NotificationDropdown";

describe("NotificationDropdown Incident Governance Suite", () => {
  const origFetch = globalThis.fetch;

  afterEach(() => {
    cleanup();
    globalThis.fetch = origFetch;
  });

  it("renders P1 incident alert and dispatches emergency control actions", async () => {
    const mockSessionId = "66666666-6666-6666-6666-666666666666";
    let dispatchedControl: any = null;

    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      const urlStr = url.toString();
      if (urlStr.includes("/api/v1/agent/incidents")) {
        return {
          ok: true,
          json: async () => [
            {
              incident_id: "inc_test_999",
              session_id: mockSessionId,
              severity: "P1_CRITICAL",
              status: "OPEN",
              category: "GENLAYER_SLA_VIOLATION",
              rule: "FAIL_CLOSED_VERIFIER",
              details: "GenLayer SLA verdict INVALID on test invoice",
              euthyna_hash: "0xabcdef1234567890",
              timestamp: new Date().toISOString(),
            },
          ],
        } as any;
      }
      if (urlStr.includes(`/api/v1/agent/sessions/${mockSessionId}/control`)) {
        dispatchedControl = JSON.parse((init?.body as string) || "{}");
        return {
          ok: true,
          json: async () => ({
            ok: true,
            session_id: mockSessionId,
            action: dispatchedControl.action,
            status: dispatchedControl.action === "kill" ? "stopped" : "running",
            euthyna_hash: "0xcontrolhash123",
          }),
        } as any;
      }
      return {
        ok: true,
        json: async () => [],
      } as any;
    }) as any;

    const handleNavigate = mock(() => {});

    await act(async () => {
      render(
        <NotificationDropdown
          walletAddress="0x1234567890123456789012345678901234567890"
          onNavigate={handleNavigate}
        />
      );
    });

    // Open dropdown
    const bellBtn = screen.getByTitle("Notifications & System Alerts");
    await act(async () => {
      fireEvent.click(bellBtn);
    });

    // Assert P1 Critical alert is visible
    expect(screen.getByText(/P1 CRITICAL/i)).toBeTruthy();
    expect(screen.getByText(/GenLayer SLA verdict INVALID/i)).toBeTruthy();

    // Click Emergency Kill button
    const killBtn = screen.getByRole("button", { name: /Emergency Kill/i });
    await act(async () => {
      fireEvent.click(killBtn);
    });

    expect(dispatchedControl).not.toBeNull();
    expect(dispatchedControl.action).toBe("kill");
  });
});
