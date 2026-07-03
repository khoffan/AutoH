# 🚀 AutoH (Auto Hotkey Mode)

**AutoH** เป็นเครื่องมือเพิ่มประสิทธิภาพการทำงาน (Productivity Tool) ที่ช่วยให้คุณเปิดชุดโปรแกรมและเว็บไซต์ที่จำเป็นสำหรับแต่ละโปรเจกต์ได้พร้อมกันด้วยการกด Hotkey เพียงครั้งเดียว

---

## 🌐 Project Website

คุณสามารถเข้าชมหน้าเว็บไซต์หลัก เพื่ออ่านรายละเอียดเพิ่มเติมและดาวน์โหลดเวอร์ชันล่าสุดได้ที่นี่:
👉 **[AutoH Official Website](https://auto-h.vercel.app)** 👈

---

## ✨ Features

- **Custom Setup:** เลือกแอปพลิเคชันจากเครื่อง (Auto-detect) และใส่ URL ที่ต้องการเปิดพร้อมกัน
- **One-Click Execution:** สั่งรันทุกอย่างผ่านคีย์ลัดที่คุณตั้งเอง (เช่น `Ctrl+Alt+W`)
- **Smart GUI:** อินเทอร์เฟซใหม่ด้วย CustomTkinter, light mode only, plain colors และ contrast ชัดเจน
- **Mode Management:** สร้าง แก้ไข เปลี่ยนชื่อ และลบ mode ได้จากหน้าจอเดียว
- **Lightweight:** ทำงานเบื้องหลัง กินทรัพยากรเครื่องน้อยมาก

---

## 📦 การติดตั้ง (Installation)

คุณสามารถติดตั้ง AutoH ได้ง่ายๆ ผ่าน 2 ช่องทาง:

1. **ผ่าน Website:** ไปที่ [AutoH Website](<(https://auto-h.vercel.app)>) แล้วกดปุ่ม Download
2. **ผ่าน GitHub Releases:** ดาวน์โหลดไฟล์จากหน้า **[Releases](<(https://github.com/khoffan/AutoH/releases/tag/autoh_v1.0.0)>)**

> [!IMPORTANT]
> **หมายเหตุสำหรับ Windows Defender:** เนื่องจากโปรแกรมนี้ยังไม่ได้ลงทะเบียนแบบเสียค่าใช้จ่าย (Digital Signature)
> หาก Windows SmartScreen ขึ้นเตือน ให้คลิกที่ **"More info"** และกดปุ่ม **"Run anyway"**

---

## 🛠 วิธีการใช้งาน (Usage)

1. **Setup Mode:** เมื่อยังไม่มี mode ที่บันทึกไว้ โปรแกรมจะเปิดหน้าจัดการ mode ให้ตั้งค่าแอป ชื่อ mode และ URL ที่ต้องการใช้
2. **Assign Hotkey:** กำหนดคีย์ลัดที่ต้องการใช้งาน (เริ่มต้นด้วย `Ctrl+Alt+...`) และเพิ่มหรือลดแอปใน mode ได้ทันที
3. **Save & Start:** บันทึก mode แล้วโปรแกรมจะเริ่มฟัง hotkeys ทันที โดยสามารถเปิดหน้าจัดการ mode ใหม่ได้ด้วย `Ctrl+Alt+E`

---

## 🏗 โครงสร้างโปรเจกต์ (Project Structure)

```text
├── 📁 config       # การจัดการค่าตั้งค่าและ Path
├── 📁 core         # ระบบรันโปรแกรม (Launcher) และ Hotkey
├── 📁 system       # การอ่านค่า Registry และ Start Menu
├── 📁 ui           # ส่วนติดต่อผู้ใช้ (CustomTkinter)
└── 🐍 main.py       # จุดเริ่มต้นของโปรแกรม
```
