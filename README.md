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
