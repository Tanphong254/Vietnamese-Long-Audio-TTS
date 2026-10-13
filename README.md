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

Mở tệp **`kichban.txt` ở thư mục gốc** của repository, bấm biểu tượng cây bút **Edit**, thay dòng `__DAN_NOI_DUNG_TRUYEN_VAO_DAY__` bằng toàn bộ nội dung truyện, rồi **Commit changes**. Bạn không cần tạo tệp mới mỗi lần; chỉ sửa nội dung trong `kichban.txt` trước khi chạy.

**Cảnh báo: repository này là Public nên nội dung `kichban.txt` được commit sẽ công khai.** Nếu truyện cần giữ riêng tư, hãy chuyển repository sang Private trước khi đưa nội dung thật vào tệp.

## Tạo audio trên GitHub

1. Mở tab **Actions** của repository.
2. Chọn workflow **Generate long audio** ở cột trái.
3. Bấm **Run workflow**.
4. Trong biểu mẫu chỉ cần chọn **giọng đọc** (Nam Minh hoặc Hoài My) và **tốc độ**. Nội dung luôn lấy từ `kichban.txt`; kích thước đoạn được xử lý tự động bên trong chương trình.
5. Bấm nút xanh **Run workflow**.
6. Mở lượt chạy vừa xuất hiện, chọn job **Generate Vietnamese audiobook** để xem log và tiến trình.
7. Khi hoàn thành, kéo xuống phần **Artifacts** ở trang chi tiết lượt chạy. Tải artifact `audio-output-...`, rồi giải nén để lấy tệp MP3.

## Tiếp tục khi tác vụ bị gián đoạn

Mỗi lượt chạy tìm checkpoint gần nhất còn hạn và tự động tiếp tục nếu văn bản trong `kichban.txt`, giọng đọc và tốc độ khớp với tác vụ đang dở. Bạn chỉ cần sửa `kichban.txt` khi muốn tạo audio cho nội dung mới, rồi chạy workflow với giọng/tốc độ mong muốn. Nếu checkpoint trước đã hết hạn hoặc tải lên thất bại, hãy chạy lại; các đoạn không có trong checkpoint sẽ cần tạo lại.

## Lỗi Edge-TTS 403

Nếu log có `WSServerHandshakeError: 403, message='Invalid response status'`, đây là lỗi bắt tay WebSocket từ dịch vụ Edge-TTS, không phải do độ dài tệp truyện. Lỗi tương tự đang được báo với `edge-tts 7.2.8` trong [upstream issue #490](https://github.com/rany2/edge-tts/issues/490).

Mã nguồn hiện dùng endpoint WebSocket thay thế đã được cộng đồng báo là hoạt động trong một số trường hợp. Đây là workaround chưa phải bản sửa chính thức; nếu Microsoft tiếp tục thay đổi dịch vụ, nó có thể cần cập nhật. Mỗi đoạn chỉ được thử lại hữu hạn để tránh lặp vô hạn.

Nếu upstream phát hành bản sửa chính thức, có thể bỏ cấu hình thay thế. Để ép dùng endpoint mặc định đi kèm thư viện, đặt biến môi trường `EDGE_TTS_WEBSOCKET_URL=default`. Để thử một endpoint khác, đặt biến này thành URL WebSocket đầy đủ.

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
