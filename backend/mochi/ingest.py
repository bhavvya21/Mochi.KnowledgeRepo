"""Server-side parsing. Raw files are temporary and never retained."""
import csv
import io
import json
import zipfile
from pathlib import Path
from .schema import DocumentInput


def parse_file(name, data, llm, collection="My uploads"):
    suffix = Path(name).suffix.lower()
    pages = []
    warnings = []
    def add(number, text, topic="", method="text"):
        if text.strip():
            pages.append({"page":number,"topic":topic or name,"text":text,"method":method})
        if sum(len(p["text"]) for p in pages)>200000:
            raise ValueError("Document exceeds 200,000 extracted characters")
    def image_text(image):
        import pytesseract
        image.thumbnail((2000,2000))
        text = pytesseract.image_to_string(image, timeout=30)
        if llm.settings.vision_model:
            out = io.BytesIO()
            image.convert("RGB").save(out, format="PNG")
            description = llm.describe(out.getvalue())
            if description:
                text += "\n\n[Model-generated visual description; may contain errors]\n" + description
        return text
    if suffix == ".pdf":
        import pdfplumber
        import pypdfium2
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages)>200:
                raise ValueError("PDF exceeds 200 pages")
            raster = None
            try:
                for i,page in enumerate(pdf.pages):
                    text = page.extract_text(layout=False) or ""
                    tables = page.extract_tables() or []
                    for table in tables:
                        text += "\n\n" + "\n".join(" | ".join(str(c or "") for c in row) for row in table)
                    method = "pdf-text-and-tables"
                    if len(text.strip())<30 or (page.images and llm.settings.vision_model):
                        if raster is None:
                            raster = pypdfium2.PdfDocument(data)
                        raster_page = raster[i]
                        scale = min(2.,2000/max(raster_page.get_size()))
                        bitmap = raster_page.render(scale=scale)
                        image = bitmap.to_pil()
                        text += "\n\n"+image_text(image)
                        image.close();bitmap.close();raster_page.close()
                        method += "+ocr" + ("+vision" if llm.settings.vision_model else "")
                    add(i+1,text,method=method)
            finally:
                if raster is not None:
                    raster.close()
        kind = "PDF"
    elif suffix in (".png",".jpg",".jpeg",".webp"):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 20_000_000
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>20_000_000:
                raise ValueError("Image exceeds 20 megapixels")
            add(1,image_text(image),method="ocr+vision" if llm.settings.vision_model else "ocr")
        kind = "IMAGE"
    elif suffix in (".xlsx", ".docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(x.file_size for x in archive.infolist())>50_000_000 or len(archive.infolist())>10000:
                raise ValueError("Expanded document is too large")
        if suffix == ".xlsx":
            import openpyxl
            book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            try:
                if len(book.worksheets)>200:
                    raise ValueError("Workbook exceeds 200 sheets")
                for i,sheet in enumerate(book.worksheets):
                    lines=[];characters=0
                    for row_index,row in enumerate(sheet.iter_rows(values_only=True)):
                        if row_index>=10000:
                            raise ValueError("Sheet exceeds 10,000 rows")
                        line=" | ".join(str(v) if v is not None else "" for v in row[:100])
                        characters+=len(line)
                        if characters>200000: raise ValueError("Sheet text is too large")
                        lines.append(line)
                    add(i+1,"\n".join(lines),f"{name}: {sheet.title}","spreadsheet")
            finally:
                book.close()
            kind="XLSX"
            warnings.append("Formula cells use cached values; formulas are not recalculated. Sheet numbers are citation pages.")
        else:
            from docx import Document
            doc=Document(io.BytesIO(data))
            text="\n\n".join(p.text for p in doc.paragraphs)
            for table in doc.tables:
                text+="\n\n"+"\n".join(" | ".join(c.text for c in row.cells) for row in table.rows)
            add(1,text,method="docx")
            kind="DOCX"
            warnings.append("DOCX uses logical page 1; original Word pagination is unavailable.")
    elif suffix in (".txt",".md",".csv",".json"):
        text=data.decode("utf-8-sig")
        if suffix==".json":text=json.dumps(json.loads(text),indent=2,ensure_ascii=False)
        if suffix==".csv":text="\n".join(" | ".join(row) for row in csv.reader(io.StringIO(text)))
        add(1,text)
        kind=suffix[1:].upper()
    else:
        raise ValueError("Supported: PDF, PNG, JPG, WEBP, XLSX, DOCX, CSV, TXT, MD, JSON")
    if not pages:
        raise ValueError("No readable content found")
    return DocumentInput(name=name,type=kind,collection=collection,pages=pages,size=len(data)/1024),warnings
