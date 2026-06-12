import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func
from . import db
from .models import Product, Seller, Purchase, Order, OrderItem, InventoryMovement

products = Blueprint('products', __name__, template_folder='templates', static_folder='static')

# Allowed file extensions for image upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== LIST PRODUCTS ====================
@products.route('/ecommerce/products')
@login_required
def product_list():
    """List all products - filtered by current user"""
    # User isolation - only show products created by current user
    products_data = Product.query.filter_by(created_by=current_user.id)\
                                 .order_by(Product.created_at.desc())\
                                 .all()
    
    # Calculate statistics for each product
    for product in products_data:
        # Get current stock (using model method)
        product.current_stock = product.get_current_stock()
        
        # Get average purchase price (using model method)
        product.avg_purchase_price = product.get_average_purchase_price()
        
        # Check low stock status (using model method)
        product.is_low = product.is_low_stock()
        
        # FIXED: Get total sold quantity using direct query instead of relationship count
        product.total_sold = db.session.query(func.sum(OrderItem.quantity))\
                                       .filter(OrderItem.product_id == product.id)\
                                       .scalar() or 0
        
        # FIXED: Get total purchase quantity using direct query
        product.total_purchased = db.session.query(func.sum(Purchase.quantity))\
                                           .filter(Purchase.product_id == product.id)\
                                           .scalar() or 0
        
        # FIXED: Calculate total profit using direct query
        product.total_profit = db.session.query(func.sum(OrderItem.profit))\
                                         .filter(OrderItem.product_id == product.id)\
                                         .scalar() or 0
    
    # Get low stock count for alert
    low_stock_count = sum(1 for p in products_data if p.is_low)
    
    return render_template(
        'ecommerce/apps-ecommerce-products.html',
        products=products_data,
        low_stock_count=low_stock_count
    )


# ==================== PRODUCT DETAILS ====================
# ==================== PRODUCT DETAILS ====================
@products.route('/ecommerce/product/<int:id>')
@login_required
def product_details(id):
    """View product details with access check"""
    product = Product.query.get_or_404(id)
    
    # User isolation check
    if product.created_by != current_user.id:
        flash('You do not have access to this product', 'danger')
        return redirect(url_for('products.product_list'))
    
    # FIX: Use direct queries instead of relationship methods
    # Get all purchases for this product
    purchases = Purchase.query.filter_by(product_id=id)\
                              .order_by(Purchase.purchase_date.desc())\
                              .all()
    
    # Get unique orders that contain this product
    orders = db.session.query(Order).distinct()\
                      .join(OrderItem, OrderItem.order_id == Order.id)\
                      .filter(OrderItem.product_id == id)\
                      .filter(Order.created_by == current_user.id)\
                      .order_by(Order.order_date.desc())\
                      .all()
    
    # Get order items for this product
    order_items = OrderItem.query.filter_by(product_id=id)\
                                 .order_by(OrderItem.id.desc())\
                                 .all()
    
    # Get inventory movements
    movements = InventoryMovement.query.filter_by(product_id=id)\
                                       .order_by(InventoryMovement.created_at.desc())\
                                       .all()
    
    # Calculate statistics using direct queries
    total_purchased = db.session.query(func.sum(Purchase.quantity))\
                                .filter(Purchase.product_id == id)\
                                .scalar() or 0
    
    total_sold = db.session.query(func.sum(OrderItem.quantity))\
                           .filter(OrderItem.product_id == id)\
                           .scalar() or 0
    
    current_stock = product.get_current_stock()
    avg_purchase_price = product.get_average_purchase_price()
    
    # Calculate total profit using OrderItem
    total_profit = db.session.query(func.sum(OrderItem.profit))\
                             .filter(OrderItem.product_id == id)\
                             .scalar() or 0
    
    # Get unique sellers for this product
    sellers = db.session.query(Seller).distinct().join(
        Purchase, Purchase.seller_id == Seller.id
    ).filter(
        Purchase.product_id == id,
        Seller.created_by == current_user.id
    ).all()
    
    return render_template(
        'ecommerce/apps-ecommerce-product_details.html',
        product=product,
        purchases=purchases,
        orders=orders,
        order_items=order_items,
        movements=movements,
        sellers=sellers,
        total_purchased=total_purchased,
        total_sold=total_sold,
        current_stock=current_stock,
        avg_purchase_price=avg_purchase_price,
        total_profit=total_profit
    )
# ==================== ADD PRODUCT ====================
@products.route('/ecommerce/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    """Add new product - assigned to current user (Stock starts at 0)"""
    if request.method == 'POST':
        try:
            # Image upload with validation
            image_filename = None
            if 'image' in request.files and request.files['image'].filename:
                image = request.files['image']
                if allowed_file(image.filename):
                    image_filename = secure_filename(image.filename)
                    image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename))
                else:
                    flash('Invalid image format. Please upload PNG, JPG, JPEG, or GIF', 'warning')
            
            # Create product with user isolation
            product = Product(
                title=request.form.get('title', '').strip(),
                description=request.form.get('description', '').strip(),
                category=request.form.get('category', '').strip(),
                manufacturer_name=request.form.get('manufacturer_name', '').strip(),
                manufacturer_brand=request.form.get('manufacturer_brand', '').strip(),
                suggested_selling_price=float(request.form.get('suggested_selling_price') or 0),
                low_stock_threshold=int(request.form.get('low_stock_threshold') or 5),
                status=request.form.get('status', 'Draft'),
                image=image_filename,
                created_by=current_user.id  # User isolation
            )
            
            # Generate SKU
            product.sku = product.generate_sku()

            # Handle published date
            published_date = request.form.get('published_date')
            if published_date:
                try:
                    product.published_date = datetime.strptime(published_date, "%Y-%m-%d")
                except:
                    try:
                        product.published_date = datetime.strptime(published_date, "%d %b, %Y")
                    except:
                        flash('Invalid date format. Use YYYY-MM-DD', 'warning')

            db.session.add(product)
            db.session.commit()
            
            # NOTE: Stock is 0 at creation - will increase when purchases are made
            flash(f'Product "{product.title}" (SKU: {product.sku}) added successfully! Stock: 0', 'success')
            return redirect(url_for('products.product_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding product: {str(e)}', 'danger')
            print(f"Error: {e}")

    # GET request - show form
    return render_template('ecommerce/apps-ecommerce-add_product.html')


# ==================== EDIT PRODUCT ====================
@products.route('/ecommerce/product/edit/<int:id>', methods=['GET'])
@login_required
def edit_product(id):
    """Edit product form with access check"""
    product = Product.query.get_or_404(id)
    
    # User isolation check
    if product.created_by != current_user.id:
        flash('You do not have permission to edit this product', 'danger')
        return redirect(url_for('products.product_list'))
    
    return render_template(
        'ecommerce/apps-ecommerce-add_product.html',
        product=product
    )


# ==================== UPDATE PRODUCT ====================
@products.route('/ecommerce/product/update/<int:id>', methods=['POST'])
@login_required
def update_product(id):
    """Update product with access check"""
    product = Product.query.get_or_404(id)
    
    # User isolation check
    if product.created_by != current_user.id:
        flash('You do not have permission to update this product', 'danger')
        return redirect(url_for('products.product_list'))

    try:
        # Fix SKU regeneration logic
        old_title = product.title
        new_title = request.form.get('title', product.title).strip()
        
        # Update fields
        product.title = new_title
        product.description = request.form.get('description', product.description).strip()
        product.category = request.form.get('category', product.category).strip()
        product.manufacturer_name = request.form.get('manufacturer_name', product.manufacturer_name).strip()
        product.manufacturer_brand = request.form.get('manufacturer_brand', product.manufacturer_brand).strip()
        product.suggested_selling_price = float(request.form.get('suggested_selling_price') or product.suggested_selling_price)
        product.low_stock_threshold = int(request.form.get('low_stock_threshold') or product.low_stock_threshold)
        product.status = request.form.get('status', product.status)

        # Regenerate SKU if title changed or no SKU
        if not product.sku or old_title != new_title:
            product.sku = product.generate_sku()

        # Image update with validation
        if 'image' in request.files and request.files['image'].filename:
            image = request.files['image']
            if allowed_file(image.filename):
                image_filename = secure_filename(image.filename)
                image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename))
                
                # Delete old image if exists
                if product.image and product.image != 'default-product.jpg':
                    old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product.image)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                product.image = image_filename
            else:
                flash('Invalid image format', 'warning')

        # Published date
        published_date = request.form.get('published_date')
        if published_date:
            try:
                product.published_date = datetime.strptime(published_date, "%Y-%m-%d")
            except:
                try:
                    product.published_date = datetime.strptime(published_date, "%d %b, %Y")
                except:
                    pass

        db.session.commit()
        flash(f'Product "{product.title}" updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating product: {str(e)}', 'danger')
        print(f"Error: {e}")

    return redirect(url_for('products.product_list'))


# ==================== DELETE PRODUCT ====================
@products.route('/ecommerce/product/delete/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    """Delete product with access check"""
    product = Product.query.get_or_404(id)
    
    # User isolation check
    if product.created_by != current_user.id:
        flash('You do not have permission to delete this product', 'danger')
        return redirect(url_for('products.product_list'))
    
    try:
        # Check if product has any purchases
        purchase_count = db.session.query(func.count(Purchase.id))\
                                   .filter(Purchase.product_id == id)\
                                   .scalar() or 0
        if purchase_count > 0:
            flash(f'Cannot delete "{product.title}" because it has {purchase_count} purchase records!', 'danger')
            return redirect(url_for('products.product_list'))
        
        # Check if product has any order items
        order_count = db.session.query(func.count(OrderItem.id))\
                                .filter(OrderItem.product_id == id)\
                                .scalar() or 0
        if order_count > 0:
            flash(f'Cannot delete "{product.title}" because it has {order_count} order records!', 'danger')
            return redirect(url_for('products.product_list'))
        
        # Delete product image if exists
        if product.image and product.image != 'default-product.jpg':
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product.image)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        product_name = product.title
        db.session.delete(product)
        db.session.commit()
        
        flash(f'Product "{product_name}" deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('products.product_list'))


# ==================== API: GET PRODUCT DETAILS ====================
@products.route('/api/product/<int:id>')
@login_required
def get_product_api(id):
    """API endpoint to get product details for order form"""
    product = Product.query.get_or_404(id)
    
    # User isolation check
    if product.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'id': product.id,
        'title': product.title,
        'sku': product.sku,
        'suggested_selling_price': product.suggested_selling_price,
        'current_stock': product.get_current_stock(),
        'avg_purchase_price': product.get_average_purchase_price(),
        'is_low_stock': product.is_low_stock(),
        'category': product.category,
        'image': product.image
    })


# ==================== API: CALCULATE ORDER VALUES ====================
@products.route('/api/calculate-order', methods=['POST'])
@login_required
def calculate_order():
    """API endpoint to auto-calculate order values"""
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        selling_price = float(data.get('selling_price', 0))
        discount_percentage = float(data.get('discount_percentage', 0))
        gst_percentage = float(data.get('gst_percentage', 18))
        
        product = Product.query.get(product_id)
        
        # User isolation check
        if not product or product.created_by != current_user.id:
            return jsonify({'error': 'Product not found or access denied'}), 404
        
        # Check stock availability
        available_stock = product.get_current_stock()
        if available_stock < quantity:
            return jsonify({
                'error': f'Only {available_stock} items available',
                'available_stock': available_stock,
                'can_order': False
            }), 400
        
        # Get average purchase price for profit calculation
        avg_purchase_price = product.get_average_purchase_price()
        
        # Calculate values with discount
        subtotal = quantity * selling_price
        discount_amount = subtotal * (discount_percentage / 100)
        after_discount = subtotal - discount_amount
        gst_amount = after_discount * (gst_percentage / 100)
        final_amount = after_discount + gst_amount
        profit = (selling_price - avg_purchase_price) * quantity
        
        return jsonify({
            'product_id': product.id,
            'product_name': product.title,
            'product_sku': product.sku,
            'quantity': quantity,
            'selling_price': selling_price,
            'avg_purchase_price': avg_purchase_price,
            'subtotal': round(subtotal, 2),
            'discount_percentage': discount_percentage,
            'discount_amount': round(discount_amount, 2),
            'after_discount': round(after_discount, 2),
            'gst_percentage': gst_percentage,
            'gst_amount': round(gst_amount, 2),
            'final_amount': round(final_amount, 2),
            'profit': round(profit, 2),
            'available_stock': available_stock,
            'can_order': available_stock >= quantity
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== API: PRODUCT STATISTICS ====================
@products.route('/api/product-stats')
@login_required
def product_stats():
    """API endpoint for product statistics - filtered by user"""
    
    # Overall statistics for current user only
    products_query = Product.query.filter_by(created_by=current_user.id)
    total_products = products_query.count()
    
    # Products with stock > 0
    products_with_stock = 0
    total_out_of_stock = 0
    total_low_stock = 0
    
    for product in products_query.all():
        stock = product.get_current_stock()
        if stock > 0:
            products_with_stock += 1
        if stock == 0:
            total_out_of_stock += 1
        if product.is_low_stock():
            total_low_stock += 1
    
    # Category-wise breakdown for current user only
    categories = db.session.query(
        Product.category,
        func.count(Product.id).label('count')
    ).filter(Product.created_by == current_user.id)\
     .group_by(Product.category).all()
    
    category_data = []
    for cat in categories:
        if cat.category:
            # Get purchases for this category
            total_purchased = db.session.query(func.sum(Purchase.quantity))\
                                        .join(Product, Product.id == Purchase.product_id)\
                                        .filter(Product.category == cat.category)\
                                        .filter(Product.created_by == current_user.id)\
                                        .scalar() or 0
            
            # Get sales for this category (through OrderItem)
            total_sold = db.session.query(func.sum(OrderItem.quantity))\
                                   .join(Product, Product.id == OrderItem.product_id)\
                                   .filter(Product.category == cat.category)\
                                   .filter(Product.created_by == current_user.id)\
                                   .scalar() or 0
            
            category_data.append({
                'category': cat.category,
                'count': cat.count,
                'total_purchased': int(total_purchased),
                'total_sold': int(total_sold)
            })
    
    return jsonify({
        'overall': {
            'total_products': total_products,
            'products_with_stock': products_with_stock,
            'out_of_stock': total_out_of_stock,
            'low_stock': total_low_stock
        },
        'categories': category_data
    })


# ==================== API: LOW STOCK ALERT ====================
@products.route('/api/low-stock')
@login_required
def low_stock_alert():
    """API endpoint for low stock alerts - filtered by user"""
    products = Product.query.filter_by(created_by=current_user.id).all()
    low_stock_products = [p for p in products if p.is_low_stock()]
    
    return jsonify([{
        'id': p.id,
        'title': p.title,
        'sku': p.sku,
        'current_stock': p.get_current_stock(),
        'threshold': p.low_stock_threshold,
        'category': p.category,
        'image': p.image
    } for p in low_stock_products])


# ==================== API: PRODUCT PURCHASE HISTORY ====================
@products.route('/api/product/<int:id>/purchases')
@login_required
def product_purchases_api(id):
    """API endpoint to get purchase history for a product"""
    product = Product.query.get_or_404(id)
    
    # User isolation check
    if product.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    purchases = product.purchases.order_by(Purchase.purchase_date.desc()).all()
    
    purchases_data = []
    total_quantity = 0
    total_spent = 0
    
    for p in purchases:
        purchases_data.append({
            'id': p.id,
            'purchase_id': p.purchase_id,
            'date': p.purchase_date.strftime('%d %b %Y'),
            'seller': p.seller.get_full_name() if p.seller else 'Unknown',
            'seller_id': p.seller_id,
            'quantity': p.quantity,
            'price': p.purchase_price,
            'total_cost': p.total_cost
        })
        total_quantity += p.quantity
        total_spent += p.total_cost
    
    return jsonify({
        'product_id': product.id,
        'product_name': product.title,
        'product_sku': product.sku,
        'total_purchases': len(purchases_data),
        'total_quantity': total_quantity,
        'total_spent': float(total_spent),
        'purchases': purchases_data
    })


# ==================== API: PRODUCT ORDER HISTORY ====================
@products.route('/api/product/<int:id>/orders')
@login_required
def product_orders_api(id):
    """API endpoint to get order history for a product"""
    product = Product.query.get_or_404(id)
    
    # User isolation check
    if product.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get order items for this product
    order_items = product.order_items.order_by(OrderItem.id.desc()).all()
    
    orders_data = []
    total_quantity = 0
    total_revenue = 0
    total_profit = 0
    
    for item in order_items:
        order = item.order
        orders_data.append({
            'id': item.id,
            'order_id': order.order_id if order else 'N/A',
            'date': order.order_date.strftime('%d %b %Y') if order else 'N/A',
            'customer': order.customer_name if order else 'Unknown',
            'customer_id': order.customer_id if order else None,
            'quantity': item.quantity,
            'selling_price': item.selling_price,
            'subtotal': item.subtotal,
            'discount': item.discount_amount,
            'gst': item.gst_amount,
            'final_amount': item.total,
            'profit': item.profit,
            'status': order.status if order else 'Unknown'
        })
        total_quantity += item.quantity
        total_revenue += item.total or 0
        total_profit += item.profit or 0
    
    return jsonify({
        'product_id': product.id,
        'product_name': product.title,
        'product_sku': product.sku,
        'total_orders': len(orders_data),
        'total_quantity_sold': total_quantity,
        'total_revenue': float(total_revenue),
        'total_profit': float(total_profit),
        'orders': orders_data
    })


# ==================== API: PRODUCT MOVEMENT HISTORY ====================
@products.route('/api/product/<int:id>/movements')
@login_required
def product_movements_api(id):
    """API endpoint to get inventory movements for a product"""
    product = Product.query.get_or_404(id)
    
    # User isolation check
    if product.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    movements = product.inventory_movements.order_by(InventoryMovement.created_at.desc()).all()
    
    movements_data = []
    for m in movements:
        movements_data.append({
            'id': m.id,
            'date': m.created_at.strftime('%d %b %Y %H:%M'),
            'type': m.movement_type,
            'quantity_change': m.quantity_change,
            'previous_stock': m.previous_stock,
            'new_stock': m.new_stock,
            'reference': m.reference_id,
            'notes': m.notes
        })
    
    return jsonify({
        'product_id': product.id,
        'product_name': product.title,
        'product_sku': product.sku,
        'current_stock': product.get_current_stock(),
        'movements': movements_data
    })


# ==================== BULK PRODUCT IMPORT ====================
@products.route('/ecommerce/product/bulk-import', methods=['POST'])
@login_required
def bulk_import():
    """Bulk import products from CSV"""
    if 'csv_file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('products.product_list'))
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('products.product_list'))
    
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file', 'danger')
        return redirect(url_for('products.product_list'))
    
    import csv
    import io
    
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        success_count = 0
        error_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_input, start=1):
            try:
                # Validate required fields
                if not row.get('title'):
                    errors.append(f"Row {row_num}: Missing title")
                    error_count += 1
                    continue
                
                # Create product
                product = Product(
                    title=row.get('title', '').strip(),
                    description=row.get('description', '').strip(),
                    category=row.get('category', '').strip(),
                    manufacturer_name=row.get('manufacturer_name', '').strip(),
                    manufacturer_brand=row.get('manufacturer_brand', '').strip(),
                    suggested_selling_price=float(row.get('suggested_selling_price', 0)),
                    low_stock_threshold=int(row.get('low_stock_threshold', 5)),
                    status=row.get('status', 'Draft'),
                    created_by=current_user.id
                )
                
                # Generate SKU
                product.sku = product.generate_sku()
                
                db.session.add(product)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        db.session.commit()
        
        if errors:
            for error in errors[:5]:
                flash(error, 'warning')
        
        flash(f'Bulk import completed: {success_count} products added, {error_count} errors', 
              'success' if success_count > 0 else 'danger')
        
    except Exception as e:
        flash(f'Error processing CSV: {str(e)}', 'danger')
    
    return redirect(url_for('products.product_list'))