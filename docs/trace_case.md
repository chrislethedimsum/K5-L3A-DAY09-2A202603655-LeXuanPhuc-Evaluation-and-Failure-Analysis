# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi nhóm 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261117-6885` (đối chứng: `fixed C-002@11`, `E-fixed-20261117-6885`) |
| Triệu chứng | `lab8 grader` báo `FAIL (status resolved != denied)`. Reply step 6 nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."`, `refund_ledger` ghi `refund_vnd=20000`, `refund_count=1` trong khi `label` là `refund_vnd=0`, `refund_count=0`, `status=denied`. |
| Bước sai đầu tiên | Event `3` (`model_override`): `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Step 1 (`handoff`) khởi tạo đúng phạm vi `owner_order_only` và các tool được phép; step 2 (`investigator`) tra cứu đúng đơn `O-202` từ DB với `status="delivered"`, `delay_days=2` (không đủ ngưỡng 3 ngày của `SHIP-LATE-03`). Đến step 3, agent mới lấy `5` ngày trong ticket ghi đè `delay_days=2` của DB, kéo theo step 4 `quote` tính sai `amount_vnd=20000` và chi tiền ở ledger. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11`: sau step 2 (`investigator`), **không có** event `model_override`; step 3 đi thẳng vào `quote` với `amount_vnd=0`, `reason="no_entitlement"`, step 4 `reply` từ chối đúng, `ledger=0`, `status=denied` (`PASS`). |
| Regression test | `test_c002_seed11_rejects_ticket_delay_override` trong `src/tests/test_lab9_trace_case.py` — assert `fixed` pass (không có `model_override`, `refund_vnd == 0`) và `seeded_regression` bị bắt lỗi (`lab8_pass is False`, có `model_override` và `refund_vnd != 0`). |
| Chưa chắc chắn | Trace MockLLM chỉ chứng minh được nhánh code tin ticket trên seed cố định; chưa đo được trên LLM thật tỷ lệ model bị prompt trong ticket đánh lừa khi có ngữ cảnh phức tạp hơn. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
