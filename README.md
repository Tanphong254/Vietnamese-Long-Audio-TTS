# Vietnamese Long Audio TTS

Công cụ chuyển văn bản tiếng Việt thành audio bằng giọng đọc Edge Neural. Có **giao diện web** để nhập văn bản, chọn giọng/tốc độ, xem thời gian tạo, nghe và tải audio; đồng thời vẫn giữ workflow GitHub Actions để tạo MP3 từ file \`kichban.txt\`.

## Giao diện web

Giao diện gồm khung nhập nội dung, chọn **Nam Minh / Hoài My**, chọn tốc độ, khu vực kết quả có đồng hồ thời gian chạy và lịch sử audio. Mỗi lần bấm **Tạo audio**, hệ thống cấp mã \`AU 1\`, \`AU 2\`, ... ngay khi nhận yêu cầu. Mã không được tính lại theo thứ tự hoàn tất: nếu \`AU 2\` xong trước \`AU 1\`, số AU vẫn giữ nguyên.

Khi tạo audio, lượt mới được xếp vào hàng đợi và tổng hợp lần lượt để hạn chế các yêu cầu đồng thời tới dịch vụ. Trạng thái hiển thị gồm đang chờ, đang tạo, hoàn tất hoặc thất bại. Khi thành công, có thể nghe trực tiếp hoặc tải MP3. Nội dung văn bản được lưu tạm trong cơ sở dữ liệu khi công việc đang chờ/xử lý và tự xóa khỏi bản ghi khi đã thành công hoặc thất bại; lịch sử vẫn giữ mã AU, giọng, tốc độ, trạng thái và đường dẫn audio.

### Chạy trên máy cá nhân

Cần Python 3.11 trở lên và kết nối Internet. Mở terminal tại thư mục repository rồi chạy:

\`\`\`bash
python -m pip install -r requirements.txt
python app.py
\`\`\`

Mở địa chỉ [http://127.0.0.1:5000](http://127.0.0.1:5000). Không cần chạy Flask bằng lệnh riêng nào khác. Audio và lịch sử mặc định được lưu trong thư mục runtime \`data/\`, thư mục này đã được thêm vào \`.gitignore\` để tránh commit nhầm audio hoặc cơ sở dữ liệu riêng tư.

### Đưa website lên Internet bằng Render

Repository có file [render.yaml](render.yaml) để triển khai dạng Blueprint trên Render:

1. Trong Render, chọn **New → Blueprint**, rồi kết nối repository này.
2. Khi được yêu cầu, đặt biến \`WEB_APP_PASSWORD\` thành một mật khẩu riêng, đủ mạnh. Không đăng nó trong mã nguồn hoặc trong file công khai.
3. Blueprint tạo web service cùng ổ đĩa lưu trữ bền vững ở \`/var/data\`. Ổ đĩa đó giữ lại lịch sử và MP3 qua các lần khởi động lại. Để đổi dung lượng, chỉnh \`sizeGB\` trong \`render.yaml\` trước khi triển khai.
4. Sau khi deploy, mở URL Render được cấp. Đăng nhập bằng mật khẩu bạn đã đặt.

**Lưu ý chi phí:** cấu hình Blueprint dùng web service và persistent disk; Render có thể tính phí cho các tài nguyên này. Hãy kiểm tra gói và giá hiện hành trong tài khoản Render trước khi tạo service.

**Bảo mật:** không công khai URL website cùng mật khẩu. Khi chạy trên Internet, ứng dụng từ chối truy cập nếu chưa cấu hình \`WEB_APP_PASSWORD\`. Cấu hình \`WEB_SESSION_SECRET\` được Blueprint tạo tự động. Audio được lưu trên ổ đĩa của service; chỉ người đã đăng nhập mới được nghe/tải qua website. Chỉ một tiến trình Gunicorn worker được sử dụng để tránh chạy trùng các tác vụ nền.

**Khả năng phục hồi:** tác vụ đang dở sẽ được xếp lại sau khi tiến trình ứng dụng khởi động lại; việc đó sẽ tổng hợp lại toàn bộ văn bản của AU đang dở, không tiếp tục từ đúng giây audio đã dừng. Các AU đã hoàn thành vẫn giữ nguyên mã và file nếu ổ đĩa bền vững còn dữ liệu.

## GitHub Actions (không cần mở website)

Nếu muốn chạy trực tiếp từ GitHub mà không dùng giao diện web:

1. Sửa file [\`kichban.txt\`](kichban.txt) ở thư mục gốc rồi commit.
2. Mở **Actions → Generate long audio → Run workflow**.
3. Chọn giọng Nam Minh hoặc Hoài My, chọn tốc độ, rồi chạy workflow.
4. Khi hoàn tất, mở lượt chạy và tải artifact \`audio-output\`.

Workflow Actions tạo một MP3 đầu ra từ toàn bộ file \`kichban.txt\`; Edge-TTS tự xử lý việc chia luồng văn bản nội bộ theo giao thức của nó. Lượt chạy này độc lập với thư viện AU được tạo trong giao diện web.

**Cảnh báo repository công khai:** \`kichban.txt\` hiện được Git theo dõi trong repository Public, nên nội dung trong file là công khai. Hãy chuyển repository sang Private hoặc loại bỏ văn bản nhạy cảm trước khi đưa truyện riêng tư lên GitHub.

## Lỗi Edge-TTS 403/429

Dịch vụ đọc trực tuyến của Edge đã thay đổi cách bắt tay WebSocket trong tháng 10/2026. Dự án đang ghim một commit của Edge-TTS upstream có hỗ trợ định dạng Sec-MS-GEC v2, thay vì ghép endpoint thay thế với thư viện dùng giao thức cũ. Xem [bản sửa upstream](https://github.com/rany2/edge-tts/pull/492).

Edge-TTS dùng dịch vụ trực tuyến không có API ổn định được Microsoft cam kết hỗ trợ; dịch vụ có thể thay đổi hoặc giới hạn yêu cầu bất cứ lúc nào. Mã HTTP 429 có thể là giới hạn phía dịch vụ. Nếu vẫn gặp 429, hãy chờ một lúc trước khi chạy lại; đừng liên tục thử lại cả truyện dài.

## Giới hạn thực tế

- Không đặt giới hạn số ký tự tổng trong ứng dụng web hoặc trình tạo audio. Tuy nhiên, dịch vụ tổng hợp vẫn có thể áp dụng giới hạn riêng.
- Tốc độ hiển thị chỉ là ước tính độ dài audio dựa trên số từ, không phải cam kết thời gian xử lý.
- Công việc audio dài phụ thuộc vào độ ổn định của dịch vụ Edge Neural, mạng và tài nguyên máy chủ. Ứng dụng không có phần trăm tiến độ chính xác từ dịch vụ, vì vậy hiển thị trạng thái cùng đồng hồ thời gian thay vì phần trăm giả.
- Với GitHub Actions, thời gian chạy và thời hạn lưu artifact phụ thuộc giới hạn GitHub Actions. Artifact audio của workflow hiện giữ 14 ngày.

## Kiểm thử

GitHub Actions chạy bộ kiểm thử tự động trên Python 3.11, 3.12 và 3.13. Các bài kiểm thử xác nhận logic ứng dụng và luồng tạo việc; chúng không thể chứng minh dịch vụ Edge-TTS trực tuyến luôn sẵn sàng.

## License

MIT cho mã nguồn của repository. Edge-TTS và các thành phần bên thứ ba có giấy phép riêng.
