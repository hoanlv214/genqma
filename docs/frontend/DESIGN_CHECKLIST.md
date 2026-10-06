# QMA Frontend Design Checklist

Audit checklist theo 4 nhóm quy tắc thiết kế, đối chiếu toàn bộ màn hình.
Được thiết kế cho design system hiện tại: `src/styles/tokens.css` (Treasury OS
palette), Tailwind v4.3 `@theme` utilities, Lucide icons, binding copy
(không em-dash, tối đa 1 dấu chấm mỗi dòng UI copy, zero fake numbers, badge
rationing).

Audit pass: 2026-10-05. Cách dùng: trước mỗi lần chỉnh UI, chạy qua nhóm
1-4 cho phần đang chạm; sau khi chỉnh, đối chiếu mục đã từng fail.

## Nhóm 1 — Nhất quán Hệ thống (Visual & Component Consistency)

| # | Quy tắc | Cách check |
| :-- | :--- | :--- |
| 1.1 | Spacing hệ 4px/8px | grep `p|gap|mt|mb|py|px-\[\d+px\]` — bội số của 4; cấm 5/6/7/9/10/13/15px |
| 1.2 | Typography scale từ tokens | cấm `text-[9px]`, `text-[10px]`, `text-[11px]`, `text-[1.1rem]`... ngoài scale; chỉ font-sans/serif/mono |
| 1.3 | Color tokens | cấm raw hex trong tsx (`bg-[#...]`, `style={{color:'#...'}}`); dùng var(--t1/t2/t3/accent/green/amber/purple) |
| 1.4 | Iconography | chỉ Lucide/Phosphor; cấm text-glyph làm icon (↻ ⇄ → x); cấm emoji trong UI |
| 1.5 | Component states | button/card đủ default/hover/disabled (dùng Button component, không tự viết) |
| 1.6 | Copy binding | KHÔNG em-dash (—) trong UI copy; tối đa 1 dấu chấm mỗi dòng hero/label; zero fake numbers |

## Nhóm 2 — UX Laws

| # | Quy tắc | Cách check |
| :-- | :--- | :--- |
| 2.1 | Hick: tối giản lựa chọn | hero ≤ 2 CTA; form thanh toán chia bước; mỗi card ≤ 1 CTA chính |
| 2.2 | Fitts: CTA đủ to, dễ chạm | CTA chính full-width trên mobile; không CTA nhỏ dưới 40px chiều cao |
| 2.3 | Jakob: mô thức quen thuộc | refresh/disconnect/close theo pattern phổ thông; không bắt học lại |

## Nhóm 3 — Phân cấp Thị giác

| # | Quy tắc | Cách check |
| :-- | :--- | :--- |
| 3.1 | Emphasis | giá tiền + CTA + tiêu đề nổi bật nhất trong paywall/marketplace |
| 3.2 | Reading pattern | landing chữ Z (copy trái, visual phải); trang dữ liệu chữ F |
| 3.3 | White space | không section nào ép >2 cột thông tin dày đặc liên tiếp |

## Nhóm 4 — Tiếp cận & Phản hồi

| # | Quy tắc | Cách check |
| :-- | :--- | :--- |
| 4.1 | Contrast WCAG 4.5:1 | cấm `text-[var(--t3)]`/opacity < 1 cho body text trên nền tối |
| 4.2 | System status | mọi async panel có loading + error + empty + success state |
| 4.3 | Error handling | cấm render `err.message` thô; icon-only button phải có aria-label |

## Kết quả audit 2026-10-05 (đã fix trong pass này ✅)

### Đã fix
- ✅ 1.6 PaywallPanel: fabricated `confidence || 98%` fallback (hiển thị giá trị thật hoặc bỏ số) — PaywallPanel.tsx
- ✅ 1.6 PaywallPanel: close button `x` text → Lucide `X` + `aria-label="Close paywall"`
- ✅ 1.6 Em-dash trong câu UI copy: ReportWorkspace (CTA "Unlock Preview/Full", dòng "98% Confidence SLA Guarantee" — đồng thời bỏ fake 98%), SignalReportsView (3 câu), ConnectPage (2 document.title + copy-failed error), OperationsPage (banner + empty state), InteractiveLiveSimulationWidget (sweep status)
- ✅ 1.6 OperationsPage banner copy tự hợp nhất với self-healing mechanism
- ✅ TractionPage poll chuyển sang quiet pattern (không flash loader, giữ snapshot khi outage)
- ✅ PaywallPanel step 4 render động theo `sla_state` (preverified → "Pre-Verified · opens immediately")

### Đã fix trong color-discipline pass (2026-10-05, visual-verified bằng browser screenshot)

- ✅ 1.3 **Color Consistency Lock** trên Traction: 3 headline card về chung một treatment indigo (card-settled green + card-yield amber → accent); amber loại khỏi value/footer; tags MEXC/Polymarket/Pyth về một style neutral
- ✅ 1.3 Badge rationing: bỏ chip "Interactive" trên tab; chip "x402 Protocol" về neutral
- ✅ 1.3 Chip system (ui.css, áp dụng toàn app): `chip-pending` amber → neutral (pending không phải warning); `chip-premium` purple → accent; radar corridor bar 5 mục về 1 accent; balance-tile amber/purple → neutral (green giữ cho Euthyna proof = semantic)
- ✅ 1.3 GlobalHeader: raw `rgba(168,156,255,1)` → `var(--accent)` token

### Đã fix trong header + fake-data pass (2026-10-05, buổi sau)

- ✅ 1.3 **Header rainbow**: NetworkBadge sky-500/400 → chip neutral (dot accent cho testnet, green cho mainnet); bỏ fake "< 500ms Block Finality" + "(~$0.01)" khỏi popover; link explorer về accent token; em-dash trong title bỏ
- ✅ 1.5 Bell badge: `bg-blue-500` + glow → `var(--accent)` không glow (red chỉ cho critical incident = danger semantic thật)
- ✅ 1.6 **InfoHint component mới** (`components/ui/InfoHint.tsx` + CSS): Lucide Info + tooltip hover/focus, neutral styling, max-width 280px, reduced-motion safe — áp dụng cho 4 chỗ chữ dài: 3 desc card Traction, intro CFO radar, hero desc Operations
- ✅ 1.6 DecisionReceipt: fake ledger indices `#426`/`#425` → nhãn thật "current"/"previous" (hash vẫn là data thật)
- ✅ 1.6 Landing "Measured, not claimed": bỏ `< 500ms`, `$0.00002`, `$0.002+`, `100%` bịa → thay bằng hằng số thật (0.002 preview / 0.005 full / 80% creator share / Per query no-subscription)

### Đã fix trong text-glyph + a11y pass (2026-10-05, tiếp sau)

- ✅ 1.4 Text-glyph icons → Lucide: `↻` (SignalSidebar refresh) → `RefreshCw`; `↻ Sync` + `Sidebar Dock ⇄` (SignalRibbon) → `RefreshCw`/`ArrowLeftRight`
- ✅ 4.3 Copy buttons trong GlobalHeader thêm `aria-label="Copy to clipboard"`
- ✅ 4.2 **InfoHint hover VERIFIED bằng browser automation**: cua.move đúng tọa độ icon (getBoundingClientRect) → `:hover` matched → opacity 1 (các đoán định sai trước đó do transition clock đóng băng trong background tab)

### Đã fix trong full-remediation pass (2026-10-05, "fix hết toàn bộ")

- ✅ 1.3 **NotFoundPage tokenized toàn bộ**: bg hex gradient → var(--bg-base), #fff/rgba-white → t1/t2/surface/bdr, bỏ fake-terminal box (AI-tell), copy thẳng thắn "Page not found", font-family inherit, 100dvh. DOM-verified: CTA bg = rgb(99,102,241) đúng indigo brand
- ✅ 1.3 ApiDocsPage: bg-[#1e1e1e]/border-[#333] → surface/bdr-md, text-green-400 → text-success, text-[1.1rem]/[0.82rem] → text-base/text-sm, py-2.5 → py-2
- ✅ 1.3 **UnifiedFundsModal 163 replacements**: toàn bộ surface tints (#090a12...#171828) → surface-1/2/3, border-white/[0.06-0.12] → bdr/bdr-md, text-white → t1, fractional py-3.5/px-3.5/p-3.5 → 12px grid
- ✅ 1.2 **Text scale sweep 86 occurrences**: text-[10px] → text-2xs, text-[11px] → text-xs (utilities bridged qua @theme inline trong index.css), text-[9px] → text-2xs; 5 sizes lẻ (11.5px, 0.78/0.82/0.92rem) → scale
- ✅ 1.1 Sub-4px spacing: NetworkBadge gap-[7px]→gap-2/py-[5px]→py-1/w-[7px]→w-2; StatusBadge gap/w-[5px] → gap-1/w-1
- ✅ 1.3 StatusBadge hex fallbacks → semantic utilities: text-success/warning/danger + bg-*-dim + border-*/30; purple variant → accent (color lock)
- ✅ 4.1 GlobalHeader: bỏ opacity-80 trên agent balance (contrast)
- ✅ 4.3 Raw err.message → friendly errors: IntelligencePage (transfer/withdrawal x3, mapping user-rejected/insufficient/network + console.error raw), MarketplacePage (providersError → actionable copy)
- ✅ 1.6 HomePage: footer brand desc 2 câu → 1 câu; footer bottom 4 chấm → 2 câu ngắn; dead ternary `metrics ?` → `metrics?.current_paid_count != null`
- ✅ 1.6 SignalReportsView aria-label em-dash → comma

### Đã fix trong header-unification pass (2026-10-05, "2 header font + chiều cao không đồng nhất")

Đo đạc bằng browser evaluate (computed styles) cả 2 header, chuẩn hóa về một spec:

- ✅ 1.2 **Font nav thống nhất**: GlobalHeader `var(--font-sans, system-ui)` (var không tồn tại → rơi về system-ui!) → `var(--sans)` (Inter); nav label 14px → `var(--text-sm)`; landing toc 13px → `var(--text-sm)`. Cả hai header giờ Inter + text-sm
- ✅ 1.5 **Control heights đồng nhất 32px**: landing CTA 34→32, menu-btn 34→32, NetworkBadge → h-8; global connect-btn 32px + radius token + `var(--on-accent)`; NetworkBadge h-8
- ✅ 1.1 **Cạnh ngang aligned**: token mới `--header-inset: max(16px, calc((100% - 1240px) / 2 + 16px))` — logo x=114 trên CẢ landing và app (trước: landing 100+, app 16 → logo nhảy vị trí khi điều hướng)
- ✅ 1.3 wallet-dropdown border green-dim → bdr-md (green chỉ semantic)
- ✅ 1.6 residue "vestiarion-style" trong comment LandingHeader → mô tả trung tính
- ✅ Landing height 60px hardcoded → `var(--header-h)` (cùng token với global)

### Đã fix trong connected-wallet header pass (2026-10-05, theo screenshot user)

- ✅ 1.5 **Wallet dropdown button về 1 dòng 32px pill** (bắt đầu là khối 2 dòng address + "Agent: $" bị dính chữ, cao hơn mọi control khác): giờ `Wallet icon + 0x2c03…53d4 + chevron`, h-32 khớp NetworkBadge/bell; số dư Agent hiển thị trong dropdown (đã có sẵn) + tooltip trên nút
- ✅ 1.5 **Bell trigger 36px → 32px** (CSS rule cố định override Tailwind class), Bell 18 → 16, bỏ glow đỏ (border red giữ cho critical)
- ✅ 2.1 **Nav labels rút gọn (Hick)**: Operations → Ops · Intelligence → Signals · Swap & StableFX → Swap · Traction & Ledger → Proof · Creator Marketplace → Market (icon giữ nguyên; LandingHeader APP_LINKS đồng bộ)
- ✅ Đo bằng computed styles: toàn bộ right cluster h=32, y=14 (căn giữa tuyệt đối trong header 60px)

### Đã fix trong report-symbol integrity pass (2026-10-06, screenshot user "HYPE Report / nội dung RLC")

- ✅ **P0 data-integrity — 2 nguồn sự thật**: title report đọc `activeQuery?.symbol` (query đang chọn) trong khi content đọc `unlockedReport` (report đang mở) → mở report owned khác query active hiện SAI symbol. Fix: title + TokenIcon derive từ `unlockedReport.query_symbol`
- ✅ **P0 receipt id "RPT-EPOCH…"**: `usePayment` ưu tiên `reportData.invoice` (meta synthetic `epoch_...` nhúng trong report snapshot chia sẻ theo epoch) hơn hóa đơn thật của buyer → đảo priority: `invoiceForReport || reportData.invoice` (hóa đơn thật thắng; meta snapshot chỉ là fallback)
- ✅ DecisionReceipt bỏ nốt fallback fake: confidence `'0.98'`, hash `'8f42...a91c'`, `|| 98` — chỉ hiển thị khi có giá trị thật
- ✅ openCachedReportEntry: fallback signal ưu tiên `report.query_symbol` trước activeQuery

### Còn lại (theo thứ tự ưu tiên, chưa fix)

| Mức | Finding | Vị trí |
| :-- | :--- | :--- |
| P3 | Inline svg brand logos (Arc/Circle/X/GH/Discord) — **user quyết định giữ nguyên** (logo exempt) | HomePage.tsx:14-30,449-461 |

### Đã đạt (pass toàn nhóm)

- tokens.css: spacing scale 4px đầy đủ, type scale, radius, focus ring, reduced-motion, tabular-nums.
- Global `:focus-visible` ring + `button:active` scale-down.
- Button component có disabled + loading states (components/ui/button.tsx).
- MarketplacePage: loading/error/empty/retry + onboarding empty state mẫu mực.
- SwapPage: async feedback đầy đủ (5 loading flags, disabled-until-valid, dual-leg receipts).
- Landing hero: đúng Hick (2 CTA), 1 chấm mỗi dòng, F-pattern.
- Zero emoji trong UI; ~43 aria-labels; Operations/Traction dùng `role="alert"`.
- Lucide là hệ icon mặc định app-wide; inline svg chỉ còn ở brand logos/token marks.
