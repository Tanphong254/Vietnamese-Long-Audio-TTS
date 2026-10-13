# Vietnamese Long Audio TTS — GitHub Actions

Tạo audio truyện dài tiếng Việt bằng Edge-TTS **ngay từ giao diện GitHub Actions**. Bạn không cần chạy Flask hay mở website riêng, và không cần cài Python trên máy tính cá nhân để chạy tác vụ.

> **Quan trọng về quyền riêng tư:** Repository này đang Public. Mọi tệp truyện được commit vào repository, cùng các checkpoint artifact được tạo ra, có thể được người khác truy cập. Chỉ sử dụng quy trình này với văn bản bạn sẵn sàng công khai. Với truyện riêng tư, hãy chuyển repository sang Private trước khi tải văn bản lên. Đừng đưa truyện riêng tư vào artifact của một repository công khai.

Edge-TTS cần Internet để gọi dịch vụ giọng nói trực tuyến. GitHub Actions có giới hạn thời gian, giới hạn artifact và điều khoản sử dụng theo tài khoản; không bảo đảm mọi tác vụ đều hoàn tất nếu dịch vụ mạng gặp lỗi.

## Tính năng

- Khởi chạy từ **Actions → Generate long audio → Run workflow**.
- Chỉ có hai giọng tiếng Việt: **Nam Minh** (`vi-VN-NamMinhNeural`) và **Hoài My** (`vi-VN-HoaiMyNeural`); tốc độ từ 0.75x đến 1.75x.
- Chia văn bản dài thành đoạn, xử lý tuần tự và ghép thành MP3.
- Lưu audio từng đoạn trong lúc chạy; có thể khôi phục từ checkpoint artifact sau khi tác vụ thất bại.
- Tải MP3 cuối cùng qua artifact audio-output.
- Tác vụ tối đa 330 phút cho mỗi lần chạy, phụ thuộc vào giới hạn của GitHub Actions và dịch vụ Edge-TTS.

## Chuẩn bị tệp truyện

1. Tạo thư mục input trong repository nếu chưa có.
2. Thêm tệp TXT mã hóa UTF-8 vào đó, ví dụ input/kichban.txt.
3. Commit tệp lên branch main.

**Repository Public nghĩa là tệp truyện trong repository cũng công khai.** Nếu không muốn nội dung truyện bị công khai, đừng tải tệp truyện lên repository Public. Hãy đổi repository sang Private trước khi thêm nội dung. Trường source_file là đường dẫn tệp đã tồn tại trên branch, không phải hộp thoại tải tệp trong giao diện Run workflow.

## Tạo audio trên GitHub

1. Mở tab **Actions** của repository.
2. Chọn workflow **Generate long audio** ở cột trái.
3. Bấm **Run workflow**.
4. Chọn branch main, rồi nhập:
   - **task_mode:** new
   - **source_file:** input/kichban.txt
   - **title:** tên truyện (tùy chọn)
   - **voice:** Nam Minh hoặc Hoài My
   - **rate:** 0.75, 1.0, 1.25, 1.5 hoặc 1.75
   - **chunk_size:** 1200, 1800, 2400 hoặc 3000
5. Bấm nút xanh **Run workflow**.
6. Mở lượt chạy vừa xuất hiện, chọn job **Generate Vietnamese audiobook** để xem log và tiến trình. Không cần giữ tab trình duyệt mở, nhưng lượt chạy sẽ bị giới hạn thời gian.
7. Khi hoàn thành, kéo xuống phần **Artifacts** ở trang chi tiết lượt chạy. Tải artifact có tên bắt đầu bằng audio-output, rồi giải nén để lấy tệp MP3.

## Tiếp tục khi tác vụ bị gián đoạn

Khi lượt chạy thất bại, workflow sẽ cố tải artifact tts-checkpoint lên trong 7 ngày. Artifact này có trạng thái tác vụ và các đoạn MP3 đã sinh ra để khôi phục tiến trình. Giữ lại tệp đầu vào gốc trên repository và không xóa artifact trước khi tiếp tục.

1. Mở trang chi tiết của lượt chạy bị lỗi.
2. Trong log của job, tìm dòng “Mã tác vụ:” và sao chép mã gồm 32 ký tự hex.
3. Sao chép **Run ID** từ URL trang chạy. Ví dụ URL có dạng https://github.com/OWNER/REPO/actions/runs/1234567890, thì 1234567890 là Run ID.
4. Vào **Actions → Generate long audio → Run workflow**, chọn:
   - **task_mode:** resume
   - **resume_job_id:** mã tác vụ từ log
   - **restore_run_id:** Run ID của lượt chạy trước
5. Bấm **Run workflow**. Workflow khôi phục artifact rồi tiếp tục tác vụ và giữ các đoạn MP3 hợp lệ.

Nếu lượt chạy trước không có artifact tts-checkpoint hoặc artifact đã hết hạn, việc resume sẽ không thực hiện được. Đừng xóa một lượt chạy đang cần dùng để khôi phục.

## Kiểm thử

Workflow Tests chạy tự động khi đẩy thay đổi lên main hoặc tạo Pull Request. Các bài kiểm thử cốt lõi dùng engine giả, không gửi nội dung thử lên dịch vụ Edge-TTS.

## Các giới hạn cần biết

- GitHub Actions không có trường tải lên file TXT dài trực tiếp trong form Run workflow; đầu vào phải nằm ở một nguồn có thể truy cập.
- Thời gian tạo phụ thuộc mạng, dịch vụ Edge-TTS, số đoạn và mức giới hạn runner.
- Checkpoint có chứa văn bản nguồn và MP3 từng đoạn. Artifact của repository Public không phù hợp để lưu nội dung riêng tư.
- Tải MP3 về máy sau khi hoàn tất; artifact có thời hạn lưu trữ 14 ngày.
- Đây là dự án cộng đồng độc lập, không được Microsoft bảo trợ.

## License

MIT. Các thư viện/binary bên thứ ba có giấy phép riêng.
