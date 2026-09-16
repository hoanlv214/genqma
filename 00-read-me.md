# GenLayer & Chương Trình Builder — Tài Liệu Context cho AI
**Phiên bản 2 — đã fix conflict, verified 2026-07-26**

> **Mục đích:** Tài liệu mồi ngữ cảnh (context-priming). AI đọc xong phải hiểu: (1) GenLayer là gì, (2) Intelligent Contract viết & chạy ra sao, (3) chương trình Builder vận hành thế nào, (4) quy trình deploy + nộp bài.
>
> **Thứ tự đọc 3 file:** `00-read-me.md` (file này) → `01-how-to-score.md` (tiêu chí chấm) → `02-common-errors.md` (bẫy kỹ thuật).

---

## 0. QUYẾT ĐỊNH ĐÃ CHỐT CỦA DỰ ÁN (đọc trước tiên — override mọi chỗ khác)

Ba quyết định này là **nguồn chân lý duy nhất**. Nếu bất kỳ đoạn nào phía dưới hoặc trong 2 file kia có vẻ mâu thuẫn, quyết định ở đây thắng.

| # | Hạng mục | Đã chốt | Hệ quả bắt buộc |
|---|---|---|---|
| **D1** | **Mạng triển khai** | **studionet** (GenLayer Studio hosted, `https://studio.genlayer.com`) | Contract deploy trên studionet. Frontend `createClient({ chain: studionet })`. Ví nạp GEN từ panel **Accounts** của Studio. **KHÔNG** dùng testnet faucet. **KHÔNG** nhắc "deploy lên testnet" ở bất kỳ đâu (README, video, pitch). |
| **D2** | **Kênh nộp bài** | **GenLayer Portal — track Builders** (`portal.genlayer.foundation`) | Nộp qua Portal dashboard: repo GitHub + live URL + video. **KHÔNG** đi đường DoraHacks (hackathon Bradbury đã đóng 10/04/2026). Cần connect ví + GitHub + Discord/X vào Portal trước. |
| **D3** | **API non-deterministic** | **`gl.eq_principle.*` là mặc định; `gl.vm.run_nondet(...)` khi cần validator tùy biến** | Không dùng `gl.vm.run_nondet_unsafe` trừ khi có lý do rõ ràng (xem §3.3). Đây là lời giải cho mâu thuẫn "Rule #7 vs prompt_comparative" trong bản cũ. |

**Ghi chú D1:** studionet và testnet (Asimov/Bradbury) là **hai mạng khác nhau, không thông nhau**. Contract deploy ở studionet chỉ tồn tại ở studionet. Nếu sau này muốn đổi sang testnet thì phải deploy lại và đổi `VITE_CONTRACT_ADDRESS`. Chọn một mạng và giữ nguyên: contract, frontend chain, số dư ví, nguồn faucet — tất cả cùng một mạng.

---

## 1. GenLayer là gì

GenLayer là blockchain Layer-1 (trên hạ tầng ZKsync Elastic Network), tự định vị là **"lớp phân xử (adjudication layer) cho nền kinh tế agentic"** — một **"synthetic jurisdiction"**, tòa án phi tập trung trên chuỗi.

Định vị lịch sử:
- **Bitcoin** → tiền tệ không cần tin cậy
- **Ethereum** → tính toán không cần tin cậy
- **GenLayer** → **phán quyết / ra quyết định không cần tin cậy**

Khác biệt cốt lõi: GenLayer tích hợp **AI ngay tại tầng đồng thuận**. Mỗi validator chạy một LLM (đa dạng model), mạng validator hoạt động như **bồi thẩm đoàn AI phi tập trung** — bỏ phiếu và hội tụ về một kết quả chung, kể cả với quyết định **chủ quan**.

Ba năng lực smart contract truyền thống không có:
1. **Quyết định chủ quan** — đánh giá ngữ cảnh, sắc thái, phán đoán.
2. **Dữ liệu phi cấu trúc** — văn bản, hình ảnh, bằng chứng định tính.
3. **Truy cập Internet trực tiếp** — fetch web ngay trên chuỗi, **không cần oracle**.

### Use case tiêu biểu
Escrow tự động cho AI agent; phân xử tranh chấp marketplace; prediction market tự kết toán bằng cách fetch kết quả từ nguồn gốc; DAO quản trị bằng AI; sàng lọc tuân thủ (KYC/AML/sanctions); giải quyết tranh chấp thay thế (ADR); hợp đồng có điều khoản mơ hồ ("hợp lý", "bất khả kháng").

### Bối cảnh 2026 (để pitch cho đúng thời điểm)
- Roadmap công bố: Asimov (2025) → **Bradbury (03/2026, đang chạy)** → Clarke (Q3/2026) → Mainnet (Q4/2026).
- GenLayer dẫn dắt một consortium ~27 công ty xây "Internet Court protocol" — giải quyết tranh chấp giữa các AI agent giao dịch on-chain.
- Hệ sinh thái: 200+ builder trên testnet, cộng đồng ~86K. Đã gọi $7.5M seed (2024). **Chưa** công bố token/airdrop chính thức.

---

## 2. Các khái niệm cốt lõi

### Intelligent Contract
Smart contract của GenLayer:
- **Viết bằng Python** (không phải Solidity).
- Thực thi được tác vụ **non-deterministic** — gọi LLM, đọc web.
- Nhất quán nhờ **đồng thuận AI**, không nhờ kết quả giống hệt nhau.

### Optimistic Democracy (cơ chế đồng thuận)
Với giao dịch có phần non-deterministic:
- Một validator làm **leader** đề xuất kết quả.
- Các validator khác **validate** bằng LLM của riêng mình rồi bỏ phiếu đồng ý / không đồng ý.
- Có **appeal** nhiều vòng, **finality**, **staking**, **slashing**.
- Thưởng/phạt theo việc validator thuộc phe đa số hay thiểu số → tạo động lực kiểm tra thật thay vì "ăn theo leader".

### Non-deterministic block — 2 giới hạn phải nhớ
Mọi thao tác không xác định **phải** nằm trong một hàm Python **không tham số**, và hàm đó được gọi qua `gl.eq_principle.*` hoặc `gl.vm.run_nondet*`. Bên trong block:
- **Không truy cập được storage** của contract.
- **Trạng thái interpreter không mang ngược về** code deterministic (đổi biến global sẽ không thấy).

Biến bên ngoài được **capture tự động** (closure), không cần truyền tham số.

### GenVM
Máy ảo (wasm-based) chạy Intelligent Contract.

### Greyboxing (đặc trưng Bradbury)
Validator được phép biến đổi input/ngữ cảnh **trước mỗi lần gọi LLM** (bắt, phân tích, sửa, lọc). Phục vụ tối ưu hiệu năng, chi phí, bảo mật. Gắn với "Constitution" — khung quản trị tương lai.

---

## 3. Equivalence Principle & API non-deterministic (mục quan trọng nhất)

### 3.1 Phân tầng API — nhớ đúng quan hệ này
`gl.eq_principle.*` **không đối lập** với `gl.vm.run_nondet*`. Ba hàm `eq_principle` chỉ là **wrapper dựng sẵn trên `run_nondet`** — chúng tự sinh `validator_fn` cho bạn. Đó là lý do bản tài liệu cũ bị mâu thuẫn: hai thứ vốn cùng một họ.

```
gl.vm.run_nondet_unsafe(leader_fn, validator_fn)   ← nền tảng thấp nhất, KHÔNG sandbox lỗi validator
        ▲
gl.vm.run_nondet(leader_fn, validator_fn)          ← KHUYẾN NGHỊ khi tự viết validator (có sandbox)
        ▲
gl.eq_principle.strict_eq(fn)                      ← wrapper: validator_fn = (my_res == leader_res)
gl.eq_principle.prompt_comparative(fn, principle)  ← wrapper: validator tự chạy fn rồi so sánh 2 kết quả bằng LLM theo `principle`
gl.eq_principle.prompt_non_comparative(fn, task=, criteria=)  ← wrapper: validator CHẤM kết quả leader theo `criteria`, không tự chạy lại
```

### 3.2 Chọn cái nào — bảng quyết định

| Kết quả trả về của nondet block | Dùng | Vì sao |
|---|---|---|
| `bool`, số, chuỗi ngắn xác định (vd `"RELEASE"` / `"REFUND"`) | `gl.eq_principle.strict_eq` | Validator chỉ cần khớp chính xác; không tốn thêm inference |
| JSON chứa cả verdict + lý do tự do (`{"verdict": ..., "reason": "..."}`) | `gl.vm.run_nondet` + `validator_fn` tự viết | So khớp **verdict**, bỏ qua khác biệt câu chữ ở `reason` — đây là cách ăn điểm cao nhất ở Trục 2 |
| Văn bản mở, cần "tương đương về ý nghĩa" | `gl.eq_principle.prompt_comparative(fn, principle=...)` | LLM validator đánh giá 2 kết quả có tương đương theo nguyên tắc bạn đặt |
| Tác vụ chủ quan, chỉ cần kiểm tính chính trực của leader | `gl.eq_principle.prompt_non_comparative(fn, task=..., criteria=...)` | Validator không chạy lại, chỉ chấm kết quả leader theo tiêu chí |

### 3.3 `run_nondet` vs `run_nondet_unsafe` (chốt theo D3)
Docs SDK chính thức nói rõ: `run_nondet` là **API được khuyến nghị** cho non-deterministic tùy biến — nó chạy `validator_fn` trong **sandbox** và xử lý lỗi validator bằng các hàm so sánh mặc định (`compare_user_errors`, `compare_vm_errors`). `run_nondet_unsafe` **không** có sandbox: validator ném exception sẽ bị quy thành `Disagree` y như trả về `False`, làm bạn mất khả năng phân biệt "bất đồng thật" với "code validator bị bug".

> **Luật của dự án:** mặc định dùng `gl.vm.run_nondet`. Chỉ dùng `run_nondet_unsafe` khi bạn cố ý muốn hành vi thô đó và ghi chú lý do trong comment.
>
> ⚠️ Docs của GenLayer có ví dụ dùng `run_nondet_unsafe`, và các build Studio cũ có thể chỉ expose hàm này. Nếu `gl.vm.run_nondet` báo `AttributeError` trên Studio đang dùng → fallback sang `run_nondet_unsafe` **và ghi chú vào README** rằng đó là giới hạn runtime, không phải lựa chọn thiết kế.

### 3.4 Khuôn mẫu chuẩn — validator kiểm Ý NGHĨA (dùng khuôn này)

```python
@gl.public.write
def adjudicate(self, case_id: str) -> None:
    url = self.cases[case_id].evidence_url   # đọc storage TRƯỚC, ngoài block nondet

    def leader_fn():
        # đọc web + suy luận LLM, cả hai đều nằm TRONG block
        evidence = gl.nondet.web.render(url, mode="text")
        prompt = f"""...{evidence}...
        Trả lời DUY NHẤT JSON: {{"verdict": "RELEASE"|"REFUND", "confidence": 0-100, "reason": str}}"""
        return gl.nondet.exec_prompt(prompt, response_format="json")

    def validator_fn(leader_res) -> bool:
        if not isinstance(leader_res, gl.vm.Return):
            return False                      # leader lỗi/rollback → không đồng ý
        leader = leader_res.calldata
        mine = leader_fn()                    # validator tự chạy lại
        # ✅ Chỉ so VERDICT — phần ý nghĩa thật. Bỏ qua khác biệt câu chữ ở `reason`.
        return mine["verdict"] == leader["verdict"]

    result = gl.vm.run_nondet(leader_fn, validator_fn)
    self._settle(case_id, result["verdict"], result.get("reason", ""))
```

**Vì sao khuôn này ăn điểm:** hai validator viết `reason` khác nhau vẫn pass, nhưng hai validator ra **verdict khác nhau thì KHÔNG pass**. Đó chính là ranh giới giữa điểm 1 và điểm 4+ ở Trục 2 (xem `01-how-to-score.md`).

---

## 4. Ví dụ Intelligent Contract tối thiểu (theo docs chính thức)

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

class Contract(gl.Contract):
    had_iana: bool

    def __init__(self):
        example_web_address = 'https://example.org'

        def my_non_deterministic_block():
            web_data = gl.nondet.web.render(example_web_address, mode='html')
            return 'iana' in web_data

        self.had_iana = gl.eq_principle.strict_eq(my_non_deterministic_block)
```

Điểm cần chú ý:
1. **Bắt buộc** gọi `gl.nondet.web.render` / `gl.nondet.web.get` / `gl.nondet.exec_prompt` từ trong hàm được invoke qua `gl.eq_principle.*` hoặc `gl.vm.run_nondet*`, nếu không sẽ lỗi.
2. State khai báo là **class attribute**; gán `self.x = ...` bên ngoài class body sẽ **không** persist.
3. Biến ngoài (`example_web_address`) capture tự động.
4. Lấy `mode='html'` vì cần text trong thẻ `<a>` (bản `mode='text'` rút gọn sẽ mất).
5. `strict_eq` vì trả `bool`.

> ⚠️ Trước khi copy đoạn trên vào Studio, đọc **Rule #1** trong `02-common-errors.md` về dòng version pragma ở đầu file. Studio có thể yêu cầu thêm một dòng trước dòng `Depends`.

---

## 5. Bộ công cụ phát triển

| Công cụ | Vai trò | Link |
|---|---|---|
| **GenLayer Studio** | IDE trên trình duyệt: viết, test, deploy. Điểm khởi đầu chính — **đây là môi trường dự án này dùng (D1)** | https://studio.genlayer.com/contracts |
| **GenLayer CLI** | Deploy & quản lý contract từ dòng lệnh; account, network, staking, localnet | docs.genlayer.com/api-references/genlayer-cli |
| **GenLayerJS** (`genlayer-js`) | Thư viện TS/JS cho frontend đọc-ghi contract. Dựa trên Viem | docs.genlayer.com/api-references/genlayer-js |
| **GenLayerPY** | SDK Python tương đương | docs.genlayer.com/api-references/genlayer-py |
| **gltest** (`genlayer-test`) | Test suite pytest cho contract. Hỗ trợ `--network studionet` | https://pypi.org/project/genlayer-test/ |
| **SDK API reference đầy đủ** | File text 1 khối, tối ưu cho AI đọc | https://sdk.genlayer.com/main/_static/ai/api.txt |
| **Docs đầy đủ 1 file** | Toàn bộ docs cho AI | https://docs.genlayer.com/full-documentation.txt |
| **GenLayer Explorer** | Trình duyệt block/transaction | https://genlayer-explorer.vercel.app |

### Kiến trúc dApp của dự án (theo D1)
```
Frontend (Vite/React, deploy Vercel)
   └─ genlayer-js: createClient({ chain: studionet, account: <địa chỉ ví MetaMask> })
        └─ Intelligent Contract đã deploy trên studionet
             ├─ gl.nondet.web.render(...)   ← đọc web trực tiếp, không oracle
             ├─ gl.nondet.exec_prompt(...)  ← suy luận LLM
             └─ gl.vm.run_nondet(leader_fn, validator_fn)  ← đồng thuận theo Ý NGHĨA
                  └─ ghi state on-chain → frontend đọc lại qua genlayer-js
```

**Quy tắc ví (rất hay sai, xem R21–R24 trong `02-common-errors.md`):** ví phải **được nạp GEN trước**, trên **đúng studionet**, rồi **người dùng ký bằng MetaMask**. Không tạo burner account trong trình duyệt. Không nhét private key vào biến môi trường `VITE_*`.

---

## 6. Các giai đoạn Testnet (bối cảnh — dự án KHÔNG deploy lên đây, xem D1)

### Testnet Asimov (giai đoạn 1 — 06/2025)
Đặt nền móng mạng lưới, onboard validator, stress-test Optimistic Democracy. GenLayer cấp LLM access trợ giá. Môi trường khá thụ động.

### Testnet Bradbury (giai đoạn 2 — 03/2026, đang chạy)
- Chuyển sang **chủ động & tham gia sâu**: Partners, Validators, Builders, Researchers.
- **LLM inference thật**: validator tự chọn & fine-tune LLM; cấu hình model là yếu tố trung tâm.
- Hướng thử nghiệm: **greyboxing**, **model routing**, đa dạng model, adversarial testing, mô phỏng appeal nhiều vòng.
- **Bradbury Gym:** môi trường benchmark định kỳ, dự kiến tích hợp hệ thống điểm.
- Thử nghiệm kinh tế: giả thuyết trả gas cho validator gấp 60–100× chi phí inference/giao dịch để "ăn theo leader" không có lợi.

Sau Bradbury là **Clarke** (Q3/2026, autonomous network operations) rồi **Mainnet** (Q4/2026).

---

## 7. Chương trình Builder / Contributor

GenLayer Foundation vận hành **Points Program** khuyến khích đóng góp giai đoạn testnet — đây chính là "chương trình Builder".

- **Cổng chính:** `https://portal.genlayer.foundation/` (trước đây `points.genlayer.foundation`).
- Bản chất: theo dõi đóng góp minh bạch, **leaderboard công khai**, mỗi hành động = **points + badges**. Hướng tới các chương trình tự trị của GLF, sẽ dần thuộc về **Deepthought DAO**.
- Mã nguồn công khai: `github.com/genlayer-foundation/points` (Django backend + Svelte frontend; có module riêng cho `builders`, `validators`, `contributions`, `leaderboard`, `stewards`).

### Ba track đóng góp
1. **Builders** — deploy contract, xây dApp, nộp dự án. ***(Track của dự án này — D2.)***
2. **Validators** — vào waitlist, vận hành AI node, quest validator.
3. **Community** — viết content, tổ chức/tham gia sự kiện, làm tool, tutorial.

### Điểm & phần thưởng (tham khảo, có thể thay đổi)
- Deploy contract loại prediction market: tới ~4000 điểm.
- Viết tutorial: tới ~600 điểm.
- Mỗi quest có **hạn ngạch điểm giới hạn** → làm sớm được nhiều hơn. Kiểm tra Portal hàng tuần vì quest mới được thêm liên tục.
- **Referral:** ~10% tổng điểm của builder mình refer, cộng dồn.

### Trạng thái hackathon (cập nhật 26/07/2026)
Hackathon **Testnet Bradbury** trên DoraHacks đã **kết thúc** (nộp bài 20/03 → 10/04/2026, giải thưởng Builder Points + $5.000, 92 BUIDL / 280 hacker). Các track khi đó: Agentic Economy Infrastructure, Subjective Consensus, AI Governance, Prediction Markets & P2P Betting, AI Gaming, Future of Work — **vẫn là chỉ dấu tốt về loại bài toán GenLayer muốn thấy**.

→ Hiện tại nộp bài qua **quest/dashboard track Builders trên Portal** (D2), không qua DoraHacks. Nội dung quest chỉ hiện sau khi connect ví — phải đăng nhập Portal để xem yêu cầu và deadline hiện hành.

### Lợi ích
- Leaderboard & ghi nhận công khai; top contributor được vinh danh khi mainnet launch.
- Early access: grant funding, nâng cấp hỗ trợ LLM, suất validator tương lai.
- **Mainnet incentive tiềm năng.** ⚠️ GenLayer **chưa** xác nhận token hay airdrop; mọi suy đoán airdrop chỉ dựa trên points program đang chạy.

### GenLayer Grant Program
Song song points program, tài trợ theo **milestone**, chia tier nhỏ/vừa/lớn theo độ phức tạp. Nộp qua form chính thức tại `genlayer.foundation/grants` (cần summary, technical plan, milestones, funding needs).

---

## 8. Quy trình thực tế cho dự án này (đã chốt theo D1 + D2)

1. **Lập & hoàn thiện profile trên Portal.** Connect ví + GitHub + Discord + X. Không connect đủ thì đóng góp không được ghi nhận và một số mission bị khoá.
2. **Star repo GitHub của GenLayer** (sau khi connect GitHub) — điểm khởi đầu nhanh nhất, không rào cản kỹ thuật.
3. **Chuẩn bị ví trên studionet.** Thêm mạng GenLayer Studio vào MetaMask; nạp GEN cho ví của mình từ panel **Accounts** trong Studio (chuyển từ account đã có sẵn số dư). **Không dùng testnet faucet** — nó nạp cho testnet, không phải studionet (D1).
4. **Phát triển contract.** Viết Intelligent Contract Python trong Studio (hoặc local + CLI, test bằng `gltest --network studionet`). Tham khảo ví dụ: Storage, LLM Hello World, Wizard of Coin, Fetch Web Content, Fetch GitHub Profile, Football Prediction Market, Vector Store Log Indexer — **để học pattern, KHÔNG copy đổi tên** (xem Trục 1 & 2 trong `01-how-to-score.md`).
5. **Deploy & xác nhận on-chain.** Trong panel Run & Debug, deploy và **bấm vào transaction để kiểm tra `Result: SUCCESS`** — `Status: FINALIZED` một mình chưa đủ (xem `02-common-errors.md`).
6. **Xây dApp frontend** bằng genlayer-js, deploy Vercel/Netlify, lấy URL công khai.
7. **Quay lại Portal**, làm quest track Builders và **nộp dự án qua dashboard**: link repo + live URL + video demo.
8. **Nhận points + badge**, theo dõi leaderboard.

---

## 9. Liên kết tham chiếu chính thức

| Mục | URL |
|---|---|
| Website | https://www.genlayer.com/ |
| Cách hoạt động | https://www.genlayer.com/how-it-works |
| Documentation | https://docs.genlayer.com/ |
| **Toàn bộ docs (1 file, cho AI)** | https://docs.genlayer.com/full-documentation.txt |
| **SDK API reference (1 file, cho AI)** | https://sdk.genlayer.com/main/_static/ai/api.txt |
| SDK API (bản duyệt web) | https://sdk.genlayer.com/main/api/genlayer.html |
| Your First Intelligent Contract | https://docs.genlayer.com/developers/intelligent-contracts/first-intelligent-contract |
| Storage / kiểu dữ liệu persist | https://docs.genlayer.com/developers/intelligent-contracts/storage |
| GenLayer Studio | https://studio.genlayer.com/contracts |
| **Portal (Builder/Contributions)** | https://portal.genlayer.foundation/#/builders/contributions |
| Points program mã nguồn | https://github.com/genlayer-foundation/points |
| GitHub tổ chức | https://github.com/genlayerlabs |
| Grants | https://genlayer.foundation/grants |
| Trang Testnet | https://www.genlayer.com/testnet |
| Whitepaper | https://www.genlayer.com/whitepaper |
| Discord | https://discord.gg/8Jm4v89VAu |
| Telegram | https://t.me/genlayer |

---

## 10. Tóm tắt một dòng (cho AI ghi nhớ nhanh)

> GenLayer là blockchain Layer-1 đặt AI tại tầng đồng thuận: validator chạy LLM đa dạng đồng thuận theo "Optimistic Democracy" trên cả quyết định chủ quan, cho phép "Intelligent Contract" viết bằng Python thực thi tác vụ non-deterministic (gọi LLM, đọc web không cần oracle) — mọi block nondet phải đi qua `gl.eq_principle.*` hoặc `gl.vm.run_nondet`. Chương trình Builder chạy qua Portal theo cơ chế Points + leaderboard, ba track Builders/Validators/Community. **Dự án này: deploy trên studionet qua GenLayer Studio, nộp bài qua track Builders trên Portal.**

---

## 11. Nhật ký sửa lỗi so với bản v1

| Chỗ sai ở bản v1 | Đã sửa thành |
|---|---|
| "Build dự án sẽ chạy trên Studio cho tất cả" nhưng file rubric lại đòi testnet | Chốt **studionet** ở D1, xoá mọi yêu cầu testnet |
| Chỉ liệt kê `strict_eq` và "các phương thức `gl.eq_principle.*` khác" | Liệt kê đủ 3 hàm + quan hệ với `run_nondet` (§3.1) + bảng chọn (§3.2) |
| Không nói `run_nondet` vs `run_nondet_unsafe` khác gì | §3.3: `run_nondet` là API khuyến nghị (có sandbox); `unsafe` chỉ khi cần |
| Ví dụ minimal thiếu cảnh báo version pragma | Thêm trỏ chéo sang Rule #1 |
| Ngụ ý nộp bài qua hackathon DoraHacks | Hackathon đã đóng 10/04/2026 → nộp qua Portal (D2) |
| Thiếu roadmap sau Bradbury | Thêm Clarke Q3/2026 → Mainnet Q4/2026 |
| Thiếu link `sdk.genlayer.com/main/_static/ai/api.txt` (bản API cho AI) | Đã thêm vào §5 và §9 |

---

*Biên soạn từ nguồn chính thức GenLayer (genlayer.com, docs.genlayer.com, sdk.genlayer.com, portal.genlayer.foundation, github.com/genlayerlabs) — verified 26/07/2026. GenLayer đang trong giai đoạn testnet: điểm số, deadline, và chính sách token/airdrop có thể thay đổi. Luôn kiểm chứng tại nguồn chính thức trước khi hành động.*
