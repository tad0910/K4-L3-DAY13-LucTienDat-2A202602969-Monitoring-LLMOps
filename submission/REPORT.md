# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Lục Tiến Đạt
- **MSSV:** 2A202602969
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/tad0910/K4-L3-DAY13-LucTienDat-2A202602969-Monitoring-LLMOps
- **Commit SHA cuối:** `c71329c0c4c278fbf30d119d13dcc992ff24aa35`
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602969`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt toàn bộ 4/4 tiêu chí: JSON schema, Correlation ID propagation, Log enrichment, PII scrubbing |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Hợp lệ 100% dashboard contract 6 panel |
| `pytest` | 22 passed | 24 passed | 100% passed (24/24 tests) |
| Số traces hợp lệ | 0 (MISSING) | > 20 traces | Đủ quan hệ cha-con root observation, retrieval và generation |
| Số PII leak | 0 | 0 leak | Scrubbing triệt để email, SĐT VN, CCCD/CMND và thẻ tín dụng |
| Latency P95 / TTFT P95 | ~579.6 ms | ~427 ms / 50 ms | Đạt ngưỡng an toàn so với SLO target <= 3000 ms |
| Retrieval success rate | 100% | 100% | 100% tool retrieval thành công trên workload thông thường |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  - Middleware `CorrelationIdMiddleware` tự động sinh `correlation_id` (dạng `req-xxxx` qua `uuid4().hex[:8]`) nếu request header chưa có `X-Correlation-ID`, hoặc nhận giá trị từ header nếu có.
  - `correlation_id` được gán vào `request.state.correlation_id`, sau đó dùng `structlog.contextvars.bind_contextvars()` để tự động đính kèm vào mọi dòng log phát sinh trong suốt vòng đời xử lý request.
- **Các metadata được ghi vào structured log:**
  - Metadata ngữ cảnh: `service`, `event`, `level`, `ts` (ISO UTC), `env`, `feature`, `model`, `user_id_hash`, `session_id`, `correlation_id`.
  - Metadata hiệu năng & vận hành: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`, `payload`.
- **Cách bảo đảm PII được scrub trước khi ghi:**
  - Dùng module `app/pii.py` với các biểu thức chính quy (Regex) để nhận diện và thay thế:
    - Email $\rightarrow$ `[REDACTED_EMAIL]`
    - Số điện thoại VN (10 chữ số đầu 03/05/07/08/09 hoặc +84) $\rightarrow$ `[REDACTED_PHONE_VN]`
    - CCCD/CMND (9 hoặc 12 chữ số) $\rightarrow$ `[REDACTED_NATIONAL_ID]`
    - Thẻ tín dụng (13-19 chữ số theo thuật toán/pattern) $\rightarrow$ `[REDACTED_CREDIT_CARD]`
  - `user_id` không được log nguyên văn mà được băm SHA-256 (`hash_user_id`) lấy tiền tố an toàn. Hàm `summarize_text()` đảm bảo preview tin nhắn đã được scrub sạch trước khi đưa vào payload log.
- **Cách kiểm chứng kết quả:**
  - Chạy `pytest tests/test_pii.py` và `python scripts/validate_logs.py` đạt 100/100 (0 PII leaks).

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  - Khởi tạo Langfuse SDK trỏ trực tiếp vào Project cá nhân `day13-k4-l3b-2A202602969` thông qua `LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY` trong `.env`.
  - Mọi trace đều đính kèm tag định danh `["lab", feature, model]` và `environment=dev`.
- **Cấu trúc root/retrieval/generation observations:**
  - Root observation: `day13-agent-request` (span bao bọc request).
  - Agent observation: `lab-agent-run` (type `agent`).
  - Child observations lồng nhau:
    - `retrieval` (type `span`): thực hiện tìm kiếm tài liệu trong knowledge base.
    - `generation` (type `generation`): gọi LLM sinh câu trả lời, ghi nhận model, usage (input/output tokens), chi phí (cost USD) và liên kết Prompt object từ Langfuse.
- **Cách nối trace với log:**
  - Đặt `correlation_id` vào trường `metadata={"correlation_id": correlation_id}` của Langfuse trace và truyền qua `propagate_attributes`. Khi có sự cố, dùng `correlation_id` từ log để tra cứu chính xác trace trên Langfuse.
- **Prompt name:** `day13-chat` (Text prompt với 3 biến `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** Version 1 / Label `baseline`.
- **Version/label candidate:** Version 2 / Label `candidate`.
- **Trace ID của mỗi version:**
  - Trace ID của version 1 (baseline): `req-baseline-v1-001` (prompt_version: 1)
  - Trace ID của version 2 (candidate): `req-candidate-v2-002` (prompt_version: 2)
- **Cách promote và rollback `production`:**
  - **Promote:** Trên Langfuse UI (hoặc qua SDK), chuyển label `production` sang trỏ vào Version 2. Ứng dụng tự động fetch prompt v2 mà không cần sửa source code.
  - **Rollback:** Khi cần hoàn tác, chuyển label `production` quay trở về Version 1. Ứng dụng ngay lập tức quay lại sử dụng prompt v1 an toàn.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  - 1. **Latency:** Percentiles P50, P95, P99 và TTFT P95 theo thời gian (ngưỡng P95 <= 3000 ms).
  - 2. **Traffic:** Tần suất request trên phút (ngưỡng >= 1 req/min).
  - 3. **Errors & Retrieval:** Tỉ lệ lỗi tổng thể (ngưỡng <= 2%) và tỉ lệ tìm kiếm tài liệu thành công (ngưỡng >= 90%).
  - 4. **Cost:** Chi phí lũy kế theo USD (ngưỡng <= $2.50).
  - 5. **Tokens:** Tổng lượng token nạp vào (Input) và sinh ra (Output) (ngưỡng <= 50,000 tokens).
  - 6. **Quality:** Điểm chất lượng trung bình theo heuristic proxy (ngưỡng >= 0.75).
- **SLO và lý do chọn:**
  - SLO: `fast_successful_requests` với mục tiêu **99.5%** trong cửa sổ 28 ngày.
  - SLI: Tỉ lệ các request thành công (`event == "response_sent"`) và có độ trễ đạt chuẩn (`latency_ms <= 3000ms`) trên tổng số request nhận vào (`event == "request_received"`).
  - Lý do: Đảm bảo trải nghiệm người dùng không bị nghẽn mạng hoặc chờ quá 3 giây cho một câu trả lời từ AI.
- **Cách tính error budget:**
  - Với SLO 99.5% trong 28 ngày, Error Budget cho phép là $100\% - 99.5\% = 0.5\%$.
  - Nếu hệ thống nhận 10,000 requests trong 28 ngày, số lượng request tối đa được phép bị lỗi hoặc có độ trễ > 3000ms là: $10,000 \times 0.5\% = 50$ requests.
- **Ba alert và runbook tương ứng:**
  - 1. `HighLatencyP95` (Warning, P95 > 3000ms trong 5m): Cảnh báo chatbot phản hồi chậm.
  - 2. `HighErrorRate` (Critical, Error rate > 2% trong 3m): Cảnh báo hệ thống gặp sự cố phát sinh lỗi 500.
  - 3. `LowRetrievalSuccess` (Warning, Retrieval success < 90% trong 5m): Cảnh báo chất lượng ngữ cảnh tìm kiếm bị suy giảm.
  - Cả 3 runbook đều hướng dẫn điều tra 3 bước: Dashboard Metric $\rightarrow$ Log correlation_id $\rightarrow$ Langfuse Span.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** `03:51:56Z` – `03:52:12Z` (ngày 30/09/2026 UTC)
- **Triệu chứng từ metrics:** Panel Latency trên Dashboard cho thấy đường P95 Latency tăng vọt bất thường lên **4134 ms** (vượt ngưỡng SLO 3000ms), trong khi Error rate vẫn giữ ở mức 0%.
- **Log line và correlation ID liên quan:**
  - Dòng log: `{"service": "api", "latency_ms": 4134, "ttft_ms": 50, "tokens_in": 35, "tokens_out": 99, "cost_usd": 0.00159, "quality_score": 0.8, "tool_name": "retrieval", "tool_success": true, "event": "response_sent", "correlation_id": "req-087e8cb3"}`
  - `correlation_id`: `req-087e8cb3`
- **Trace ID và span gây ảnh hưởng:**
  - Trace ID: `dfdc210809946829248a44e808cdc389` (tương ứng `correlation_id: req-087e8cb3`)
  - Span gây ảnh hưởng: Span **`retrieval`** bị kéo dài bất thường hơn **2.50 giây** (chiếm 2.50s / 4.13s tổng thời gian xử lý của agent).
- **Root cause:** Kịch bản sự cố `rag_slow` được kích hoạt khiến hàm tìm kiếm vector retrieval bị sleep/chậm 2.5s trên mỗi truy vấn tài liệu, làm tổng thời gian phản hồi của agent vượt quá 4 giây.
- **Fix action:** Tắt sự cố bằng lệnh `POST /incidents/rag_slow/disable`, kiểm tra và tái khởi động kết nối cơ sở dữ liệu vector.
- **Preventive measure:** Bổ sung cơ chế Timeout & Circuit Breaker cho module retrieval (nếu quá 1.5s chưa có kết quả thì tự động chuyển sang fallback thay vì treo cả request), đồng thời kích hoạt cảnh báo `HighLatencyP95` qua kênh Slack để đội trực SRE can thiệp ngay.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  - Quyết định tách rời việc quản lý Prompt ra khỏi mã nguồn và quản lý qua Langfuse Managed Prompts theo các nhãn `production`, `candidate`, `baseline`.
  - Lý do: Cho phép đội ngũ vận hành cập nhật, thử nghiệm A/B hoặc rollback prompt ngay lập tức khi phát hiện hallucination hoặc chi phí token tăng mà không cần phải trải qua quy trình rebuild/redeploy source code phức tạp.
- **Một lỗi/blocker đã gặp:**
  - Khi bắn tải đồng thời (`--concurrency 5`), thời gian đo lường ở phía client (wall clock) tăng cao do hàng đợi kết nối, dẫn đến số liệu client khác với server.
- **Cách tìm nguyên nhân và xử lý:**
  - Đối chiếu giữa log đo lường ở server (`latency_ms` ghi nhận từ middleware/agent) và log của client; hiểu rõ sự khác biệt giữa server processing latency và network/queueing latency để đưa số liệu chính xác vào báo cáo điều tra.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics (Dashboard):** Là tín hiệu cảnh báo cấp cao (30,000 feet view) giúp phát hiện sự cố đang diễn ra ở đâu, thuộc nhóm nào (độ trễ, lỗi, chi phí) và có vi phạm SLO hay không.
  - **Logs:** Cung cấp thông tin chi tiết về từng sự kiện riêng lẻ, chứa metadata ngữ cảnh và `correlation_id` của các request bị lỗi/chậm trong khoảng thời gian xảy ra sự cố.
  - **Traces:** Cung cấp góc nhìn sâu nhất (cây phân cấp span) để bóc tách chính xác từng bước xử lý bên trong một request cụ thể, chỉ ra đích danh span/hàm nào (Retrieval hay LLM Generation) là thủ phạm gây chậm hoặc fail.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Giúp kiểm soát chi phí vận hành (tránh bùng nổ token/cost ngoài ý muốn), bảo đảm chất lượng cam kết với người dùng (qua SLO/Error budget) và cung cấp cơ chế cứu cánh (Rollback) an toàn khi một prompt mới gây suy giảm chất lượng hoặc tăng đột biến độ trễ.
- **Điều quan trọng nhất đã học:**
  - Nắm vững kiến trúc Observability hoàn chỉnh cho ứng dụng GenAI/LLMOps từ Structured Logging có che PII, Distributed Tracing với Langfuse, Dashboard 6 panel và tư duy điều tra sự cố chuẩn SRE.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Hiện tại hàm chất lượng câu trả lời vẫn dùng heuristic proxy đơn giản; trong tương lai có thể tích hợp LLM-as-a-judge bất đồng bộ để chấm điểm ngữ nghĩa chuẩn xác hơn.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
