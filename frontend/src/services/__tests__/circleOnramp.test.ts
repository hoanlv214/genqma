import { describe, expect, it, mock, beforeEach, afterEach } from "bun:test";
import {
  requestOnrampSession,
  mountOnrampIframe,
  openOnrampPopup,
  getOnrampKit,
} from "../circleOnramp";

describe("Circle / Arc Onramp Service Suite", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    // reset fetch mock
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("1. Successfully requests an onramp session from backend", async () => {
    const mockSession = {
      sessionToken: "test_token_123",
      sessionId: "session_abc",
      widgetUrl: "https://onramp.arc.io/?sessionToken=test_token_123",
      destinationWallet: "0x1111111111111111111111111111111111111111",
    };

    globalThis.fetch = mock(() =>
      Promise.resolve(new Response(JSON.stringify(mockSession), { status: 200 }))
    ) as any;

    const res = await requestOnrampSession("0x1111111111111111111111111111111111111111", "test-user");
    expect(res.sessionToken).toBe("test_token_123");
    expect(res.widgetUrl).toContain("onramp.arc.io");
    expect(res.destinationWallet).toBe("0x1111111111111111111111111111111111111111");
  });

  it("2. Handles backend error on onramp session request", async () => {
    globalThis.fetch = mock(() =>
      Promise.resolve(new Response(JSON.stringify({ detail: "Invalid address" }), { status: 400 }))
    ) as any;

    expect(requestOnrampSession("invalid-addr")).rejects.toThrow("Invalid address");
  });

  it("3. Initializes and returns singleton onramp kit instance", () => {
    const kit1 = getOnrampKit();
    const kit2 = getOnrampKit();
    expect(kit1).toBeDefined();
    expect(kit1).toBe(kit2);
  });

  it("4. Mounts onramp iframe into container element with lifecycle callbacks", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);

    let settledCalled = false;

    const widget = mountOnrampIframe(
      container,
      {
        sessionToken: "test_tok",
        sessionId: "sess_1",
        widgetUrl: "https://onramp.arc.io/?sessionToken=test_tok",
        destinationWallet: "0x1111111111111111111111111111111111111111",
      },
      {
        onDepositSettled: () => {
          settledCalled = true;
        },
      }
    );

    expect(widget).toBeDefined();
    expect(typeof widget.close).toBe("function");

    // Clean up
    widget.close();
    container.remove();
  });
});
