from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class users(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    
    
    full_name = db.Column(db.String(150))
    role = db.Column(db.String(50), default='admin')
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Create hashed password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check hashed password"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def password(self):
        """Prevent password from being accessed"""
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        """Set password automatically hashes it"""
        self.set_password(password)


class Seller(db.Model):
    __tablename__ = "seller"
    id = db.Column(db.Integer, primary_key=True)

    # User isolation
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Personal Details
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    contact_number = db.Column(db.String(20))
    email = db.Column(db.String(120), index=True)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))

    # Business Details
    company_name = db.Column(db.String(150))
    company_email = db.Column(db.String(120))
    work_number = db.Column(db.String(20))
    company_logo = db.Column(db.String(200))
    gst_number = db.Column(db.String(50))
    seller_code = db.Column(db.String(50), unique=True)

    # Bank Details
    bank_name = db.Column(db.String(100))
    account_holder_name = db.Column(db.String(150))
    account_number = db.Column(db.String(50))
    ifsc = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=db.func.now())
    
    # Relationships
    purchases = db.relationship('Purchase', backref='seller', lazy='dynamic',
                                foreign_keys='Purchase.seller_id')

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_total_purchased(self):
        """Total quantity purchased from this seller"""
        return db.session.query(db.func.sum(Purchase.quantity))\
            .filter_by(seller_id=self.id).scalar() or 0
    
    def get_total_spent(self):
        """Total amount spent with this seller"""
        return db.session.query(db.func.sum(Purchase.total_cost))\
            .filter_by(seller_id=self.id).scalar() or 0
    
    def __repr__(self):
        return f'<Seller {self.get_full_name()}>'


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    # User isolation
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # SKU for multi-product support
    sku = db.Column(db.String(50), unique=True, index=True)

    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    
    category = db.Column(db.String(100), index=True)
    
    image = db.Column(db.String(255), default='default-product.jpg')

    manufacturer_name = db.Column(db.String(100))
    manufacturer_brand = db.Column(db.String(100))

    # Suggested selling price (for order form default)
    suggested_selling_price = db.Column(db.Float, default=0)
    
    # Low stock threshold
    low_stock_threshold = db.Column(db.Integer, default=5)
    
    status = db.Column(db.String(50), default='Draft')
    
    published_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    purchases = db.relationship('Purchase', backref='product', lazy='select',
                                foreign_keys='Purchase.product_id')
    order_items = db.relationship('OrderItem', backref='product', lazy='select',
                                  foreign_keys='OrderItem.product_id')

    def generate_sku(self):
        """Generate a unique SKU for the product"""
        import random
        import string
        category_code = (self.category[:3].upper() if self.category else 'PRD')
        random_num = ''.join(random.choices(string.digits, k=4))
        random_chars = ''.join(random.choices(string.ascii_uppercase, k=3))
        return f"{category_code}-{random_chars}-{random_num}"

    def get_current_stock(self):
        """Calculate current stock = total purchased - total sold"""
        from sqlalchemy import func
        
        total_purchased = db.session.query(func.sum(Purchase.quantity))\
            .filter(Purchase.product_id == self.id).scalar() or 0
        
        total_sold = db.session.query(func.sum(OrderItem.quantity))\
            .join(Order, Order.id == OrderItem.order_id)\
            .filter(OrderItem.product_id == self.id)\
            .filter(Order.status != 'Cancelled')\
            .scalar() or 0
        
        return total_purchased - total_sold

    def get_average_purchase_price(self):
        """Calculate average purchase price from all purchases"""
        from sqlalchemy import func
        
        total_cost = db.session.query(func.sum(Purchase.total_cost))\
            .filter(Purchase.product_id == self.id).scalar()
        total_qty = db.session.query(func.sum(Purchase.quantity))\
            .filter(Purchase.product_id == self.id).scalar()
        
        total_cost = float(total_cost) if total_cost is not None else 0
        total_qty = float(total_qty) if total_qty is not None else 0
        
        if total_qty > 0:
            return round(total_cost / total_qty, 2)
        return 0

    def is_low_stock(self):
        """Check if stock is below threshold"""
        return self.get_current_stock() <= self.low_stock_threshold
    
    def __repr__(self):
        return f'<Product {self.title}>'


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    
    # User isolation
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
   # pincode = db.Column(db.String(10))
    join_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="Active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy='select',
                            foreign_keys='Order.customer_id')
    
    def get_total_purchases(self):
        """Calculate total amount spent by customer"""
        return sum(order.final_amount for order in self.orders if order.final_amount) or 0
    
    def get_total_orders(self):
        """Get total number of orders"""
        return len(self.orders)
    
    def __repr__(self):
        return f'<Customer {self.name}>'


class Purchase(db.Model):
    __tablename__ = "purchases"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User isolation
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    purchase_id = db.Column(db.String(50), unique=True, index=True)
    
    # Foreign Keys
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    
    # Purchase Details
    quantity = db.Column(db.Integer, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    
    # Date
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.purchase_id:
            self.purchase_id = self.generate_purchase_id()
    
    def calculate_total(self):
        self.total_cost = round(self.quantity * self.purchase_price, 2)
        return self.total_cost
    
    def generate_purchase_id(self):
        import random
        import string
        prefix = 'PUR'
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{prefix}-{timestamp}-{random_str}"
    
    def __repr__(self):
        return f'<Purchase {self.purchase_id}>'


class OrderItem(db.Model):
    __tablename__ = "order_items"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User isolation
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Foreign Keys
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    
    # Product Information Snapshot
    product_name = db.Column(db.String(200))
    product_sku = db.Column(db.String(50))
    product_category = db.Column(db.String(100))
    
    # Item Details
    quantity = db.Column(db.Integer, nullable=False, default=1)
    selling_price = db.Column(db.Float, nullable=False)
    
    # Cost and Profit
    purchase_price = db.Column(db.Float, default=0)      # Average purchase price at time of order
    profit_per_unit = db.Column(db.Float, default=0)
    profit = db.Column(db.Float, default=0)
    
    # Discount (per item)
    discount_percentage = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    
    # Tax
    gst_percentage = db.Column(db.Float, default=18)
    gst_amount = db.Column(db.Float, default=0)
    
    # Calculated Fields
    subtotal = db.Column(db.Float, default=0)            # Before discount
    after_discount = db.Column(db.Float, default=0)      # After discount
    total = db.Column(db.Float, default=0)                # After discount and GST
    
    def calculate_item(self):
        """Calculate all values for this item"""
        # Subtotal
        self.subtotal = self.quantity * self.selling_price
        
        # Discount
        self.discount_amount = (self.subtotal * self.discount_percentage) / 100
        self.after_discount = self.subtotal - self.discount_amount
        
        # GST
        self.gst_amount = (self.after_discount * self.gst_percentage) / 100
        self.total = self.after_discount + self.gst_amount
        
        # Profit
        self.profit_per_unit = self.selling_price - self.purchase_price
        self.profit = self.profit_per_unit * self.quantity
        
        return {
            'subtotal': self.subtotal,
            'discount_amount': self.discount_amount,
            'after_discount': self.after_discount,
            'gst_amount': self.gst_amount,
            'total': self.total,
            'profit': self.profit
        }
    
    def update_product_snapshot(self):
        """Update product information snapshot"""
        if self.product:
            self.product_name = self.product.title
            self.product_sku = self.product.sku or ''
            self.product_category = self.product.category or ''
            self.purchase_price = self.product.get_average_purchase_price()
    
    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity}>'


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    
    # User isolation
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    order_id = db.Column(db.String(50), unique=True, index=True)
    
    # Foreign Keys
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    
    # Order Header Information
    order_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status = db.Column(db.String(50), default='Pending', index=True)
    payment_method = db.Column(db.String(50), default='Cash')
    payment_status = db.Column(db.String(50), default='Unpaid')
    
    # Invoice Information
    invoice_number = db.Column(db.String(50), unique=True)
    invoice_date = db.Column(db.DateTime)
    
    # Customer Information Snapshot
    customer_name = db.Column(db.String(150))
    customer_email = db.Column(db.String(150))
    customer_phone = db.Column(db.String(20))
    
    # Order Totals
    subtotal = db.Column(db.Float, default=0)           # Before discount
    discount_amount = db.Column(db.Float, default=0)    # Total discount
    after_discount = db.Column(db.Float, default=0)     # After discount
    gst_amount = db.Column(db.Float, default=0)         # Total GST
    shipping_charge = db.Column(db.Float, default=0)    # Shipping
    final_amount = db.Column(db.Float, default=0)       # Final amount
    profit = db.Column(db.Float, default=0)             # Total profit
    
    # Additional Information
    notes = db.Column(db.Text)
    delivery_address = db.Column(db.Text)
    billing_address = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - MULTIPLE PRODUCTS PER ORDER
    items = db.relationship(
        'OrderItem', 
        backref='order', 
        cascade='all, delete-orphan',
        lazy='select',
        foreign_keys='OrderItem.order_id'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.order_id:
            self.order_id = self.generate_order_id()
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
    
    def generate_order_id(self):
        import random
        import string
        prefix = 'ORD'
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{prefix}-{timestamp}-{random_str}"
    
    def generate_invoice_number(self):
        import random
        import string
        prefix = 'INV'
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{prefix}-{timestamp}-{random_str}"
    
    def calculate_totals(self):
        """Calculate all order totals from items"""
        self.subtotal = sum(item.subtotal for item in self.items) or 0
        self.discount_amount = sum(item.discount_amount for item in self.items) or 0
        self.after_discount = self.subtotal - self.discount_amount
        self.gst_amount = sum(item.gst_amount for item in self.items) or 0
        self.final_amount = self.after_discount + self.gst_amount + (self.shipping_charge or 0)
        self.profit = sum(item.profit for item in self.items) or 0
        
        return {
            'subtotal': self.subtotal,
            'discount_amount': self.discount_amount,
            'after_discount': self.after_discount,
            'gst_amount': self.gst_amount,
            'shipping_charge': self.shipping_charge,
            'final_amount': self.final_amount,
            'profit': self.profit
        }
    
    def get_item_count(self):
        """Get total number of items"""
        return len(self.items)
    
    def get_total_quantity(self):
        """Get total quantity of all items"""
        return sum(item.quantity for item in self.items) or 0
    
    def __repr__(self):
        return f'<Order {self.order_id}>'


class InventoryMovement(db.Model):
    __tablename__ = "inventory_movements"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User isolation
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    
    # Movement Details
    quantity_change = db.Column(db.Integer)  # Positive for stock in, negative for stock out
    movement_type = db.Column(db.String(50), index=True)  # 'Purchase', 'Sale', 'Return', 'Adjustment'
    reference_id = db.Column(db.String(100), index=True)  # Order ID or Purchase ID
    
    # Stock snapshot
    previous_stock = db.Column(db.Integer)
    new_stock = db.Column(db.Integer)
    
    # Additional info
    notes = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    @staticmethod
    def create_movement(product, quantity_change, movement_type, reference_id, created_by, notes=None):
        """Create inventory movement record"""
        previous_stock = product.get_current_stock()
        new_stock = previous_stock + quantity_change
        
        movement = InventoryMovement(
            product_id=product.id,
            quantity_change=quantity_change,
            movement_type=movement_type,
            reference_id=reference_id,
            previous_stock=previous_stock,
            new_stock=new_stock,
            notes=notes,
            created_by=created_by
        )
        return movement
    
    def __repr__(self):
        return f'<InventoryMovement {self.movement_type}: {self.quantity_change}>'