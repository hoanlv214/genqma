# BUILD BRIEF: DỰ ÁN GENLAYER NHẮM ĐIỂM "UNICORN" (4–5)
**Phiên bản 2 — đã đồng bộ với `00-read-me.md` (studionet + Portal)**

═══════════════════════════════════════════════════════════

**MỤC TIÊU:** Xây một Intelligent Contract trên GenLayer đạt 4–5 ở cả 4 trục chấm của Builder Program. Mọi quyết định kiến trúc phải trả lời được câu hỏi: *"Việc này có làm tôi rớt xuống điểm 1 không?"* — nếu có, làm lại.

**Ràng buộc dự án đã chốt** (chi tiết ở §0 của `00-read-me.md`):
- **D1 — Mạng: studionet** (GenLayer Studio hosted). Không phải testnet.
- **D2 — Nộp bài: track Builders trên Portal.** Không phải DoraHacks.
- **D3 — Nondet API: `gl.eq_principle.*` mặc định, `gl.vm.run_nondet` khi cần validator tùy biến.**

---

## ⛔ RÀNG BUỘC SỐNG-CÒN (cổng loại — trượt là vứt cả dự án)

- Phần ra quyết định cốt lõi **PHẢI** chạy bằng Intelligent Contract thật trên GenLayer (`gl.nondet.exec_prompt` / `gl.nondet.web.render`), **không** phải gọi AI off-chain rồi ghi kết quả lên chuỗi.
- Code phải **build & chạy được end-to-end trên studionet** trước khi nộp — deploy thật, ký giao dịch thật, đọc state thật.
- **KHÔNG** được là bản sao của example. Bài toán phải là của riêng dự án.

> 📌 **Đã sửa so với bản v1:** bản cũ ghi "chạy end-to-end trên **testnet**". Nay đọc là **studionet** (D1). Trong README, video, và pitch tuyệt đối không viết "deployed to testnet" — viết đúng là "deployed to GenLayer studionet via GenLayer Studio". Nói sai mạng là một lỗi tính minh bạch, không đáng đánh đổi.

---

## TRỤC 1 — GENLAYER FIT (nhắm 5)
### *"Không có GenLayer thì dự án sập"*

**YÊU CẦU BUILD:**
- Chọn bài toán mà cốt lõi là một **PHÁN QUYẾT CHỦ QUAN** có tiền hoặc kết quả thật đặt cược, và **không một cá nhân nào nên tự quyết một mình**.
  *(Ví dụ: phân xử tranh chấp freelancer, duyệt claim bảo hiểm định tính, nghiệm thu nội dung marketing, chấm thưởng bounty đọc từ GitHub, kháng nghị demonetization.)*
- Phán quyết đó **PHẢI** phụ thuộc vào dữ liệu web đọc trực tiếp on-chain (`gl.nondet.web.render` / `web.get`) **+** suy luận LLM — thứ Solidity không thể làm.

**TEST LOẠI BỎ:** bỏ phần AI/web đi mà dự án vẫn dùng được như app thường → **thiết kế sai, làm lại**. Phần AI phải là **TRÁI TIM**, không phải gia vị.

**CHỐNG ANTI-PATTERN (rớt về 1):** AI chỉ sinh câu chữ vui / mô tả / lời chào mừng.

**Gợi ý chọn đề tài:** sáu track của hackathon Bradbury là chỉ dấu tốt nhất về loại bài toán GenLayer muốn thấy — *Agentic Economy Infrastructure, Subjective Consensus, AI Governance, Prediction Markets & P2P Betting, AI Gaming, Future of Work*. Bài toán nằm gọn trong một track sẽ dễ ăn điểm Trục 1.

---

## TRỤC 2 — CONTRACT QUALITY (nhắm 4–5)
### *"Validator kiểm NỘI DUNG, không kiểm hình dạng"*

**Đây là ranh giới quan trọng nhất giữa điểm 1 và điểm 4+.**

**YÊU CẦU BUILD:**
- **TUYỆT ĐỐI KHÔNG** để consensus chỉ là `strict_eq` trên format/JSON keys. Hai validator ra **phán quyết khác nhau** mà **cùng pass** = **điểm 1**.
- Validator phải kiểm **Ý NGHĨA THẬT** của phán quyết AI. Có ba đường hợp lệ:

  | Đường | Khi nào dùng | API |
  |---|---|---|
  | **A. Validator tùy biến** *(khuyến nghị cho dự án này)* | Nondet trả JSON có cả verdict lẫn lý do tự do | `gl.vm.run_nondet(leader_fn, validator_fn)` — `validator_fn` so **verdict**, bỏ qua khác biệt ở `reason` |
  | **B. So sánh bằng LLM** | Kết quả là văn bản mở cần "tương đương ý nghĩa" | `gl.eq_principle.prompt_comparative(fn, principle=...)` |
  | **C. Chấm tính chính trực** | Tác vụ chủ quan, validator không cần chạy lại | `gl.eq_principle.prompt_non_comparative(fn, task=..., criteria=...)` |

  `gl.eq_principle.strict_eq` **vẫn hợp lệ** — nhưng chỉ khi nondet block trả về **đúng một giá trị verdict xác định** (`bool`, hoặc chuỗi `"RELEASE"`/`"REFUND"`), tức bạn đã tự chắt lọc ý nghĩa ra trước khi giao cho consensus. Dùng `strict_eq` trên **cả cục JSON có trường `reason` tự do** là sai — hai validator gần như chắc chắn bất đồng vì câu chữ khác nhau, và bạn vừa tạo ra một contract không bao giờ đạt đồng thuận.

- **Xử lý edge-case rõ ràng.** Mỗi cái phải có nhánh xử lý riêng + `UserError`:
  - `web.render` fail / timeout
  - URL chết hoặc trả 404
  - LLM trả JSON hỏng (bọc ```` ```json ````, thiếu dấu ngoặc, thiếu key)
  - giá trị tiền = 0, hoặc vượt số dư
  - double-claim / gọi lại khi case đã đóng
  - `confidence` dưới ngưỡng → escalate thay vì quyết bừa

- **ĐỂ LÊN 5** — chọn một trong hai:
  - **nhiều contract phối hợp** (vd `Policy` + `Treasury` + `Reputation`, gọi chéo qua `gl.get_contract_at`), **hoặc**
  - **logic nondet nâng cao**: multi-source cross-check (đọc 2–3 URL độc lập rồi đối chiếu), hoặc escalation/appeal flow tự viết ở tầng contract.

**CHỐNG ANTI-PATTERN:** copy `WizardOfCoin` và đổi tên.

> 📌 **Đã sửa so với bản v1:** bản cũ viết "dùng `prompt_comparative` HOẶC tự viết `validator_fn`", trong khi file lỗi lại bắt buộc `run_nondet_unsafe` — nghe như hai lệnh trái nhau. Thực tế `eq_principle.*` chỉ là wrapper dựng sẵn trên `run_nondet`; cả hai cùng một họ. Xem §3.1 của `00-read-me.md`.

---

## TRỤC 3 — ENGINEERING (nhắm 4–5)
### *"Lịch sử công sức thật, dễ chạy"*

**YÊU CẦU BUILD:**
- **Commit thường xuyên, có ý nghĩa** — nhiều commit kể được câu chuyện phát triển. **KHÔNG** dồn một commit `"init"` duy nhất. Đây là thứ người chấm nhìn thấy đầu tiên và khó nguỵ tạo nhất.
- **Cấu trúc thư mục rõ:**
  ```
  contracts/       # .py Intelligent Contract
  frontend/        # app genlayer-js
  tests/           # gltest
  scripts/deploy/  # script deploy + địa chỉ contract
  README.md
  ```
- **README đầy đủ:** bài toán, kiến trúc, **cách deploy lên studionet từng bước**, cách chạy frontend, link live app + video, và **địa chỉ contract đã deploy**.
- Code tách hàm, đặt tên rõ, **có comment ở chỗ logic nondet phức tạp** — đặc biệt giải thích `validator_fn` đang so cái gì và **vì sao** so cái đó.
- **ĐIỂM CỘNG (đẩy lên 5): viết test cho contract** — happy path + edge-case, bằng `gltest`, chạy được với `gltest --network studionet` (hoặc `localnet` cho vòng lặp nhanh).

> 💡 Test nondet cần **cài mock LLM/web trước** khi chạy giao dịch, nếu không sẽ fail consensus và báo lỗi *state* gây hiểu nhầm. Xem **R17** trong `02-common-errors.md`.

---

## TRỤC 4 — FRONTEND / UX (nhắm 4–5)
### *"App thật, kết nối contract thật"*

**YÊU CẦU BUILD:**
- Frontend (dùng `genlayer-js`) phải **GỌI THẬT** lên contract đã deploy: ký giao dịch, đọc state, hiển thị kết quả phán quyết của AI on-chain.
- **Cấu hình mạng đúng (D1):**
  ```js
  import { createClient } from 'genlayer-js';
  import { studionet } from 'genlayer-js/chains';

  // ✅ MetaMask ký; không có secret nào trong bundle
  const client = createClient({ chain: studionet, account: userAddress });
  ```
- **Deploy live** (Vercel/Netlify) — có URL truy cập được.
- **Cover trọn luồng người dùng:** tạo → nộp → AI phân xử → thấy kết quả/giải ngân.
- **UX mượt:**
  - loading state trong lúc chờ consensus (giao dịch nondet chậm hơn hẳn giao dịch thường — phải nói cho người dùng biết đang chờ gì)
  - hiển thị **`reason`** mà AI trả về, không chỉ verdict — đây là điểm bán hàng của GenLayer, đừng giấu nó
  - hiện link tới transaction trên Explorer để người xem tự kiểm chứng

**CHỐNG ANTI-PATTERN (rớt về 1):** trang tĩnh giả vờ kết nối, hoặc hardcode kết quả mà không thực sự đọc từ contract → **bị loại thẳng ở cổng**.

> ⚠️ **Nhóm lỗi giết chết demo — đọc R21–R24 trong `02-common-errors.md` TRƯỚC khi quay video.** Tóm tắt: ví phải **được nạp GEN trước**, trên **đúng studionet**, rồi **người dùng ký bằng MetaMask**. Không burner account. Không private key trong `VITE_*`. Tự động `wallet_switchEthereumChain` khi connect.

---

## 📦 SẢN PHẨM BÀN GIAO KHI NỘP

1. **GitHub repo** — code + README + lịch sử commit thật
2. **Live app URL** — frontend kết nối contract đã deploy **trên studionet**
3. **Video demo ngắn** chạy trọn luồng (bao gồm cả cảnh chờ consensus và cảnh hiện `reason`)
4. **Một dòng pitch:** *"Vì sao dự án này CHẾT nếu không có GenLayer"*
5. **Địa chỉ contract** đã deploy + link transaction trên Explorer

**Nộp qua:** dashboard track **Builders** trên `portal.genlayer.foundation` (D2). Connect ví + GitHub vào Portal trước khi nộp, nếu không đóng góp sẽ không được ghi nhận. Kiểm tra trang quest trên Portal để lấy yêu cầu và deadline hiện hành — nội dung chỉ hiện sau khi đăng nhập.

---

## ✅ CHECKLIST TỰ CHẤM TRƯỚC KHI NỘP

**Cổng loại**
- [ ] Quyết định cốt lõi chạy bằng `gl.nondet.*` **trong** contract, không phải AI off-chain
- [ ] Contract đã deploy studionet, `Result: SUCCESS` (không chỉ `Status: FINALIZED`)
- [ ] Bài toán là của riêng dự án, không phải example đổi tên

**Trục 1**
- [ ] Bỏ AI/web đi thì dự án **hỏng**, không chỉ kém đi
- [ ] Có tiền hoặc kết quả thật đặt cược trên phán quyết
- [ ] Phán quyết cần dữ liệu web đọc on-chain

**Trục 2**
- [ ] Validator so **verdict**, không so schema
- [ ] Hai validator ra verdict khác nhau thì **không** pass được
- [ ] Có nhánh xử lý + `UserError` cho: web fail, URL chết, JSON hỏng, tiền = 0, double-claim
- [ ] Có multi-contract **hoặc** logic nondet nâng cao (để lên 5)

**Trục 3**
- [ ] Lịch sử commit kể được câu chuyện phát triển
- [ ] Thư mục `contracts/ frontend/ tests/ scripts/`
- [ ] README có: bài toán, kiến trúc, deploy studionet từng bước, chạy frontend, live URL, video, địa chỉ contract
- [ ] Có test happy path + edge-case chạy được

**Trục 4**
- [ ] Frontend ký giao dịch thật và đọc state thật
- [ ] `chain: studionet`, không hardcode kết quả
- [ ] Live URL truy cập được
- [ ] Có loading state khi chờ consensus + hiển thị `reason`
- [ ] Ví demo đã được nạp GEN trên studionet trước khi quay video

---

*Đồng bộ với `00-read-me.md` v2 và `02-common-errors.md` v2 — 26/07/2026.*
