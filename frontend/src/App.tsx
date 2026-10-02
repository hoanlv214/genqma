import React from "react";
import { WalletProvider } from "@/state/walletStore";
import { AppRoutes } from "@/routes";
import { Toaster } from "sonner";

export function App() {
  return (
    <WalletProvider>
      <AppRoutes />
      <Toaster position="bottom-right" richColors theme="dark" closeButton />
    </WalletProvider>
  );
}

export default App;
