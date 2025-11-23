# LAB 4 — SDN/OpenFlow (Mininet + Ryu)

This lab builds an SDN topology with Mininet and a Ryu controller that learns MAC addresses and periodically polls switch statistics.

## Files
- `LAB 4/q1_topology.py`: Mininet script tạo topology 4 switch (ring) và 16 host, link host 10Mb/1ms, link switch 20Mb/2ms.
- `LAB 4/q2_monitor.py`: Ryu app (SimpleSwitch13 + monitor) gửi Flow/Port Stats Request định kỳ và in thống kê.

## Chuẩn bị
1) Cài Mininet và Ryu (Ubuntu 22.04, Python 3):  
   ```bash
   git clone https://github.com/mininet/mininet
   sudo ./mininet/util/install.sh -a   # hoặc theo hướng dẫn GV
   sudo apt-get install -y ryu-bin || pip install ryu
   ```
2) (Tuỳ chọn) cài Wireshark để bắt gói giữa switch và controller.

## Chạy controller (câu 2)
Mặc định poll mỗi 10s; có thể đổi bằng `POLL_INTERVAL` (giây).
```bash
cd "LAB 4"
POLL_INTERVAL=1 ryu-manager q2_monitor.py   # dùng 1s để quan sát nhanh, hoặc bỏ biến để lấy 10s
```

## Tạo topology (câu 1)
Trong terminal khác:
```bash
cd "LAB 4"
sudo python3 q1_topology.py
```
CLI của Mininet mở ra (`mininet>`). Controller mặc định 127.0.0.1:6653; nếu khác, chỉnh `run(controller_ip, controller_port)` trong `q1_topology.py`.

## Kiểm thử
- Kiểm tra kết nối: `pingall`
- Đo băng thông giữa hai host bất kỳ: `iperf h1 h9` (hoặc `iperf h4 h12`, v.v.)
- Quan sát log trong terminal Ryu: Flow/Port stats sẽ in theo chu kỳ.
- Muốn bắt gói thống kê: chạy Wireshark/tcpdump trên interface kết nối controller-switch (OpenFlow TCP 6633/6653).

## Ghi chú báo cáo
- Chụp màn hình kết quả `pingall`, `iperf`, log Ryu (Flow/Port Stats Reply) và gói tin Statistics trong Wireshark.
- Mỗi bước trên tương ứng yêu cầu câu 1 và câu 2 của đề.***
