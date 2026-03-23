from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import json
import os
from werkzeug.utils import secure_filename
# -----------------------------------
# APP CONFIGURATION
# -----------------------------------

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'shopnova-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///shopnova.db'
).replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# -----------------------------------
# MODELS
# -----------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Brand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    market_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    images = db.Column(db.Text)  # JSON list
    stock = db.Column(db.Integer, default=0)
    weight = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def discount_percentage(self):
        if self.market_price > 0:
            return round(((self.market_price - self.selling_price) / self.market_price) * 100)
        return 0

    def to_dict(self):
        try:
            image_list = json.loads(self.images) if self.images else []
        except:
            image_list = []

        return {
            "id": self.id,
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "market_price": self.market_price,
            "selling_price": self.selling_price,
            "description": self.description,
            "images": image_list,
            "stock": self.stock,
            "weight": self.weight,
            "discount": self.discount_percentage(),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M")
        }


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(50), nullable=False)
    customer_city = db.Column(db.String(100))
    order_items = db.Column(db.Text, nullable=False)
    cart_total = db.Column(db.Float, default=0.0)
    delivery_fee = db.Column(db.Float, default=0.0)
    grand_total = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        try:
            items = json.loads(self.order_items)
        except:
            items = []

        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "customer_city": self.customer_city,
            "items": items,
            "cart_total": self.cart_total,
            "delivery_fee": self.delivery_fee,
            "grand_total": self.grand_total,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M")
        }


# -----------------------------------
# HELPER FUNCTIONS
# -----------------------------------

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# -----------------------------------
# AUTH DECORATORS
# -----------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = User.query.get(session.get("user_id"))
        if not user or not user.is_admin:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


# -----------------------------------
# INITIAL DATA
# -----------------------------------

def create_admin():
    with app.app_context():
        if not User.query.filter_by(is_admin=True).first():
            admin = User(username="admin", is_admin=True)
            admin.set_password("shopnova123")
            db.session.add(admin)
            db.session.commit()


# -----------------------------------
# ROUTES
# -----------------------------------

@app.route("/")
def home():
    products = Product.query.order_by(Product.created_at.desc()).all()
    categories = Category.query.all()
    return render_template("index.html", products=products, categories=categories)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Temporary hardcoded admin
        if email == "admin@shopnova.com" and password == "admin123":
            # Create a session for the admin
            # First, check if admin exists in database
            admin = User.query.filter_by(is_admin=True).first()
            if admin:
                session["user_id"] = admin.id
                session["username"] = admin.username
            else:
                # Create admin if doesn't exist
                admin = User(username="admin", is_admin=True)
                admin.set_password("shopnova123")
                db.session.add(admin)
                db.session.commit()
                session["user_id"] = admin.id
                session["username"] = admin.username

            return redirect(url_for("admin_panel"))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

@app.route("/info")
def info():
    return render_template("info.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_panel():
    products = Product.query.all()
    orders = Order.query.order_by(Order.id.desc()).all()
    return render_template(
        "admin.html",
        products=products,
        orders=[o.to_dict() for o in orders]
    )







@app.route("/admin/products")
@admin_required
def get_products():
    """API endpoint to get all products"""
    products = Product.query.order_by(Product.created_at.desc()).all()
    return jsonify([p.to_dict() for p in products])


@app.route("/admin/brands-categories")
@admin_required
def get_brands_categories():
    """API endpoint to get all brands and categories"""
    try:
        brands = Brand.query.order_by(Brand.name).all()
        categories = Category.query.order_by(Category.name).all()

        return jsonify({
            'success': True,
            'brands': [{'id': b.id, 'name': b.name} for b in brands],
            'categories': [{'id': c.id, 'name': c.name} for c in categories]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route("/admin/product/add", methods=["POST"])
@admin_required
def add_product():
    """Add a new product"""
    try:
        # Get form data
        name = request.form.get('name')
        brand = request.form.get('brand')
        category = request.form.get('category')
        market_price = float(request.form.get('market_price'))
        selling_price = float(request.form.get('selling_price'))
        stock = int(request.form.get('stock'))
        weight = float(request.form.get('weight', 0))
        description = request.form.get('description', '')

        # Handle image uploads
        images = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Add timestamp to filename to make it unique
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    images.append(f"/static/uploads/{filename}")

        # Create new product
        new_product = Product(
            name=name,
            brand=brand,
            category=category,
            market_price=market_price,
            selling_price=selling_price,
            stock=stock,
            weight=weight,
            description=description,
            images=json.dumps(images)
        )

        db.session.add(new_product)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Product added successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route("/admin/brand/add", methods=["POST"])
@admin_required
def add_brand():
    """Add a new brand"""
    try:
        # Check if request has JSON
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

        data = request.get_json()
        name = data.get('name', '').strip()

        if not name:
            return jsonify({'success': False, 'error': 'Brand name required'}), 400

        # Check if brand already exists (case insensitive)
        existing = Brand.query.filter(Brand.name.ilike(name)).first()
        if existing:
            return jsonify({'success': False, 'error': f'Brand "{name}" already exists'}), 400

        new_brand = Brand(name=name)
        db.session.add(new_brand)
        db.session.commit()

        return jsonify({
            'success': True,
            'id': new_brand.id,
            'name': new_brand.name,
            'message': f'Brand "{name}" added successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/checkout')
def checkout_page():
    return render_template('checkout.html')


@app.route("/admin/category/add", methods=["POST"])
@admin_required
def add_category():
    """Add a new category"""
    try:
        # Check if request has JSON
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

        data = request.get_json()
        name = data.get('name', '').strip()

        if not name:
            return jsonify({'success': False, 'error': 'Category name required'}), 400

        # Check if category already exists (case insensitive)
        existing = Category.query.filter(Category.name.ilike(name)).first()
        if existing:
            return jsonify({'success': False, 'error': f'Category "{name}" already exists'}), 400

        new_category = Category(name=name)
        db.session.add(new_category)
        db.session.commit()

        return jsonify({
            'success': True,
            'id': new_category.id,
            'name': new_category.name,
            'message': f'Category "{name}" added successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route("/admin/product/<int:product_id>", methods=["DELETE"])
@admin_required
def delete_product(product_id):
    """Delete a product"""
    try:
        product = Product.query.get_or_404(product_id)

        # Delete associated images
        if product.images:
            images = json.loads(product.images)
            for image_path in images:
                # Extract filename from path and delete
                filename = image_path.replace('/static/uploads/', '')
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    os.remove(file_path)

        db.session.delete(product)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Product deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route("/admin/orders")
@admin_required
def get_orders():
    """API endpoint to get all orders"""
    orders = Order.query.order_by(Order.id.desc()).all()
    return jsonify([o.to_dict() for o in orders])


@app.route("/admin/order/<int:order_id>/status", methods=["PUT"])
@admin_required
def update_order_status(order_id):
    """Update order status"""
    try:
        data = request.get_json()
        status = data.get('status')

        order = Order.query.get_or_404(order_id)
        order.status = status
        db.session.commit()

        return jsonify({'success': True, 'message': 'Order status updated'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route("/submit-order", methods=["POST"])
def submit_order():
    data = request.get_json()

    new_order = Order(
        customer_name=data["customer"]["fullName"],
        customer_phone=data["customer"]["phone"],
        customer_city=data["customer"].get("city", ""),
        order_items=json.dumps(data["items"]),
        cart_total=data["totals"]["cartTotal"],
        delivery_fee=data["totals"]["deliveryFee"],
        grand_total=data["totals"]["grandTotal"],
    )

    db.session.add(new_order)
    db.session.commit()

    return jsonify({"success": True, "order_id": new_order.id})


# Add these DELETE routes to your app.py (place them with your other routes)

@app.route("/admin/brand/<int:brand_id>", methods=["DELETE"])
@admin_required
def delete_brand(brand_id):
    """Delete a brand"""
    try:
        brand = Brand.query.get_or_404(brand_id)

        # Check if brand is used by any products
        products_using_brand = Product.query.filter_by(brand=brand.name).first()
        if products_using_brand:
            return jsonify({'success': False, 'error': 'Cannot delete brand that is being used by products'}), 400

        db.session.delete(brand)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Brand deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route("/admin/category/<int:category_id>", methods=["DELETE"])
@admin_required
def delete_category(category_id):
    """Delete a category"""
    try:
        category = Category.query.get_or_404(category_id)

        # Check if category is used by any products
        products_using_category = Product.query.filter_by(category=category.name).first()
        if products_using_category:
            return jsonify({'success': False, 'error': 'Cannot delete category that is being used by products'}), 400

        db.session.delete(category)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Category deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400



# Add to your app.py
@app.route("/api/categories")
def get_categories():
    categories = Category.query.all()
    return jsonify([c.name for c in categories])

@app.route("/api/brands")
def get_brands():
    brands = Brand.query.all()
    return jsonify([b.name for b in brands])

# Add these routes to your app.py file

@app.route("/api/products")
def get_public_products():
    """Public API endpoint to get all products - no login required"""
    try:
        products = Product.query.order_by(Product.created_at.desc()).all()
        products_list = []
        for p in products:
            product_dict = p.to_dict()
            # Ensure images are properly formatted
            if isinstance(product_dict.get('images'), str):
                try:
                    product_dict['images'] = json.loads(product_dict['images'])
                except:
                    product_dict['images'] = []
            products_list.append(product_dict)
        return jsonify(products_list)
    except Exception as e:
        print(f"Error in /api/products: {str(e)}")  # Server-side logging
        return jsonify({'error': str(e)}), 500

@app.route("/api/categories")
def get_public_categories():
    """Public API endpoint to get all categories - no login required"""
    try:
        categories = Category.query.all()
        return jsonify([{'id': c.id, 'name': c.name} for c in categories])
    except Exception as e:
        print(f"Error in /api/categories: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/brands")
def get_public_brands():
    """Public API endpoint to get all brands - no login required"""
    try:
        brands = Brand.query.all()
        return jsonify([{'id': b.id, 'name': b.name} for b in brands])
    except Exception as e:
        print(f"Error in /api/brands: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add a debug route to see all available routes
@app.route("/api/debug/routes")
def debug_routes():
    """Debug endpoint to see all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule)
        })
    return jsonify(routes)


with app.app_context():
    db.create_all()
    create_admin()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_admin()
    app.run(debug=True, port=5002)
