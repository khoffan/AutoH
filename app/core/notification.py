from plyer import notification
import threading

def send_toast(title, message):
    """ส่ง Toast Noti โดยไม่ขัดจังหวะ Thread หลัก"""
    def run():
        try:
            notification.notify(
                title=f"AutoH: {title}",
                message=message,
                app_name="AutoH",
                timeout=2
            )
        except Exception:
            pass # กันเหนี่ยวถ้าระบบ Noti ของ Windows มีปัญหา

    # รันแยก Thread เล็กๆ เพื่อให้ Logic หลักเดินต่อได้ทันที
    threading.Thread(target=run, daemon=True).start()