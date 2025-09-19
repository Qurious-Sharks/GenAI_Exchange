import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, UploadFile, File, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from jinja2 import Environment, FileSystemLoader, select_autoescape
import secrets

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "shop_data"
STATIC_DIR = DATA_DIR / "static"
TEMPLATES_DIR = DATA_DIR / "templates"
IMAGES_DIR = DATA_DIR / "uploads"

for d in (DATA_DIR, STATIC_DIR, TEMPLATES_DIR, IMAGES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Minimal CSS
(STATIC_DIR / "styles.css").write_text(
    """
body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:0;background:linear-gradient(180deg,#0ea5e9 0%,#22c55e 100%);color:#0b132a}
.container{max-width:1100px;margin:24px auto;padding:0 16px}
header{background:rgba(11,19,42,.9);backdrop-filter:saturate(1.5) blur(8px);color:#fff;padding:16px;border-bottom:1px solid rgba(255,255,255,.12)}
nav a{color:#fff;margin-right:16px;text-decoration:none;font-weight:600}
.card{background:rgba(255,255,255,.92);backdrop-filter:blur(6px);border:1px solid #e2e8f0;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 8px 24px rgba(2,6,23,.15)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px}
.product img{width:100%;height:180px;object-fit:cover;border-radius:10px;border:1px solid #cbd5e1;box-shadow:0 2px 6px rgba(2,6,23,.1)}
form input,form textarea{width:100%;padding:12px;margin:8px 0;border:1px solid #cbd5e1;border-radius:10px;background:#fff}
form button{background:linear-gradient(90deg,#ec4899,#8b5cf6);color:#fff;border:none;border-radius:10px;padding:12px 18px;cursor:pointer;box-shadow:0 6px 20px rgba(139,92,246,.35)}
h1,h2{margin:12px 0;text-shadow:0 1px 0 rgba(255,255,255,.6)}
footer{margin:24px 0;color:#0b132a;opacity:.8;text-align:center}
.search-container{display:flex;justify-content:flex-end;gap:12px;align-items:center;margin:16px 0 24px 0;flex-wrap:wrap}
.search-form{display:flex;gap:8px;align-items:center;background:rgba(255,255,255,.9);padding:8px 12px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,.1)}
.search-form input{width:200px;padding:8px 12px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-size:14px}
.search-form button{padding:8px 16px;background:linear-gradient(90deg,#ec4899,#8b5cf6);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600}
    """,
    encoding="utf-8",
)

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(['html'])
)

def ensure_template(name: str, content: str) -> None:
    p = TEMPLATES_DIR / name
    if not p.exists():
        p.write_text(content, encoding="utf-8")

ensure_template("base.html", """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="/static/styles.css" />
    <title>{{ title or 'Shop' }}</title>
  </head>
  <body>
    <header>
      <div class="container">
        <nav>
          <a href="/">All Products</a>
          <a href="/upload">Upload Product</a>
          <a href="/admin">Admin Panel</a>
          <form action="/search" method="get" style="display:inline-block;margin-left:16px">
            <input type="text" name="q" placeholder="Search products…" style="width:200px" />
          </form>
          <form action="/search/users" method="get" style="display:inline-block;margin-left:8px">
            <input type="text" name="u" placeholder="Search users…" style="width:180px" />
          </form>
        </nav>
      </div>
    </header>
    <div class="container">
      {% block content %}{% endblock %}
    </div>
  </body>
</html>
""")

ensure_template("index.html", """
{% extends 'base.html' %}
{% block content %}
<h1>All Products</h1>
<div class="search-container">
  <form action="/search" method="get" class="search-form">
    <input type="text" name="q" placeholder="Search products…" />
    <button type="submit">Search</button>
  </form>
  <form action="/search/users" method="get" class="search-form">
    <input type="text" name="u" placeholder="Search users…" />
    <button type="submit">Find</button>
  </form>
</div>
<div class="grid">
  {% for p in products %}
  <div class="card product">
    {% if p.image_path %}<img src="/static/uploads/{{ p.image_path | basename }}" alt="{{ p.name }}" />{% endif %}
    <h3>{{ p.name }}</h3>
    <p><strong>Price:</strong> ₹{{ p.price }}</p>
    <p>{{ p.details }}</p>
    <p><a href="/user/{{ p.user.username }}">By {{ p.user.username }}</a></p>
  </div>
  {% endfor %}
  {% if products|length == 0 %}
    <p>No products yet.</p>
  {% endif %}
  </div>
{% endblock %}
""")

ensure_template("user.html", """
{% extends 'base.html' %}
{% block content %}
<h1>{{ username }}'s Products</h1>
<div class="grid">
  {% for p in products %}
  <div class="card product">
    {% if p.image_path %}<img src="/static/uploads/{{ p.image_path | basename }}" alt="{{ p.name }}" />{% endif %}
    <h3>{{ p.name }}</h3>
    <p><strong>Price:</strong> ₹{{ p.price }}</p>
    <p>{{ p.details }}</p>
  </div>
  {% endfor %}
  {% if products|length == 0 %}
    <p>No products yet for {{ username }}.</p>
  {% endif %}
</div>
{% endblock %}
""")

ensure_template("search.html", """
{% extends 'base.html' %}
{% block content %}
<h1>Search Results</h1>
<p>Query: <strong>{{ query or '' }}</strong></p>
<div class="grid">
  {% for p in products %}
  <div class="card product">
    {% if p.image_path %}<img src="/static/uploads/{{ p.image_path | basename }}" alt="{{ p.name }}" />{% endif %}
    <h3>{{ p.name }}</h3>
    <p><strong>Price:</strong> ₹{{ p.price }}</p>
    <p>{{ p.details }}</p>
    <p><a href="/user/{{ p.user.username }}">By {{ p.user.username }}</a></p>
  </div>
  {% endfor %}
  {% if products|length == 0 %}
    <p>No matching products.</p>
  {% endif %}
</div>
{% endblock %}
""")

ensure_template("users_search.html", """
{% extends 'base.html' %}
{% block content %}
<h1>User Results</h1>
<p>Query: <strong>{{ query or '' }}</strong></p>
<div class="grid">
  {% for user in users %}
    <div class="card">
      <h3><a href="/user/{{ user.username }}">{{ user.username }}</a></h3>
      <p>{{ (user.products | length) if user.products else 0 }} product(s)</p>
    </div>
  {% endfor %}
  {% if users|length == 0 %}
    <p>No matching users.</p>
  {% endif %}
</div>
{% endblock %}
""")

ensure_template("upload.html", """
{% extends 'base.html' %}
{% block content %}
<h1>Upload Product</h1>
<div class="card">
  <form action="/upload" method="post" enctype="multipart/form-data">
    <input type="text" name="username" placeholder="Your Name" required />
    <input type="text" name="name" placeholder="Product Name" required />
    <textarea name="details" rows="4" placeholder="Product Details" required></textarea>
    <input type="number" name="price" step="0.01" placeholder="Price (₹)" required />
    <input type="file" name="image" accept="image/*" />
    <button type="submit">Upload</button>
  </form>
  <p>Duplicate check: same user, same product name → update instead of create.</p>
  <p>View: <a href="/">All Products</a></p>
{% if message %}<p><strong>{{ message }}</strong></p>{% endif %}
 </div>
{% endblock %}
""")

ensure_template("admin.html", """
{% extends 'base.html' %}
{% block content %}
<h1>Admin Panel</h1>
<p>Welcome, {{ admin_user.username }}!</p>

<h2>All Products</h2>
<div class="grid">
  {% for p in products %}
  <div class="card product">
    {% if p.image_path %}<img src="/static/uploads/{{ p.image_path | basename }}" alt="{{ p.name }}" />{% endif %}
    <h3>{{ p.name }}</h3>
    <p><strong>Price:</strong> ₹{{ p.price }}</p>
    <p>{{ p.details }}</p>
    <p><a href="/user/{{ p.user.username }}">By {{ p.user.username }}</a></p>
    <button onclick="deleteProduct({{ p.id }})" style="background:#dc2626;color:#fff;border:none;padding:8px 12px;border-radius:6px;cursor:pointer;margin-top:8px">Delete</button>
  </div>
  {% endfor %}
</div>

<h2>All Users</h2>
<div class="grid">
  {% for u in users %}
  <div class="card">
    <h3>{{ u.username }}</h3>
    <p>Admin: {{ 'Yes' if u.is_admin else 'No' }}</p>
    <p>Products: {{ u.products | length }}</p>
  </div>
  {% endfor %}
</div>

<script>
function deleteProduct(productId) {
  if (confirm('Are you sure you want to delete this product?')) {
    fetch(`/admin/products/${productId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': 'Basic ' + btoa('admin:admin123')
      }
    })
    .then(response => {
      if (response.ok) {
        location.reload();
      } else {
        alert('Failed to delete product');
      }
    })
    .catch(error => {
      alert('Error: ' + error);
    });
  }
}
</script>
{% endblock %}
""")

def basename_filter(path: str) -> str:
    return os.path.basename(path) if path else ""

env.filters['basename'] = basename_filter

DATABASE_URL = f"sqlite:///{DATA_DIR / 'shop.db'}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(128), unique=True, index=True, nullable=False)
    password = Column(String(128), nullable=False, default="")
    is_admin = Column(Boolean, default=False)
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    details = Column(Text, nullable=False)
    price = Column(String(32), nullable=False)
    image_path = Column(String(512), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", back_populates="products")
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_product_name'),
    )

Base.metadata.create_all(engine)

# Initialize default users
def init_default_users():
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(username="admin", password="admin123", is_admin=True)
            db.add(admin)
        
        # Check if user exists
        user = db.query(User).filter(User.username == "user").first()
        if not user:
            user = User(username="user", password="user123", is_admin=False)
            db.add(user)
        
        db.commit()
    finally:
        db.close()

# Initialize users on startup
init_default_users()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

security = HTTPBasic()

def get_current_user(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or user.password != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

app = FastAPI(title="Simple Shop")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
UPLOADS_WEB_DIR = STATIC_DIR / "uploads"
UPLOADS_WEB_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
def all_products(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.id.desc()).all()
    # Force template refresh
    try:
        tpl = env.get_template("index.html")
        return tpl.render(title="All Products", products=products)
    except Exception as e:
        # If template doesn't exist, recreate it
        ensure_template("index.html", """
{% extends 'base.html' %}
{% block content %}
<h1>All Products</h1>
<div class="search-container">
  <form action="/search" method="get" class="search-form">
    <input type="text" name="q" placeholder="Search products…" />
    <button type="submit">Search</button>
  </form>
  <form action="/search/users" method="get" class="search-form">
    <input type="text" name="u" placeholder="Search users…" />
    <button type="submit">Find</button>
  </form>
</div>
<div class="grid">
  {% for p in products %}
  <div class="card product">
    {% if p.image_path %}<img src="/static/uploads/{{ p.image_path | basename }}" alt="{{ p.name }}" />{% endif %}
    <h3>{{ p.name }}</h3>
    <p><strong>Price:</strong> ₹{{ p.price }}</p>
    <p>{{ p.details }}</p>
    <p><a href="/user/{{ p.user.username }}">By {{ p.user.username }}</a></p>
  </div>
  {% endfor %}
  {% if products|length == 0 %}
    <p>No products yet.</p>
  {% endif %}
  </div>
{% endblock %}
""")
        tpl = env.get_template("index.html")
        return tpl.render(title="All Products", products=products)

@app.get("/user/{username}", response_class=HTMLResponse)
def user_products(username: str, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    products = user.products if user else []
    tpl = env.get_template("user.html")
    return tpl.render(title=f"{username}", username=username, products=products)

@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    tpl = env.get_template("upload.html")
    return tpl.render(title="Upload Product", message=None)

@app.get("/search", response_class=HTMLResponse)
def search_products(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    query = (q or "").strip()
    products = []
    if query:
        like = f"%{query}%"
        products = db.query(Product).join(User).filter(
            (Product.name.ilike(like)) | (Product.details.ilike(like)) | (User.username.ilike(like))
        ).order_by(Product.id.desc()).all()
    tpl = env.get_template("search.html")
    return tpl.render(title="Search", products=products, query=query)

@app.get("/search/users", response_class=HTMLResponse)
def search_users(request: Request, u: Optional[str] = None, db: Session = Depends(get_db)):
    query = (u or "").strip()
    users = []
    if query:
        like = f"%{query}%"
        users = db.query(User).filter(User.username.ilike(like)).order_by(User.username.asc()).all()
    tpl = env.get_template("users_search.html")
    return tpl.render(title="Users", users=users, query=query)

@app.get("/debug")
def debug_info():
    """Debug endpoint to check template files"""
    template_files = list(TEMPLATES_DIR.glob("*.html"))
    return {
        "templates_dir": str(TEMPLATES_DIR),
        "template_files": [f.name for f in template_files],
        "index_exists": (TEMPLATES_DIR / "index.html").exists(),
        "static_dir": str(STATIC_DIR),
        "css_exists": (STATIC_DIR / "styles.css").exists()
    }

@app.delete("/admin/products/{product_id}")
def delete_product(product_id: int, admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Delete a product (admin only)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Delete associated image file if it exists
    if product.image_path and os.path.exists(product.image_path):
        try:
            os.remove(product.image_path)
        except:
            pass
    
    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Admin panel with all products and delete options"""
    products = db.query(Product).order_by(Product.id.desc()).all()
    users = db.query(User).all()
    
    tpl = env.get_template("admin.html")
    return tpl.render(title="Admin Panel", products=products, users=users, admin_user=admin_user)

@app.post("/upload")
def upload_product(
    username: str = Form(...),
    name: str = Form(...),
    details: str = Form(...),
    price: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user:
        user = User(username=username.strip())
        db.add(user)
        db.flush()

    # Save image if provided
    saved_path = None
    if image and image.filename:
        fname = f"{user.username}_{name.strip().replace(' ', '_')}_{image.filename}"
        dest = IMAGES_DIR / fname
        with open(dest, 'wb') as f:
            f.write(image.file.read())
        saved_path = str(dest)
        # Also copy to web-accessible uploads for serving
        web_dest = UPLOADS_WEB_DIR / os.path.basename(saved_path)
        try:
            with open(saved_path, 'rb') as src, open(web_dest, 'wb') as dst:
                dst.write(src.read())
        except Exception:
            pass

    # Duplicate check: same user + same product name
    existing = db.query(Product).filter(Product.user_id == user.id, Product.name == name.strip()).first()
    if existing:
        existing.details = details.strip()
        existing.price = price.strip()
        if saved_path:
            existing.image_path = saved_path
        db.commit()
        return RedirectResponse(url=f"/user/{user.username}", status_code=303)

    product = Product(
        name=name.strip(),
        details=details.strip(),
        price=price.strip(),
        image_path=saved_path,
        user=user,
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url=f"/user/{user.username}", status_code=303)

@app.post("/api/products")
def api_create_product(payload: dict, db: Session = Depends(get_db)):
    username = (payload.get('user') or payload.get('username') or '').strip()
    name = (payload.get('product_name') or payload.get('name') or '').strip()
    details = (payload.get('product_details') or payload.get('details') or '').strip()
    price = str(payload.get('price') or payload.get('cost') or '').strip()
    image_path = (payload.get('image_path') or payload.get('product_image_path') or '').strip()
    if not (username and name and details and price):
        raise HTTPException(status_code=400, detail="Missing required fields")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username)
        db.add(user)
        db.flush()

    existing = db.query(Product).filter(Product.user_id == user.id, Product.name == name).first()
    if existing:
        existing.details = details
        existing.price = price
        if image_path:
            existing.image_path = image_path
            # Copy into static uploads if it exists
            try:
                if os.path.exists(image_path):
                    web_dest = UPLOADS_WEB_DIR / os.path.basename(image_path)
                    with open(image_path, 'rb') as src, open(web_dest, 'wb') as dst:
                        dst.write(src.read())
            except Exception:
                pass
        db.commit()
        return {"status": "updated", "id": existing.id}

    # If image_path points to external generated image, copy it into static uploads for serving
    copied_path = None
    if image_path and os.path.exists(image_path):
        try:
            web_dest = UPLOADS_WEB_DIR / os.path.basename(image_path)
            with open(image_path, 'rb') as src, open(web_dest, 'wb') as dst:
                dst.write(src.read())
            copied_path = str(image_path)
        except Exception:
            copied_path = image_path

    product = Product(name=name, details=details, price=price, image_path=copied_path or image_path or None, user=user)
    db.add(product)
    db.commit()
    return {"status": "created", "id": product.id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)


