# ThingDaddy — เดโมที่ deploy ได้ (deployable demo)

เดโมเดิมของ KJ ต้องเปิดไฟล์ HTML จากดิสก์ แล้วให้ไฟล์นั้นยิง API ที่
`http://127.0.0.1:8787` ซึ่งแปลว่าคนอื่นเอาไปรันต่อไม่ได้ — ต้องมี Postgres
เครื่องตัวเอง ต้องรัน `node server.js` เอง และต้องเปิด HTML จาก path ที่ถูกต้อง

โฟลเดอร์นี้ห่อของเดิมให้กลายเป็น **แอปเดียวที่ deploy ได้จริง**: หน้าเว็บกับ API
ออกมาจาก origin เดียวกัน ฐานข้อมูลมี seed ให้อัตโนมัติตั้งแต่บูตแรก

> ของในนี้ยังไม่ได้ deploy ที่ไหนทั้งนั้น — รันในเครื่องอย่างเดียว

---

## รันยังไง — 3 คำสั่ง

ต้องมี Docker Desktop (หรือ OrbStack) เปิดอยู่ แค่นั้น ไม่ต้องลง Node ไม่ต้องลง Postgres

```bash
cd <repo root>

docker compose -f deploy/docker-compose.yml up -d --build

open http://localhost:8789/
```

ครั้งแรกจะนานหน่อย (build image + โหลด seed) ประมาณ 1–2 นาที
หลังจากนั้นขึ้นใน ~5 วินาที

**เลิกใช้:**
```bash
docker compose -f deploy/docker-compose.yml down
```
`down` เฉยๆ **ข้อมูลไม่หาย** (อยู่ใน docker volume) เปิดใหม่ได้เลย
ถ้าอยากล้างฐานข้อมูลให้เริ่มใหม่หมดจริงๆ ใช้ `down -v` แล้ว seed จะโหลดใหม่ตอนบูต

---

## เปิดหน้าไหนได้บ้าง

| URL | คืออะไร |
|---|---|
| http://localhost:8789/ | หน้าจอ S1…S6 (ของเดิมชื่อ `td_screens_live.html`) |
| http://localhost:8789/console.html | คอนโซล 26 จอ (ของเดิมชื่อ `td_console.html`) |
| http://localhost:8789/health | API ตอบว่าต่อ DB ได้ไหม |
| http://localhost:8789/stats | นับจำนวนแถวในฐานข้อมูล |
| http://localhost:8789/record/prefix/081627002 | ตัวอย่าง — Illumina |

ถ้าแถบบนสุดของหน้าเป็น **สีเขียวและเขียนว่า LIVE พร้อมจำนวน records** แปลว่าหน้าเว็บ
คุยกับ API ได้จริง ถ้าเป็นสีแดง `NO API` แปลว่า container `app` ยังไม่ขึ้น

### ทำไม 8789 ไม่ใช่ 8787 หรือ 8788
เครื่องนี้มีของรันอยู่ก่อนแล้ว และเราห้ามไปยุ่งกับมัน:
`8787` = เดโมของ KJ ที่รันด้วย `node` ตรงๆ · `8788` = `thingdaddy-staging-api-1` ·
`5432` = `taxmap-survey-db-1` (ลูกค้าอีกเจ้า) · `5433` = `td-demo-pg`
เดโมนี้เลยใช้ **8789** และ Postgres ใช้ **5434** เปลี่ยนได้ใน `.env`

---

## ในโฟลเดอร์นี้มีอะไร

| ไฟล์ | หน้าที่ |
|---|---|
| `docker-compose.yml` | ปะติดปะต่อทุกอย่าง — postgres + app, พอร์ต, healthcheck |
| `Dockerfile` | image เดียว = `apps/api` + `apps/web` (build เป็น dist แล้วเสิร์ฟ) |
| `Dockerfile.dockerignore` | ตัด context ไม่ให้ส่งทั้ง repo เข้า docker |
| `.env.example` | ตัวแปรทุกตัวพร้อมคำอธิบาย — **ไม่ต้องก็อปก็รันได้** |
| `db-init/10-seed.sh` | สคริปต์ที่โหลด seed เข้า DB ตอนบูตแรก (ครั้งเดียว) |
| `public/index.html` | = `apps/web/public/demo/screens.html` (ย้ายมาแล้ว) |
| `public/console.html` | = `apps/web/public/demo/console.html` (ย้ายมาแล้ว) |
| `ARCHITECTURE.md` | อะไรคุยกับอะไร พอร์ตไหน ข้อมูลมาจากไหน |

---

## แก้ของเดิมไปแค่ไหน

น้อยที่สุดเท่าที่ทำได้ — รวม **3 จุด**

1. `apps/web/public/demo/screens.html` บรรทัด 649 — `const API = 'http://127.0.0.1:8787';` → `const API = '';`
2. `apps/web/public/demo/console.html` บรรทัด 149 — บรรทัดเดียวกัน เปลี่ยนแบบเดียวกัน
3. `apps/api/server.js` — เพิ่ม 5 บรรทัด (import `fs` + เสิร์ฟไฟล์ static แบบ opt-in)

ข้อ 3 **ไม่กระทบของเดิมเลย** ถ้าไม่ตั้ง `PUBLIC_DIR` เซิร์ฟเวอร์จะทำงานเหมือนเดิมทุกอย่าง
(พิสูจน์แล้ว: ไม่ตั้ง `PUBLIC_DIR` แล้วเรียก `/` ยังได้ `{"error":"no route GET /"}` เหมือนเดิม)

---

## ข้อมูลมาจากไหน

`population/seed/` — snapshot จริงลงวันที่ 2026-09-05 จาก `thingdaddy_population`
บน Mac mini มี 4 parties / 187 content_claims / 4 party_events

ตอนบูตแรก `db-init/10-seed.sh` จะเรียก `seed_up.sh` ของ KJ เอง ซึ่งจะโหลด schema +
data แล้ว **ตรวจนับแถวเทียบกับ MANIFEST.txt** ถ้าจำนวนไม่ตรง container จะไม่ขึ้น
(ตั้งใจ — โหลดครึ่งๆ กลางๆ จะทำให้หน้าจอว่างและดูเหมือนหน้าเว็บพัง)

seed นี้เป็นของ dev เท่านั้น: *not fabricated · not authoritative · not a source of
truth · REGENERATE, NEVER EDIT*

---

## เอาไป deploy จริงต้องแก้อะไรก่อน

1. **`POSTGRES_PASSWORD`** — ตอนนี้เป็น `thingdaddy` ตายตัว ต้องเปลี่ยน
2. **`CORS_ORIGIN`** — ตอนนี้ `*` หน้าเว็บนี้ไม่ได้ใช้ (same-origin) แต่ควรปิดให้แคบ
3. **`ports:`** — ตอนนี้ผูก `127.0.0.1` ไว้ทั้งคู่ ถ้าจะให้คนนอกเข้าต้องเอาออก
   แล้ว **ต้องมี reverse proxy + TLS ข้างหน้า**
4. **ตัด host port ของ postgres ออก** ไม่มีเหตุผลให้ DB โผล่ออกมาข้างนอก
5. **seed** — ของ production ไม่ควรใช้ seed dev ตัวนี้
6. **write endpoints** — `/ingest` `/gate` ต้องมี `INGEST_TOKEN` และ `/gate` ยังต้องใช้
   `population/verify/verify_cli.py` ซึ่งไม่ได้อยู่ใน git เดโมนี้เป็น read-only

---

# English

The original demo needed a hand-opened HTML file talking to a hand-started API on
`127.0.0.1:8787`. This folder wraps it into **one deployable app**: pages and API
on a single origin, database seeded automatically on first boot.

**Nothing here has been deployed anywhere. Local only.**

## Run it — three commands

```bash
cd <repo root>
docker compose -f deploy/docker-compose.yml up -d --build
open http://localhost:8789/
```

Requires only Docker. First run takes 1–2 minutes (image build + seed load);
after that it comes up in about five seconds. Stop with
`docker compose -f deploy/docker-compose.yml down` — data survives, because it lives
in a named volume. Use `down -v` to wipe and re-seed from scratch.

## What it serves

`/` is the S1…S6 screens, `/console.html` is the 26-screen console, and the API
routes (`/health`, `/stats`, `/search`, `/record/prefix/:prefix`, …) are on the same
origin. A green **LIVE** banner with a record count means the page reached the API.

Port 8789 rather than 8787/8788 because both are already held by other running
demos on this machine; Postgres is on 5434 because 5432 and 5433 are taken too.
Change either in `.env`.

## Changes to existing files — three, all minimal

1. `apps/web/public/demo/screens.html` line 649: `const API = 'http://127.0.0.1:8787';` → `const API = '';`
2. `apps/web/public/demo/console.html` line 149: the same one-line change
3. `apps/api/server.js`: five added lines — an `fs` import and an opt-in
   static block. With `PUBLIC_DIR` unset the server behaves exactly as before
   (verified: `/` still returns `{"error":"no route GET /"}`).

## Before deploying this for real

Change `POSTGRES_PASSWORD`, narrow `CORS_ORIGIN`, drop the Postgres host port,
put TLS and a reverse proxy in front, and replace the dev seed. The demo is
read-only; write endpoints need `INGEST_TOKEN` and `/gate` additionally needs
`population/verify/verify_cli.py`, which is not in git.
