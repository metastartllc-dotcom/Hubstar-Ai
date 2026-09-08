# Hubstar AI Web Dashboard

Hubstar AI-ийн frontend нь React, TypeScript, Vite дээр бүтээгдсэн read-only
төслийн төсвийн dashboard юм. API client нь зөвхөн GET хүсэлт ашиглана.

## Environment тохиргоо

`.env.example`-ийг `.env.local` болгон хуулж, шаардлагатай бол утгыг өөрчилнө:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_PROJECT_ID=PRJ-ALTAI-R7-B
```

`VITE_API_BASE_URL` нь backend-ийн суурь URL, `VITE_PROJECT_ID` нь dashboard-д
харуулах external project ID байна. Real `.env` болон credential-ийг Git-д
нэмэхгүй.

## Ажиллуулах ба шалгах

```powershell
npm install
npm run dev -- --host 127.0.0.1 --port 3000
npm run build
npm run lint
```

Development үед frontend `http://127.0.0.1:3000`, backend
`http://127.0.0.1:8000` дээр ажиллана.

## Одоогийн боломжууд

- Төслийн мэдээлэл болон мэдэгдэж буй төсвийн нийлбэрийг харуулна.
- Төслийн ажлын жагсаалт, хөдөлмөр, материал, машин механизмын дүнг харуулна.
- Ажил сонгоход material болон equipment detail-ийг тухайн үед API-аас ачаална.
- Үнэ, төлөв, анхааруулгыг Монгол тайлбартай харуулна.
- Responsive хүснэгтүүд mobile/tablet дэлгэцэд өөрийн хүрээнд scroll хийнэ.

Authentication, authorization болон POST/PATCH зэрэг write UI одоогоор байхгүй.
Production deployment-д Vite development server-ийг шууд ашиглахгүй.
