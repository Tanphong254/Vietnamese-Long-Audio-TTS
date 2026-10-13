# Vietnamese Long Audio TTS (Codespaces CLI)

Công cụ dòng lệnh tạo audio truyện dài tiếng Việt bằng [Edge-TTS](https://github.com/rany2/edge-tts). Dự án này **không có giao diện web/Flask**. Bạn chạy lệnh trong terminal của GitHub Codespaces, theo dõi tiến trình ngay trong terminal, rồi tải MP3 từ thư mục `outputs/`.

Edge-TTS cần Internet để gọi dịch vụ tổng hợp giọng nói. Codespaces có giới hạn sử dụng và có thể phát sinh chi phí tùy tài khoản; đây không phải tài nguyên chạy miễn phí không giới hạn. Kiểm tra phần sử dụng Codespaces trong tài khoản trước khi chạy các tác vụ rất dài.

## Tính năng

- Nhận tệp truyện `.txt` UTF-8 hoặc UTF-8 BOM.
- Giọng tiếng Việt Nam Minh và Hoài My.
- Tốc độ đọc 0.75x, 1.0x, 1.25x, 1.5x và 1.75x.
- Chia văn bản theo ranh giới tự nhiên, giữ nguyên nội dung và thứ tự.
- Xử lý lần lượt từng đoạn, thử lại lỗi tạm thời.
- Lưu trạng thái và audio của từng đoạn xuống đĩa.
- Khôi phục tác vụ còn dở khi chạy lại trong cùng Codespace; không phải tạo lại những đoạn MP3 còn hợp lệ.
- Tự ghép các đoạn thành một MP3 bằng FFmpeg.
- Hỗ trợ liệt kê tác vụ, tiếp tục/thử lại và báo lỗi trong terminal.
- GitHub Actions chạy kiểm thử tự động.

## Chạy trên GitHub Codespaces

1. Mở [repository này](https://github.com/Tanphong254/Vietnamese-Long-Audio-TTS).
2. Bấm **Code → Codespaces → Create codespace on main**. Nếu GitHub hỏi cấu hình, chọn cấu hình mặc định của repository.
3. Chờ môi trường hoàn tất cài đặt. Tệp `.devcontainer/devcontainer.json` cài Python dependencies và FFmpeg.
4. Mở terminal bên trong Codespaces. Tạo thư mục đầu vào riêng:

   ```bash
   mkdir -p input jobs outputs
   ```

5. Tải tệp truyện từ máy tính vào thư mục `input/` bằng File Explorer của VS Code Web (dùng menu Upload nếu có, hoặc kéo thả tệp vào Explorer). Không cần và không nên commit tệp truyện lên GitHub.
6. Kiểm tra lệnh đã sẵn sàng:

   ```bash
   python --version
   python tts_cli.py --help
   ```

## Tạo audio

Ví dụ đọc tệp `input/truyen.txt` bằng giọng nam Nam Minh tốc độ 1.25x:

```bash
python tts_cli.py --input input/truyen.txt --voice vi-VN-NamMinhNeural --rate 1.25
```

Dùng giọng nữ Hoài My tốc độ bình thường:

```bash
python tts_cli.py --input input/truyen.txt --voice vi-VN-HoaiMyNeural --rate 1.0
```

Điều chỉnh kích thước đoạn (500–3500 ký tự; mặc định 2400):

```bash
python tts_cli.py --input input/truyen.txt --chunk-size 1800
```

Khi hoàn tất, terminal sẽ in đường dẫn MP3. Mở thư mục `outputs/` trong Explorer của Codespaces, bấm chuột phải vào tệp MP3 và tải xuống. Tải MP3 về máy tính trước khi xóa Codespace. **Dữ liệu trong Codespace không nằm trong Git commit; nếu bạn xóa Codespace thì các tệp riêng và audio trong ổ đĩa Codespace cũng có thể bị mất.**

## Theo dõi, liệt kê và tiếp tục

Liệt kê các tác vụ đã lưu:

```bash
python tts_cli.py --list-jobs
```

Mỗi lần tạo audio, chương trình in ra mã tác vụ. Ghi lại mã này. Nếu tác vụ bị gián đoạn, Codespace bị dừng, hoặc một đoạn thất bại, chạy:

```bash
python tts_cli.py --resume MA_TAC_VU
```

Thay `MA_TAC_VU` bằng ID được in trong terminal. Chương trình sẽ thử lại tác vụ lỗi/bị hủy và giữ những đoạn audio đã tạo hợp lệ. Nếu tác vụ còn chạy trong terminal cũ, không khởi động một lệnh resume thứ hai cho cùng tác vụ.

Bạn có thể nhấn `Ctrl+C` để ngừng theo dõi; nếu tiến trình bị dừng, hãy dùng `--resume` để tiếp tục. Việc tổng hợp một đoạn đang gọi dịch vụ mạng có thể chưa dừng tức thì.

## Tệp và dữ liệu cá nhân

- `tts_cli.py`: lệnh dòng lệnh chính.
- `tts_engine.py`: chia văn bản, hàng đợi, lưu tiến độ, Edge-TTS và ghép MP3.
- `.devcontainer/devcontainer.json`: cấu hình môi trường Codespaces.
- `input/`: tệp truyện bạn tải vào; được `.gitignore` loại khỏi Git.
- `jobs/`: văn bản nguồn, trạng thái tác vụ và các đoạn MP3; được loại khỏi Git.
- `outputs/`: MP3 hoàn chỉnh; được loại khỏi Git.

Repository này là Public. Đừng commit văn bản truyện, dữ liệu cá nhân hoặc các tệp MP3. Trước khi commit mọi thay đổi, kiểm tra:

```bash
git status --short
```

`.gitignore` giảm nguy cơ đưa nhầm dữ liệu vào Git nhưng không thay thế việc kiểm tra thủ công.

## Kiểm thử

Trong Codespaces:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Các bài kiểm thử dùng hàm tổng hợp giả để không cần gửi văn bản thử lên dịch vụ Edge-TTS. Bài kiểm thử thành công không bảo đảm dịch vụ mạng luôn sẵn sàng hay mọi truyện rất dài sẽ hoàn tất không lỗi.

## Giới hạn cần biết

- Tác vụ dài phụ thuộc tốc độ mạng, dịch vụ Edge-TTS và thời gian/dung lượng Codespaces khả dụng.
- Quá trình không thể bảo đảm hoàn thành khi môi trường bị xóa, lưu trữ bị đầy hoặc dịch vụ từ chối yêu cầu. Hãy tải MP3 hoàn chỉnh về máy sau khi tạo.
- Không commit nội dung truyện hoặc audio vào repository Public.
- Edge-TTS dùng dịch vụ trực tuyến, không phải engine ngoại tuyến.
- Đây là dự án độc lập, không được Microsoft bảo trợ.

## License

MIT. Các thư viện và binary bên thứ ba có giấy phép riêng.
