# Vietnamese Long Audio TTS

Ứng dụng web chạy cục bộ trên Windows, chuyển tiểu thuyết tiếng Việt thành audio MP3 dài bằng [Edge-TTS](https://github.com/rany2/edge-tts). Dự án hướng tới các bản đọc 1,5–2,5 giờ hoặc lâu hơn bằng cách chia văn bản thành từng đoạn, lưu tiến trình xuống đĩa và ghép audio bằng FFmpeg.

> **Lưu ý:** Edge-TTS sử dụng dịch vụ giọng nói trực tuyến của Microsoft Edge và cần Internet. Đây không phải TTS hoàn toàn ngoại tuyến. Dự án không liên kết hoặc được Microsoft bảo trợ.

## Tính năng

- Giao diện tiếng Việt chạy tại `http://127.0.0.1:5000`.
- Giọng `vi-VN-NamMinhNeural` và `vi-VN-HoaiMyNeural`.
- Tốc độ đọc 0.75x, 1.0x, 1.25x, 1.5x và 1.75x.
- Dán văn bản hoặc tải tệp `.txt` có mã hóa UTF-8/UTF-8 BOM.
- Chia đoạn theo dấu câu, dòng và đoạn văn; giữ nguyên thứ tự và ký tự văn bản.
- Worker nền xử lý tuần tự, thử lại lỗi tạm thời tối đa 3 lần.
- Lưu audio của từng đoạn và trạng thái công việc vào `jobs/`.
- Tiếp tục tác vụ đang chạy dở sau khi khởi động lại chương trình; bỏ qua audio đoạn còn hợp lệ.
- Hủy tác vụ sau khi đoạn đang xử lý kết thúc; tiếp tục/thử lại tác vụ bị hủy hoặc thất bại.
- Ghép các đoạn MP3 thành một tệp duy nhất trong `outputs/` bằng FFmpeg.
- Hỗ trợ FFmpeg có trong PATH hoặc binary do `imageio-ffmpeg` cung cấp.
- Tệp văn bản truyện, tác vụ, audio và môi trường ảo được loại khỏi Git bằng `.gitignore`.

## Cài đặt nhanh trên Windows

1. Khuyến nghị cài Python 3.12 hoặc 3.13 từ [python.org](https://www.python.org/downloads/windows/). CI của dự án kiểm thử Python 3.11–3.13; Python 3.14 chưa được CI xác nhận. Bật Python Launcher nếu trình cài đặt có tùy chọn đó.
2. Tải hoặc clone repository về máy.
3. Nhấp đúp `run.bat`. Lần đầu, tập lệnh sẽ tạo `.venv`, cài thư viện trong `requirements.txt` và khởi động ứng dụng.
4. Mở `http://127.0.0.1:5000` trong trình duyệt.
5. Để dừng ứng dụng, quay lại cửa sổ terminal và nhấn `Ctrl+C`.

Nếu `run.bat` không tìm thấy Python, mở PowerShell tại thư mục dự án và kiểm tra:

```powershell
py -3 --version
```

Nếu lệnh hoạt động, có thể cài và chạy thủ công:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Nếu lệnh `py` cũng không được nhận diện, cài Python và mở lại VS Code/Terminal. Nếu đã đổi `requirements.txt` sau lần cài đầu tiên, chạy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Cách sử dụng

1. Nhập tên truyện, rồi dán văn bản hoặc chọn tệp TXT.
2. Chọn giọng đọc, tốc độ và độ dài đoạn (mặc định 2.400 ký tự). Đoạn ngắn hơn có thể giảm rủi ro lỗi dịch vụ nhưng tạo ra nhiều yêu cầu hơn.
3. Nhấn **Tạo audio truyện**. Worker chạy nền; trạng thái cập nhật trên giao diện.
4. Khi tất cả đoạn thành công, ứng dụng tự ghép MP3. Tải tệp hoàn chỉnh trong khu vực kết quả.
5. Nếu tác vụ thất bại, đọc thông báo, kiểm tra Internet rồi chọn **Thử lại / tiếp tục**. Các đoạn MP3 hợp lệ được giữ lại.

## Dữ liệu nằm ở đâu?

- `jobs/<job_id>/source.txt`: văn bản nguồn của tác vụ.
- `jobs/<job_id>/status.json`: trạng thái và thông tin từng đoạn.
- `jobs/<job_id>/segments/`: MP3 từng đoạn.
- `outputs/`: MP3 hoàn chỉnh.

Các đường dẫn này nằm trên máy cục bộ. Không đưa truyện riêng tư, tệp MP3 hoặc dữ liệu trong `jobs/`/`outputs/` lên repository công khai. Dự án có `.gitignore` để loại chúng khỏi Git mặc định; hãy kiểm tra `git status` trước khi commit.

## Khôi phục và giới hạn

- Tác vụ đang chờ/đang chạy/đang ghép khi chương trình tắt bất ngờ sẽ được đưa lại vào hàng đợi khi mở ứng dụng.
- Tác vụ đã đánh dấu `failed` hoặc `cancelled` cần người dùng bấm thử lại/tiếp tục.
- Các đoạn được lưu riêng để hạn chế phải tổng hợp lại toàn bộ truyện. Nếu tệp đoạn bị hỏng hoặc rỗng, nó sẽ được tạo lại.
- Tiến trình phản ánh số đoạn đã tạo thực tế. Trong lúc ghép MP3, phần trăm hiển thị 98% cho tới khi tệp hoàn chỉnh được kiểm tra.
- Tốc độ thực tế phụ thuộc dịch vụ Edge-TTS, độ dài nội dung, mạng và giới hạn dịch vụ. Không thể bảo đảm mọi tác vụ dài đều hoàn thành trong một lần.
- Ứng dụng chỉ bind vào `127.0.0.1`, không bật Flask debug server và không có xác thực người dùng. Không chỉnh host sang `0.0.0.0` nếu không triển khai thêm các biện pháp bảo mật.
- Giới hạn hiện tại: tối đa 20 triệu ký tự cho mỗi tác vụ và 100 MiB cho một yêu cầu HTTP.

## Kiểm thử

```powershell
py -3 -m pip install -r requirements-dev.txt
py -3 -m pytest -q
```

Các kiểm thử tự động không gửi nội dung lên Edge-TTS và không xác minh chất lượng giọng nói trực tuyến. Để kiểm tra tích hợp thực tế, hãy tạo một tác vụ thử ngắn khi có Internet.

## Tạo repository Public trên GitHub

1. Mở [GitHub New repository](https://github.com/new), đặt tên `Vietnamese-Long-Audio-TTS` và chọn **Public**.
2. Không chọn khởi tạo README, `.gitignore` hoặc license trên GitHub (những tệp đó đã có sẵn trong dự án).
3. Mở terminal trong thư mục dự án và chạy lệnh sau, thay `<YOUR_GITHUB_USERNAME>` bằng tên tài khoản GitHub của bạn:

```powershell
git init
git add .
git status
git commit -m "Initial Vietnamese Long Audio TTS project"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/Vietnamese-Long-Audio-TTS.git
git push -u origin main
```

Trước khi `git commit`, hãy xem `git status` để xác nhận không có truyện, audio, `.venv` hoặc dữ liệu tác vụ trong danh sách. Nếu Git chưa được cài đặt, cài [Git for Windows](https://git-scm.com/download/win) rồi mở Terminal mới.

## Công nghệ

- Python, Flask
- Edge-TTS
- FFmpeg / imageio-ffmpeg
- HTML, CSS, JavaScript
- pytest cho kiểm thử phần lõi

## License

MIT. Các thành phần phụ thuộc có giấy phép riêng; hãy xem thông tin license tương ứng của từng dự án, đặc biệt khi phân phối binary FFmpeg.
