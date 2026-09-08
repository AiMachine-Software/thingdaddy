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
