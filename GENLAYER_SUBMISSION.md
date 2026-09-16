# GenLayer Agent Tank — Bản Điền Form Nộp Bài Chuẩn 1:1

> **Link nộp bài trực tiếp:** [portal.genlayer.foundation/agent-tank/hackathon/submit](https://portal.genlayer.foundation/agent-tank/hackathon/submit)
> **Hạn chót nộp bài:** 17/09/2026 · 15:30 UTC
> **Quy tắc:** Chỉ copy nội dung trong các khung `[COPY NỘI DUNG NÀY]` tương ứng với từng ô trên giao diện web.

---

### [Trường 00] Track
* **Tên trường trên web:** `00 Track / Choose a track`
* **Loại input:** Dropdown chọn 1 track

```text
Agentic Commerce Infrastructure
```

---

### [Trường 01A] GitHub repository
* **Tên trường trên web:** `01 GitHub repository / The repository the panel reviews`
* **Loại input:** Chọn repo từ GitHub account đã liên kết

```text
https://github.com/hoanlv214/genqma
```
*(Hoặc chọn repository `genqma` trong danh sách dropdown)*

---

### [Trường 01B] Identity
* **Tên trường trên web:** `01 Identity / Make it recognizable`

1. **Choose logo (PNG, JPEG, WebP · 128–2048 px · max 2 MB):**
   *Upload file logo có sẵn trong repo tại đường dẫn:*
   `frontend/public/android-chrome-512x512.png` (Kích thước 512x512 px, 66 KB, chuẩn PNG)

2. **Project name:**
```text
GenQMA
```

---

### [Trường 02] Project summary
* **Tên trường trên web:** `02 Project summary / One-liner (0/180 characters)`
* **Độ dài ký tự thực tế:** 132 / 180 ký tự (Đạt chuẩn)

```text
Market-memory marketplace with one-signature x402 USDC payment and hash-bound, fail-closed GenLayer report verification.
```

---

### [Trường 03] Project overview
* **Tên trường trên web:** `03 Project overview / Description (0/1000 characters)`
* **Độ dài ký tự thực tế:** 862 / 1000 ký tự (Đạt chuẩn)

```text
When AI agents buy quantitative market memory via x402, ordinary smart contracts cannot judge data quality. A fabricated report can take the buyer's funds with no recourse.

GenQMA adds a GenLayer Intelligent Contract as an on-chain SLA arbiter:

1. Live Evidence: gl.nondet.web.render() fetches the provider-specific MEXC API.
2. Semantic Consensus: gl.vm.run_nondet validates structured verdicts without comparing LLM prose byte-for-byte.
3. Hash Binding: invoice_id, query_hash and report_hash bind the verdict to the exact cached report. Only finalized VALID / VERIFIED unlocks it; all errors stay locked.
4. Verdict Settlement: after one buyer authorization, VALID schedules the creator share while the platform share stays in treasury. INVALID schedules a full Arc refund to the verified payer. Only a Circle COMPLETE receipt marks money movement complete.
```

---

### [Trường 04] Demo video (Bắt buộc cho Agent Tank)
* **Tên trường trên web:** `04 Demo video / Show it in action (YouTube URL · optional)`
* **Loại input:** Ô dán đường dẫn video YouTube (`https://youtu.be/...` hoặc `https://www.youtube.com/watch?v=...`)

```text
[Dán link YouTube video demo hoàn chỉnh vào đây]
```
*(Giao diện có thể ghi Optional, nhưng luật Agent Tank yêu cầu video để bài dự thi hợp lệ. Không nộp khi ô này còn trống.)*

---

### [Trường 05] How-to
* **Tên trường trên web:** `05 How-to / Write the exact path`
* **Cách điền trên web:** Bấm `+ Add another step` để tạo 4 bước, mỗi bước copy đúng cặp Heading và Instruction:

#### Step 1:
* **Heading (Optional):**
```text
1. Explore Live Market Anomalies
```
* **Instruction:**
```text
Open https://genqma.vercel.app. The autonomous agent continuously scans live funding rate and open-interest divergences across crypto pairs (e.g. ETH-USDT). Select any live anomaly card on the radar to inspect current divergence and expected historical analog utility.
```

#### Step 2:
* **Heading (Optional):**
```text
2. Connect Wallet & Authorize One x402 Payment
```
* **Instruction:**
```text
Connect your wallet on Arc Testnet and click 'Unlock Full Memory' or 'Preview ($0.001)'. The invoice contains one treasury-bound Circle x402 requirement, so the buyer signs one payment authorization. The backend then generates and hashes the exact report selected by that invoice.
```

#### Step 3:
* **Heading (Optional):**
```text
3. Validator Consensus & Live Exchange Verification
```
* **Instruction:**
```text
The backend relayer submits `invoice_id`, `query_hash`, the full-report hash, a public verification manifest (excluding paid analog rows), and an HTTPS evidence URL. The contract fetches evidence and executes `gl.vm.run_nondet` with a semantic validator before recording `VALID` or `INVALID`.
```

#### Step 4:
* **Heading (Optional):**
```text
4. Verify Access, Payout, or Refund
```
* **Instruction:**
```text
Inspect the finalized contract order. VALID / VERIFIED unlocks the exact cached report and schedules the configured creator payout; the platform share remains in treasury. INVALID / REJECTED blocks access and schedules a full refund to the verified payer. Arc payout/refund is complete only after Circle reports COMPLETE; RPC errors remain locked and retryable.
```

---

### [Trường 06] Review verification
* **Tên trường trên web:** `06 Review verification / Prove the path works`

1. **Expected verification outcome (0/500 characters):**
   *Độ dài thực tế: 441 / 500 ký tự (Đạt chuẩn)*
```text
GenQMAShield binds invoice_id, query_hash and report_hash, fetches live HTTPS evidence and runs gl.vm.run_nondet. VALID / VERIFIED unlocks only that report and schedules the configured creator payout. INVALID / REJECTED blocks access and schedules a full refund to the verified payer. Money movement is confirmed only by a Circle COMPLETE receipt; the GenLayer contract does not custody Arc USDC.
```

2. **Contract link 1 (optional):**
   *Dán URL Studio hoặc Contract Explorer:*
```text
https://explorer-studio-dev.genlayer.com/address/0x367728bf66Cf962Ce15fD2b65193b7a1466f087c
```
*(Contract deployed on GenLayer Studio Next, Chain ID 61997: `0x367728bf66Cf962Ce15fD2b65193b7a1466f087c`)*

---

### [Trường 07] Project links
* **Tên trường trên web:** `07 Project links / Send people to it`

1. **Website (required):**
```text
https://genqma.vercel.app
```

2. **GitHub:**
```text
https://github.com/hoanlv214/genqma
```

---

## Phụ Lục Kỹ Thuật (Dành Riêng Cho Bạn - Không Cần Dán Lên Web)

### Gợi ý kịch bản quay Video Demo 60-90 giây (Nếu bạn muốn quay):
1. **0:00 - 0:15:** Mở [genqma.vercel.app](https://genqma.vercel.app), chỉ vào radar: Anomaly ETH-USDT xuất hiện (funding rate âm sâu, OI tăng vọt).
2. **0:15 - 0:35:** Nhấn mua báo cáo Market Memory ($0.005). Giải thích vấn đề: nếu không có GenLayer, nếu nhà cung cấp trả data rác/ảo giác thì agent mất tiền.
3. **0:35 - 0:55:** Cho xem bước GenLayer: `GenQMAShield.py` lấy feed MEXC thật và chạy `gl.vm.run_nondet` semantic consensus. `VALID` mở đúng report hash; `INVALID` khóa report. Không mô tả payout/refund là hoàn tất nếu chưa có Arc receipt.
4. **0:55 - 1:15:** Cho xem order finalized trên GenLayer: `VALID / VERIFIED` mở đúng report hash; `INVALID / REJECTED` chặn access token. Không dùng cờ giả lập public.
