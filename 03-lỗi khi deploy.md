# GenLayer Smart Contract — Common Errors & Rules

Tài liệu này liệt kê các lỗi phổ biến khi viết/sửa GenLayer Intelligent Contract.
**AI assistants (Claude, Cursor, Antigravity, ...) phải đọc file này TRƯỚC khi chỉnh sửa bất kỳ file nào trong thư mục `contracts/`.**

---

## 🔴 Lỗi 1: "Could not load contract schema" trên GenLayer Studio

### Nguyên nhân gốc
GenLayer Studio **KHÔNG THỂ** parse contract nếu thiếu hoặc sai bất kỳ điều kiện nào sau đây.

### Quy tắc bắt buộc

#### 1.1 — Dòng đầu tiên PHẢI là magic comment `Depends`
```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
```
- Đây là dòng **đầu tiên tuyệt đối** (line 1) của file `.py`.
- Tương đương `pragma solidity` trong Solidity — cho Studio biết dùng GenVM runtime version nào.
- **KHÔNG ĐƯỢC xóa, di chuyển, hoặc thêm dòng trống phía trên.**
- Hash `1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6` là version cố định, KHÔNG tự đặt.

❌ Sai:
```python
from genlayer import *   # ← thiếu dòng Depends → Studio báo lỗi đỏ
```

✅ Đúng:
```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
```

#### 1.2 — Kiểu dữ liệu bị cấm trong state variables
Các kiểu sau **KHÔNG ĐƯỢC** dùng cho persistent fields (class-level annotations):

| ❌ Cấm        | ✅ Thay bằng              |
|---------------|--------------------------|
| `int`         | `u256`, `i256`, `bigint` |
| `list[T]`     | `DynArray[T]`            |
| `dict[K, V]`  | `TreeMap[K, V]`          |
| `float`       | Không hỗ trợ — dùng `u256` với scale factor |

#### 1.3 — Import bị cấm ở top-level
Các module sau bị cấm import ở cấp module: `os`, `sys`, `subprocess`, v.v.  
Các module khác như `hashlib`, `datetime` nên import **bên trong method** để tránh lỗi sandbox:

❌ Sai:
```python
# { "Depends": "py-genlayer:..." }
from genlayer import *
import hashlib          # ← có thể gây lỗi schema trên Studio
```

✅ Đúng:
```python
# { "Depends": "py-genlayer:..." }
from genlayer import *
import json             # json luôn OK

class Contract(gl.Contract):
    ...
    def my_method(self):
        import hashlib  # ← import bên trong method
        h = hashlib.sha256(b"data").hexdigest()
```

#### 1.4 — `@gl.contract_interface` vs `@gl.evm.contract_interface`
- Dùng `@gl.contract_interface` cho giao tiếp **IC ↔ IC** (Intelligent Contract gọi Intelligent Contract).
- Dùng `@gl.evm.contract_interface` cho giao tiếp **IC ↔ EVM** (gọi Solidity contract).
- **Lưu ý:** `@gl.evm.contract_interface` **KHÔNG hoạt động trên Studio** (chỉ hoạt động trên live network).

#### 1.5 — Positional-only parameter (`/`) bị cấm trong interface
```python
# ❌ Sai — GenVM không hỗ trợ positional-only
def get_balance(self, user: Address, /) -> u256: ...

# ✅ Đúng
def get_balance(self, user: Address) -> u256: ...
```

---

## 🔴 Lỗi 2: Test thất bại — `AttributeError: 'str' object has no attribute 'as_bytes'`

### Nguyên nhân
Truyền string `"0x1111..."` cho tham số kiểu `Address` trong test. Hàm `set_dependencies` nhận `Address`, không nhận `str`.

### Cách sửa
```python
# ❌ Sai
core.set_dependencies("0x3333...", "0x4444...")

# ✅ Đúng
from genlayer import Address
core.set_dependencies(Address("0x3333..."), Address("0x4444..."))
```

**Lưu ý:** `from genlayer import Address` phải import **sau khi** `direct_deploy()` đã chạy (vì `genlayer` chỉ available sau khi gltest setup SDK paths). Import bên trong test function, sau dòng `direct_deploy(...)`.

---

## 🔴 Lỗi 3: `only one contract is allowed` khi chạy tests

### Nguyên nhân
GenVM chỉ cho phép **1 class Contract** per module. Khi test deploy nhiều contract files liên tiếp, registry global `__known_contract__` chưa được reset.

### Cách sửa
Gọi `clear_known_contracts()` **trước mỗi** `direct_deploy(...)`:
```python
def clear_known_contracts():
    for name, module in list(sys.modules.items()):
        if "genlayer" in name and hasattr(module, "__known_contract__"):
            setattr(module, "__known_contract__", None)
```

---

## 🟡 Lưu ý chung cho AI assistants

1. **KHÔNG BAO GIỜ xóa dòng `# { "Depends": ... }`** — đó là pragma version.
2. **KHÔNG thay đổi hash** trong dòng Depends trừ khi có chỉ thị rõ ràng từ người dùng.
3. Khi thêm import mới, **đặt bên trong method**, không phải top-level (trừ `json`).
4. Kiểm tra `pytest tests/` sau mỗi thay đổi contract.
5. State variables chỉ dùng: `str`, `bytes`, `bool`, `Address`, `u256`/`i256`/sized ints, `TreeMap[K,V]`, `DynArray[T]`.
6. Luôn giữ class tên `Contract` kế thừa `gl.Contract`.
