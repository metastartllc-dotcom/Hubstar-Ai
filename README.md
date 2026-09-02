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

API серверийг ажиллуулах:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload
```

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Тест ажиллуулах:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
