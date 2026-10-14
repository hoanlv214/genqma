# QMA — Báo Cáo Kiểm Chứng Độc Lập & Kiểm Toán Đối Kháng V4 (Crash Recovery, Nonce Safety & Deployment Guardrails)

**Mã tài liệu**: `QMA-AUDIT-FINAL-202610-V4`  
**Ngày thực hiện**: Tháng 10/2026  
**Chi nhánh git**: `main` (commit baseline: `f78a0e2687950aa4ea0f7bcbec13142700cd7f6e`)  
**Tiêu chuẩn kiểm chứng**: Controlled Refactoring & Codebase Intelligence Protocol (CRCIP, E0–E5)  
**Tình trạng kết luận**: **ĐÃ CHỨNG MINH THỰC NGHIỆM PHỤC HỒI SAU CRASH & NONCE SAFETY / GIỮ NGUYÊN KHUYẾN NGHỊ: CHƯA BẬT LIVE MONEY TRÊN MAINNET**

---

## 1. Kết Luận Điều Hành & Tóm Tắt Vòng 4 (Executive Summary)

Đợt kiểm toán đối kháng chuyên sâu V4 giải quyết triệt để 5 vấn đề cốt lõi do reviewer chỉ định trước khi chấp nhận tài liệu an toàn tài chính:

### 1.1. Phục Hồi Sau Crash: Trạng Thái `PREPARED` & 5 Cửa Sổ Thất Bại (Failure Windows)
- **Thiết kế phân lập 6 trạng thái vòng đời**:
  - `PREPARED`: Đã ký cục bộ, tính trước `expected_tx_hash`, `nonce`, và lưu `raw_tx` bền vững xuống đĩa kèm fsync. Broadcast CHƯA được xác nhận.
  - `SUBMITTED`: Đã bắt đầu phát sóng lên mạng Arc.
  - `UNCERTAIN`: Đã thử phát sóng nhưng timeout hoặc RPC ngắt kết nối; kết quả chưa xác định.
  - `CONFIRMED`: Có biên nhận on-chain với `receipt.status == 1`.
  - `REVERTED`: Có biên nhận on-chain với `receipt.status == 0`.
  - `FAILED`: Chỉ dùng khi có bằng chứng mạnh rằng giao dịch không thể hoàn tất (ví dụ: nonce đã bị transaction khác chiếm dụng).
- **Quy tắc bất biến tài chính**:
  - **Không bao giờ tự ý giải phóng reservation** chỉ vì `get_transaction()` hoặc `get_transaction_receipt()` trả về `None`.
  - Nếu gặp bản ghi `PREPARED` khi phục hồi: kiểm tra nonce on-chain. Nếu nonce chưa dịch chuyển, **chỉ phát lại chính xác payload `raw_tx` đã ký trước đó**, tuyệt đối không ký mới.

### 1.2. Nonce Safety: Bóc Tách `already known` vs `nonce too low`
- **`already known`**: Node mempool đã biết payload giao dịch này -> Tiếp tục truy vấn receipt của `tx_hash` dự kiến.
- **`nonce too low`**: KHÔNG được suy diễn là giao dịch của QMA đã thành công!
  1. Tra cứu `receipt = w3.eth.get_transaction_receipt(expected_tx_hash)`. Nếu tìm thấy receipt thành công -> Xác nhận `CONFIRMED`.
  2. Nếu KHÔNG tìm thấy receipt: Tra cứu nonce xác nhận on-chain `onchain_latest_nonce = w3.eth.get_transaction_count(relayer, "latest")`.
     - Nếu `onchain_latest_nonce > record_nonce`: Nonce này đã bị một transaction khác sử dụng on-chain (thay thế hoặc chi tiêu ngoài). Giao dịch của QMA đã bị rớt/thay thế (dropped/replaced) và vĩnh viễn không thể đào được nữa -> Đánh dấu `FAILED` và **giải phóng an toàn spend reservation**.
     - Nếu `onchain_latest_nonce <= record_nonce`: Trạng thái mạng chưa ổn định/chưa rõ -> Giữ nguyên `UNCERTAIN` và **bảo lưu spend reservation**.

### 1.3. Bảo Đảm Đa Worker vs Đa Container (Deployment Guardrail)
- **Giới hạn kiến trúc**: File lock (`fcntl.flock`) và file ledger trên disk chỉ bảo đảm tính nguyên tử cho mô hình **Single-Container Multi-Worker** (ví dụ Uvicorn/Gunicorn nhiều worker process chia sẻ cùng filesystem trên Render). Nó **không** có hiệu lực giữa nhiều container độc lập (scale ngang).
- **Cơ chế phòng vệ chủ động (`enforce_single_instance_topology_guard`)**:
  - Được tích hợp trực tiếp vào startup lifespan (`_qma_lifespan` trong `backend/app/main.py`).
  - Nếu phát hiện cấu hình đa container (`RENDER_INSTANCE_COUNT > 1` hoặc `QMA_MULTI_INSTANCE=1`) mà **không có** `REDIS_URL`, hệ thống lập tức ném lỗi `RuntimeError` và từ chối khởi động.
  - Khuyến nghị triển khai hiện tại: Cố định chạy trên 1 single container instance.

### 1.4. Thống Nhất Emergency Stop & Đọc Động Lúc Runtime
- **Hàm đánh giá động tập trung**: `is_treasury_halted() -> bool` tại `backend/app/core/config.py`.
- **Thứ tự ưu tiên (Precedence)**:
  1. Biến môi trường: `QMA_TREASURY_HALTED` hoặc `QMA_TREASURY_HALT` (được đọc trực tiếp tại thời điểm gọi hàm bằng `os.getenv`, có tác dụng ngay lập tức mà không cần restart tiến trình).
  2. Chính sách quản trị động: `CorporateTreasuryPolicy.treasury_halted`.
  3. Cơ chế Fail-Closed: Nếu việc đọc cấu hình gặp sự cố/lỗi, hàm tự động trả về `True` (dừng hoạt động để bảo vệ an toàn quỹ).
- **Phạm vi bảo vệ toàn diện**: Áp dụng đồng bộ cho:
  - Swap execution (`swap_executor.execute_quote`)
  - USYC treasury sweep (`usyc_treasury.sweep_idle_cash`)
  - USYC deposit & JIT redemption (`execute_deposit`, `execute_redemption`)
  - Creator withdrawals (`submit_withdraw` tại `backend/app/main.py`)
  - User session withdrawals (`/api/v1/sessions/withdraw` tại `backend/app/api/v1/endpoints/sessions.py`)

### 1.5. Khắc Phục Mismatch Dependency (FastAPI & Starlette)
- Xác minh metadata phụ thuộc:
  - Cài đặt `fastapi==0.124.4`.
  - Khóa phiên bản tương thích `starlette==0.50.0` trong `requirements.txt` (thỏa mãn hoàn toàn điều kiện `starlette<0.51.0,>=0.40.0` của FastAPI 0.124.4).
  - Kiểm tra `pip check`: Không có bất kỳ xung đột dependency nào liên quan tới FastAPI/Starlette.
  - OpenAPI Test Gate: **13/13 tests passed**.

---

## 2. Bảng Ma Trận Kiểm Chứng 21 Kịch Bản Đối Kháng V4 (V4 Adversarial Matrix)

Mọi kịch bản đều được kiểm chứng tự động bằng mã kiểm thử thực tế trong `tests/unit/test_transaction_lifecycle_and_spend_guard.py`:

| # | Kịch bản đối kháng (Adversarial Scenario) | Rủi ro trước đây | Cơ chế bảo vệ V4 | Kết quả kiểm chứng |
| :- | :--- | :--- | :--- | :--- |
| **1** | **5 requests đồng thời dùng cùng 1 quote** | Quote replay phát sinh nhiều swap on-chain | `consume_quote()` nguyên tử + lock thực thi | **ĐẠT** (`test_five_concurrent_requests_using_same_quote`) |
| **2** | **10 workers cùng chạm trần daily cap** | TOCTOU race: cả 10 workers chi tiêu vượt 600% cap | `reserve_spend` với `cross_process_lock` | **ĐẠT** (`test_concurrent_workers_approaching_daily_spend_cap`: 1 thành công, 9 từ chối) |
| **3** | **Hai idempotency keys tranh chấp 1 quote** | Giao dịch sau đè giao dịch trước | Request 1 tiêu thụ quote, request 2 bị từ chối `expired/not found` | **ĐẠT** (`test_competing_idempotency_keys_on_single_quote`) |
| **4** | **Reverted transaction on Arc** | Hạn mức chi tiêu bị giam oan | `receipt.status != 1` tự động gọi `release_spend` giải phóng hạn mức | **ĐẠT** (`test_reverted_transaction_releases_spend_reservation`) |
| **5** | **Giao dịch pending lâu vượt TTL 300s** | Hạn mức bị giải phóng ngầm gây overspend | `pin_reservation` ghim hạn mức đến khi finalized | **ĐẠT** (`test_pinned_reservation_survives_past_ttl_until_finalized`) |
| **6** | **Commit & Release lặp lại nhiều lần** | Sai lệch số dư hoặc mảng spends bị ô nhiễm | Tính độc đẳng (Idempotence): gọi lặp lại là no-op an toàn | **ĐẠT** (`test_commit_and_release_are_strictly_idempotent`) |
| **7** | **Process restart khôi phục trạng thái** | Mất dữ liệu bộ đếm chi tiêu khi reboot | Nạp lại các reservation đang active và pinned từ ledger bền vững | **ĐẠT** (`test_spend_guard_durable_reservation_survives_restart`) |
| **8** | **Cửa sổ 1: Crash sau khi lưu signed tx nhưng trước khi gửi** | Mất giao dịch hoặc gửi giao dịch mới gây duplicate nonce | Lưu `PREPARED` + `raw_tx`. Recovery phát lại chính xác payload cũ mà không ký mới | **ĐẠT** (`test_failure_point_1_prepared_tx_interrupted_before_broadcast`) |
| **9** | **Cửa sổ 2: Broadcast được chấp nhận nhưng crash trước khi app nhận ack** | Ứng dụng không biết hash giao dịch đã gửi | `tx_hash` đã lưu trước; recovery tìm thấy receipt -> `CONFIRMED` & commit reservation | **ĐẠT** (`test_failure_point_2_broadcast_accepted_receipt_mined_before_ack`) |
| **10** | **Cửa sổ 3: Broadcast timeout kết quả không xác định** | Giải phóng reservation vội vàng làm overspend | Chuyển `UNCERTAIN`, ghim reservation, không giải phóng khi chưa có receipt | **ĐẠT** (`test_failure_point_3_broadcast_timeout_unknown_outcome`) |
| **11** | **Cửa sổ 4: Receipt đã có on-chain nhưng crash trước khi commit spend** | Kế toán nội bộ không ghi nhận khoản chi | Recovery đọc receipt -> chuyển `CONFIRMED` và commit reservation an toàn | **ĐẠT** (`test_failure_point_4_receipt_available_before_spend_committed`) |
| **12** | **Cửa sổ 5: Tạo reservation nhưng crash trước khi lưu tx** | Tiền bị giam vô thời hạn do unpinned | Reservation không được pin, tự động hết hạn và thu hồi sau TTL 300s | **ĐẠT** (`test_failure_point_5_reservation_unpinned_expires_after_ttl`) |
| **13** | **`nonce too low`: Giao dịch đã được đào thành công** | Báo lỗi nhầm khi giao dịch thực chất đã vào block | Tìm thấy receipt hợp lệ -> chuyển `CONFIRMED` | **ĐẠT** (`test_nonce_too_low_receipt_found_vs_dropped_replacement` Case A) |
| **14** | **`nonce too low`: Nonce bị giao dịch khác chiếm dụng (Replacement)** | Bị treo UNCERTAIN vĩnh viễn dù tx không bao giờ vào block | Phát hiện `onchain_nonce > record_nonce` mà không có receipt -> Đánh dấu `FAILED` và nhả reservation | **ĐẠT** (`test_nonce_too_low_receipt_found_vs_dropped_replacement` Case B) |
| **15** | **Scale ngang đa container không có Redis** | Hai container không chia sẻ file lock gây chi tiêu kép | `enforce_single_instance_topology_guard` chặn khởi động và báo lỗi cấu hình | **ĐẠT** (`test_deployment_topology_guard`) |
| **16** | **Emergency Stop qua Env Var chặn tức thì Creator Withdrawal** | Rút tiền creator vẫn lọt qua khi dừng khẩn cấp | `submit_withdraw` kiểm tra `is_treasury_halted()` -> trả về 503 ngay lập tức | **ĐẠT** (`test_runtime_emergency_halt_stops_creator_and_session_withdrawals`) |
| **17** | **Emergency Stop qua Env Var chặn tức thì Session Withdrawal** | Rút tiền agent session vẫn lọt qua khi dừng khẩn cấp | `/api/v1/sessions/withdraw` kiểm tra `is_treasury_halted()` -> trả về 503 | **ĐẠT** (`test_runtime_emergency_halt_stops_creator_and_session_withdrawals`) |
| **18** | **Emergency Stop qua Env Var chặn tức thì Swaps** | Swap lọt qua khi dừng khẩn cấp | `execute_quote` kiểm tra `_treasury_halted()` -> ném `SwapExecutionError` | **ĐẠT** (`test_emergency_stop_via_env_var_blocks_swaps_and_treasury`) |
| **19** | **Emergency Stop qua Env Var chặn tức thì Treasury Sweep** | Sweep tự động lọt qua khi dừng khẩn cấp | `_enforce_safety_rails` kiểm tra `is_treasury_halted()` -> ném `ValueError` | **ĐẠT** (`test_emergency_stop_via_env_var_blocks_swaps_and_treasury`) |
| **20** | **Idempotent retry trả về receipt cũ không phát sinh broadcast** | Người dùng bấm retry nhiều lần | Kiểm tra trạng thái `CONFIRMED` -> trả ngay receipt đã lưu | **ĐẠT** (`test_idempotent_retry_returns_receipt_without_duplicate_action`) |
| **21** | **Vòng đời đặt chỗ 2 pha (Reserve -> Commit / Release)** | Chi tiêu không kiểm soát | Thử nghiệm đặt chỗ, giải phóng, và xác nhận hạn mức liên tục | **ĐẠT** (`test_spend_guard_two_phase_reservation_lifecycle`) |

---

## 3. Tổng Hợp Bằng Chứng Kiểm Thử Hồi Quy (Empirical Verification Gates)

| Công cụ kiểm tra | Lệnh thực thi | Kết quả thực tế | Trạng thái |
| :--- | :--- | :--- | :--- |
| **Backend Pytest (Full Suite)** | `python -m pytest tests/ -q` | **542 passed**, 16 warnings (78.50s) | **100% PASS** |
| **Unit & Adversarial Tests** | `python -m pytest tests/unit/test_transaction_lifecycle_and_spend_guard.py -v` | **21 passed**, 0 failed, 2 warnings (6.86s) | **100% PASS** |
| **OpenAPI Contract Gate** | `python -m pytest tests/api_v1/test_api_openapi_docs.py -q` | **13 passed**, 0 failed (0.93s) | **100% PASS** |
| **Frontend Test Suite** | `npm --prefix frontend test -- --run` | **35 passed**, 142 assertions (2.62s) | **100% PASS** |
| **Dependency Audit** | `python -m pip show fastapi starlette` | `fastapi==0.124.4`, `starlette==0.50.0` | **MATCH & COMPATIBLE** |

---

## 4. Quyết Định & Giới Hạn Triển Khai (Deployment Decisions)

| Hạng mục | Quyết định V4 | Ràng buộc kỹ thuật |
| :--- | :--- | :--- |
| **Mainnet với tiền thật** | **KHÔNG BẬT** | Giữ mặc định `SWAP_EXECUTION_MODE=dry_run` và `SWAP_EXECUTION_LIVE=0`. |
| **Arc Testnet Staging** | **ĐƯỢC PHÉP** | Chỉ sử dụng ví relayer thử nghiệm với hạn mức nhỏ (dưới 50 USDC/ngày). |
| **Mô hình triển khai** | **Single Container duy nhất** | Chạy trên 1 instance container (Render). Tuyệt đối không bật scale ngang khi chưa tích hợp Redis atomic ledger. |
| **Cơ chế khôi phục** | **Tự động đối soát (Reconcile)** | Khi RPC timeout hoặc server reboot, gọi `reconcile_swap_execution` để đối soát dựa trên receipt và nonce on-chain. |
| **Dừng khẩn cấp** | **Runtime Environment Switch** | Có thể ngắt toàn bộ dòng tiền ngay lập tức bằng cách set biến môi trường `QMA_TREASURY_HALTED=1` mà không cần restart service. |

---

## 5. Kết Luận Cuối Cùng

Hệ thống QMA V4 đã hoàn tất việc đóng kín các cửa sổ thất bại trong chu trình giao dịch, ngăn chặn hoàn toàn rủi ro suy diễn sai về `nonce too low`, bảo đảm tính toàn vẹn của hạn mức chi tiêu đa worker, và thiết lập hàng rào kỹ thuật ngăn scale ngang không an toàn. Codebase đạt trạng thái an toàn cao nhất trên môi trường kiểm thử và sẵn sàng cho giai đoạn phát triển tiếp theo (Human Approval & Timelock Governance).
