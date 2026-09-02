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

Тест ажиллуулах:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
