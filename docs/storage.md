# การเก็บข้อมูล (SQLite Storage)

ตั้งแต่เวอร์ชันนี้ AutoH เก็บ config (modes) และ log ไว้ในไฟล์ SQLite ไฟล์เดียวแทน `config.json` และ `log.txt`

## ตำแหน่งไฟล์

ไฟล์ชื่อ `autoh.db` โปรแกรมหาตามลำดับนี้ ([get_base_dir.py](../app/config/get_base_dir.py)):

1. ข้าง exe ถ้ามี `autoh.db` วางอยู่แล้ว (portable mode)
2. `%LOCALAPPDATA%\AutoH\autoh.db`
3. ถ้ายังไม่มีไฟล์ จะสร้างที่ `%LOCALAPPDATA%\AutoH\` ก่อน ถ้าเขียนไม่ได้ค่อยลองข้าง exe

ถ้าเปิด DB ไม่ได้เลย โปรแกรมจะใช้ฐานข้อมูลใน memory แทน ยังใช้งานได้ แต่ข้อมูลจะหายเมื่อปิดโปรแกรม

## ย้ายข้อมูลจาก config.json เดิม

ครั้งแรกที่เปิดโปรแกรม ถ้าเจอ `config.json` ข้าง exe หรือใน `%LOCALAPPDATA%\AutoH\`:

- นำ mode ทั้งหมดเข้า DB (เฉพาะกรณีที่ DB ยังไม่มี mode)
- rename ไฟล์เดิมเป็น `config.json.bak`
- ทำแค่ครั้งเดียว (บันทึกไว้ในตาราง `meta`)

ถ้า `config.json` เสียหรือ format ผิด จะข้ามไปและไม่แตะไฟล์นั้น

`log.txt` เดิมไม่ได้ย้ายเข้า DB

## Import / Export

ในหน้า Mode Manager มีปุ่มใต้รายการ mode:

- **Export JSON** บันทึก mode ทั้งหมดเป็นไฟล์ JSON รูปแบบเดียวกับ `config.json` เดิม
- **Import JSON** นำเข้าไฟล์ JSON
  - ตรวจก่อนบันทึกเสมอ: format JSON, ทุก mode ต้องมี hotkey, apps ต้องเป็นชื่อ → path, hotkey ต้องใช้ได้จริง ไม่ซ้ำ และไม่ใช่ hotkey ที่ระบบสงวนไว้
  - ถ้าไม่ผ่าน จะแจ้งว่าผิดที่ mode ไหน และข้อมูลเดิมไม่ถูกแก้
  - เลือกได้ว่า **แทนที่ทั้งหมด** หรือ **รวม** กับของเดิม (mode ชื่อซ้ำจะถูกทับ)

รูปแบบไฟล์:

```json
{
    "modes": {
        "work": {
            "hotkey": "ctrl+alt+t",
            "apps": { "LINE": "C:\path\to\LineLauncher.exe" },
            "urls": "https://a.com, https://b.com"
        }
    }
}
```

## Schema

| ตาราง | ใช้เก็บ |
|---|---|
| `modes` | `name`, `hotkey`, `urls` |
| `mode_apps` | app ของแต่ละ mode (`mode_name`, `position`, `app_name`, `path`) เก็บลำดับตามที่เลือก |
| `logs` | `ts`, `level`, `message` ลบรายการที่เก่ากว่า 30 วันทุกครั้งที่เปิดโปรแกรม |
| `meta` | `schema_version`, สถานะการย้ายข้อมูล |

เปิด WAL mode ไว้ ให้ process ของ hotkey กับ UI อ่านและเขียนพร้อมกันได้

## สถานะการทดสอบ

> [!WARNING]
> **ยังไม่ได้ manual test** ทั้งการเปิดโปรแกรมจริง หน้า UI และ exe ที่ build แล้ว

ที่ทดสอบแล้ว (ด้วยสคริปต์ ในโฟลเดอร์จำลอง):

- [x] ย้ายข้อมูลจาก `config.json` และ rename เป็น `.bak`
- [x] ย้ายข้อมูลซ้ำไม่เกิดขึ้น
- [x] บันทึก / ลบ mode และลำดับ app ถูกต้อง
- [x] Export แล้ว Import กลับได้ข้อมูลตรงกัน
- [x] ปฏิเสธ JSON ที่เสีย และ mode ที่ไม่มี hotkey
- [x] เขียน / อ่าน log และลบ log เก่า
- [x] เปิด DB ไม่ได้ → ใช้ memory แทนโดยไม่ crash
- [x] ทุกไฟล์ compile ผ่าน

ยังต้อง manual test:

- [ ] เปิดโปรแกรมครั้งแรกบนเครื่องที่มี `config.json` เดิม → mode ขึ้นครบ hotkey ใช้ได้
- [ ] ปุ่ม Import / Export แสดงผลถูกต้องในหน้าต่าง และ dialog เปิดได้
- [ ] Import แบบแทนที่ และแบบรวม → hotkey ใหม่ใช้ได้ทันทีโดยไม่ต้องเปิดโปรแกรมใหม่
- [ ] Import ไฟล์ที่ผิด → มีข้อความแจ้ง ข้อมูลเดิมไม่เปลี่ยน
- [ ] บันทึก / ลบ mode ผ่าน UI ขณะที่ hotkey listener ทำงานอยู่
- [ ] build exe (PyInstaller) แล้วติดตั้งผ่าน installer → DB ถูกสร้างที่ `%LOCALAPPDATA%\AutoH\`
- [ ] รัน exe จาก Program Files โดยไม่ใช้สิทธิ์ admin
