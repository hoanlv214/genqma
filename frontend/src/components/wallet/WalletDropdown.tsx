import { useState } from "react";
import { connectWallet, shortAddress } from "../../services/wallet";
import { clearAllWalletProfileSessions } from "../../services/walletProfileSession";

export function WalletDropdown({ onFundArc }: { onFundArc: () => void }) {
  const [address, setAddress] = useState(() => localStorage.getItem("qma_connected_wallet") || "");
  const [open, setOpen] = useState(false);

  const connect = async () => {
    const next = await connectWallet();
    setAddress(next);
    localStorage.setItem("qma_connected_wallet", next);
  };

  return (
    <div className="wallet-control">
      <button type="button" className="wallet-button" onClick={address ? () => setOpen(!open) : connect}>
        {address ? shortAddress(address) : "Connect Wallet"}
      </button>
      {open ? (
        <div className="wallet-menu">
          <div className="wallet-menu-address">{address}</div>
          <button type="button" onClick={onFundArc}>Fund Arc Wallet</button>
          <button type="button" onClick={() => window.location.assign(`/profile?wallet=${encodeURIComponent(address)}`)}>Profile</button>
          <button type="button" onClick={() => { localStorage.removeItem("qma_connected_wallet"); clearAllWalletProfileSessions(); setAddress(""); setOpen(false); }}>
            Disconnect
          </button>
        </div>
      ) : null}
    </div>
  );
}
