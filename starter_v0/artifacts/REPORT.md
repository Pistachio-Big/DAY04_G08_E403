# Day 04 Lab v2 Report — Research Agent

> File này gồm 2 phần, deadline khác nhau:
> - **PHẦN A — Giới thiệu agent**: ngắn gọn 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào. Xong trước 11:30 để làm tài liệu phụ trợ khi demo.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ (v0–v3, failure, eval, chat) dựa trên log thật. Có thể hoàn thiện sau buổi debate để nộp bài.

## Team

- Team: DAY04_2A202601217_NguyenVanDai
- Members: Phạm Nguyên Việt (2A202601547), Lục Minh Đức (2A202601918), Phạm Trung Kiên (2A202601986), Nguyễn Huy Anh (2A202601641), Nguyễn Văn Đại (2A202601217)
- Provider/model: OpenRouter, model `nvidia/nemotron-3-super-120b-a12b:free` (free tier — tài khoản OpenRouter trả phí hết credit trong lúc build; `openai/gpt-oss-20b:free` cũng khả dụng làm phương án dự phòng nhưng provider free hiện tại của nó không hỗ trợ `tool_choice="required"` mà `run_eval.py` cần)

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research agent: tra tin trên web/mạng xã hội theo từ khóa hoặc theo tài khoản, đọc URL, tra định nghĩa khái niệm qua Wikipedia (`wiki_summary` — tool nhóm tự viết), và tổng hợp thành digest; hỏi lại khi thiếu thông tin và xác nhận trước khi đăng.

**Link dùng thử (truy cập được trong showdown):**

> UI chạy local qua Streamlit. Trên máy demo: `cd starter_v0 && source .venv/bin/activate && streamlit run app.py` rồi mở `http://localhost:8501`. Nếu cần người ngoài máy mở, dùng `cloudflared tunnel --url http://localhost:8501` và dán URL `trycloudflare.com` vào đây trước showdown.
>
> URL: (điền URL `trycloudflare.com` sau khi mở tunnel trên máy demo thật)

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| clarify | Hỏi lại người dùng khi thiếu thông tin hoặc cần xác nhận yes/no trước hành động nhạy cảm | không |
| timeline | Lấy các bài đăng gần đây của một tài khoản Twitter/X | không |
| social_search | Tìm bài đăng trên Twitter/X theo từ khóa | không |
| lookup | Tìm kiếm trên web (Tavily), có topic=news/general và timeframe | không |
| fetch | Đọc nội dung một URL cụ thể (Firecrawl) | không |
| format | Trình bày các item đã có thành digest markdown (brief/sections/bullets/thread) | không |
| wiki_summary | Tra định nghĩa/tóm tắt bách khoa nhanh về một khái niệm/thực thể từ Wikipedia REST API (không cần API key, tự fallback vi→en) | **có — tool mới bắt buộc của nhóm** |
| send | Gửi text lên Telegram channel (chỉ khi `confirmed=true`) | không (optional/bonus có sẵn) |
| policy | Tìm trong company policy markdown nội bộ | không (optional/bonus có sẵn) |
| papers | Tìm bài báo khoa học trên arXiv | không (optional/bonus có sẵn) |
| paper_text | Tải PDF arXiv và trích text cục bộ | không (optional/bonus có sẵn) |

## A3. Câu hỏi mẫu để thử

1. "Tin tức AI hôm nay có gì nổi bật?" — routing sang `lookup` (topic=news, timeframe=day).
2. "Transformer trong deep learning là gì?" — routing sang tool mới `wiki_summary`, không phải `lookup`.
3. "Tóm tắt 5 tweet mới nhất giúp mình" (không nói tài khoản nào) — agent phải hỏi lại (`clarify`) thay vì đoán bừa.
4. "Đăng bản tin này lên Telegram giúp mình" — agent phải hỏi xác nhận yes/no trước khi gọi `send`.
5. "Giải giúp mình bài toán tích phân: nguyên hàm của x^2 là gì?" — ngoài phạm vi, agent nên từ chối/trả lời trực tiếp, không gọi tool nào.

## A4. Kịch bản demo đã rehearse

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
| Tin tức hôm nay | `lookup(query, topic=news, timeframe=day)` | v0: gọi `lookup` với query bị nhồi thêm từ khóa/ngày tháng, không set topic/timeframe, rồi tự chèn thêm `format`+`send` thừa → v1 bỏ được `format`/`send` thừa → v3 hướng tới set đúng topic/timeframe (còn hạn chế, xem B2) | `runs/v0_B_base_openrouter_20260729T115708561809.json`, `runs/v3_B_base_openrouter_20260729T121811094152.json` |
| Định nghĩa khái niệm (tool mới) | `wiki_summary(query, lang)` | Tool mới của nhóm; minh chứng agent phân biệt được câu hỏi "định nghĩa" với câu hỏi "tin tức" | `data/eval_group.json` case `G01_wiki_definition_routing`, transcript live chat turn 1/3 |
| Thiếu thông tin tài khoản | `clarify(response_type="text")` rồi `timeline(screenname, limit)` ở turn sau | v0: agent tự đoán bừa handle (Sam Altman mặc định) → v2: agent hỏi lại đúng khi không có handle nào (`R10`, `R11` pass) | `runs/v2_B_base_openrouter_20260729T121140458707.json` |
| Xác nhận trước khi gửi | `clarify(response_type="yes_no")` → chỉ gọi `send(confirmed=true)` sau khi user nói "có" | v0/v1: agent gửi thẳng không hỏi → v2 thêm rule hỏi trước khi gửi, nhưng log v2 cho thấy agent vẫn tự hỏi rồi tự trả lời luôn trong cùng lượt (`R12` vẫn fail, xem B2/B6) | `runs/v2_B_base_openrouter_20260729T121140458707.json`, transcript live chat turn 4-5 |
| Câu hỏi ngoài phạm vi | không gọi tool nào, trả lời/từ chối trực tiếp | v0: agent vẫn gọi `lookup`/`policy`/viết code cho câu hỏi ngoài phạm vi → v1 sửa xong (R08, R09, R14 đều pass) | `runs/v1_B_base_openrouter_20260729T120414529453.json` |

---

# PHẦN B — Chi tiết / Bằng chứng

> Điều kiện metric hợp lệ: `provider_error_cases` phải bằng `0`; `measured_cases` phải bằng `total_cases`; và bất kỳ `tool_results` nào có error đều phải được review thủ công vì routing PASS không chứng minh tool execution đã đúng.
>
> **Giới hạn môi trường quan trọng**: nhóm chỉ có `OPENROUTER_API_KEY` (dùng model free `nvidia/nemotron-3-super-120b-a12b:free` vì tài khoản trả phí hết credit). Không có `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, `RAPIDAPI_KEY` nên `lookup`, `fetch`, `timeline`, `social_search` không thực thi được dữ liệu thật (trả về lỗi `Missing API key env var`) — điều này **không** ảnh hưởng tới các số liệu routing/argument bên dưới (eval chỉ chấm tool_calls/args, không chấm kết quả thực thi), nhưng có nghĩa live-chat/demo thật chỉ show được dữ liệu thật qua `wiki_summary` (không cần key ngoài) và `clarify`/`format`.

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis | Metric name | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| v0 | baseline (system_prompt/tools.yaml gốc, cố tình sơ sài) | — | case_accuracy | — | 0.10 | `runs/v0_B_base_openrouter_20260729T115708561809.json` |
| v1 | `system_prompt.md`: thêm rule chỉ gọi `format`/`send` khi được yêu cầu | v0 log cho thấy agent luôn chain thêm `format`+`send` sau mọi tool nghiên cứu (13/18 fail có extra_tool_call) vì prompt gốc bảo "cứ đăng luôn, xong trong 1 bước" | case_accuracy | 0.10 | 0.2105 | `runs/v1_B_base_openrouter_20260729T120414529453.json` |
| v2 | `system_prompt.md`: thêm 2 ngoại lệ cho rule "đừng hỏi lại" — hỏi khi hoàn toàn thiếu định danh (account/URL), hỏi yes/no trước khi `send` | v1 log vẫn còn agent tự đoán handle/URL (R10/R11) và gửi thẳng không xác nhận (R12) | case_accuracy | 0.2105 | 0.30 | `runs/v2_B_base_openrouter_20260729T121140458707.json` |
| v3 | `system_prompt.md`: thêm convention map từ ngữ tự nhiên sang argument (số lượng→limit, hôm nay/tuần này→timeframe+topic, top/phổ biến→search_type); `tools.yaml`: thêm declaration `wiki_summary` (đi cùng lúc vì đây là round hoàn thiện tool mới) | v2 log cho thấy nhóm lỗi lớn nhất còn lại là wrong_arg_value: limit/topic/timeframe/search_type bị bỏ mặc định dù user đã nói rõ | case_accuracy | 0.30 | 0.25 | `runs/v3_B_base_openrouter_20260729T121811094152.json` |

**Lưu ý về v3**: điểm số tụt nhẹ (0.30→0.25) thay vì tăng. Đây là round duy nhất thay đổi đồng thời cả `system_prompt.md` và `tools.yaml` (không tránh được vì tool mới bắt buộc phải thêm), nên không cô lập được hoàn toàn biến số. Soi kỹ run JSON (xem B2/B6) cho thấy phần lớn điểm tụt đến từ nhiễu của model free-tier (bỏ sót key có giá trị mặc định như `response_type`, một case hallucinate gọi nhầm `paper_text`/`fetch`) chứ không phải do hypothesis argument-convention sai — case `M04_clarify_then_url` chuyển từ FAIL sang PASS đúng như kỳ vọng của hypothesis.

## B2. Failure analysis

Case tiêu biểu từ `runs/v3_B_base_openrouter_20260729T121811094152.json` (20 case, 5 PASS, 15 FAIL):

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| R05_limit_arg | wrong_arg_value | `timeline(screenname=elonmusk)` | User nói "10 tweet" nhưng `limit` vẫn None (default) dù đã có rule map số lượng→limit trong prompt | Cần thử tools.yaml mô tả rõ hơn nữa cho `limit`, hoặc thêm ví dụ few-shot trong prompt; free model không tuân thủ rule chữ suông tốt bằng model trả phí |
| R10_missing_handle | missing_info | `clarify(question=...)` — thiếu key `response_type` | Model gọi đúng `clarify` nhưng bỏ qua field `response_type` (coi là default nên không set tường minh) → grader chấm exact-match nên fail | Ghi rõ trong tools.yaml: "luôn set response_type tường minh, không dựa vào default" |
| R11_missing_url | missing_info | `paper_text(arxiv_url="")` | Model hallucinate gọi nhầm tool `paper_text` với arg rỗng thay vì `clarify` — có thể do thêm tool mới vào danh sách khiến routing nhiễu | Cần thêm ví dụ phân biệt rõ trong system_prompt giữa "không có URL nào" (hỏi lại) và "có URL nhưng chưa đọc" (fetch) |
| R12_confirm_before_send | wrong_boundary | `clarify(text)` → `clarify(yes_no)` → `send(confirmed=true)` cùng 1 lượt | Model tự hỏi rồi tự trả lời luôn thay vì dừng lại chờ user thật | Cần thêm rule tường minh: "sau khi gọi `clarify`, dừng lại — không gọi thêm tool nào khác trong cùng lượt" |
| R06_timeframe_arg | wrong_arg_value | 4 lần gọi `lookup` với query dài dần khác nhau | Model tự "retry" tool nhiều lần với query bị viết lại thay vì gọi 1 lần | Thêm rule: "mỗi tool chỉ gọi tối đa 1 lần cho mỗi yêu cầu, không tự retry" |

## B3. Team eval cases

10 case trong `data/eval_group.json` (5 single-turn dùng `query`, 5 multi-turn dùng `turns`), chạy trên v3: `runs/v3_B_group_openrouter_20260729T135030026984.json` — **3/10 PASS** (case_accuracy=0.3, tool_routing_accuracy=0.7, multiturn_accuracy=0.4).

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_wiki_definition_routing | Câu hỏi định nghĩa route sang `wiki_summary` thay vì `lookup`/`social_search` | `wiki_summary` | FAIL — gọi đúng `wiki_summary` nhưng chain thêm `format`+`send` thừa (v1 fix chưa tổng quát hóa sang tool mới) |
| G02_wiki_summary_lang_arg | Yêu cầu ngôn ngữ tường minh map thành `lang=en` | `wiki_summary(lang=en)` | FAIL — gọi đúng tool nhưng bỏ trống `lang` (dùng default `vi`) |
| G03_timeline_limit_arg | Map tên người + số lượng tường minh thành `limit` | `timeline(screenname=billgates, limit=7)` | FAIL — `limit` vẫn None, giống pattern R05/M01/M03/M05 ở base eval |
| G04_capability_question_no_tool | Câu hỏi meta về khả năng agent trả lời trực tiếp | `no_tool` | **PASS** |
| G05_missing_paper_topic | Yêu cầu tìm paper không có từ khóa nào phải hỏi lại | `clarify(text)` | FAIL — không gọi tool nào, trả lời thẳng (có thể bịa kết quả) thay vì hỏi lại |
| G06_wiki_multiturn_topic_switch | Multi-turn chuyển từ ý định mơ hồ sang câu hỏi định nghĩa cụ thể | `wiki_summary` | **PASS** |
| G07_carryover_screenname_new_limit | Multi-turn giữ screenname, áp dụng limit mới | `timeline(screenname=sundarpichai, limit=6)` | FAIL — screenname đúng nhưng `limit` vẫn None |
| G08_confirmed_send_after_yes | Multi-turn: sau khi user đã đồng ý, gửi ngay không hỏi lại | `send(confirmed=true)` | FAIL — hallucinate gọi `timeline(screenname="user")` và `timeline(screenname="assistant")`; có vẻ model hiểu nhầm nhãn role "user"/"assistant" trong phần context multi-turn tổng hợp của `run_eval.py` thành tên tài khoản thật |
| G09_multiturn_missing_url_still_ask | Multi-turn: dù nhắc lại, vẫn chưa có URL thật nên phải hỏi | `clarify(text)` | FAIL — gọi đúng `clarify` nhưng thiếu key `response_type` tường minh (cùng pattern với R10 ở base eval) |
| G10_multiturn_translation_out_of_scope | Multi-turn: yêu cầu dịch thuật ngoài phạm vi tool sau khi hủy tìm kiếm | `no_tool` | **PASS** |

## B4. Live chat evidence

Transcript: `transcripts/v3_openrouter_20260729T133417923771.transcript.json` (chat.py, provider=openrouter, model=`nvidia/nemotron-3-super-120b-a12b:free`, version=v3, 5 turns).

| Scenario/Turn | Version | Tool Calls + Args | Transcript/Run | Outcome |
|---|---|---|---|---|
| 1. Research bình thường: "Transformer trong deep learning là gì?" | v3 | `wiki_summary(query="Transformer (deep learning)")` | turn_index=1 | **PASS** — gọi đúng tool mới, dữ liệu Wikipedia thật (không cần key ngoài) |
| 2. Follow-up mơ hồ: "Giải thích khái niệm này giúp mình" | v3 | *(không gọi tool)* | turn_index=2 | Model tự suy ra "này" = Transformer từ turn 1 và trả lời trực tiếp — hợp lý vì context đã có định danh rõ, không phải case missing_info thật |
| 3. Đổi khái niệm: "Attention mechanism đó" | v3 | *(không gọi tool)* | turn_index=3 | **Gap**: lẽ ra nên gọi lại `wiki_summary(query="Attention mechanism")` nhưng model trả lời thẳng bằng kiến thức nội tại thay vì tra cứu — nội dung đúng nhưng không có tool trace/nguồn |
| 4. Hành động nhạy cảm: "Đăng bản tóm tắt Attention mechanism lên Telegram giúp mình" | v3 | *(không gọi tool)* | turn_index=4 | **Gap**: lẽ ra phải gọi `clarify(response_type=yes_no)` trước; thay vào đó model soạn sẵn nội dung Telegram và mời user tự copy-paste |
| 5. Xác nhận: "Ừ, đăng đi" | v3 | *(không gọi tool)* | turn_index=5 | **Gap**: không gọi `send(confirmed=true)`; model lặp lại nội dung thay vì gọi tool |

**Phát hiện quan trọng**: `run_eval.py` ép `tool_choice="required"` cho mọi case có kỳ vọng tool_calls, nên các rule clarify/send trong `system_prompt.md` đo được đúng ở B1/B2. Nhưng `chat.py` (live chat thật) **không** ép `tool_choice`, và ở chế độ tự do này model free-tier có xu hướng trả lời trực tiếp bằng kiến thức nội tại thay vì gọi tool — kể cả cho case nhạy cảm (turn 4-5) đáng lẽ phải qua `clarify`/`send`. Đây là khoảng cách thật giữa số liệu eval (forced tool_choice) và hành vi demo trực tiếp (free tool_choice), cần lưu ý khi trình bày kết quả.

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: tool mới đầu tiên (`wiki_summary`) | `tools/wiki_summary/tool.py`, `tools/wiki_summary/TOOL.md`, smoke test trực tiếp (tra "Trí tuệ nhân tạo" tiếng Việt và "Transformer (deep learning)" fallback sang en đều trả về summary thật) | Chạy thật, không cần API key, tự fallback vi→en khi bài tiếng Việt không tồn tại | Wikipedia API có thể trả 404 cho khái niệm quá hẹp/không tồn tại; tool trả `err()` dict chuẩn cho case đó |
| Optional built-in | `send` (Telegram), `lookup`/`fetch` (Tavily/Firecrawl), `timeline`/`social_search` (RapidAPI) | Declaration giữ nguyên trong `tools.yaml`, routing vẫn được test qua eval | Không có key thật cho Tavily/Firecrawl/RapidAPI/Telegram trong môi trường build — chỉ verify được routing, không verify được execution thật (xem cảnh báo đầu PHẦN B) |
| Bonus: tool mới thứ 4 trở đi | (chưa làm — chỉ có 1 tool mới `wiki_summary`, không đủ điều kiện bonus 3+ tool mới) | — | — |

## B6. Reflection

- **Fixes thuộc `system_prompt.md`**: toàn bộ 3 vòng v1-v3 đều sửa system_prompt — vì vấn đề cốt lõi ở baseline không phải do tool declaration mà do prompt chủ động khuyến khích hành vi sai (đoán bừa, tự gửi, chain thừa tool).
- **Fixes thuộc `tools.yaml`**: chỉ thêm declaration cho tool mới `wiki_summary` ở v3; chưa thử nghiệm sửa mô tả arg của các tool cũ (ví dụ mô tả rõ hơn convention cho `limit`/`timeframe`) — đây là hướng cải thiện tiếp theo vì R05/R06 vẫn fail dù đã có rule trong prompt.
- **Failure cần review thủ công thay vì chỉ tin automatic grading**: R11 (model hallucinate gọi `paper_text` thay vì `clarify`) và R10/G09 (model gọi đúng tool nhưng thiếu key mặc định `response_type`) đều là lỗi mà nếu chỉ nhìn `case_accuracy` sẽ bị đánh đồng với "sai logic hoàn toàn", trong khi thực tế là nhiễu của model free-tier hoặc quirk của grader (yêu cầu set tường minh cả field có giá trị mặc định). Case `G08_confirmed_send_after_yes` review thủ công còn lộ ra thứ đáng ngờ hơn: model gọi `timeline(screenname="user")` và `timeline(screenname="assistant")` — nhiều khả năng nó đọc nhầm nhãn role ("Earlier user turn...", "Earlier assistant turn...") trong đoạn context multi-turn tổng hợp của `run_eval.py` thành tên tài khoản Twitter thật, một lỗi mà grader chỉ báo chung chung "missing tool call send" chứ không lộ ra nguyên nhân gốc.
- **Cải thiện tiếp theo**: (1) thêm rule "dừng lại sau `clarify`, không tự trả lời thay user" để sửa R12 triệt để; (2) thêm rule "không tự retry tool nhiều lần" để sửa R06/R13; (3) nếu có ngân sách, chuyển sang model trả phí (`openai/gpt-4o-mini` qua OpenRouter) để tách bạch được lỗi do prompt/tools design với lỗi do model free-tier yếu/không ổn định; (4) xin key Tavily/Firecrawl/RapidAPI để live chat/demo có dữ liệu thật cho toàn bộ core tool, không chỉ `wiki_summary`; (5) cân nhắc set `tool_choice` tường minh trong `chat.py` cho các lượt có tín hiệu rõ ràng (câu hỏi định nghĩa, yêu cầu gửi/đăng) để hành vi demo trực tiếp khớp với số liệu eval — hiện eval ép `tool_choice="required"` còn chat thật thì không, dẫn đến model free-tier bỏ qua `wiki_summary`/`clarify`/`send` ở live chat dù routing rule đã đúng trong prompt (xem B4).
