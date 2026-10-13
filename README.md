# Vietnamese Long Audio TTS — GitHub Actions

Tạo một tệp MP3 dài từ toàn bộ kichban.txt ngay trong giao diện GitHub Actions, theo cách dùng của repository Tanphong254/edge-tts. Không dùng Flask, không mở website riêng, không cần Codespaces.

## Cách hoạt động

- Bạn sửa file kichban.txt ở thư mục gốc của repository.
- Trong Actions → Generate long audio → Run workflow, chỉ chọn giọng đọc (Nam Minh/Hoài My) và tốc độ.
- Workflow đưa toàn bộ nội dung vào một edge_tts.Communicate và lưu thành một tệp outputs/audio_youtube.mp3.
- Repository không tự chia truyện thành hàng chục tác vụ MP3 và không ghép hàng chục MP3 lại sau đó. Edge-TTS có thể tự stream các phần văn bản bên trong thư viện theo giao thức của nó; đầu ra vẫn là một MP3 duy nhất.
- Nếu dịch vụ lỗi, chương trình thử lại hữu hạn số lần. Nếu lần chạy thất bại giữa chừng, phải chạy lại toàn bộ nội dung; không có checkpoint từng chương ở cấp ứng dụng.

## Chuẩn bị kichban.txt

Mở kichban.txt trong repository, bấm biểu tượng bút chì Edit, thay dòng hướng dẫn bằng toàn bộ nội dung truyện rồi Commit changes.

**Cảnh báo quyền riêng tư:** repository hiện là Public; mọi nội dung được commit trong kichban.txt sẽ công khai. Nếu truyện riêng tư, hãy chuyển repository sang Private trước khi đưa nội dung thật vào.

## Tạo audio

1. Mở tab Actions.
2. Chọn Generate long audio.
3. Bấm Run workflow.
4. Chỉ chọn giọng Nam Minh hoặc Hoài My, và tốc độ 0.75, 1.0, 1.25, 1.5 hoặc 1.75.
5. Bấm Run workflow.
6. Khi chạy thành công, mở trang chi tiết lượt chạy, tải artifact audio-output và giải nén để lấy audio_youtube.mp3.

## Lỗi Edge-TTS 403

Mã nguồn dùng tạm thời một endpoint WebSocket thay thế, do lỗi HTTP 403 đang được báo cáo trong upstream issue #490 của edge-tts. Đây là workaround cộng đồng, không phải sửa đổi chính thức của Microsoft; có thể cần cập nhật nếu dịch vụ thay đổi tiếp.

## Giới hạn thực tế

- Không đặt giới hạn ký tự tổng trong mã ứng dụng; văn bản được đọc từ tệp UTF-8.
- GitHub Actions vẫn giới hạn thời gian chạy; workflow có giới hạn 350 phút và lệnh tổng hợp dừng trước đó để có thời gian tải artifact.
- Nếu tổng hợp thất bại giữa chừng, cần chạy lại toàn bộ script; đây là đánh đổi của cách tạo một MP3 duy nhất.
- Edge-TTS cần Internet. Hạn mức GitHub Actions tùy tài khoản.
- Artifact đầu ra được lưu 14 ngày; hãy tải MP3 về máy sau khi hoàn thành.

## Kiểm thử

GitHub Actions chạy các bài kiểm thử mà không gọi dịch vụ tổng hợp trực tuyến; kiểm thử không chứng minh dịch vụ Edge-TTS luôn hoạt động.

## License

MIT. Edge-TTS và các thành phần bên thứ ba có giấy phép riêng.
