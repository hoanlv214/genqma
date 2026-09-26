import { useState } from "react";
import { shortAddress } from "../../services/wallet";
import { clearAllWalletProfileSessions } from "../../services/walletProfileSession";
import { WalletAppKitModal } from "../modals/WalletAppKitModal";

export function WalletDropdown({ onFundArc }: { onFundArc: () => void }) {
  const [address, setAddress] = useState(() => localStorage.getItem("qma_connected_wallet") || "");
  const [open, setOpen] = useState(false);
  const [showAppKit, setShowAppKit] = useState(false);

  return (
    <div className="wallet-control">
      <button type="button" className="wallet-button" onClick={address ? () => setOpen(!open) : () => setShowAppKit(true)}>
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
      <WalletAppKitModal
        open={showAppKit}
        onClose={() => setShowAppKit(false)}
        onConnected={(next) => {
          setAddress(next);
          localStorage.setItem("qma_connected_wallet", next);
          setShowAppKit(false);
        }}
      />
    </div>
  );
}
