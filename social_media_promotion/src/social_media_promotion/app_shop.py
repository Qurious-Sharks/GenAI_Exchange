import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, UploadFile, File, Request, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.templating import Jinja2Templates

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "shop_data"

app = FastAPI()
templates = Jinja2Templates(directory=str(DATA_DIR / "templates"))
DATA_DIR = BASE_DIR / "shop_data"
STATIC_DIR = DATA_DIR / "static"
TEMPLATES_DIR = DATA_DIR / "templates"
IMAGES_DIR = DATA_DIR / "uploads"

for d in (DATA_DIR, STATIC_DIR, TEMPLATES_DIR, IMAGES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Database setup
engine = create_engine(f"sqlite:///{DATA_DIR}/shop.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# User models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    is_admin = Column(Boolean, default=False)
    session_id = Column(String, unique=True, nullable=True)
    products = relationship("Product", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    details = Column(Text)
    price = Column(String)
    image_path = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="products")
    __table_args__ = (UniqueConstraint('user_id', 'name', name='unique_user_product'),)

# User authentication dependency
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    user = db.query(User).filter(User.session_id == session_id).first()
    if user:
        print(f"Found user {user.username} with session {session_id}")
    return user

async def authenticate_user(username: str, password: str, db: Session):
    print(f"Attempting to authenticate user: {username}")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        print("User not found")
        return None
    if user.password != password:  # In production, use proper password hashing!
        print("Invalid password")
        return None
    print(f"Authentication successful for user: {username}")
    return user

def ensure_admin_exists(db: Session):
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        print("Creating default admin user")
        admin = User(
            username="admin",
            password="admin123",  # In production, use proper password hashing!
            is_admin=True
        )
        db.add(admin)
        try:
            db.commit()
            db.refresh(admin)
            print("Admin user created successfully")
        except Exception as e:
            print(f"Error creating admin user: {e}")
            db.rollback()
    return admin

# Create tables
Base.metadata.create_all(bind=engine)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    print(f"Root page accessed by: {current_user.username if current_user else 'anonymous'}")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": current_user,
            "title": "ArtisanHub - Home",
            "products": []  # You can add products here if needed
        }
    )

# User authentication dependency
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    user = db.query(User).filter(User.session_id == session_id).first()
    if user:
        print(f"Found user {user.username} with session {session_id}")
    return user

async def authenticate_user(username: str, password: str, db: Session):
    print(f"Attempting to authenticate user: {username}")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        print("User not found")
        return None
    if user.password != password:  # In production, use proper password hashing!
        print("Invalid password")
        return None
    print(f"Authentication successful for user: {username}")
    return user

# Ensure default admin user exists
def ensure_admin_exists(db: Session):
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        print("Creating default admin user")
        admin = User(
            username="admin",
            password="admin123",  # In production, use proper password hashing!
            is_admin=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    return admin

def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

# Startup event to ensure admin exists
@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    ensure_admin_exists(db)
    db.close()

# Login routes
@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    if current_user:
        print(f"User already logged in: {current_user.username}")
        return RedirectResponse(url="/", status_code=302)
    
    print("Rendering login page for anonymous user")
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "current_user": None,
            "messages": [],
            "title": "Login - ArtisanHub"
        }
    )

@app.post("/login")
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...)
):
    print(f"Login attempt for user: {username}")
    
    try:
        # First, ensure we have a default admin user
        ensure_admin_exists(db)
        
        # Try to authenticate
        user = await authenticate_user(username, password, db)
        
        if not user:
            print("Authentication failed")
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "current_user": None,
                    "messages": ["Invalid username or password"],
                    "title": "Login - ArtisanHub"
                }
            )
        
        print(f"Authentication successful for {username}")
        
        # Create new session
        session_id = secrets.token_urlsafe(32)
        user.session_id = session_id
        db.commit()
        db.refresh(user)
        
        # Create response
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=3600,
            secure=False,  # Set to True in production with HTTPS
            samesite='lax',
            path="/"
        )
        
        print(f"Set session cookie for user {username}")
        return response
        
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "current_user": None,
                "messages": ["An error occurred during login. Please try again."],
                "title": "Login - ArtisanHub"
            }
        )

@app.get("/logout")
async def logout(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print("Logout attempt")
    if current_user:
        print(f"Logging out user: {current_user.username}")
        # Clear the session from database
        current_user.session_id = None
        db.commit()
        db.refresh(current_user)
    
    # Always clear the cookie regardless of current_user
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(
        key="session_id",
        path="/",  # Important: must match the path used when setting
        httponly=True,
        secure=False  # Match the secure setting used when setting
    )
    print("Cleared session cookie")
    return response

# Product deletion routes
@app.post("/admin/products/{product_id}/delete")
async def delete_product(
    product_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Delete the product image if it exists
    if product.image_path:
        image_path = STATIC_DIR / "uploads" / product.image_path
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            print(f"Error deleting image: {e}")
    
    db.delete(product)
    db.commit()
    return RedirectResponse(url="/admin", status_code=302)
import secrets

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "shop_data"
STATIC_DIR = DATA_DIR / "static"
TEMPLATES_DIR = DATA_DIR / "templates"
IMAGES_DIR = DATA_DIR / "uploads"

for d in (DATA_DIR, STATIC_DIR, TEMPLATES_DIR, IMAGES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Beautiful Modern CSS
(STATIC_DIR / "styles.css").write_text(
    """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { 
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #333;
}
.container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
header { 
    background: rgba(255,255,255,0.95); 
    backdrop-filter: blur(10px);
    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
    position: sticky; top: 0; z-index: 100;
}
.navbar { 
    display: flex; 
    justify-content: space-between; 
    align-items: center; 
    padding: 1rem 0;
}
.logo { 
    font-size: 1.8rem; 
    font-weight: bold; 
    background: linear-gradient(45deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-decoration: none;
}
.nav-links { display: flex; gap: 2rem; align-items: center; }
.nav-links a { 
    text-decoration: none; 
    color: #333; 
    font-weight: 500; 
    transition: color 0.3s;
    padding: 0.5rem 1rem;
    border-radius: 8px;
}
.nav-links a:hover { color: #667eea; background: rgba(102,126,234,0.1); }
.search-bar { 
    display: flex; 
    gap: 1rem; 
    align-items: center;
    margin-left: 2rem;
}
.search-form {
    display: flex; 
    gap: 0.25rem; 
    background: rgba(255,255,255,0.9); 
    padding: 0.35rem;
    border-radius: 50px; 
    box-shadow: 0 2px 15px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
    border: 2px solid transparent;
}
.search-form:hover, .search-form:focus-within {
    background: white;
    border-color: #667eea;
    box-shadow: 0 4px 20px rgba(102,126,234,0.2);
    transform: translateY(-1px);
}
.search-form input { 
    border: none; 
    outline: none;
    background: transparent;
    padding: 0.5rem 1rem; 
    font-size: 0.95rem;
    width: 180px;
    color: #333;
    transition: width 0.3s ease;
}
.search-form input::placeholder {
    color: #999;
}
.search-form input:focus {
    width: 220px;
}
.search-form button { 
    background: linear-gradient(45deg, #667eea, #764ba2); 
    color: white; 
    border: none; 
    width: 32px;
    height: 32px;
    border-radius: 50%; 
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    transition: all 0.3s ease;
    padding: 0;
}
.search-form button:hover { 
    transform: scale(1.1); 
    box-shadow: 0 2px 10px rgba(102,126,234,0.3);
}
.hero { 
    text-align: center; 
    padding: 4rem 0; 
    color: white;
}
.hero h1 { 
    font-size: 3.5rem; 
    margin-bottom: 1rem; 
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}
.hero p { 
    font-size: 1.2rem; 
    margin-bottom: 2rem; 
    opacity: 0.9;
}
.btn { 
    display: inline-block; 
    background: linear-gradient(45deg, #667eea, #764ba2); 
    color: white; 
    padding: 1rem 2rem; 
    text-decoration: none; 
    border-radius: 30px; 
    font-weight: 600; 
    transition: transform 0.3s, box-shadow 0.3s;
    box-shadow: 0 4px 15px rgba(102,126,234,0.4);
    border: none;
    cursor: pointer;
}
.btn:hover { 
    transform: translateY(-2px); 
    box-shadow: 0 6px 20px rgba(102,126,234,0.6);
}
.grid { 
    display: grid; 
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); 
    gap: 2rem; 
    padding: 2rem 0;
}
.card { 
    background: white; 
    border-radius: 20px; 
    padding: 1.5rem; 
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    transition: transform 0.3s, box-shadow 0.3s;
    overflow: hidden;
}
.card:hover { 
    transform: translateY(-5px); 
    box-shadow: 0 20px 40px rgba(0,0,0,0.15);
}
.product img { 
    width: 100%; 
    height: 200px; 
    object-fit: cover; 
    border-radius: 15px; 
    margin-bottom: 1rem;
}
.product h3 { 
    font-size: 1.3rem; 
    margin-bottom: 0.5rem; 
    color: #333;
}
.product .price { 
    font-size: 1.5rem; 
    font-weight: bold; 
    color: #667eea; 
    margin-bottom: 1rem;
}
.product p { 
    color: #666; 
    line-height: 1.6; 
    margin-bottom: 1rem;
}
.product .author { 
    color: #999; 
    font-size: 0.9rem;
}
.form-container { 
    max-width: 600px; 
    margin: 2rem auto; 
    background: white; 
    padding: 2rem; 
    border-radius: 20px; 
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}
.form-group { margin-bottom: 1.5rem; }
.form-group label { 
    display: block; 
    margin-bottom: 0.5rem; 
    font-weight: 600; 
    color: #333;
}
.form-group input, .form-group textarea { 
    width: 100%; 
    padding: 1rem; 
    border: 2px solid #e1e5e9; 
    border-radius: 10px; 
    font-size: 1rem; 
    transition: border-color 0.3s;
}
.form-group input:focus, .form-group textarea:focus { 
    outline: none; 
    border-color: #667eea;
}
.login-form { 
    max-width: 400px; 
    margin: 4rem auto; 
    background: white; 
    padding: 2rem; 
    border-radius: 20px; 
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}
.page-title { 
    text-align: center; 
    color: white; 
    font-size: 2.5rem; 
    margin: 2rem 0; 
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}
.delete-btn { 
    background: #ff4757; 
    color: white; 
    border: none; 
    padding: 0.5rem 1rem; 
    border-radius: 8px; 
    cursor: pointer; 
    transition: background 0.3s;
}
.delete-btn:hover { background: #ff3742; }
.admin-badge { 
    background: #667eea; 
    color: white; 
    padding: 0.2rem 0.5rem; 
    border-radius: 12px; 
    font-size: 0.8rem;
}
    """,
    encoding="utf-8",
)

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(['html'])
)

# Add basename filter
def basename_filter(path):
    return os.path.basename(path) if path else ""

env.filters['basename'] = basename_filter

# Database setup
engine = create_engine(f"sqlite:///{DATA_DIR}/shop.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    is_admin = Column(Boolean, default=False)
    session_id = Column(String, unique=True, nullable=True)
    products = relationship("Product", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    details = Column(Text)
    price = Column(String)
    image_path = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="products")
    __table_args__ = (UniqueConstraint('user_id', 'name', name='unique_user_product'),)

Base.metadata.create_all(bind=engine)

def init_default_users():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(username="admin", password="admin123", is_admin=True)
            db.add(admin)
        
        user = db.query(User).filter(User.username == "user").first()
        if not user:
            user = User(username="user", password="user123", is_admin=False)
            db.add(user)
        
        db.commit()
        print("✅ Default users created: admin/admin123, user/user123")
    finally:
        db.close()

# Create templates
def ensure_template(name: str, content: str) -> None:
    p = TEMPLATES_DIR / name
    if not p.exists():
        p.write_text(content, encoding="utf-8")

ensure_template("base.html", """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title or 'ArtisanHub - Marketplace' }}</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <header>
        <div class="container">
            <nav class="navbar">
                <a href="/" class="logo">🎨 ArtisanHub</a>
                <div class="nav-links">
                    <a href="/">Home</a>
                    {% if not current_user or not current_user.is_admin %}
                        <a href="/products">Products</a>
                        <a href="/upload">Upload</a>
                    {% endif %}
                    {% if current_user %}
                        {% if current_user.is_admin %}
                            <a href="/user/{{ current_user.username }}">My Profile</a>
                            <a href="/admin" style="display: none;">Admin Panel</a>
                        {% else %}
                            <a href="/user/{{ current_user.username }}">My Profile</a>
                        {% endif %}
                        <a href="/logout" class="btn" style="padding: 0.4rem 1rem; font-size: 0.9rem;">Logout</a>
                    {% else %}
                        <a href="/login" class="btn" style="padding: 0.4rem 1rem; font-size: 0.9rem;">Login</a>
                    {% endif %}
                </div>
                <div class="search-bar">
                    <form action="/search" method="get" class="search-form">
                        <input type="text" name="q" placeholder="Find products..." aria-label="Search products" />
                        <button type="submit" title="Search products">�</button>
                    </form>
                    <form action="/search/users" method="get" class="search-form">
                        <input type="text" name="u" placeholder="Find creators..." aria-label="Search users" />
                        <button type="submit" title="Search users">👤</button>
                    </form>
                </div>
            </nav>
        </div>
    </header>
    <main>
        {% block content %}{% endblock %}
    </main>
</body>
</html>
""")

ensure_template("index.html", """
{% extends 'base.html' %}
{% block content %}
<div class="hero">
    <h1>Welcome to ArtisanHub</h1>
    <p>Discover unique handmade products from talented artisans around the world</p>
    <a href="/products" class="btn">Browse Products</a>
    <a href="/upload" class="btn" style="margin-left: 1rem;">Start Selling</a>
</div>
<div class="container">
    <h2 class="page-title">Featured Products</h2>
    <div class="grid">
        {% for p in products[:6] %}
        <div class="card product">
            {% if p.image_path %}<img src="/static/uploads/{{ p.image_path.split('/')[-1] if '/' in p.image_path else p.image_path }}" alt="{{ p.name }}" />{% endif %}
            <h3>{{ p.name }}</h3>
            <div class="price">₹{{ p.price }}</div>
            <p>{{ p.details[:100] }}{% if p.details|length > 100 %}...{% endif %}</p>
            <div class="author">By {{ p.user.username }}</div>
        </div>
        {% endfor %}
        {% if products|length == 0 %}
        <div class="card" style="text-align: center; grid-column: 1/-1;">
            <h3>No products yet</h3>
            <p>Be the first to showcase your amazing creations!</p>
            <a href="/upload" class="btn">Upload Product</a>
        </div>
        {% endif %}
    </div>
    {% if products|length > 6 %}
    <div style="text-align: center; margin: 2rem 0;">
        <a href="/products" class="btn">View All Products</a>
    </div>
    {% endif %}
</div>
{% endblock %}
""")

ensure_template("products.html", """
{% extends 'base.html' %}
{% block content %}
<div class="container">
    <h1 class="page-title">All Products</h1>
    <div class="grid">
        {% for p in products %}
        <div class="card product">
            {% if p.image_path %}<img src="/static/uploads/{{ p.image_path.split('/')[-1] if '/' in p.image_path else p.image_path }}" alt="{{ p.name }}" />{% endif %}
            <h3>{{ p.name }}</h3>
            <div class="price">₹{{ p.price }}</div>
            <p>{{ p.details }}</p>
            <div class="author">By {{ p.user.username }}</div>
        </div>
        {% endfor %}
        {% if products|length == 0 %}
        <div class="card" style="text-align: center; grid-column: 1/-1;">
            <h3>No products found</h3>
            <p>Be the first to showcase your amazing creations!</p>
            <a href="/upload" class="btn">Upload Product</a>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
""")

ensure_template("login.html", """
{% extends 'base.html' %}
{% block content %}
<div class="container">
    <div class="login-form">
        <h2 style="text-align: center; margin-bottom: 2rem; color: #333;">Login to ArtisanHub</h2>
        <form action="/login" method="post">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="btn" style="width: 100%; margin-top: 1rem;">Login</button>
        </form>
        <div style="text-align: center; margin-top: 2rem; color: #666;">
            <p>Demo accounts:</p>
            <p><strong>Admin:</strong> admin / admin123</p>
            <p><strong>User:</strong> user / user123</p>
        </div>
    </div>
</div>
{% endblock %}
""")

ensure_template("upload.html", """
{% extends 'base.html' %}
{% block content %}
<div class="container">
    <h1 class="page-title">Sell Your Product</h1>
    <div class="form-container">
        <form action="/upload" method="post" enctype="multipart/form-data">
            <div class="form-group">
                <label for="username">Your Name</label>
                <input type="text" id="username" name="username" placeholder="Enter your name" required>
            </div>
            <div class="form-group">
                <label for="name">Product Name</label>
                <input type="text" id="name" name="name" placeholder="What are you selling?" required>
            </div>
            <div class="form-group">
                <label for="details">Product Description</label>
                <textarea id="details" name="details" rows="4" placeholder="Describe your product in detail..." required></textarea>
            </div>
            <div class="form-group">
                <label for="price">Price (₹)</label>
                <input type="number" id="price" name="price" step="0.01" placeholder="0.00" required>
            </div>
            <div class="form-group">
                <label for="image">Product Image</label>
                <input type="file" id="image" name="image" accept="image/*">
            </div>
            <button type="submit" class="btn" style="width: 100%;">List Product</button>
        </form>
        {% if message %}<p style="color: #667eea; text-align: center; margin-top: 1rem;"><strong>{{ message }}</strong></p>{% endif %}
    </div>
</div>
{% endblock %}
""")

ensure_template("user.html", """
{% extends 'base.html' %}
{% block content %}
<div class="container">
    <h1 class="page-title">
        {{ user.username }}'s Profile
        {% if user.is_admin %}<span class="admin-badge">Admin</span>{% endif %}
    </h1>

    <div class="card" style="margin-bottom: 2rem;">
        <h2 style="margin-bottom: 1.5rem;">User Information</h2>
        <div class="user-info">
            <p><strong>Username:</strong> {{ user.username }}</p>
            <p><strong>Role:</strong> {% if user.is_admin %}Administrator{% else %}Regular User{% endif %}</p>
            <p><strong>Products:</strong> {{ products|length }} items</p>
        </div>
    </div>

    <div class="card">
        <h2 style="margin-bottom: 1.5rem;">{{ user.username }}'s Products</h2>
        <div class="grid">
            {% for p in products %}
            <div class="card product">
                {% if p.image_path %}<img src="/static/uploads/{{ p.image_path.split('/')[-1] if '/' in p.image_path else p.image_path }}" alt="{{ p.name }}" />{% endif %}
                <h3>{{ p.name }}</h3>
                <div class="price">₹{{ p.price }}</div>
                <p>{{ p.details }}</p>
                {% if current_user and (current_user.is_admin or current_user.id == user.id) %}
                <div style="margin-top: 1rem;">
                    <form action="/admin/products/{{ p.id }}/delete" method="post">
                        <button type="submit" class="delete-btn" style="width: 100%;" onclick="return confirm('Are you sure you want to delete this product?')">Delete Product</button>
                    </form>
                </div>
                {% endif %}
            </div>
            {% endfor %}
            {% if products|length == 0 %}
            <div class="card" style="text-align: center; grid-column: 1/-1;">
                <h3>No products yet</h3>
                <p>This user hasn't added any products yet.</p>
            </div>
            {% endif %}
        </div>
    </div>
</div>

<style>
.user-info {
    display: grid;
    gap: 1rem;
}
.user-info p {
    margin: 0;
    padding: 0;
    color: #495057;
}
.user-info strong {
    color: #333;
    font-weight: 600;
    margin-right: 0.5rem;
}
</style>
{% endblock %}
""")

ensure_template("admin.html", """
{% extends 'base.html' %}
{% block content %}
<div class="container">
    <h1 class="page-title">Admin Panel</h1>
    <p class="admin-welcome">Welcome, {{ current_user.username }}!</p>
    
    <!-- User Management Section -->
    <div class="card" style="margin-bottom: 2rem;">
        <h2 style="margin-bottom: 1.5rem;">User Management</h2>
        <div class="table-wrapper">
            <table class="admin-table">
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Products</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for u in users %}
                    <tr>
                        <td>{{ u.username }}</td>
                        <td>{% if u.is_admin %}<span class="admin-badge">Admin</span>{% else %}User{% endif %}</td>
                        <td><a href="/user/{{ u.username }}" class="link-btn">View Products ({{ u.products|length }})</a></td>
                        <td>
                            {% if not u.is_admin %}
                            <form action="/admin/users/{{ u.id }}/delete" method="post" style="display: inline;">
                                <button type="submit" class="delete-btn" onclick="return confirm('Are you sure you want to delete this user?')">Delete</button>
                            </form>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Product Management Section -->
    <div class="card">
        <h2 style="margin-bottom: 1.5rem;">Product Management</h2>
        <div class="grid">
            {% for p in products %}
            <div class="card product">
                {% if p.image_path %}<img src="/static/uploads/{{ p.image_path.split('/')[-1] if '/' in p.image_path else p.image_path }}" alt="{{ p.name }}" />{% endif %}
                <h3>{{ p.name }}</h3>
                <div class="price">₹{{ p.price }}</div>
                <p>{{ p.details }}</p>
                <div class="author">
                    By <a href="/user/{{ p.user.username }}" class="author-link">{{ p.user.username }}</a>
                    {% if p.user.is_admin %}<span class="admin-badge">Admin</span>{% endif %}
                </div>
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <form action="/admin/products/{{ p.id }}/delete" method="post" style="flex: 1;">
                        <button type="submit" class="delete-btn" style="width: 100%;" onclick="return confirm('Are you sure you want to delete this product?')">Delete Product</button>
                    </form>
                </div>
            </div>
            {% endfor %}
            {% if products|length == 0 %}
            <div class="card" style="text-align: center; grid-column: 1/-1;">
                <h3>No products yet</h3>
                <p>Products added by users will appear here.</p>
            </div>
            {% endif %}
        </div>
    </div>
</div>

<style>
.table-wrapper {
    overflow-x: auto;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.admin-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}
.admin-table th,
.admin-table td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid #eee;
}
.admin-table th {
    background: #f8f9fa;
    font-weight: 600;
    color: #333;
}
.admin-table tr:last-child td {
    border-bottom: none;
}
.link-btn {
    display: inline-block;
    padding: 0.5rem 1rem;
    background: #e9ecef;
    color: #495057;
    text-decoration: none;
    border-radius: 5px;
    font-size: 0.9rem;
    transition: all 0.3s ease;
}
.link-btn:hover {
    background: #dee2e6;
    transform: translateY(-1px);
}
.author-link {
    color: #667eea;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.3s;
}
.author-link:hover {
    color: #764ba2;
    text-decoration: underline;
}
.admin-welcome {
    text-align: center;
    color: #495057;
    margin-bottom: 2rem;
    font-size: 1.2rem;
    font-weight: 500;
}
</style>
{% endblock %}
""")

# FastAPI app
app = FastAPI(title="ArtisanHub - Marketplace")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
UPLOADS_WEB_DIR = STATIC_DIR / "uploads"
UPLOADS_WEB_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_id")
    return response

@app.get("/", response_class=HTMLResponse)
async def homepage(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    products = db.query(Product).order_by(Product.id.desc()).all()
    tpl = env.get_template("index.html")
    return tpl.render(
        title="ArtisanHub - Home",
        products=products,
        current_user=current_user
    )

@app.get("/products", response_class=HTMLResponse)
async def all_products(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    products = db.query(Product).order_by(Product.id.desc()).all()
    tpl = env.get_template("products.html")
    return tpl.render(
        title="All Products - ArtisanHub",
        products=products,
        current_user=current_user
    )

@app.get("/login", response_class=HTMLResponse)
async def login_form(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    tpl = env.get_template("login.html")
    return tpl.render(
        title="Login - ArtisanHub",
        message=None,
        current_user=None
    )

@app.post("/login")
def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if user and user.password == password:
        # Generate a new session ID
        session_id = secrets.token_hex(32)
        user.session_id = session_id
        db.commit()
        
        # Create response with cookie
        if user.is_admin:
            response = RedirectResponse(url="/admin", status_code=303)
        else:
            response = RedirectResponse(url="/products", status_code=303)
        
        # Set session cookie
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            samesite='lax'
        )
        return response
    else:
        tpl = env.get_template("login.html")
        return tpl.render(title="Login - ArtisanHub", message="Invalid credentials")

@app.get("/user/{username}", response_class=HTMLResponse)
async def user_profile(
    username: str, 
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    products = user.products
    tpl = env.get_template("user.html")
    return tpl.render(
        title=f"{username}'s Profile - ArtisanHub",
        user=user,
        products=products,
        current_user=current_user
    )

@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    tpl = env.get_template("upload.html")
    return tpl.render(title="Upload Product - ArtisanHub", message=None)

@app.post("/upload")
def upload_product(
    username: str = Form(...),
    name: str = Form(...),
    details: str = Form(...),
    price: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Find or create user
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, password="", is_admin=False)
        db.add(user)
        db.flush()
    
    # Handle image upload
    image_path = None
    if image and image.filename:
        image_path = f"{username}_{name}_{image.filename}"
        image_path = "".join(c for c in image_path if c.isalnum() or c in "._-")
        full_path = IMAGES_DIR / image_path
        with open(full_path, "wb") as f:
            f.write(image.file.read())
        
        # Copy to web directory
        web_path = UPLOADS_WEB_DIR / image_path
        with open(web_path, "wb") as f:
            f.write(image.file.read())
    
    # Check for duplicate
    existing = db.query(Product).filter(Product.user_id == user.id, Product.name == name).first()
    if existing:
        existing.details = details
        existing.price = price
        if image_path:
            existing.image_path = image_path
        message = f"Updated existing product: {name}"
    else:
        product = Product(
            name=name,
            details=details,
            price=price,
            image_path=image_path,
            user_id=user.id
        )
        db.add(product)
        message = f"Created new product: {name}"
    
    db.commit()
    tpl = env.get_template("upload.html")
    return tpl.render(title="Upload Product - ArtisanHub", message=message)

@app.post("/api/products")
def api_upload_product(
    username: str = Form(...),
    name: str = Form(...),
    details: str = Form(...),
    price: str = Form(...),
    image_path: str = Form(None),
    db: Session = Depends(get_db)
):
    # Find or create user
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, password="", is_admin=False)
        db.add(user)
        db.flush()
    
    # Handle image copy
    web_image_path = None
    if image_path and os.path.exists(image_path):
        filename = os.path.basename(image_path)
        web_image_path = f"{username}_{name}_{filename}"
        web_image_path = "".join(c for c in web_image_path if c.isalnum() or c in "._-")
        web_path = UPLOADS_WEB_DIR / web_image_path
        with open(image_path, "rb") as src, open(web_path, "wb") as dst:
            dst.write(src.read())
    
    # Check for duplicate
    existing = db.query(Product).filter(Product.user_id == user.id, Product.name == name).first()
    if existing:
        existing.details = details
        existing.price = price
        if web_image_path:
            existing.image_path = web_image_path
    else:
        product = Product(
            name=name,
            details=details,
            price=price,
            image_path=web_image_path,
            user_id=user.id
        )
        db.add(product)
    
    db.commit()
    return {"status": "success", "message": f"Product {name} uploaded successfully"}

@app.get("/search", response_class=HTMLResponse)
def search_products(q: str, request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).filter(
        Product.name.contains(q) | Product.details.contains(q)
    ).all()
    tpl = env.get_template("products.html")
    return tpl.render(title=f"Search Results for '{q}' - ArtisanHub", products=products)

@app.get("/search/users", response_class=HTMLResponse)
def search_users(u: str, request: Request, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.username.contains(u)).all()
    products = []
    for user in users:
        products.extend(user.products)
    tpl = env.get_template("products.html")
    return tpl.render(title=f"Products by users matching '{u}' - ArtisanHub", products=products)

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    
    products = db.query(Product).all()
    users = db.query(User).all()
    tpl = env.get_template("admin.html")
    return tpl.render(
        title="Admin Panel - ArtisanHub",
        current_user=admin,  # Pass the admin user from the require_admin dependency
        products=products,
        users=users
    )

@app.post("/admin/products/{product_id}/delete")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        if product.image_path:
            image_path = UPLOADS_WEB_DIR / product.image_path
            if image_path.exists():
                image_path.unlink()
        db.delete(product)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)

# User authentication dependency
def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    user = db.query(User).filter(User.session_id == session_id).first()
    return user

@app.get("/user/{user_id}/products", response_class=HTMLResponse)
def user_products(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    products = db.query(Product).filter(Product.user_id == user_id).all()
    tpl = env.get_template("user_products.html")
    return tpl.render(
        title=f"Products by {user.username} - ArtisanHub",
        user=user,
        products=products
    )

@app.post("/admin/users/{user_id}/delete")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        if user.is_admin:
            raise HTTPException(status_code=400, detail="Cannot delete admin users")
        
        # Delete user's products
        products = db.query(Product).filter(Product.user_id == user_id).all()
        for product in products:
            if product.image_path:
                image_path = UPLOADS_WEB_DIR / product.image_path
                if image_path.exists():
                    image_path.unlink()
            db.delete(product)
        
        db.delete(user)
        db.commit()
    
    return RedirectResponse(url="/admin", status_code=303)

# Update the base model to include is_admin field
Base.metadata.create_all(bind=engine)

# Initialize default users
init_default_users()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)