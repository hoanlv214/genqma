# QMA — Báo Cáo Kiểm Toán An Toàn & Bảo Mật V4 (Security Audit Report)

**Mã tài liệu**: `QMA-SEC-AUDIT-202610-V4`  
**Ngày thực hiện**: Tháng 10/2026  
**Chi nhánh git**: `main`  
**Phạm vi**: Backend API (`backend/app`), Smart Contract Interactions, Spend Guards, Swap & Treasury, Secret Exposure, Nonce Safety, Crash Recovery, Deployment Topology  

---

## 1. Mô Hình Đe Dọa (Threat Model & Attack Surfaces)

Hệ thống QMA vận hành trên mô hình đại lý tự chủ (Autonomous AI Agent) có thẩm quyền ký và phát lệnh thanh toán stablecoin on-chain. Có 6 bề mặt tấn công trọng yếu:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CÁC BỀ MẶT TẤN CÔNG CỐT LÕI                     │
├──────────────────────────┬─────────────────────────┬───────────────────┤
│ 1. Cổng x402 & Hóa Đơn   │ 2. Swap Router & Exec   │ 3. USYC Treasury  │
│ - Replay settlement_id   │ - Quote replay / reuse  │ - Halt switch bypass
│ - Giả mạo chữ ký EIP-712 │ - Multi-worker TOCTOU   │ - Oracle NAV spoof│
│ - Token access leakage   │ - Nonce collision       │ - Withdrawal abuse│
├──────────────────────────┼─────────────────────────┼───────────────────┤
│ 4. GenLayer Validator    │ 5. Khóa Relayer & EOA   │ 6. Storage Engine │
│ - Giả mạo bằng chứng     │ - Lộ Private Key        │ - Race condition  │
│ - Làm nghẽn queue DoS    │ - Crash intermediate    │ - Trực tiếp sửa DB│
└──────────────────────────┴─────────────────────────┴───────────────────┘
```

---

## 2. Danh Mục Lỗ Hổng & Tình Trạng Khắc Phục (Vulnerability Catalog)

### SEC-01 [CRITICAL / P0]: Lỗ Hổng Tái Thực Thi Báo Giá Swap (Swap Quote Replay & Exactly-Once Invariant)
- **Vị trí**: `backend/app/services/swap_executor.py` & `backend/app/services/swap_router.py`.
- **Cơ chế lỗi**: Ban đầu `execute_quote` chỉ đọc quote mà không tiêu thụ. Khi được nâng cấp `consume_quote()`, quote bị pop khỏi bộ nhớ nhưng nếu xảy ra lỗi RPC hoặc tiến trình crash giữa chừng, quote bị mất vĩnh viễn và không thể retry; ngược lại nếu retry mù quáng sẽ phát sinh giao dịch on-chain trùng lặp.
- **Biện pháp khắc phục**:
  - Triển khai mô hình **Transaction Lifecycle 6 trạng thái**: `PENDING`, `PREPARED`, `SUBMITTED`, `CONFIRMED`, `REVERTED`, `UNCERTAIN`, `FAILED`.
  - Hỗ trợ `idempotency_key` và `idempotent_retry`: Nếu quote đã `CONFIRMED`, trả về receipt đã lưu trữ mà không bao giờ broadcast lại transaction thứ hai.
  - Ngăn chặn triệt để replay và duplicate transactions trên mạng Arc.
- **Bằng chứng kiểm chứng**: `test_idempotent_retry_returns_receipt_without_duplicate_action` và `test_five_concurrent_requests_using_same_quote` (5 luồng chạy đồng thời: 1 thành công, 4 từ chối).

### SEC-02 [CRITICAL / P0]: Race Condition Vượt Hạn Mức Chi Tiêu Khi Chạy Đa Worker (Spend Guard TOCTOU Vulnerability)
- **Vị trí**: `backend/app/services/spend_guard.py`.
- **Cơ chế lỗi**: `enforce_spend()` trước đây chỉ kiểm tra tổng số tiền đã chi tiêu trong quá khứ (`daily_spent`). Khi 10 workers cùng gửi request đồng thời (ví dụ mỗi worker yêu cầu 0.03 USDC trong khi hạn mức ngày là 0.05 USDC), cả 10 workers đều đọc thấy `daily_spent == 0` và cùng thông qua, dẫn tới tổng chi tiêu thực tế lên tới 0.30 USDC (vượt 600% hạn mức).
- **Biện pháp khắc phục**:
  - Triển khai mô hình **Two-Phase Reservation**:
    1. `reserve_spend(payer, amount, tx_ref)`: Kiểm tra `effective_daily_spent = confirmed_spends + pending_reservations`. Nếu trong hạn mức, tạo `reservation_id` có thời hạn TTL (300s) và khóa ngay hạn mức lại.
    2. Bọc toàn bộ thao tác trong `cross_process_lock` (hỗ trợ cả đa luồng và đa tiến trình thông qua OS-level `fcntl.flock`).
    3. `commit_spend(payer, reservation_id, tx_hash)`: Khi giao dịch on-chain thành công, chuyển đổi reservation thành khoản chi tiêu chính thức.
    4. `release_spend(payer, reservation_id, reason)`: Khi giao dịch bị revert hoặc hủy, giải phóng khoản reservation ngay lập tức.
- **Bằng chứng kiểm chứng**: `test_concurrent_workers_approaching_daily_spend_cap` (10 workers cùng bắn đồng thời: chính xác 1 worker thành công, 9 worker bị từ chối) và `test_spend_guard_durable_reservation_survives_restart`.

### SEC-03 [HIGH / P0]: Thất Lạc Bằng Chứng Giao Dịch & Sai Lệch Kế Toán Khi RPC Timeout (Uncertain Outcome Handling)
- **Vị trí**: `backend/app/services/swap_executor.py:wait_for_transaction_receipt`.
- **Cơ chế lỗi**: Sau khi ký và phát raw transaction lên Arc qua `send_raw_transaction`, nếu hàm chờ biên nhận `wait_for_transaction_receipt` bị timeout (do nghẽn mạng RPC sau 60s), code cũ văng exception làm mất `tx_hash` của giao dịch, giải phóng nhầm spend reservation hoặc để người dùng retry dẫn tới chuyển tiền 2 lần.
- **Biện pháp khắc phục**:
  - Ghi nhận và lưu trữ trạng thái `PREPARED` cùng `expected_tx_hash`, `nonce`, và `raw_tx` TRƯỚC KHI gọi `send_raw_transaction`.
  - Khi timeout xảy ra, trạng thái được đánh dấu rõ ràng là `UNCERTAIN` (Không xác định), **GIỮ NGUYÊN SPEND RESERVATION** để bảo vệ ngân sách.
  - Cung cấp hàm đối soát `reconcile_swap_execution(quote_id)` để tra cứu trạng thái thực tế trên Arc khi RPC phục hồi.
- **Bằng chứng kiểm chứng**: `test_rpc_timeout_marks_uncertain_and_reconciles_on_chain`.

### SEC-04 [HIGH / P0]: Xung Đột Nonce Của Relayer Khi Phát Giao Dịch Đồng Thời (Relayer Nonce Serialization)
- **Vị trí**: `backend/app/services/swap_executor.py:build_transaction`.
- **Cơ chế lỗi**: Việc gọi `w3.eth.get_transaction_count(acct.address, "pending")` không có khóa đồng bộ giữa các worker dẫn tới nhiều worker nhận cùng một số nonce, gây lỗi `nonce too low` hoặc `replacement transaction underpriced`.
- **Biện pháp khắc phục**:
  - Bọc quy trình lấy nonce, ký và phát raw transaction trong `cross_process_lock(f"relayer_broadcast_{acct.address.lower()}")`.
  - Ngay sau khi transaction được mạng ghi nhận vào mempool (`SUBMITTED`), khóa được giải phóng để giao dịch tiếp theo lấy nonce kế tiếp (`nonce + 1`) mà không phải chờ đợi receipt.
- **Bằng chứng kiểm chứng**: Đã kiểm chứng trong test suite `test_swap_executor.py` và `test_transaction_lifecycle_and_spend_guard.py`.

### SEC-05 [CRITICAL / P0]: Phục Hồi Crash Giữa Chừng & Trạng Thái `PREPARED` (Intermediate Crash Recovery)
- **Vị trí**: `backend/app/services/swap_executor.py:execute_quote` & `reconcile_swap_execution`.
- **Cơ chế lỗi**: Nếu tiến trình bị chết đột ngột (crash/kill) sau khi ký và lưu đĩa nhưng trước khi `send_raw_transaction` hoàn tất, trạng thái nếu ghi nhận là `SUBMITTED` có thể khiến recovery worker chỉ tìm receipt mà không thấy, dẫn tới giam tiền vô thời hạn hoặc xử lý sai.
- **Biện pháp khắc phục**:
  - Tách rõ trạng thái `PREPARED` (đã ký, tính trước hash, lưu đĩa) và `SUBMITTED` (bắt đầu gọi broadcast).
  - Recovery worker kiểm tra nonce on-chain: Nếu nonce chưa dịch chuyển, phát lại đúng `raw_tx` bytes đã ký; nếu nonce đã vượt qua mà không có receipt, đánh dấu `FAILED` và nhả reservation.
- **Bằng chứng kiểm chứng**: `test_failure_point_1_prepared_tx_interrupted_before_broadcast` và `test_failure_point_2_broadcast_accepted_receipt_mined_before_ack`.

### SEC-06 [CRITICAL / P0]: Nguy Cơ Suy Diễn Nhầm `nonce too low` Khi Giao Dịch Bị Thay Thế (Replacement Nonce Hazard)
- **Vị trí**: `backend/app/services/swap_executor.py:execute_quote`.
- **Cơ chế lỗi**: Khi node trả về `nonce too low`, code cũ coi như giao dịch đã vào mempool. Điều này sai lầm vì có thể một giao dịch khác ngoài luồng đã chiếm nonce đó, khiến giao dịch của QMA bị rớt hoàn toàn.
- **Biện pháp khắc phục**:
  - Khi gặp `nonce too low`, bắt buộc truy vấn `get_transaction_receipt(expected_tx_hash)` kèm retry chống lag read-replica của node RPC.
  - Nếu không có receipt, kiểm tra `get_transaction_count(acct.address, "latest")`. Nếu nonce on-chain lớn hơn nonce bản ghi -> Khẳng định giao dịch bị drop/replace bởi một giao dịch khác ngoài luồng.
  - **Cơ chế phòng vệ tài chính nghiêm ngặt**:
    1. Đánh dấu trạng thái `FAILED_NONCE_COLLISION`.
    2. Ghi nhận sự cố bảo mật nghiêm trọng `P1_CRITICAL` vào `incident_engine` và xâu chuỗi vào Athenian Euthyna audit trail.
    3. Kích hoạt ngắt mạch khẩn cấp (`guard.trip_circuit_breaker(payer)`), lập tức đóng băng mọi yêu cầu chi tiêu tự động tiếp theo từ payer/relayer này cho đến khi quản trị viên con người kiểm tra số dư và trạng thái on-chain.
    4. Nhả spend reservation cụ thể để không bị kẹt vĩnh viễn, nhưng circuit breaker đã khóa ngăn chặn triệt để mọi hành vi chi tiêu vượt hạn mức hoặc xung đột số dư.
- **Bằng chứng kiểm chứng**: `test_nonce_too_low_receipt_found_vs_dropped_replacement` (kiểm chứng Case A có receipt mined, Case B bị replacement chuyển sang `FAILED_NONCE_COLLISION`, ngắt mạch tripped và chặn mọi lần đặt trước tiếp theo với `CircuitBreakerTrippedError`).

### SEC-07 [HIGH / P0]: Ngăn Chặn Triệt Để Scale Ngang Đa Container (Single-Instance Topology Guard)
- **Vị trí**: `backend/app/core/config.py:enforce_single_instance_topology_guard` & `backend/app/main.py:_qma_lifespan`.
- **Cơ chế lỗi**: Primitives đồng bộ hiện tại của QMA (`cross_process_lock` dùng `fcntl.flock`, `SpendLimitGuard` lưu in-memory reservations, và `swap_executions.json`) là các tài nguyên cục bộ trên hệ thống tệp của 1 container. Ngay cả khi có `REDIS_URL`, code hiện tại chưa tích hợp adapter distributed lock (Redlock) và distributed reservation store. Cho phép nhiều container khi có Redis là một giả định sai lầm nguy hiểm.
- **Biện pháp khắc phục**:
  - `enforce_single_instance_topology_guard` kiểm tra và **chặn đứng vô điều kiện** (`RuntimeError`) bất kỳ cấu hình nào có `RENDER_INSTANCE_COUNT > 1`, `INSTANCE_COUNT > 1` hoặc `QMA_MULTI_INSTANCE=1`, bất kể `REDIS_URL` có tồn tại hay không.
  - Ghi rõ trong thông báo lỗi và tài liệu kiến trúc rằng QMA bắt buộc vận hành trên mô hình single container cho đến khi hoàn thành tích hợp Redlock phân tán.
- **Bằng chứng kiểm chứng**: `test_deployment_topology_guard` (kiểm chứng pass trên 1 instance, ném lỗi trên multi-instance không có Redis, ném lỗi trên multi-instance CÓ Redis, và ném lỗi khi bật cờ `QMA_MULTI_INSTANCE`).

### SEC-08 [HIGH / P0]: Cơ Chế Dừng Khẩn Cấp Runtime Toàn Diện (Runtime Emergency Halt & All Financial Flows)
- **Vị trí**: `backend/app/core/config.py:is_treasury_halted`, `backend/app/core/config.py:set_emergency_halt`, `backend/app/services/usyc_treasury.py`, `backend/app/services/swap_executor.py`, `backend/app/services/stablefx_service.py`, `backend/app/services/earn_kit.py`, `backend/app/main.py:submit_withdraw`, `backend/app/api/v1/endpoints/sessions.py`.
- **Cơ chế lỗi**: Biến môi trường hệ thống chỉ nạp lúc tiến trình khởi động; thay đổi trên dashboard triển khai không tự cập nhật cho tiến trình đang chạy. Cache `self._policy` trong bộ nhớ của tiến trình có thể che khuất cấu hình cập nhật từ đĩa hoặc worker khác. Một số dịch vụ chuyển tiền (`stablefx_service`, `earn_kit`) chưa được đấu nối vào hàm kiểm tra dừng khẩn cấp.
- **Biện pháp khắc phục**:
  - Bổ sung file cờ runtime `data/EMERGENCY_HALT`: Bất kỳ script vận hành, monitor hay webhook nào cũng có thể tạo file này để lập tức dừng toàn bộ hệ thống mà không cần restart tiến trình.
  - Hàm `set_emergency_halt(halted: bool, reason: str)` đồng bộ tạo/xóa file cờ runtime và cập nhật `CorporateTreasuryPolicy.treasury_halted`.
  - `get_policy(reload=True)` loại bỏ stale cache trong bộ nhớ khi kiểm tra dừng khẩn cấp.
  - Đấu nối `is_treasury_halted()` vào **100% các luồng chuyển tiền**:
    1. DEX Aggregator Swap (`swap_executor.py:execute_quote`)
    2. USYC Treasury Deposit (`usyc_treasury.py:execute_deposit`)
    3. USYC Treasury Redeem (`usyc_treasury.py:execute_redeem`)
    4. Autonomous CFO Agent Decisions (`usyc_treasury.py:evaluate_cfo_decision`)
    5. Creator Withdrawals (`backend/app/main.py:submit_withdraw`)
    6. Session User Withdrawals (`backend/app/api/v1/endpoints/sessions.py:withdraw`)
    7. StableFX Institutional Settlement (`backend/app/services/stablefx_service.py:settle_stablefx_swap`)
    8. Morpho Earn Kit Deposit & Withdraw (`backend/app/services/earn_kit.py:deposit`, `withdraw`)
- **Bằng chứng kiểm chứng**: `test_runtime_emergency_halt_flag_file_and_all_money_flows` (chứng minh việc tạo cờ dừng lập tức từ chối cả 6 luồng tài chính và việc gỡ cờ giải phóng lại hệ thống).

### SEC-09 [HIGH / P0]: Kiểm Thử Phục Hồi Crash Bằng Subprocess Thật (Real Subprocess Crash & Rebroadcast)
- **Vị trí**: `tests/unit/test_transaction_lifecycle_and_spend_guard.py:test_real_subprocess_crash_recovery_rebroadcasts_raw_tx`.
- **Cơ chế kiểm thử**: Thay vì chỉ dùng mock nội bộ, kiểm thử đã kích hoạt một tiến trình Python độc lập của hệ điều hành (`subprocess.run`), ký và ghi trạng thái `PREPARED` vào file đĩa, sau đó thoát tiến trình đột ngột.
- **Kết quả kiểm chứng**: Tiến trình cha nạp lại dữ liệu, phát hiện giao dịch ở trạng thái `PREPARED`, phát lại đúng payload `raw_tx` bytes nguyên bản ra mempool mà không ký lại, và chuyển thành `CONFIRMED` khi có receipt.

---

## 3. Báo Cáo Rà Soát Secret & Phụ Thuộc (Secret & Dependency Forensic)

### 3.1. Rà Soát Lịch Sử Git Bằng Gitleaks (v8.30.1)
- Đã chạy phân tích trên 236 commit:
  - **1.430 findings (98.2%)**: Thuộc file fixture `data/qma_invoices_rows.csv` (`invoice_secret` dạng UUID mock).
  - **18 findings**: Dummy test keys trong `tests/` (`0x1111111111111111111111111111111111111111111111111111111111111111`).
  - **7 findings**: Địa chỉ hợp đồng public TokenMessenger / ERC-20 trên Sepolia, Base, Arbitrum testnets.
  - **1 finding**: Placeholder trong `README.md`.
- **Kết luận**: **Không có bất kỳ credential hay live private key thật nào từng bị commit vào Git**.

### 3.2. Đồng Bộ Phụ Thuộc FastAPI & Starlette
- Đồng bộ metadata chính xác: `fastapi==0.124.4` và `starlette==0.50.0`.
- Thỏa mãn hoàn toàn ràng buộc `starlette<0.51.0,>=0.40.0` của FastAPI 0.124.4.
- `pip check` xác nhận 0 xung đột phụ thuộc.

---

## 4. Bảng Trạng Thái Tuân Thủ An Toàn V4 (Đã Kiểm Chứng Thực Nghiệm)

| Tiêu chuẩn bảo mật | Đánh giá V4 | Bằng chứng kiểm chứng thực tế |
| :--- | :--- | :--- |
| **Chống Double Spend** | **ĐẠT** | Exactly-once transaction lifecycle + idempotent retry + pre-broadcast persistence (`test_commit_and_release_are_strictly_idempotent`) |
| **Spend Limit Concurrency** | **ĐẠT** | Two-phase reservation + cross-process locking + TTL pinning (`test_concurrent_workers_approaching_daily_spend_cap`) |
| **Crash Recovery (5 Windows)** | **ĐẠT** | Subprocess OS thật: rebroadcast đúng `raw_tx` đã ký (`test_real_subprocess_crash_recovery_rebroadcasts_raw_tx`) |
| **Nonce Safety & Collision** | **ĐẠT** | Phân lập `nonce too low` + `FAILED_NONCE_COLLISION` + ngắt mạch tự động + P1 incident (`test_nonce_too_low_receipt_found_vs_dropped_replacement`) |
| **Topology Guardrail** | **ĐẠT** | Chặn khởi động vô điều kiện nếu multi-instance (`test_deployment_topology_guard`) |
| **Runtime Emergency Halt** | **ĐẠT** | Cờ runtime `data/EMERGENCY_HALT` chặn nhất quán 100% cả 8 luồng chi tiêu (`test_runtime_emergency_halt_flag_file_and_all_money_flows`) |
| **Lộ Secret / Key** | **ĐẠT** | 0 secret rò rỉ trong lịch sử Git (Gitleaks v8.30.1 trên 236 commits) |
| **Toàn Vẹn Backend Regression** | **ĐẠT** | **543 passed, 0 failed** trên toàn bộ test suite backend |
| **Toàn Vẹn Frontend Rebuild** | **ĐẠT** | **35 passed, 142 assertions** trên Vite/React test suite |
| **Production Live Money** | **CHƯA BẬT** | Giữ `SWAP_EXECUTION_MODE=dry_run` cho đến khi staging testnet tối thiểu 48h |
