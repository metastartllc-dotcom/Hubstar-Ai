# Hubstar AI

Барилгын төслийн удирдлага, төсвийн систем (Construction project management and cost-estimation system).

## Системийн тухай (About)
Энэхүү систем нь барилгын төслийн нэгдсэн төсөв, материалын жагсаалт, тээвэр болон машин механизмын зардлыг үнэн зөвөөр тооцоолох зорилготой Python MVP юм. 

## Суулгах заавар (Installation)
1. Python 3.12+ суусан байх шаардлагатай.
2. Сангуудыг суулгах:
   ```bash
   pip install -r requirements.txt
   ```
3. Өгөгдлийн сангийн тохиргоо үүсгэх:
   ```bash
   cp .env.example .env
   ```

## Ажиллуулах заавар (Usage)
Үндсэн цэсийг дуудах:
```bash
python -m app.cli.main interactive
```

Мөн тайлангууд `data/output` хавтас дотор хадгалагдана. Excel импорт хийх мэдээллүүдийг `data/input` хавтсанд хийнэ үү.

## API ашиглах заавар

Өгөгдлийн сангийн хүснэгтүүдийг анх удаа үүсгэх:

```powershell
.\.venv\Scripts\python.exe -m app.core.init_db
```

API серверийг ажиллуулах:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload
```

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Projects: [http://127.0.0.1:8000/api/v1/projects](http://127.0.0.1:8000/api/v1/projects)
- Project detail: `http://127.0.0.1:8000/api/v1/projects/{project_id}`

### Төсөл шинээр бүртгэх

Swagger интерфэйсийн `POST /api/v1/projects` хэсгийг ашиглах эсвэл дараах JSON
хүсэлтийг илгээнэ. `project_id` нь заавал өгөх, хоосон биш external ID байна.

```powershell
$body = @{
    project_id = "PRJ-001"
    name = "Орон сууцны төсөл"
    location = "Улаанбаатар"
    project_type = "Residential"
    gross_floor_area = 1250.5
    start_date = "2026-09-01"
    end_date = "2027-09-01"
    status = "ACTIVE"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/projects" `
    -ContentType "application/json" `
    -Body $body
```

Энэ write endpoint одоогоор зөвхөн local development зориулалттай. Authentication
нэмэгдээгүй тул public орчинд deploy хийж болохгүй.

### Төслийн мэдээллийг хэсэгчлэн шинэчлэх

Зөвхөн өөрчлөх утгуудаа `PATCH /api/v1/projects/{project_id}` руу илгээнэ:

```json
{
  "name": "Шинэчилсэн төслийн нэр"
}
```

`project_id` нь immutable бөгөөд PATCH request body-д оруулахгүй. Мэдэхгүй optional
утгыг тааж илгээхгүй.

Тест ажиллуулах:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Төслийн ажлын API

Төслийн external ID-аар ажлын жагсаалт авах:

```text
GET http://127.0.0.1:8000/api/v1/projects/PRJ-ALTAI-R7-B/work-items?offset=0&limit=100
```

Ажил шинээр бүртгэх (зөвхөн local development):

```json
POST /api/v1/projects/PRJ-ALTAI-R7-B/work-items
{
  "work_id": "PRJ-ALTAI-R7-B-WRK-001",
  "name": "Суурийн ажил",
  "unit": "м2",
  "quantity": 10.005,
  "labor_unit_rate": 1
}
```

`work_id` нь системийн хэмжээнд unique байх ёстой. Санал болгосон формат нь
`{PROJECT_ID}-WRK-{SEQUENCE}`. Client URL-д external project ID ашиглах бөгөөд
internal integer project ID-г request body-д илгээхгүй. Танигдсан нэгжийн alias-ыг
нормчилно; танигдаагүй нэгжийг захын зайг цэвэрлээд эх утгаар нь хадгална.
`quantity` болон `labor_unit_rate` хоёул байвал сервер `labor_total`-ийг Decimal-аар
тооцож, half-up дүрмээр хоёр орны нарийвчлалтай тоймлоно.

## Material master API

Material жагсаалт болон detail:

```text
GET http://127.0.0.1:8000/api/v1/materials?offset=0&limit=100
GET http://127.0.0.1:8000/api/v1/materials/PRD-ALTAI-B-127
```

Material үүсгэх (зөвхөн local development):

```json
POST /api/v1/materials
{
  "material_id": "PRD-ALTAI-B-127",
  "name": "Барилгын силикон/нейтрал чигжээс",
  "normalized_unit": "картриж",
  "unit_price": 25000
}
```

`material_id` нь системийн хэмжээнд unique global external identifier бөгөөд client
internal integer ID ашиглахгүй. `unit_price` нь MNT-ээр илэрхийлсэн одоогийн snapshot
үнэ. Price history болон supplier source мэдээллийг дараагийн шатанд тусдаа бүтэцтэй
нэмнэ. Authentication байхгүй тул write endpoint-ийг public орчинд ашиглахгүй.

Material-ийн зөвхөн өгсөн талбаруудыг хэсэгчлэн шинэчлэх (зөвхөн local development):

```json
PATCH /api/v1/materials/PRD-ALTAI-B-005
{
  "specification": "Шинэчилсэн техникийн үзүүлэлт",
  "normalized_unit": "ш",
  "unit_price": 1600
}
```

`material_id` нь immutable тул request body-д оруулахгүй. `unit_price`-д `null`
илгээж үнийг “тодорхойгүй” болгон цэвэрлэж болно. Link нь үнийн snapshot
хадгалдаггүй учраас үнэ өөрчлөгдвөл холбоотой ажлын `material_total` GET response-д
шинэ үнээр дахин тооцогдоно. Authentication байхгүй тул PATCH endpoint мөн
local-development-only бөгөөд public орчинд ашиглахгүй.

## Ажлын материалын хэрэгцээний API

Тухайн ажилд холбосон материалыг external project, work ID-аар авах:

```text
GET /api/v1/projects/PRJ-ALTAI-R7-B/work-items/PRJ-ALTAI-R7-B-WRK-001/materials
```

Материал холбох (зөвхөн local development):

```json
POST /api/v1/projects/PRJ-ALTAI-R7-B/work-items/PRJ-ALTAI-R7-B-WRK-001/materials
{
  "material_id": "PRD-ALTAI-B-001",
  "consumption_rate": 1.05,
  "waste_percentage": 5,
  "approved_quantity": 5500
}
```

`consumption_rate` нь материалын нэгж / ажлын нэгж гэсэн утгатай. Сервер дараах
томьёогоор хэрэгцээг тооцно:

```text
calculated_quantity = work_quantity × consumption_rate × (1 + waste_percentage / 100)
effective_quantity = approved_quantity (өгөгдсөн бол), бусад үед calculated_quantity
material_total = effective_quantity × unit_price
```

Тооцоолсон болон effective quantity-г 3, материалын нийт үнийг 2 орны
нарийвчлалтай `ROUND_HALF_UP` дүрмээр тоймлоно. Material master дээр `unit_price`
байхгүй бол `material_total` нь `null` байна.

Link model нь үнийн snapshot хадгалдаггүй. Material master-ийн үнэ шинэчлэгдэхэд
GET response дахь link-ийн `material_total` мөн шинэ үнээр өөрчлөгдөнө; historical
price snapshot болон price history-г дараагийн шатанд нэмнэ.

Одоогийн database-д `(work_id, material_id)` composite unique constraint байхгүй.
Иймээс duplicate хамгаалалт нь application-level бөгөөд зөвхөн local-development,
single-writer хэрэглээнд тохирно. Public эсвэл multi-user deployment хийхийн өмнө
composite unique migration болон authentication заавал нэмнэ.

## Ажлын материалын холбоос шинэчлэх

`PATCH /api/v1/projects/{project_id}/work-items/{work_id}/materials/{material_id}`
руу зөвхөн өөрчлөх утгаа явуулна:

```json
{
  "consumption_rate": 1.1,
  "waste_percentage": 5,
  "approved_quantity": null,
  "status": "ACTIVE"
}
```

`approved_quantity=null` нь override-ийг арилгаж calculated quantity руу буцаана.
`calculated_quantity`, `effective_quantity`, `material_total`, үнэ болон ID-уудыг
client өөрчилж болохгүй. Сервер quantity-г 3, мөнгийг 2 орноор ROUND_HALF_UP
тооцно. Link price snapshot хадгалахгүй; одоогийн Material үнэ ашиглана.
Энэ write endpoint нь local-development-only, authentication-гүй public deployment
хийхгүй.

## Нэг ажлын мэдэгдэж буй төсвийн summary

```text
GET /api/v1/projects/PRJ-ALTAI-R7-B/work-items/PRJ-ALTAI-R7-B-WRK-001/summary
```

Жишээ response:

```json
{
  "project_id": "PRJ-ALTAI-R7-B",
  "work_id": "PRJ-ALTAI-R7-B-WRK-001",
  "labor_total": 255000000,
  "material_link_count": 6,
  "priced_material_count": 2,
  "missing_price_count": 4,
  "needs_review_count": 1,
  "material_subtotal_known": 71145000,
  "subtotal_known_before_vat": 326145000,
  "is_pricing_complete": false,
  "has_review_warnings": true,
  "pricing_status": "INCOMPLETE"
}
```

`subtotal_known_before_vat` нь зөвхөн одоогоор үнэ мэдэгдэж буй хөдөлмөр болон
материалын хэсэг бөгөөд бүрэн нийт төсөв биш. `INCOMPLETE` үед үүнийг бүрэн төсөв
гэж ашиглаж болохгүй. Энэ endpoint-д НӨАТ, тээвэр, тоног төхөөрөмж болон historical
price snapshot хараахан ороогүй. Material master-ийн одоогийн үнэ өөрчлөгдвөл
summary мөн шинэ үнээр дахин тооцогдоно.
