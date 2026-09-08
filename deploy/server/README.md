# ThingDaddy demo บนเซิร์ฟเวอร์ (prod ให้คนนอกกดเล่น)

ใช้ stack เดียวกับ `deploy/docker-compose.yml` (Postgres seed + API + เว็บ ใน origin เดียว) แล้วเอา nginx ครอบให้เป็น https

## ครั้งแรก (บนเซิร์ฟเวอร์ Ubuntu ที่มี Docker + nginx + certbot — เครื่องเดียวกับ field-mark ได้)

```bash
git clone -b production https://github.com/AiMachine-Software/thingdaddy.git ~/thingdaddy
bash ~/thingdaddy/deploy/server/up.sh            # build + start · ครั้งแรก 1–2 นาที
sudo cp ~/thingdaddy/deploy/server/thingdaddy.nginx.conf /etc/nginx/sites-available/thingdaddy
sudo ln -s /etc/nginx/sites-available/thingdaddy /etc/nginx/sites-enabled/thingdaddy
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d td-demo.49.0.64.117.nip.io
```

เปิด https://td-demo.49.0.64.117.nip.io/ — แถบบนต้องเป็นสีเขียว LIVE พร้อมจำนวน record
`/console.html` = คอนโซล 26 จอ · `/health` `/stats` `/record/prefix/081627002` = API ตรง ๆ

## อัปเดตครั้งต่อไป
```bash
bash ~/thingdaddy/deploy/server/up.sh
```

## ข้อควรรู้
- ข้อมูลมาจาก `population/seed/` (snapshot จริง 4 บริษัท 187 claims) — ไม่ใช่ฐานเต็ม 81,928 แถวที่อยู่กับ KJ
  ถ้าได้ dump มา ให้ restore เข้า Postgres ของ container แทน seed (พอร์ต 5434 loopback)
- API เขียนได้เฉพาะเมื่อมี `INGEST_TOKEN` (ดู `deploy/.env.example`) ค่าเริ่มต้นคืออ่านอย่างเดียว ปลอดภัยสำหรับให้คนนอกเล่น
- ถ้าอยากให้เว็บบน GitHub Pages ใช้ API ตัวนี้ด้วย: ตั้ง repository variable `API_BASE=https://td-demo.49.0.64.117.nip.io`
  และตั้ง `CORS_ORIGIN=https://aimachine-software.github.io` ใน `deploy/.env` แล้ว push production ให้ Pages build ใหม่
- พอร์ตในเครื่อง: เว็บ+API 8789 · Postgres 5434 (ทั้งคู่ loopback) — ไม่ชนกับ field-mark

## แบบที่ 2: เว็บ static ที่ /thingdaddy/ บน IP ตรง + API ผ่าน proxy (แบบที่ Ant ทำอยู่ 8 ก.ย.)

หน้าเว็บ (dist/) วางเป็นไฟล์ static ใต้ nginx default server ที่ `http://49.0.64.117/thingdaddy/`
ส่วน API รันใน container (8789) แล้วให้ nginx ส่ง path ของ API ไปหา

```bash
cd ~/thingdaddy && git pull --ff-only origin production
docker compose -f deploy/docker-compose.yml up -d --build            # API (+ฐาน seed) ที่ 127.0.0.1:8789
sudo cp deploy/server/thingdaddy-api-proxy.conf /etc/nginx/snippets/
#   เปิด server block ที่เสิร์ฟ /thingdaddy/ แล้วเพิ่มบรรทัด:  include snippets/thingdaddy-api-proxy.conf;
sudo nginx -t && sudo systemctl reload nginx
WEB_ROOT=<โฟลเดอร์ที่ nginx เสิร์ฟเป็น /thingdaddy/> bash deploy/server/static-up.sh   # build ใหม่ + copy dist
```

ตรวจ: `curl http://49.0.64.117/health` ต้องได้ JSON ไม่ใช่ HTML · เปิด `/thingdaddy/demo/td_screens_live.html` แถบบนต้องเขียว LIVE
หน้า demo ทุกหน้าถูกแก้ให้ `const API = ''` (same origin) แล้ว ไม่ยิง 127.0.0.1:8787 อีก
