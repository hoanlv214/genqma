# AGENT TANK HACKATHON — TÀI LIỆU NGỮ CẢNH CHO AI
**GenLayer · Season 1 · 03 – 17 September 2026**
**Phiên bản 1 — biên soạn 15/09/2026, tham chiếu chéo với `00-read-me.md`, `01-how-to-score.md`, `02-common-errors.md`, `03-lỗi khi deploy.md`**

> **Mục đích của file này:** mồi ngữ cảnh cho AI khác. Sau khi đọc xong, AI phải hiểu:
> (1) Agent Tank Hackathon là gì, khác gì các hackathon GenLayer trước đó,
> (2) Deadline, luật chơi, cách chấm,
> (3) 6 tracks + các "prompts" (ideas we want built) + các dự án live đã có trong ecosystem để không đụng hàng,
> (4) Ràng buộc hạ tầng đã chốt cho hackathon này (studio-next, chain 61997) — **khác** với studionet mặc định trong `00-read-me.md`,
> (5) Một danh sách ý tưởng bao quát để builder pick trong 2 tuần.
>
> **Nguồn:** `portal.genlayer.foundation/agent-tank`, thông báo tuần 1 của BTC ("cấu hình deploy hackathon"), tweet chính thức từ `@GenLayer`, và các ảnh chụp trang hackathon do user cung cấp.

---

## 0. QUYẾT ĐỊNH ĐÃ CHỐT CHO HACKATHON NÀY (đọc trước tiên — override `00-read-me.md`)

Ba mục dưới đây **override** mặc định của dự án builder thông thường. Nếu bất kỳ file nào khác nói khác, mục này thắng **chỉ trong phạm vi Agent Tank Hackathon**.

| # | Hạng mục | Đã chốt | Hệ quả bắt buộc |
|---|---|---|---|
| **H1** | **Mạng deploy** | **Studio Next** (không phải studionet cũ) | RPC `https://studio-next.genlayer.com/api`, Chain ID `61997`, Explorer `https://explorer-studio-dev.genlayer.com/`. Contract deploy trên Studio Next mới được xét. Bao gồm cả **fees** (feature mới của consensus v0.6). |
| **H2** | **Boilerplate** | `genlayerlabs/genlayer-project-boilerplate` **branch `v2-dev`** | Đã tích hợp Transaction Kit RC2. Với project cũ: cài `@genlayer/transaction-kit@0.1.0-rc.2` + adapter React/Vue cùng version, `genlayer-js@2.0.0-rc.1`. Đây là prerelease — build/test/CI xanh nhưng vẫn là RC. |
| **H3** | **Kênh nộp bài** | **Portal → Agent Tank track** (không phải Project Explorer thường) | Nộp qua form Agent Tank trên `portal.genlayer.foundation/agent-tank/`. **1 project / 1 account**, editable đến khi submissions close. Accepted builds được publish sang Project Explorer như một bonus, nhưng review đó là stage riêng. |

**Ghi chú H1 — Studio Next vs studionet:** đây là hai mạng khác nhau. `00-read-me.md` ghi mặc định dự án dùng studionet (chain 61999, RPC `studio.genlayer.com/api`). Hackathon **buộc** dùng Studio Next (chain **61997**, RPC `studio-next.genlayer.com/api`) vì phiên bản consensus mới có fees. Nếu redeploy từ studionet → Studio Next: phải cập nhật `VITE_CONTRACT_ADDRESS`, cấu hình chain trong frontend, và hướng dẫn nạp GEN. Migration notes: `https://docs.genlayer.com/developers/consensus-v06-migration#test-on-studio-dev-first`.

**Ghi chú H3 — hai lớp review:**
1. **Portal reviewers** (trong build period, 03–17/09): có thể trả "Action needed" → sửa và respond lại. Nộp sớm để có thời gian xử lý.
2. **Judging team** (sau 17/09, kết quả 25/09): duyệt shortlist top 20+ dựa trên community ratings + comments.

---

## 1. AGENT TANK LÀ GÌ

**Agent Tank Hackathon** là hackathon flagship của GenLayer trong Season 1, mở cho **mọi người** đang build cho *Agentic Economy*. Format ẩn dụ "Shark Tank" nhưng cho các AI agent — nộp bài như pitch cho một hội đồng, cộng đồng cũng rate/comment công khai trong khi tank đang mở.

### 1.1 Bối cảnh lịch sử — Agent Tank khác gì các hackathon GenLayer trước đó

| Hackathon | Thời điểm | Prize pool | Đặc trưng |
|---|---|---|---|
| Aleph / Crecimiento (Argentina) | 11/2025 | $500 + mentorship | Onsite 2 ngày, 5 tracks. Warm-up. |
| Bradbury Builders Hackathon | 20/03 – 10/04/2026 | $5K+ + Builder Points + **10–20% dev fees forever** | 2 tuần online, 6 AI-native tracks. Winner: TreasuryPilot ($650), AutoBounty ($400). |
| **Agent Tank** | **03 – 17/09/2026** | **5% of ALL Season 1 GenLayer Points** | **2 tuần online, 6 tracks, deploy trên Studio Next có fees.** |

Điểm bán hàng của Agent Tank: prize pool tính bằng **5% tổng GLP của Season 1**, không phải USD cứng. Về mặt EV cho builder đây có thể lớn hơn hẳn Bradbury nếu Season 1 tích tụ nhiều point.

### 1.2 Định vị mà GenLayer muốn nhấn

Tweet chính thức: *"Almost nothing has been built on the only chain that can judge. That is not a warning, it is the opportunity. The categories that are empty today are the ones somebody owns by the 17th."*

Đọc dịch: **track nào ecosystem đang trống (đặc biệt Autonomous Protocols — hiện không có live project nào), team đầu tiên ship trong track đó về mặt vị thế là "reference implementation"** cho tất cả những gì đến sau. Đây là góc chiến lược mạnh nhất cho team đến muộn.

---

## 2. LUẬT CHƠI (THE RULES)

Ba luật cứng từ landing page:

1. **ONE BUILD PER ACCOUNT** — 1 project / 1 portal account, editable đến khi submissions close.
2. **SHIP SOMETHING REAL** — public GitHub repo + full project application. Build được accept sẽ publish sang Project Explorer.
3. **RATED IN THE TANK** — panel review mọi build, mọi người có thể rate + comment khi tank còn mở. **Winners share 5% of all GenLayer Points**.

### 2.1 Yêu cầu bắt buộc bổ sung (từ thông báo tuần 1)

- **Video demo là bắt buộc** cho hackathon này, kể cả khi form Portal ghi field đó là *optional*. Video phải: cho thấy app làm gì, giải thích chuyện gì đang diễn ra, giúp người mới hiểu trước khi tự thử.
- Public GitHub repo (mã nguồn thật, không private).
- Contract deploy trên **Studio Next** (H1).
- Frontend chạy được end-to-end, gọi contract thật.

### 2.2 Tiêu chí self-check trước khi submit (nguyên văn của BTC)

Passing lint và test chỉ là điểm khởi đầu. Trước khi nộp, tự hỏi:
- App **thật sự** gọi một contract GenLayer thật chứ?
- Vì sao **decentralized judgment** quan trọng với bài toán này?
- Contract có giữ **meaningful state** không, và validator có kiểm **meaningful outcome** không?
- Repo build được và chạy được không?
- Đã build gì **beyond the starter/boilerplate**?
- Người khác dùng frontend + làm theo hướng dẫn có verify được kết quả không?

→ Đây là ánh xạ trực tiếp sang rubric 4 trục trong `01-how-to-score.md`. **Trục 2** ("validator kiểm ý nghĩa, không kiểm schema") vẫn là ranh giới quan trọng nhất giữa điểm cao và điểm thấp.

---

## 3. LỊCH TRÌNH (THE SCHEDULE)

| Mốc | Thời gian (UTC) |
|---|---|
| **Kickoff** | 03/09/2026 · 15:30 UTC |
| **Build window** | 03/09 → 17/09/2026 (2 tuần) |
| **Submissions close** | 17/09/2026 · 15:30 UTC |
| **Winners announced** | 25/09/2026 |

**Chiến thuật thời gian:**
- Portal reviewers có thể ping "Action needed" trong build period → nộp sớm để có buffer.
- Community rating + comment mở trong khi tank mở → nộp sớm cũng thu được nhiều feedback + rating hơn (rating có ảnh hưởng đến shortlist judging).
- Judging team review shortlist top 20+ **sau** 17/09, informed by community ratings.

---

## 4. 6 TRACKS (PICK A TRACK)

Mỗi build vào **đúng 1 track**. Mỗi track có 2 phần:
- **IDEAS WE WANT BUILT** — "prompts" mà GenLayer muốn thấy có người build.
- **LIVE IN THE ECOSYSTEM** — dự án đã tồn tại (có thể extend, hoặc tránh đụng hàng, hoặc dùng làm reference).

Builder có 3 lựa chọn trong mỗi track:
- **Extend a live project** (hợp tác với team đang có),
- **Take an open idea** (build từ prompt),
- **Bring your own** (miễn nằm trong scope track).

### 4.1 AGENTIC COMMERCE INFRASTRUCTURE
> *"Payments, escrow, identity and insurance for agents trading with agents."*

**Ideas we want built:**
- **SLA and uptime enforcement** — API escrow releases against signed logs or decentralized monitoring.
- **Stablecoin payments with chargeback** — one dispute API across cards, x402 and any chain.
- **Agent-liability insurance** — covers agent misbehavior and data leaks.
- **Model fingerprinting verifiers** — prove which model an agent is actually running.
- **B2C agent platforms** — open brief.

**Live in the ecosystem:**
- **Collective Memory** — shared memory & marketplace for agents.
- **Antseed** — open market for AI inference.
- **BuildersClaw** — agents compete for bounties.
- **Molly.fun** — agent launch and commerce infra.
- **Uptime** — consensus-verified SLA resolution.

### 4.2 ONCHAIN JUSTICE
> *"Disputes, appeals and rule enforcement decided from evidence."*

**Ideas we want built:**
- **Agentic marketplace disputes** — escrow released when a deliverable meets machine-readable terms.
- **Content moderation with public rules** — same rules for everyone, auditable appeal.
- **AI sports referee** — disputed calls resolved from public footage and data.

**Live in the ecosystem:**
- **Internet Court** — enforceable agreements and AI-jury verdicts for agent-to-agent commerce.

### 4.3 PREDICTION MARKETS & REAL-WORLD SETTLEMENT
> *"Money that moves when validators settle a question about the real world. Basic markets are covered; build the next layer."*

**Ideas we want built:**
- **Parametric insurance** — weather, satellite or news triggers payout with no claim filed.
- **Long-tail and local markets** — cheap resolution lets any two parties bet on anything.

**Live in the ecosystem:**
- **MicroMarkets, FUD Markets, Precog** — AI-resolved prediction markets.
- **Proven** — staked challenges resolved from outcomes.
- **COFI Bets, P2P Bets** (reference) — bet creation and settlement.
- **Cross-Border Settlement** (reference) — conditional payment on trade outcomes.
- **Intelligent Oracle** — reusable AI resolution layer any market can call.
- **Prediction Market Kit, Polymarket Benchmark** (reference) — reusable components + resolution accuracy.

### 4.4 AI GOVERNANCE
> *"Humans deciding together with AI help. If a community, DAO or committee is the one choosing, it belongs here."*

**Ideas we want built:**
- **Intelligent airdrop** — tokens distributed by evaluating real tasks, not a casino.
- **Investment DAO** — agents manage capital on behalf of a community.
- **Grants by open criteria** — contract scores proposals against public rules and disburses.

**Live in the ecosystem:**
- **Argue.fun** — agent debate and collective decisions.
- **Axiom Pilot** — grants judged against a constitution.
- **Progressive Autonomy in DAOs** (reference) — how a DAO hands authority to AI over time.

### 4.5 FUTURE OF WORK
> *"Work verified by consensus, paid on outcome, with portable reputation."*

**Ideas we want built:**
- **Automated bug bounties** — severity tier assigned from the PR, bounty released on merge.
- **Hiring and access via referral** — referrers and applicants paid automatically once the job is done.

**Live in the ecosystem:**
- **Rally** — verified creator marketing, paid on outcome.
- **Apolo** — freelance delivery evidence checked before payment.
- **GHBounty** — open-source bounties released on verified work.
- **MergeProof** — staked review and settlement on pull requests.

### 4.6 AUTONOMOUS PROTOCOLS ⭐ (track trống)
> *"Systems that run themselves. If a contract pauses, tunes or rewrites another contract or its own rules with no one voting, it belongs here."*

**Ideas we want built:**
- **Emergency halt module** — pauses a target contract when anyone proves an active exploit.
- **Intelligent stablecoins** — monetary policy that reads and reacts. Open brief.
- **Contracts that govern contracts** — one contract defines and enforces the behavior rules of another.
- **Lifeform** — a self-evolving contract that rewrites itself on a loop.

**Live in the ecosystem:** **KHÔNG có live project.** *"The first team here sets the reference."* → track có leverage vị thế cao nhất trong 6 tracks.

---

## 5. RÀNG BUỘC KỸ THUẬT (bổ sung `02-common-errors.md`)

Mọi rule trong `02-common-errors.md` vẫn áp dụng (pragma line 1, `TreeMap`/`DynArray`, `bigint`, `@allow_storage @dataclass`, str-keyed maps, MetaMask ký, v.v.). Bên trên đó, hackathon này thêm:

### 5.1 Studio Next specifics
- **Chain ID `61997`** (studionet cũ là 61999) — hardcode nhầm là frontend không switch được network.
- RPC: `https://studio-next.genlayer.com/api`.
- Explorer: `https://explorer-studio-dev.genlayer.com/` — kiểm tra tx `SUCCESS` + `Accepted` giống Explorer studionet.
- **Có fees** — consensus v0.6 tính phí giao dịch. Với hackathon: ví phải có GEN đủ **cho cả gas lẫn value transfer**. Test edge-case "not enough for fee" cũng là một điểm cộng (Trục 2).

### 5.2 Frontend stack chuẩn
```
genlayer-js@2.0.0-rc.1
@genlayer/transaction-kit@0.1.0-rc.2
@genlayer/transaction-kit-react@0.1.0-rc.2  # hoặc -vue
```
Boilerplate `v2-dev`: clone → `npm ci` → `cp frontend/.env.example frontend/.env` → set `VITE_CONTRACT_ADDRESS`.

Vì đây là **prerelease** RC, breakage nhỏ vẫn có thể xảy ra — pin version chính xác, đừng dùng `^` hay `~`.

### 5.3 Sai lầm hay gặp riêng của hackathon
- Deploy trên **studionet** thay vì Studio Next → bị loại. Đây là lỗi số 1 dễ mắc vì tài liệu builder mặc định (`00-read-me.md`) trỏ về studionet.
- Frontend ghi `chain: studionet` từ boilerplate cũ → build sai chain, MetaMask không switch được. Phải import chain Studio Next hoặc override chain object với `id: 61997`, RPC mới.
- Copy y nguyên contract example (Wizard of Coin, Storage) và đổi tên → **auto-reject**. BTC nói thẳng trong self-check: *"What have I built beyond the starter or boilerplate?"*
- `strict_eq` trên JSON có `reason` tự do → hai validator không bao giờ đồng thuận, tx toàn `Consensus: Undetermined`. Xem Trục 2 của `01-how-to-score.md`.
- Quên video demo (form ghi optional nhưng BTC bắt buộc).

---

## 6. CHẤM ĐIỂM

Hackathon dùng **hai stage** review độc lập:

### 6.1 Portal submission review (trong build period)
Reviewer Portal duyệt như submission Project Explorer thường. Tiêu chí = 4 trục trong `01-how-to-score.md`:
- **Trục 1 — GenLayer Fit:** bỏ AI/web đi dự án có sập không?
- **Trục 2 — Contract Quality:** validator so verdict/ý nghĩa, không so schema. `bigint`, edge-case, multi-contract hoặc nondet nâng cao để lên 5.
- **Trục 3 — Engineering:** commit history thật, cấu trúc thư mục, README, test `gltest`.
- **Trục 4 — Frontend/UX:** genlayer-js gọi contract thật, live URL, loading state khi chờ consensus, hiển thị `reason` AI trả về.

Nếu status "Action needed" → sửa và respond, **không** tạo submission mới.

### 6.2 Final judging (sau 17/09)
- Judging team review **shortlist top 20+**.
- Shortlist informed by **community star ratings + comments**.
- Winners chia **5% of all Season 1 GenLayer Points**.

**Chiến thuật rating:** share dự án ra ngoài + trong community, xin người thật thử và rate. Đồng thời rate dự án khác một cách honest và specific — BTC nhấn: rating hời hợt/spam làm hỏng hệ thống review cho tất cả.

### 6.3 Anti-pattern làm rớt shortlist
- App tĩnh, không gọi contract thật.
- README bịa tính năng chưa build.
- Description dùng "revolutionary", "seamless", "cutting-edge" — reviewer dị ứng buzzword.
- Contract deploy nhưng chưa có tx `SUCCESS` nào — state trống, reviewer không có gì đánh giá.
- Video demo chỉ show mock UI, không show tx thật trên explorer.

---

## 7. Ý TƯỞNG BUILD (bao quát — chưa spec cụ thể)

Nguyên tắc chọn đề tài, ưu tiên giảm dần:

**A. Xét theo leverage vị thế (empty category):**
1. Autonomous Protocols — hoàn toàn trống, first mover là reference.
2. Onchain Justice — chỉ có Internet Court, còn nhiều nhánh mở (moderation appeal, sports referee).
3. Agentic Commerce Infrastructure — có ~5 project nhưng đa số là infra chung; các nhánh chargeback / insurance / model fingerprinting còn trống.

**B. Xét theo GenLayer Fit (Trục 1 — bỏ AI/web đi thì sập):**
- Ưu tiên bài toán cần **phán quyết chủ quan** trên **dữ liệu web sống**, có **tiền hoặc reputation** đặt cược.

**C. Xét theo khả thi trong 2 tuần:**
- 1 contract core + 1 frontend + 3–5 write method là đủ đẹp. Đừng ôm 3 contract nếu chưa từng viết Intelligent Contract.

### 7.1 Autonomous Protocols (empty — leverage cao nhất)

- **Exploit-triggered circuit breaker** cho DeFi contract khác: bất kỳ ai post URL bằng chứng exploit (tx suspicious, thread security researcher), AI validator đọc + confirm, contract tự pause target. Free-rider hoặc slash nếu bằng chứng giả.
- **Rate-adjusting stablecoin controller**: contract đọc dữ liệu on-chain + web (news, oracle, TVL) rồi tự sửa collateral ratio / interest rate. Không voting, chỉ policy rule tự viết.
- **Rule-of-conduct enforcer cho DAO contract khác**: contract A định nghĩa "hành vi được phép" bằng natural language, wrap tất cả call tới contract B; validator kiểm mỗi call có phù hợp không.
- **Self-mutating contract**: contract tự propose thay đổi rule của chính nó dựa trên metrics (tx thành công, complaint rate), validator confirm/reject.
- **Auto-tuning fee market**: fee cho một dịch vụ tự sửa theo demand + chất lượng output (đo bằng LLM đánh giá).

### 7.2 Onchain Justice

- **Moderation-appeal court cho platform giả lập**: user upload content, mod bị takedown, user appeal — validator đọc content + community guidelines URL + decide overturn/uphold.
- **AI sports referee cho E-sports/streaming**: dispute trên một clip/streamer highlight; validator đọc footage metadata + rules → phân xử.
- **Freelance milestone arbiter**: 2 bên ký hợp đồng có natural-language "definition of done"; validator đọc PR/link deliverable → giải ngân từng milestone.
- **Doxxing / harassment claim court**: đơn tố cáo có URL bằng chứng; validator đọc + phân xử ban/không ban.
- **Rental deposit arbiter**: landlord vs tenant về deposit refund; upload ảnh + biên bản; AI cân nhắc.

### 7.3 Prediction Markets & Real-World Settlement

- **Parametric insurance cho drone delivery / crop / travel**: policy trigger tự resolve từ nguồn web (weather API, flight status).
- **Hyperlocal betting market**: cược sự kiện cấp phường/khối (nhà hàng X có mở cửa cuối tuần này không) — resolve từ Google Maps / Instagram post.
- **Prediction market chuyên đề GitHub**: cược PR nào merge trước ngày X, resolve từ GitHub API.
- **AI narrative market**: cược "meme narrative Y có trend không" — resolve bằng cách validator đọc Twitter search + tính engagement.

### 7.4 AI Governance

- **Retroactive public goods funding**: contract chấm impact của project quá khứ theo criteria công khai + phân bổ tiền.
- **Grant scorer** cho DAO nhỏ: DAO gửi proposal, contract chấm điểm theo constitution → auto-disburse nếu qua ngưỡng.
- **Airdrop-by-task**: user hoàn thành task đo lường được (contribute code, viết bài, refer), validator verify → tự claim.
- **DAO "constitution" enforcer**: mọi proposal chạy qua validator kiểm có vi phạm constitution không trước khi được đưa lên vote.

### 7.5 Future of Work

- **Bug bounty tự chấm severity**: PR đóng issue security, validator đọc issue + PR + mã → gán tier (P0..P3) và giải ngân đúng bracket.
- **Content bounty (paid on outcome)**: brand đặt bounty "content về X đạt Y views + không phá guideline"; validator đọc URL sau N ngày → phân xử.
- **Recruitment referral market**: refer candidate → nếu candidate được thuê và pass probation (validator đọc bằng chứng) → referrer nhận thưởng.
- **Portable reputation ledger** cho freelancer cross-platform: gộp bằng chứng (review, deliverable) từ nhiều nguồn, validator tính reputation score.

### 7.6 Agentic Commerce Infrastructure

- **Chargeback dispute API cho stablecoin merchant**: merchant + buyer tranh chấp, validator đọc order + delivery log → refund/keep.
- **API SLA enforcer**: provider stake tiền, hứa uptime X%; monitor decentralized post log; validator so log với SLA → giải ngân slash.
- **Agent identity + reputation registry**: agent đăng ký, mỗi giao dịch bổ sung score, validator kiểm chứng hành vi từ log ký số.
- **Model fingerprint verifier**: agent claim chạy model X; contract dùng validator gửi challenge prompt, so response đặc trưng → confirm/deny.
- **Data-leak insurance pool** cho AI agent: agent trả premium, khi có claim leak, validator xác minh leak thật rồi trả bảo hiểm.

### 7.7 Ý tưởng "cross-track" cho team tham vọng

- **Agent-to-agent B2B contract engine**: kết hợp *Agentic Commerce* (payment + identity) + *Onchain Justice* (dispute) + *Autonomous Protocols* (auto-halt khi phát hiện abuse). Sản phẩm cuối là platform full-stack.
- **Autonomous prediction market với dispute layer**: markets tự resolve (Prediction Markets), có appeal court (Onchain Justice), fee tự điều chỉnh (Autonomous Protocols).

---

## 8. CHECKLIST NỘP BÀI (rút gọn cho hackathon này)

**Trước 17/09/2026 15:30 UTC:**

- [ ] Contract deploy trên **Studio Next** (chain 61997), tx đầu tiên đã `SUCCESS` + `Accepted` trên explorer
- [ ] Frontend dùng `genlayer-js@2.0.0-rc.1` + `@genlayer/transaction-kit@0.1.0-rc.2`, chain 61997
- [ ] Live URL truy cập được, ký giao dịch thật, không hardcode kết quả
- [ ] Public GitHub repo, README có: bài toán, kiến trúc, hướng dẫn deploy Studio Next, live URL, contract address
- [ ] **Video demo** (bắt buộc): show tính năng + tx thật trên explorer + `reason` AI trả về
- [ ] Chọn đúng 1 track trên form Portal
- [ ] Seed sẵn ≥1 record hoàn tất luồng chính để reviewer thấy state có ý nghĩa
- [ ] Validator kiểm **verdict/ý nghĩa**, không so schema
- [ ] Không copy y nguyên example contract
- [ ] Nộp SỚM (ngay khi có v1) — Portal reviewer có thể "Action needed", cần buffer để sửa

**Trong lúc chờ judging (17/09 → 25/09):**
- [ ] Share dự án ra ngoài + trong Discord/Telegram community
- [ ] Xin người thật thử + rate + comment (rate thật → shortlist)
- [ ] Rate + comment honest cho dự án khác

---

## 9. NGUỒN CHÍNH THỨC

| Mục | URL |
|---|---|
| Trang hackathon | https://portal.genlayer.foundation/agent-tank/ |
| Studio Next RPC | https://studio-next.genlayer.com/api |
| Studio Next Explorer | https://explorer-studio-dev.genlayer.com/ |
| Migration notes v0.6 | https://docs.genlayer.com/developers/consensus-v06-migration#test-on-studio-dev-first |
| Boilerplate v2-dev | https://github.com/genlayerlabs/genlayer-project-boilerplate/tree/v2-dev |
| Portal chính | https://portal.genlayer.foundation/ |
| Docs (full 1 file) | https://docs.genlayer.com/full-documentation.txt |
| SDK API (1 file cho AI) | https://sdk.genlayer.com/main/_static/ai/api.txt |
| Discord | https://discord.gg/8Jm4v89VAu |
| GenLayer X | https://x.com/GenLayer |

---

## 10. TÓM TẮT 1 DÒNG (cho AI ghi nhớ nhanh)

> Agent Tank Hackathon là hackathon flagship của GenLayer Season 1 (03–17/09/2026, 2 tuần, deploy trên **Studio Next chain 61997**, boilerplate `v2-dev` với Transaction Kit RC2 + genlayer-js 2.0.0-rc.1), có 6 tracks (Agentic Commerce Infrastructure, Onchain Justice, Prediction Markets & Real-World Settlement, AI Governance, Future of Work, **Autonomous Protocols — track trống, cơ hội đặt reference**), 1 build/account, video demo bắt buộc, chấm 2 stage (Portal review trong build period + judging shortlist top 20+ sau 17/09 informed bởi community rating), winners chia **5% of all Season 1 GenLayer Points**, công bố 25/09/2026.

---

*Biên soạn 15/09/2026 từ landing page hackathon, tweet chính thức @GenLayer, thông báo tuần 1 của BTC. Cross-check với `00-read-me.md` (bối cảnh GenLayer + quyết định D1/D2/D3), `01-how-to-score.md` (rubric 4 trục), `02-common-errors.md` (bẫy kỹ thuật + wallet), `03-lỗi khi deploy.md` (schema errors). Vì file này override một số quyết định trong `00-read-me.md` (mạng deploy, kênh nộp) trong phạm vi hackathon, luôn đọc §0 trước tiên khi có mâu thuẫn.*