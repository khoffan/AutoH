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
- **Import / Export:** สำรองหรือย้าย mode, alias และการตั้งค่าเสียงผ่านไฟล์ JSON จากหน้า Mode Manager
- **สั่งงานด้วยเสียง (v2.0):** กด `Ctrl+Alt+V` ค้างแล้วพูด เช่น "เปิดไลน์", "เปิดเพลง ...", "ค้นหา ...", "เปิดโฟลเดอร์ดาวน์โหลด", "ตั้งค่าไวไฟ", "เข้าโหมด work"
  - ทำงาน offline ในเครื่อง (Typhoon ASR) ไม่ส่งเสียงออกนอกเครื่อง
  - ไม่แน่ใจจะถามก่อน, ไม่รู้จักจะให้เลือก และจำคำที่เลือกไว้ใช้ครั้งต่อไป
  - ตั้งค่า/จัดการคำที่จำไว้/ดูประวัติได้ที่ปุ่ม "🎙 Voice Settings" ใน Mode Manager
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
├── 📁 voice        # สั่งงานด้วยเสียง: อัดเสียง, แปลงเสียง, แยกคำสั่ง, ทำงาน
└── 🐍 main.py       # จุดเริ่มต้นของโปรแกรม
```

---

## 🔨 Build (สำหรับนักพัฒนา)

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirement.txt pyinstaller
venv\Scripts\python.exe scripts\build.py
```

`scripts\build.py` รันเทสต์ → PyInstaller (`installer\AutoH.spec`, แบบ one-folder) → copy model เสียง → Inno Setup (`installer\AutoH.iss`)

- ผลลัพธ์: `dist\AutoH\AutoH.exe` และ `installer-output\AutoH-Setup-<version>.exe` (เวอร์ชันอยู่ที่ `app\version.py`)
- ต้องมีไฟล์ model int8 ใน `models\typhoon-asr-realtime\` (ไม่อยู่ใน git) ดูที่มาใน `SOURCE.txt` แล้วสร้าง int8 ด้วย `scripts\quantize_typhoon.py` (ต้อง `pip install onnx`)
- ต้องติดตั้ง [Inno Setup 6](https://jrsoftware.org/isinfo.php) สำหรับขั้นตอน installer หรือใช้ `--no-installer`

---

## 💾 การเก็บข้อมูล (Storage)

mode, alias, การตั้งค่า, ประวัติคำสั่ง และ log เก็บในไฟล์ SQLite `%LOCALAPPDATA%\AutoH\autoh.db` (สร้างให้อัตโนมัติ) และย้ายข้อมูลจาก `config.json` เดิมให้อัตโนมัติ
การถอนการติดตั้งไม่ลบไฟล์นี้ รายละเอียดดูที่ [docs/storage.md](docs/storage.md)
