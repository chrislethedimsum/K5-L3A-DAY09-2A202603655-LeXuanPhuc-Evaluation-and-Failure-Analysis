# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có (`{tp: 24, fp: 4, fn: 6, tn: 66}`; obs=0.28 → RG=0.30) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không (`{tp: 9, fp: 0, fn: 21, tn: 70}`; obs=0.09 → RG=0.30) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | `tone_ok` `H-008` ("Em đã hoàn tiền cho anh rồi nha, anh check giúp em.") | PASS | FAIL | Người | Xưng "em/anh" + "nha" quá suồng sã; sửa rubric `tone_ok` cấm đại từ suồng sã và từ đệm "nha/nhé". |
| 2 | `tone_ok` `H-029` ("Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm.") | PASS | FAIL | Người | Giọng ra lệnh ("không cần nhắn thêm") dù mở đầu có "Dạ, vui lòng"; bổ sung negative example giọng ra lệnh vào rubric. |
| 3 | `tone_ok` `H-051` ("Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ.") | FAIL | PASS | Người | Dùng "refund" được CS LogiX cho phép; cập nhật whitelist thuật ngữ tiếng Anh hợp lệ trong rubric. |
| 4 | `tone_ok` `H-081` ("Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ.") | FAIL | PASS | Judge | Nhãn người gán nhầm do đọc nhầm ticket; cần sửa lại nhãn ground-truth của `H-081`. |
| 5 | `helpful` `HL-015` ("Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ.") | PASS | FAIL | Người | Ledger thực tế ghi `40.000đ` (lỗi `FM-08`); judge không có dữ liệu ledger nên chấm PASS. Hành động: **bỏ judge `helpful`, thay bằng code grader đối chiếu ledger**. |
| 6 | `helpful` `HL-016` ("...thành thật xin lỗi... LogiX đã hoàn 55.000đ cho đơn O-404...") | PASS | FAIL | Người | Văn phong dài dòng/lịch sự đánh lừa judge (`sycophancy/verbosity bias`) dù ledger ghi `35.000đ`; bắt buộc tách kiểm tra số tiền sang code grader. |

## Kết luận
- **Tiêu chí bị loại:** `helpful` bị **loại** khỏi gate vì $\kappa = 0.375 < 0.6$ và Recall chỉ đạt $0.300 < 0.7$. Nhìn ma trận nhầm lẫn (`tp=9, fp=0, fn=21, tn=70`), judge bỏ sót tới 21/30 ca lỗi thật (`FN=21`), làm tỉ lệ lỗi quan sát bị đánh giá thấp giả tạo (9% so với 30% sau hiệu chỉnh Rogan-Gladen). Nguyên nhân chính: các ca sai tiền (`HL-015`, `HL-016`, `HL-020`...) vẫn được viết lịch sự/dài dòng nên judge cho PASS. Tiêu chí tính đúng số tiền phải chuyển sang **code grader** (M3, FM-08), còn `tone_ok` đạt cả 3 ngưỡng FLOORS ($\kappa=0.757, P=0.857, R=0.800$) nên dùng được kèm cập nhật rubric.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
