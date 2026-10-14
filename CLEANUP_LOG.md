# QMA — Nhật Ký Dọn Dẹp & Cải Thiện Codebase V4 (Cleanup & Remediation Log)

**Mã tài liệu**: `QMA-CLEANUP-LOG-202610-V4`  
**Ngày thực hiện**: Tháng 10/2026  
**Chi nhánh git**: `main`  
**Quy tắc tuân thủ**: CRCIP Protocol, bảo toàn thay đổi của người dùng, không refactor tùy tiện.  

---

## 1. Bảng Tổng Hợp Các Thay Đổi Đã Thực Hiện

| Tệp tin | Loại thay đổi | Lý do / Căn cứ kỹ thuật | Kết quả kiểm chứng |
| :--- | :--- | :--- | :--- |
| `backend/app/services/swap_executor.py` | Bảo mật P0 | Triển khai trạng thái `PREPARED`, trích xuất `expected_tx_hash`, `nonce`, `raw_tx` và lưu bền vững trước khi broadcast. Bóc tách `nonce too low` (kiểm tra receipt và on-chain nonce). Phát lại đúng payload cũ khi recovery. | Ngăn chặn mất hash giao dịch, chống double broadcast, phân biệt chính xác tx bị rớt do replacement. |
| `backend/app/services/spend_guard.py` | Bảo mật P0 | Bổ sung cơ chế `pin_reservation` ghim hạn mức cho giao dịch pending, độc đẳng cho `commit_spend` / `release_spend`, và `cleanup_expired_reservations`. | Ngăn chặn giải phóng hạn mức do quá hạn TTL trong khi tx đang xử lý trên mạng. |
| `backend/app/core/config.py` | Kiến trúc P0 | Bổ sung hàm đánh giá khẩn cấp động `is_treasury_halted()` và hàm bảo vệ topo `enforce_single_instance_topology_guard()`. | Đảm bảo dừng khẩn cấp đọc lúc runtime với cơ chế fail-closed; chặn scale ngang container không có Redis. |
| `backend/app/main.py` | Bảo mật P0 | Gọi `enforce_single_instance_topology_guard()` trong `_qma_lifespan`; gọi `is_treasury_halted()` trong `submit_withdraw`. | Chặn startup nếu cấu hình đa container không an toàn; chặn rút tiền creator khi dừng khẩn cấp. |
| `backend/app/api/v1/endpoints/sessions.py` | Bảo mật P0 | Bổ sung kiểm tra `is_treasury_halted()` trong `/api/v1/sessions/withdraw`. | Chặn rút tiền agent session tức thì khi dừng khẩn cấp. |
| `backend/app/services/usyc_treasury.py` | Bảo mật P0 | Tích hợp `is_treasury_halted()` vào `_enforce_safety_rails` cho mọi thao tác sweep, deposit, redeem. | Chặn sweep và rút nạp USYC tức thì khi dừng khẩn cấp. |
| `requirements.txt` | Phụ thuộc | Khóa `fastapi==0.124.4` và `starlette==0.50.0`. | Giải quyết triệt để mismatch dependency; `pip check` sạch hoàn toàn. |
| `tests/unit/test_transaction_lifecycle_and_spend_guard.py` | Kiểm thử đối kháng | Bổ sung đầy đủ kiểm thử cho 5 failure windows, nonce too low (mình vs replacement), topology guard, và emergency stop. | 21/21 tests pass 100%. |

---

## 2. Chi Tiết Kỹ Thuật Các Bản Vá Trọng Yếu

### 2.1. Phân Lập Vòng Đời Giao Dịch & Trạng Thái `PREPARED`
- Trước khi phát sóng giao dịch qua `send_raw_transaction`:
  1. Trích xuất `expected_tx_hash = signed.hash.hex()`.
  2. Trích xuất `raw_tx_hex = signed.raw_transaction.hex()`.
  3. Ghi đĩa atomic (`.tmp` + `os.fsync` + `os.replace`) với trạng thái `PREPARED`, `nonce`, và `raw_tx`.
  4. Ghim reservation: `guard.pin_reservation(payer, reservation_id)`.
  5. Chuyển trạng thái `SUBMITTED` và gọi broadcast.
- Khi recovery đối soát gặp bản ghi `PREPARED`:
  - Tra cứu receipt on-chain: Nếu có -> `CONFIRMED` / `REVERTED`.
  - Nếu không có receipt và `onchain_nonce == record_nonce`: Giao dịch chưa được đào và chưa có tx nào chiếm nonce -> Phát lại chính xác byte `raw_tx` cũ, **không ký mới**.
  - Nếu `onchain_nonce > record_nonce`: Đã có transaction khác chiếm nonce on-chain -> Chuyển `FAILED` và giải phóng reservation.

### 2.2. Xử Lý Nonce Too Low & Phát Hiện Thay Thế (Replacement Hazard)
- Không suy diễn `nonce too low` là giao dịch thành công.
- Quy trình bóc tách:
  ```python
  found_rc = w3.eth.get_transaction_receipt(tx_hex)
  if found_rc:
      # Giao dịch thực chất đã được đào
      raw_hash = bytes.fromhex(tx_hex[2:])
  else:
      onchain_latest_nonce = w3.eth.get_transaction_count(acct.address, "latest")
      if onchain_latest_nonce > current_nonce:
          # Nonce đã bị chiếm dụng bởi một giao dịch khác
          record["status"] = "FAILED"
          record["error"] = f"nonce {current_nonce} consumed by another transaction; dropped/replaced"
          guard.release_spend(payer, reservation_id, reason="nonce_consumed_by_replacement")
          _save_swap_execution(record)
          raise SwapExecutionError(record["error"])
      else:
          # Outcome chưa xác định, giữ UNCERTAIN và BẢO LƯU reservation
          record["status"] = "UNCERTAIN"
          _save_swap_execution(record)
  ```

### 2.3. Hàng Rào Bảo Vệ Mô Hình Triển Khai (Single-Instance Topology Guard)
- File lock (`fcntl.flock`), in-memory reservations, và `swap_executions.json` là tài nguyên cục bộ trên 1 container.
- Cập nhật `enforce_single_instance_topology_guard()` chặn đứng vô điều kiện mọi cấu hình đa container:
  ```python
  def enforce_single_instance_topology_guard() -> None:
      multi_instance = os.getenv("QMA_MULTI_INSTANCE", "0").strip().lower() in ("1", "true", "yes")
      render_instances = int(os.getenv("RENDER_INSTANCE_COUNT", os.getenv("INSTANCE_COUNT", "1")))
      if multi_instance or render_instances > 1:
          raise RuntimeError(
              "DEPLOYMENT TOPOLOGY ERROR: QMA requires single-container deployment (instance_count=1). "
              f"Detected configuration: instances={render_instances}, multi_instance={multi_instance}. "
              "Local OS advisory locks (fcntl.flock), in-memory spend reservations, and local file ledgers "
              "do not span separate container filesystems. Multi-container deployment is strictly forbidden "
              "until distributed locking (Redlock) and centralized reservation storage are implemented."
          )
  ```

### 2.4. Ngắt Mạch Tự Động Khi Nonce Collision & Ghi Nhận Sự Cố P1
- Khi gặp `nonce too low` và on-chain nonce đã bị tiêu thụ bởi giao dịch ngoài luồng:
  1. Trạng thái chuyển sang `FAILED_NONCE_COLLISION`.
  2. Ghi sự cố `P1_CRITICAL` vào `incident_engine` liên kết Euthyna.
  3. Gọi `guard.trip_circuit_breaker(payer)` lập tức khóa tài khoản chi tiêu, chặn đứng mọi giao dịch tiếp theo bằng `CircuitBreakerTrippedError`.

### 2.5. Cơ Chế Dừng Khẩn Cấp Runtime Qua Cờ File (data/EMERGENCY_HALT)
- Tạo file cờ `data/EMERGENCY_HALT` lập tức có hiệu lực qua `is_treasury_halted()` trên mọi worker mà không cần khởi động lại tiến trình.
- Đấu nối chặn nhất quán 100% cả 8 luồng chi tiêu (`swap_executor`, `usyc_treasury`, `submit_withdraw`, `sessions_withdraw`, `stablefx_service`, `earn_kit`).

### 2.6. Kiểm Thử Phục Hồi Crash Bằng Subprocess Hệ Điều Hành Thật
- `test_real_subprocess_crash_recovery_rebroadcasts_raw_tx`: Khởi chạy subprocess Python thật, ghi `PREPARED`, kết thúc tiến trình, tiến trình cha phục hồi và phát lại đúng `raw_tx` bytes gốc.

---

## 3. Tổng Kết Số Liệu Kiểm Thử Sau Bản Vá V4

- **Backend Pytest**: **543 passed**, 0 failed, 16 warnings.
- **Transaction Lifecycle & Spend Guard Suite**: **22 passed**, 0 failed.
- **USYC Treasury & Emergency Halt Suite**: **24 passed**, 0 failed.
- **Frontend Bun/Vitest Tests**: **35 passed**, 142 assertions, 0 failed.
- **OpenAPI Documentation Gate**: **13 passed**, 0 failed.
- **Xung đột Dependency**: 0.
