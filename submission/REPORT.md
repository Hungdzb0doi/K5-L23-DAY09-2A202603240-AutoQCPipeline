# Báo cáo Day 09 — Phạm Mạnh Hùng, 2A202603240

## 1. Kết luận trước
Pipeline đưa ra quyết định **Hold** đối với lô dữ liệu kiểm thử. Trong tổng số 224 ảnh thô ban đầu, bước Intake đã loại bỏ 22 ảnh không đạt chuẩn (ảnh hỏng, sai kích thước, ảnh trùng và rò rỉ sang tập test), tiếp nhận 202 ảnh hợp lệ vào quy trình kiểm tra nhãn và cuối cùng xuất đủ 202 ảnh sang bộ dữ liệu sạch `submission/export/clean_v1`. Toàn bộ các lỗi nghiêm trọng (severity ERROR) đã được xử lý triệt để (0 lỗi còn lại), tuy nhiên tỷ lệ ảnh còn cảnh báo nghi ngờ là 21.78% (44/202 ảnh), vượt quá ngưỡng cho phép 10.00% do ngân sách người duyệt bị giới hạn ở 80 ảnh.

## 2. Lỗi và phân việc
Tổng hợp các lỗi phát hiện trước khi sửa từ báo cáo `02_error_list_v1`:

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `BAD_CLASS_ID` | 6 dòng | Máy (autofix) | ID lớp ngoài dải [0, 3], máy tự xóa dòng lỗi an toàn (`drop_line`). |
| `BAD_CLASS_NAME` | 2 tên | Máy (autofix) | Tên lớp trong `data.yaml` bị viết hoa ('Person', 'Bus'), máy chuẩn hóa lại theo `cfg["classes"]`. |
| `BAD_FORMAT` | 3 dòng | Máy (autofix) | Sai định dạng cú pháp (chứa `nan`/`inf`, thiếu cột), máy xóa dòng hỏng (`drop_line`). |
| `BAD_SIZE` | 3 ảnh | Máy (autofix) | Cạnh ngắn ảnh < 250px không đạt chuẩn kích thước, máy loại bỏ ảnh (`remove_image`). |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy (autofix) | Box tràn ra ngoài biên ảnh quá mức cho phép (tol 0.002), máy cắt gọt về [0, 1] (`clip_box`). |
| `BOX_ZERO` | 4 dòng | Máy (autofix) | Kích thước box có chiều rộng hoặc chiều cao $\le 0$, máy xóa dòng rác (`drop_line`). |
| `CORRUPT_IMAGE` | 2 ảnh | Máy (autofix) | File ảnh bị hỏng cấu trúc không thể đọc được, máy loại bỏ ảnh (`remove_image`). |
| `DUP_BOX` | 7 dòng | Máy (autofix) | Trùng lặp cùng lớp trong cùng một ảnh ($IoU > 0.9$), máy xóa dòng trùng phía sau (`drop_line`). |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy (autofix) | Trùng khớp từng byte mã băm MD5 với ảnh trước, máy xóa ảnh trùng (`remove_image`). |
| `DUP_IMAGE_NEAR` | 4 ảnh | Máy (autofix) | Trùng gần đúng theo pHash (khoảng cách $\le 10$), máy xóa ảnh trùng (`remove_image`). |
| `LEAK_TEST` | 5 ảnh | Máy (autofix) | Trùng ảnh với kho test/val, vi phạm rò rỉ dữ liệu, máy xóa ảnh (`remove_image`). |
| `MISSING_LABEL_FILE` | 6 ảnh | Người (hàng đợi) | Thiếu file nhãn, máy không được tự đoán/bịa nhãn, bắt buộc con người mở ảnh gán nhãn thật. |
| `BOX_HUGE` | 3 dòng | Người (hàng đợi) | Box chiếm diện tích > 95% ảnh, cần người thẩm định là vật thể lớn thật hay box rác phủ toàn ảnh. |
| `BOX_TINY` | 6 dòng | Người (hàng đợi) | Cạnh ngắn box < 12px, cần mắt người xác nhận là vật thể nhỏ ở xa hay nhiễu nền. |
| `CLASS_RARE` | 4 ảnh | Người (hàng đợi) | Lớp xuất hiện quá ít (< 5 box), cần người giám sát độ mất cân bằng dữ liệu. |
| `EMPTY_LABEL` | 12 ảnh | Người (hàng đợi) | File nhãn rỗng, cần người xác nhận là ảnh nền (background) hay do người gán bỏ quên. |
| `POSSIBLE_FALSE_POS` | 29 dòng | Người (hàng đợi) | Box nhãn không khớp dự đoán nào của model lớn, nghi ngờ người gán vẽ nhầm vào vùng nền. |
| `POSSIBLE_LOOSE_BOX` | 31 dòng | Người (hàng đợi) | Box nhãn vẽ lệch/lỏng so với model ($IoU < 0.5$), cần người căn chỉnh lại biên viền. |
| `POSSIBLE_MISSING` | 68 dòng | Người (hàng đợi) | Model lớn phát hiện vật thể mà nhãn người bị bỏ sót, cần người bổ sung box. |
| `POSSIBLE_WRONG_CLASS` | 18 dòng | Người (hàng đợi) | Nghi ngờ nhầm lẫn giữa các lớp hợp lệ (xe tải/xe buýt/ô tô), cần người phân biệt ngữ nghĩa. |

**Giải thích thứ tự hàng đợi `05_review_queue.csv`:**
Hàng đợi sắp xếp theo điểm ưu tiên giảm dần. Đứng đầu là các ảnh kết hợp nhiều lỗi nặng như `img_0020` (priority 14.528, dính `FIXED_DROP_LINE`, `POSSIBLE_MISSING`, `POSSIBLE_WRONG_CLASS`), `img_0185` (priority 10.052), và 6 ảnh dính `NEEDS_LABEL` (đều có trọng số cao nhất là 10.0 gồm `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`). Việc đẩy các ảnh thiếu nhãn lên đầu là bắt buộc vì nếu người không gán nhãn cho các ảnh này thì lỗi ERROR vẫn còn và pipeline chắc chắn bị Rework.

Với ngân sách duyệt tối đa 80 ảnh, con người đã xem và sửa toàn bộ 6 ảnh thiếu nhãn cùng 74 ảnh có cảnh báo ngữ nghĩa nghiêm trọng nhất, giúp loại bỏ hoàn toàn các lỗi sai lớp và sót nhãn nặng trên các ảnh này.

## 3. Calibration (2 ngưỡng)
Bảng kết quả hiệu chuẩn trên tập dữ liệu mẫu `data/calib/`:

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 10 | 1.00 / 0.50 → 1.00 / 0.67 (F1: 0.67 → 0.80) | Ngưỡng 2 quá khắt khe, bỏ sót 50% ảnh gần trùng. Tăng lên 10 giúp Recall tăng lên 67% mà vẫn giữ Precision tuyệt đối 1.00 (không xóa nhầm ảnh thật). Tránh chọn 16 vì dễ xóa nhầm trên ảnh thật. |
| `second_opinion.conf` | 0.25 | 0.5 | P/R MISSING: 0.50 / 1.00 → 0.57 / 1.00<br>P/R WRONG_CLASS: 0.56 / 0.83 → 0.56 / 0.83 | Ngưỡng 0.25 khiến model cảnh báo quá nhạy, sinh nhiều báo động giả (Precision MISSING chỉ 50%) làm tràn hàng đợi. Nâng lên 0.5 giúp giảm tải cho người duyệt mà vẫn giữ trọn vẹn 100% Recall cho MISSING và 83% cho WRONG_CLASS. |

**Một chỗ calibration có thể đánh lừa bạn:**
Tập `data/calib/` chỉ có 39 ảnh với các lỗi được chèn nhân tạo theo quy luật đơn giản. Trong bảng sweep, `phash_dist = 16` cho F1 cao nhất (0.91, Recall 83%). Tuy nhiên, nếu áp dụng ngưỡng 16 vào tập dữ liệu thật (`raw` 224 ảnh) có nhiều góc phố tương đồng, khoảng cách 16 quá lỏng sẽ khiến thuật toán gộp nhầm các ảnh chụp cùng khu vực thành ảnh trùng và tự động xóa nhầm ảnh hợp lệ. Do đó, việc chọn ngưỡng an toàn `10` là sự đánh đổi cần thiết giữa lý thuyết calib và thực tế triển khai.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Chứng minh cửa chặn Gate hoạt động chính xác:**
Khi tiến hành thử nghiệm chạy pipeline với ngân sách người duyệt bằng 0 bằng lệnh:
`python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`
Do không có người can thiệp gán nhãn, 6 ảnh thiếu file nhãn (`MISSING_LABEL_FILE`) không được xử lý và vẫn còn nguyên trong danh sách lỗi v3. Cửa chặn Gate đã phát hiện 6 lỗi bắt buộc (`n_errors = 6`), ra phán quyết **Rework**, trả về mã thoát lệnh `$LASTEXITCODE = 20`, và hệ thống **hoàn toàn từ chối xuất dữ liệu** (thư mục `work/exp_nb/clean_v1` không được tạo ra). Điều này chứng minh cửa chặn đã thực sự hoạt động để bảo vệ chất lượng dữ liệu.

**(b) Các điểm mù mà pipeline không bắt được:**
1. *Box vẽ lệch hoặc lỏng ở mức độ nhẹ:* Các box có $IoU$ với vật thể thật trong khoảng 0.50 đến 0.65 sẽ không bị cắm cờ `POSSIBLE_LOOSE_BOX` (do quy ước $IoU \ge 0.5$ đã được coi là bao phủ vật thể), dẫn đến các box chưa khít vẫn lọt vào tập dữ liệu.
2. *Lỗi ngữ nghĩa mà chính mô hình lớn cũng nhận định sai:* Ví dụ xe bán tải (pickup truck) hoặc xe van nhỏ bị người gán nhãn là `car`, và mô hình `yolo26l` cũng nhận diện là `car` với độ tin cậy cao. Khi cả người và mô hình kiểm tra cùng mắc sai lầm, pipeline hoàn toàn không thể phát hiện ra lỗi này.
3. *Ảnh trùng bị cắt xén quá lớn hoặc thay đổi góc chụp:* Các trường hợp ảnh chụp cùng một cảnh nhưng bị zoom cắt trên 60% làm pHash sai khác vượt quá khoảng cách 10, khiến ảnh bị trùng lặp nội dung vẫn lọt qua bước lọc Intake.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy (tùy chọn, chấm riêng 15 điểm). 
Lý do: Tập trung nguồn lực hoàn thiện triệt để 4 module kiểm tra chất lượng nhãn, quy trình hiệu chuẩn và phân tích báo cáo dữ liệu cục bộ; chưa cấu hình môi trường GPU Google Colab cho việc huấn luyện mô hình YOLO26n lặp lại theo nhiều seed. Bài nộp được nghiệm thu theo phạm vi kiểm tra cốt lõi (`check-core`).

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối cùng:**
Quyết định cuối cùng của pipeline là **Hold**. 
Để chuyển trạng thái này thành **Release**, dự án cần cấp thêm ngân sách để con người tiếp tục thẩm định 44 ảnh còn lại trong hàng đợi cảnh báo, hoặc người quản lý dự án rà soát nhanh 44 cảnh báo này và chấp thuận rằng mức độ rủi ro là chấp nhận được trước khi đưa vào huấn luyện mô hình.


