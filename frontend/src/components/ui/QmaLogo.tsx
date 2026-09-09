import React from "react";

interface QmaLogoProps {
  size?: number;
  className?: string;
  showText?: boolean;
}

export function QmaLogo({ size = 26, className = "", showText = true }: QmaLogoProps) {
  return (
    <div className={`logo-item qma-logo-item ${className}`} style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
      <svg
        width={size}
        height={Math.round(size * (700 / 743))}
        viewBox="0 0 743 700"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="qma-logo-svg flex-shrink-0"
        style={{ width: `${size}px`, height: "auto" }}
      >
        <defs>
          <linearGradient id="qma-logo-ring-grad" x1="0" y1="0" x2="743" y2="700" gradientUnits="userSpaceOnUse">
            <stop stopColor="#6745FA" />
            <stop offset="1" stopColor="#30FCEB" />
          </linearGradient>
          <linearGradient id="qma-logo-slash-grad" x1="328.264" y1="400" x2="742.189" y2="700" gradientUnits="userSpaceOnUse">
            <stop stopColor="#6745FA" />
            <stop offset="1" stopColor="#30FCEB" />
          </linearGradient>
        </defs>
        <path
          d="M350 0C543.3 0 700 156.7 700 350C700 402.299 688.528 451.918 667.965 496.479L593.563 406.607C597.774 388.418 600 369.469 600 350C600 211.929 488.071 100 350 100C211.929 100 100 211.929 100 350C100 488.071 211.929 600 350 600C367.397 600 384.378 598.222 400.773 594.84L470.27 678.787C432.765 692.51 392.257 700 350 700C156.7 700 0 543.3 0 350C0 156.7 156.7 0 350 0Z"
          fill="url(#qma-logo-ring-grad)"
        />
        <path
          d="M493.834 400H328.264L576.619 700H742.189L493.834 400Z"
          fill="url(#qma-logo-slash-grad)"
        />
      </svg>
      {showText && <span className="logo-text">QMA</span>}
    </div>
  );
}
