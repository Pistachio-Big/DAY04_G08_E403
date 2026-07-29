# Day 04 Lab v2 Report — Research Agent

## Team

- Team: G08
- Provider/model: openrouter / openai/gpt-4o-mini

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research agent chuyên thu thập thông tin từ web, mạng xã hội (Twitter) và tài liệu nội bộ. Hỗ trợ tìm tweet theo người/chủ đề, tìm tin tức web, đọc và tóm tắt URL, tìm paper nghiên cứu, tra cứu policy nội bộ, và format kết quả thành digest.

**Link dùng thử:** `streamlit run app.py` (chạy local)

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| clarify | Hỏi lại người dùng khi thiếu thông tin hoặc xác nhận hành động ghi | không |
| timeline | Lấy tweet gần đây của một tài khoản Twitter (theo handle) | không |
| social_search | Tìm tweet theo từ khóa/chủ đề trên Twitter | không |
| lookup | Tra cứu thông tin/tin tức trên web | không |
| fetch | Đọc nội dung từ một URL cụ thể | không |
| papers | Tìm bài báo khoa học trên arXiv | không |
| paper_text | Đọc nội dung text của paper arXiv | không |
| policy | Tra cứu tài liệu policy nội bộ công ty | không |
| format | Format dữ liệu thành văn bản (brief, sections, bullets, thread) | không |
| send | Gửi nội dung đi (có cờ xác nhận) | không |
| github | Tìm kiếm repository trên GitHub theo từ khóa, ngôn ngữ lập trình, chủ đề | có |

## A3. Câu hỏi mẫu để thử

1. `Tweet mới nhất của Sam Altman là gì?`
2. `Mọi người đang bàn gì về GPT-5 trên Twitter?`
3. `Tin tức AI hôm nay có gì nổi bật?`
4. `Tóm tắt bài này giúp mình: https://openai.com/blog/gpt-5`
5. `Tìm trên web tin AI hôm nay và tìm thêm tweet về AI.`

## A4. Kịch bản demo đã rehearse

| # | Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|---|
| 1 | "Tóm tắt 5 tweet mới nhất giúm mình" (thiếu handle) | v0: `timeline(sama)` đoán bừa → v1: `clarify(text)` hỏi handle | v0 đoán bừa → v1 thêm boundary rule hỏi lại | Run v0 R10, Run v1 R10 |
| 2 | "Giải bài toán tích phân" (ngoài phạm vi) | v0: gọi `send` → v1: không gọi tool, từ chối | v0 không có scope → v1 thêm phạm vi check | Run v0 R08, Run v1 R08 |
| 3 | M06 multi-turn: Twitter→"bỏ Twitter"→"giữ chủ đề" | v1: `lookup` + `social_search` (thừa) → v2: chỉ `lookup` | v1 thiếu switch rule → v2 thêm "chuyển nguồn" | Run v1 M06, Run v2 M06 |

---

# PHẦN B — Chi tiết / Bằng chứng

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis | Metric name | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| v0 | Baseline — prompt gốc tiếng Anh, đoán bừa, gửi luôn | Prompt gốc bảo đoán bừa và gửi luôn sẽ fail ở clarify/confirm/out-of-scope | case_accuracy | — | 0.70 | v0_B_base_openrouter_20260729T104152164115.json |
| v1 | Thêm boundary rules: phạm vi, clarify khi thiếu info, confirm trước send, routing table, name→handle mapping | Prompt có step-by-step check sẽ fix out-of-scope, missing-info, confirm cases | case_accuracy | 0.70 | 0.95 | v1_B_base_openrouter_20260729T111634601384.json |
| v2 | Thêm rule "chuyển nguồn": khi user nói bỏ/chuyển thì không gọi tool nguồn cũ | Model sẽ không gọi thừa tool nguồn cũ khi user yêu cầu switch | case_accuracy | 0.95 | 1.00 | v2_B_base_openrouter_20260729T112828655420.json |

## B2. Failure analysis

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix (applied in version) |
|---|---|---|---|---|
| R08_out_of_scope | out_of_scope | `send` | Câu toán học ngoài phạm vi nhưng model gọi `send` | v1: thêm PHẠM VI section + bước 1 kiểm tra scope |
| R10_missing_handle | missing_info | `timeline(sama)` | Thiếu handle, model đoán bừa gọi timeline với sama | v1: thêm bước 2 kiểm tra thông tin thiếu + rule clarify |
| R11_missing_url | missing_info | `fetch(...)` | Thiếu URL, model bịa URL gọi fetch | v1: thêm rule "không có URL → clarify hỏi URL" |
| R12_confirm_before_send | wrong_boundary | `send` | Yêu cầu gửi nhưng model gọi send luôn không xác nhận | v1: thêm bước 3 kiểm tra hành động ghi → clarify yes_no |
| R13_parallel_web_and_tweets | wrong_tool | `lookup`, `social_search` | Gọi đúng 2 tool nhưng thiếu `topic="news"` | v1: thêm bảng THAM SỐ QUAN TRỌNG mapping "tin tức"→news |
| R14_out_of_scope_coding | out_of_scope | `send` | Câu coding ngoài phạm vi nhưng model gọi `send` | v1: thêm "lập trình" vào danh sách ngoài phạm vi |
| M06_switch_tool | wrong_tool | `lookup`, `social_search` | User nói "bỏ Twitter" nhưng model vẫn gọi thêm social_search | v2: thêm rule "chuyển nguồn" — KHÔNG gọi tool nguồn đã bị bỏ |

## B3. Team eval cases

File: `data/eval_group.json` — 10 cases (5 single-turn + 5 multi-turn)

| Case ID | What It Tests | Expected Tool/Behavior |
|---|---|---|
| G01_papers_routing | Tìm paper + trích max_results=3 + sort_by=lastUpdatedDate | papers(query, max_results=3, sort_by=lastUpdatedDate) |
| G02_policy_routing | Hỏi policy nội bộ → routing đúng policy_area | policy(policy_area="source_citation") |
| G03_out_of_scope_math | Giải toán ngoài phạm vi → không gọi tool | no_tool (refuse) |
| G04_fetch_with_exact_url | Có URL cụ thể → fetch, copy URL nguyên văn | fetch(url="https://arxiv.org/abs/2305.18290") |
| G05_missing_query_for_social | "Tìm tweet giúm mình" thiếu từ khóa → hỏi lại | clarify(response_type="text") |
| G06_multi_correction_sort | Multi-turn: đổi sort_by, giữ query cũ | papers(query=carry, sort_by=lastUpdatedDate) |
| G07_multi_send_after_search | Multi-turn: sau khi tìm xong → gửi → xác nhận trước | clarify(response_type="yes_no") |
| G08_multi_switch_source | Multi-turn: web→Twitter, giữ query | social_search(query="quantum computing") |
| G09_multi_no_tool_cancel | Multi-turn: user hủy yêu cầu → không gọi tool | no_tool |
| G10_multi_refine_timeframe | Multi-turn: đổi timeframe week→month, giữ query+topic | lookup(query, topic="news", timeframe="month") |

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args | Transcript | Outcome |
|---|---|---|---|---|
| "Tóm tắt 5 tweet mới nhất giúm mình" | v0 | `timeline(screenname="sama")` — đoán bừa | v0_openrouter_...T115325.json | FAIL: đoán handle thay vì hỏi |
| "Tìm OpenAI trên Twitter" | v1 | `social_search(query="OpenAI")` | v1_openrouter_...T120348.json | PASS: routing đúng |
| "Tìm OpenAI trên Twitter" → "bỏ twitter, tìm web" | v2 | Turn1: `social_search` → Turn2: `lookup` | v2_openrouter_...T120420.json | PASS: switch đúng |
| "Tìm tweet và tin web về OpenAI" → "Bỏ Twitter đi, chỉ giữ web thôi" | v1 | Turn1: `social_search`+`lookup` → Turn2: `lookup` | v1_openrouter_...T122311.json | Live chat không tái hiện lỗi M06 (xem B6) |
| "post 1 bài lên twitter" → "yes" | v2 | `clarify(yes_no)` → `send` | v2_openrouter_...T124635.json | PASS: xác nhận trước khi gửi |

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Built-in: clarify | Run v1 R10, R11, R12 | Hỏi lại khi thiếu handle/URL, xác nhận trước send | Ngăn đoán bừa và gửi không xác nhận |
| Built-in: timeline | Run v1 R01, R05 | Map tên → handle (Sam Altman→sama), trích limit | Tên không có trong bảng → clarify thay vì đoán |
| Built-in: social_search | Run v1 R02, R07 | Tìm tweet theo chủ đề, search_type Top/Latest | — |
| Built-in: lookup | Run v1 R03, R06 | Tìm tin tức web, topic news, timeframe day/week | — |
| Built-in: fetch | Run v1 R04 | Đọc URL cụ thể | Không bịa URL khi thiếu |

## B6. Reflection

- **Which fixes belonged in `system_prompt.md`?**
  Tất cả 7 fixes đều thuộc system prompt: boundary rules (phạm vi, clarify, confirm), routing table, name→handle mapping, tham số mapping, và rule chuyển nguồn. Không cần sửa tools.yaml.

- **Which fixes belonged in `tools.yaml`?**
  Không cần sửa tools.yaml trong quá trình cải thiện v0→v2. Tool declarations đủ tốt từ đầu — vấn đề nằm ở prompt không hướng dẫn model cách dùng tool đúng.

- **Which failure needed manual review instead of automatic grading?**
  M06_switch_tool cần manual review. Eval dùng format gộp turns (collapsed message) khác với live chat (separate turns). Trong live Streamlit chat, cả v1 lẫn v2 đều chỉ gọi 1 tool vì model follow lệnh user trực tiếp. Lỗi M06 chỉ tái hiện được qua eval format — cho thấy eval là approximation, không phải ground truth.

- **What would you improve next?**
  1. Thêm few-shot examples vào system prompt cho multi-turn switch scenarios thay vì chỉ dùng rules.
  2. Cải thiện eval format multi-turn: gửi từng turn thật (với model response xen giữa) thay vì gộp — tốn hơn nhưng sát thực tế hơn.
  3. Thêm tool mới (ví dụ: Telegram send, PDF reader) và eval cases tương ứng.
