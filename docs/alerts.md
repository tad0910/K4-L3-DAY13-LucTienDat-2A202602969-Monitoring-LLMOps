# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-2A202602969`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLI độ trễ phản hồi (`response_sent.latency_ms <= 3000ms`), mục tiêu SLO 99.5%
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` duy trì liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng bị chậm khi nhận câu trả lời, trải nghiệm tương tác chatbot bị gián đoạn hoặc đơ
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Mở panel Latency trên Dashboard để đối chiếu đường P95/P99 và TTFT, xác định chính xác thời điểm độ trễ tăng đột biến.
  2. **Logs:** Truy vấn file `data/logs.jsonl` lọc các sự kiện `response_sent` có `latency_ms > 3000`, trích xuất `correlation_id` đại diện.
  3. **Traces:** Tìm trace trên Langfuse theo `correlation_id` tương ứng, kiểm tra xem độ trễ cao nằm ở span `retrieval` (vector store chậm) hay span `generation` (LLM sinh token chậm).
- Mitigation tạm thời: Tắt scenario mô phỏng làm chậm RAG nếu đang test, hoặc chuyển hướng model/vector store sang cấu hình dự phòng.
- Owner: `student-2A202602969`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỉ lệ lỗi tổng thể của hệ thống (`count(request_failed) / count(request_received) * 100 <= 2%`)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` duy trì trong 3 phút
- Ảnh hưởng tới người dùng: Người dùng nhận thông báo lỗi HTTP 500 hoặc không nhận được câu trả lời từ hệ thống
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Kiểm tra panel Errors trên Dashboard để xác định tỉ lệ lỗi và các loại `error_type` phổ biến (ví dụ `RuntimeError`, `RateLimitError`).
  2. **Logs:** Mở `data/logs.jsonl` lọc các dòng có `event == "request_failed"`, xem trường `payload.detail` và lấy `correlation_id` của request lỗi.
  3. **Traces:** Tra cứu `correlation_id` trên Langfuse để xem span nào bị đánh dấu đỏ/lỗi (như `retrieval` fail hoặc API key LLM invalid).
- Mitigation tạm thời: Khởi động lại service, chuyển sang prompt/model fallback hoặc kiểm tra tính sẵn sàng của cơ sở dữ liệu tri thức.
- Owner: `student-2A202602969`

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Guardrail tỉ lệ tìm kiếm tài liệu thành công (`retrieval_success_rate_pct_min: 90%`)
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90%` duy trì trong 5 phút
- Ảnh hưởng tới người dùng: Chất lượng câu trả lời bị suy giảm do chatbot phải dùng câu trả lời fallback khi không tìm thấy tài liệu ngữ cảnh
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Xem panel Errors & Retrieval trên Dashboard để đối chiếu đường `tool_success_rate_pct` so với ngưỡng 90%.
  2. **Logs:** Lọc `data/logs.jsonl` tìm các log có `tool_name == "retrieval"` và `tool_success == false`, lấy `correlation_id`.
  3. **Traces:** Mở Langfuse trace để kiểm tra chi tiết span `retrieval` xem lỗi do timeout vector database hay do câu truy vấn không khớp corpus.
- Mitigation tạm thời: Reset kết nối vector database hoặc kích hoạt cache kết quả tìm kiếm cục bộ.
- Owner: `student-2A202602969`
