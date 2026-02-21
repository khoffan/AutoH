# 🚀 AutoH (Auto Hotkey Mode)

**AutoH** เป็นเครื่องมือเพิ่มประสิทธิภาพการทำงาน (Productivity Tool) ที่ช่วยให้คุณเปิดชุดโปรแกรมและเว็บไซต์ที่จำเป็นสำหรับแต่ละโปรเจกต์ได้พร้อมกันด้วยการกด Hotkey เพียงครั้งเดียว

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)

---

## ✨ Features

- **Custom Setup:** เลือกแอปพลิเคชันจากเครื่อง (Auto-detect) และใส่ URL ที่ต้องการเปิดพร้อมกัน
- **One-Click Execution:** สั่งรันทุกอย่างผ่านคีย์ลัดที่คุณตั้งเอง (เช่น `Ctrl+Alt+W`)
- **Smart GUI:** อินเทอร์เฟซใช้งานง่าย ไม่ต้องมีความรู้เรื่องการเขียนโปรแกรม
- **Lightweight:** ทำงานเบื้องหลัง กินทรัพยากรเครื่องน้อยมาก

---

## 📦 การติดตั้ง (Installation)

คุณสามารถติดตั้ง AutoH ได้ง่ายๆ ผ่านตัวติดตั้ง Windows:

1. ไปที่หน้า **[Releases](https://github.com/YOUR_USERNAME/YOUR_REPO/releases)**
2. ดาวน์โหลดไฟล์ `AutoH_Installer_v1.0.zip`
3. แตกไฟล์แล้วรัน `setup.exe` เพื่อทำการติดตั้ง

> [!IMPORTANT]
> **หมายเหตุสำหรับ Windows Defender:** เนื่องจากโปรแกรมนี้ยังไม่ได้ลงทะเบียนแบบเสียค่าใช้จ่าย (Digital Signature) 
> หาก Windows SmartScreen ขึ้นเตือน ให้คลิกที่ **"More info"** และกดปุ่ม **"Run anyway"**

---

## 🛠 วิธีการใช้งาน (Usage)

1. **Setup Mode:** เมื่อเปิดโปรแกรมครั้งแรก คุณสามารถค้นหาแอปที่ต้องการจากรายการ และใส่ชื่อโหมด (เช่น Work, Gaming)
2. **Assign Hotkey:** กำหนดคีย์ลัดที่ต้องการใช้งาน (เริ่มต้นด้วย `Ctrl+Alt+...`)
3. **Save & Start:** กดบันทึก โปรแกรมจะย่อตัวไปอยู่ที่ System Tray และพร้อมทำงานทันที

---

## 🏗 โครงสร้างโปรเจกต์ (Project Structure)

```text
├── 📁 config       # การจัดการค่าตั้งค่าและ Path
├── 📁 core         # ระบบรันโปรแกรม (Launcher) และ Hotkey 
├── 📁 system       # การอ่านค่า Registry และ Start Menu
├── 📁 ui           # ส่วนติดต่อผู้ใช้ (Tkinter)
└── 🐍 main.py       # จุดเริ่มต้นของโปรแกรม
