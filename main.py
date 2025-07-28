from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
from uuid import uuid4

from database import SessionLocal, engine
from models import Product
from schemas import ProductCreate, ProductOut

app = FastAPI()

UPLOAD_FOLDER = "./images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Cria as tabelas se não existirem
from database import Base
Base.metadata.create_all(bind=engine)


# Dependency para obter sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/products/", response_model=ProductOut)
def create_product(product: ProductCreate):
    if product.price < 0.01:
        raise HTTPException(status_code=400, detail="Preço mínimo é R$0,01")
    db = SessionLocal()
    db_product = Product(
        name=product.name,
        description=product.description,
        price=product.price,
        image_filename=None
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    db.close()
    return ProductOut(
        id=db_product.id,
        name=db_product.name,
        description=db_product.description,
        price=db_product.price,
        image_url=None
    )


@app.post("/products/{product_id}/upload-image")
async def upload_image(product_id: int, file: UploadFile = File(...)):
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Formato de imagem inválido")
    db = SessionLocal()
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        db.close()
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    ext = file.filename.split(".")[-1]
    filename = f"{uuid4()}.{ext}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    product.image_filename = filename
    db.commit()
    db.close()
    return {"filename": filename}


@app.get("/products/", response_model=List[ProductOut])
def list_products():
    db = SessionLocal()
    products = db.query(Product).all()
    result = []
    for p in products:
        image_url = f"/images/{p.image_filename}" if p.image_filename else None
        result.append(ProductOut(
            id=p.id,
            name=p.name,
            description=p.description,
            price=p.price,
            image_url=image_url
        ))
    db.close()
    return result


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    db = SessionLocal()
    product = db.query(Product).filter(Product.id == product_id).first()
    db.close()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    image_url = f"/images/{product.image_filename}" if product.image_filename else None
    return ProductOut(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        image_url=image_url
    )


@app.put("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, updated_product: ProductCreate):
    db = SessionLocal()
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        db.close()
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    product.name = updated_product.name
    product.description = updated_product.description
    product.price = updated_product.price

    db.commit()
    db.refresh(product)
    db.close()

    image_url = f"/images/{product.image_filename}" if product.image_filename else None
    return ProductOut(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        image_url=image_url
    )


@app.delete("/products/{product_id}")
def delete_product(product_id: int):
    db = SessionLocal()
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        db.close()
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Remove imagem associada, se houver
    if product.image_filename:
        image_path = os.path.join(UPLOAD_FOLDER, product.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)

    db.delete(product)
    db.commit()
    db.close()
    return {"detail": "Produto deletado com sucesso"}


@app.get("/images/{image_filename}")
def get_image(image_filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, image_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(file_path)
