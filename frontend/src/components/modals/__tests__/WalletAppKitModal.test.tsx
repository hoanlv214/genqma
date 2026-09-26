import { describe, expect, it, mock, beforeEach, afterEach } from "bun:test";
import React from "react";
import { render, act, cleanup } from "@testing-library/react";
import { WalletAppKitModal } from "../WalletAppKitModal";
import { appKit, arcTestnetChain, getAppKitAccount } from "../../../config/reownAppKit";

describe("WalletAppKitModal & Reown AppKit Suite", () => {
  afterEach(() => {
    cleanup();
  });

  it("1. Reown AppKit is configured with Arc Testnet chain settings", () => {
    expect(arcTestnetChain.id).toBe(5042002);
    expect(arcTestnetChain.name).toBe("Arc Testnet");
    expect(arcTestnetChain.nativeCurrency.symbol).toBe("USDC");
    expect(arcTestnetChain.chainNamespace).toBe("eip155");

    const account = getAppKitAccount();
    expect(account).toHaveProperty("isConnected");
    expect(account).toHaveProperty("address");
  });

  it("2. Does not open AppKit modal when open prop is false", () => {
    const handleClose = mock(() => {});
    const handleConnected = mock((_addr: string) => {});

    let openCalled = false;
    const origOpen = appKit.open;
    appKit.open = (async () => {
      openCalled = true;
    }) as any;

    try {
      render(
        <WalletAppKitModal
          open={false}
          onClose={handleClose}
          onConnected={handleConnected}
        />
      );

      expect(openCalled).toBe(false);
      expect(handleClose).not.toHaveBeenCalled();
      expect(handleConnected).not.toHaveBeenCalled();
    } finally {
      appKit.open = origOpen;
    }
  });

  it("3. Triggers openAppKitModal and subscribes to account changes when open is true", async () => {
    const handleClose = mock(() => {});
    const handleConnected = mock((_addr: string) => {});

    let openCalled = false;
    let accountCallback: ((acc: any) => void) | null = null;

    const origOpen = appKit.open;
    const origSubscribeAccount = appKit.subscribeAccount;

    appKit.open = (async () => {
      openCalled = true;
    }) as any;

    appKit.subscribeAccount = ((cb: any) => {
      accountCallback = cb;
      return () => {};
    }) as any;

    try {
      render(
        <WalletAppKitModal
          open={true}
          onClose={handleClose}
          onConnected={handleConnected}
        />
      );

      expect(openCalled).toBe(true);
      expect(accountCallback).toBeDefined();

      // Simulate wallet connection event from Reown AppKit
      act(() => {
        if (accountCallback) {
          accountCallback({
            isConnected: true,
            address: "0x9999999999999999999999999999999999999999",
          });
        }
      });

      expect(handleConnected).toHaveBeenCalledWith("0x9999999999999999999999999999999999999999");
      expect(handleClose).toHaveBeenCalled();
    } finally {
      appKit.open = origOpen;
      appKit.subscribeAccount = origSubscribeAccount;
    }
  });

  it("4. Calls onClose when user dismisses/closes Reown AppKit modal", async () => {
    const handleClose = mock(() => {});
    const handleConnected = mock((_addr: string) => {});

    let stateCallback: ((state: any) => void) | null = null;
    const origSubscribeState = appKit.subscribeState;

    appKit.subscribeState = ((cb: any) => {
      stateCallback = cb;
      return () => {};
    }) as any;

    try {
      render(
        <WalletAppKitModal
          open={true}
          onClose={handleClose}
          onConnected={handleConnected}
        />
      );

      expect(stateCallback).toBeDefined();

      // Simulate user closing the AppKit modal dialog
      act(() => {
        if (stateCallback) {
          stateCallback({ open: false });
        }
      });

      expect(handleClose).toHaveBeenCalled();
    } finally {
      appKit.subscribeState = origSubscribeState;
    }
  });
});
