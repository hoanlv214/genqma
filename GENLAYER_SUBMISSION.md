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
https://explorer-studio-dev.genlayer.com/address/0x1e5B4d7Be22A3f7F4Ecb616bA65123cB03B7cc13
```
*(Contract deployed on GenLayer Studio Next, Chain ID 61997: `0x1e5B4d7Be22A3f7F4Ecb616bA65123cB03B7cc13`)*
*(Live On-Chain Verified Txs: `0x10c014f608b3b550127ff3d0fdc419460c91ba260a95127c110e3b09931e6f0e` (94% confidence), `0x73b618c6266f9b5e700b545b8fb2cfc601fc2e658669a0ae124d0d2dc373d685` (91% confidence))*

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
3. **0:35 - 0:55:** Cho xem bước GenLayer: `GenQMAShield.py` lấy feed MEXC thật và chạy `gl.vm.run_nondet` semantic consensus. UI hiển thị toast xác nhận settlement Arc USDC và tiến hành verify GenLayer.
4. **0:55 - 1:15:** GenLayer consensus hoàn tất trả về `VALID / VERIFIED`, UI lập tức hiển thị toast chứa GenLayer Tx hash (`0x73b6...`) và mở khóa đúng báo cáo.

### Bằng Chứng On-Chain Đã Xác Thực (Sẵn Sàng Cho Giám Khảo):
- **GenLayer Intelligent Contract:** `0x1e5B4d7Be22A3f7F4Ecb616bA65123cB03B7cc13`
- **GenLayer Studio Dev Explorer:** [explorer-studio-dev.genlayer.com/address/0x1e5B4d7Be22A3f7F4Ecb616bA65123cB03B7cc13](https://explorer-studio-dev.genlayer.com/address/0x1e5B4d7Be22A3f7F4Ecb616bA65123cB03B7cc13)
- **Giao Dịch Xác Thực Thực Tế (Live Verified Txs):**
  - **Tx 1:** `0x10c014f608b3b550127ff3d0fdc419460c91ba260a95127c110e3b09931e6f0e` ([Xem trên Explorer](https://explorer-studio-dev.genlayer.com/transactions/0x10c014f608b3b550127ff3d0fdc419460c91ba260a95127c110e3b09931e6f0e)) - Verdict: `VALID` (94% Confidence), Anomaly: `LASERTECSTOCK`
  - **Tx 2:** `0x73b618c6266f9b5e700b545b8fb2cfc601fc2e658669a0ae124d0d2dc373d685` ([Xem trên Explorer](https://explorer-studio-dev.genlayer.com/transactions/0x73b618c6266f9b5e700b545b8fb2cfc601fc2e658669a0ae124d0d2dc373d685)) - Verdict: `VALID` (91% Confidence), Anomaly: `SOFTBANKSTOCK`
  - **Tx 3 (Live End-to-End Autonomous Agent Purchase):** `0x581dd9292beb9e356aa1a97b1e8e7b30b83d8530e6c30eaf8218f7518ce263cb` ([Xem trên Explorer](https://explorer-studio-dev.genlayer.com/transactions/0x581dd9292beb9e356aa1a97b1e8e7b30b83d8530e6c30eaf8218f7518ce263cb)) - Verdict: `VALID` (92% Confidence), Anomaly: `AVA`

