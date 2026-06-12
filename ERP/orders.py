from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import json
import decimal
from . import db
from .models import Order, OrderItem, Customer, Product, InventoryMovement

# Helper function to convert Decimal to float for JSON serialization
def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError

orders = Blueprint('orders', __name__, template_folder='templates', static_folder='static')


# ==================== LIST ORDERS ====================
@orders.route('/ecommerce/orders')
@login_required
def order_list():
    """List all orders - filtered by current user"""
    # Get filter parameters
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Start with base query - USER ISOLATION
    query = Order.query.filter_by(created_by=current_user.id)\
                       .order_by(Order.order_date.desc())
    
    # Apply search filter
    if search:
        query = query.join(Customer).filter(
            or_(
                Order.order_id.ilike(f'%{search}%'),
                Customer.name.ilike(f'%{search}%'),
                Customer.email.ilike(f'%{search}%')
            )
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter(Order.status == status_filter)
    
    # Apply date range filter
    if date_from:
        try:
            query = query.filter(Order.order_date >= datetime.strptime(date_from, '%Y-%m-%d'))
        except:
            pass
    
    if date_to:
        try:
            query = query.filter(Order.order_date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except:
            pass
    
    orders = query.all()
    
    # Use database aggregation for statistics
    total_orders = len(orders)
    
    total_revenue = db.session.query(func.sum(Order.final_amount))\
                              .filter(Order.created_by == current_user.id)\
                              .scalar() or 0
    
    total_profit = db.session.query(func.sum(Order.profit))\
                             .filter(Order.created_by == current_user.id)\
                             .scalar() or 0
    
    # Status counts using database queries
    pending_count = Order.query.filter_by(created_by=current_user.id, status='Pending').count()
    processing_count = Order.query.filter_by(created_by=current_user.id, status='Processing').count()
    delivered_count = Order.query.filter_by(created_by=current_user.id, status='Delivered').count()
    cancelled_count = Order.query.filter_by(created_by=current_user.id, status='Cancelled').count()
    
    # Get customers and products for dropdowns - USER ISOLATION
    # Get customers and products for dropdowns - USER ISOLATION
    customers = Customer.query.filter_by(created_by=current_user.id, status='Active').all()
    products = Product.query.filter_by(created_by=current_user.id, status='Published').all()   # ✅ Fixed

    # Get low stock products for alert
    low_stock_count = sum(1 for p in products if p.is_low_stock())
    
    return render_template(
        'ecommerce/apps-ecommerce-orders.html',
        orders=orders,
        total_orders=total_orders,
        total_revenue=total_revenue,
        total_profit=total_profit,
        pending_count=pending_count,
        processing_count=processing_count,
        delivered_count=delivered_count,
        cancelled_count=cancelled_count,
        customers=customers,
        products=products,
        low_stock_count=low_stock_count,
        search=search,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to
    )


@orders.route('/ecommerce/orders/fix-product-names', methods=['GET'])
@login_required
def fix_product_names():
    """Temporary route to fix product names in order items (admin only)"""
    if current_user.role != 'super_admin':
        flash('Access denied', 'danger')
        return redirect(url_for('orders.order_list'))
    
    fixed_count = 0
    items = OrderItem.query.all()
    
    for item in items:
        if (not item.product_name or item.product_name == 'None') and item.product_id:
            product = Product.query.get(item.product_id)
            if product:
                item.product_name = product.title
                item.product_sku = product.sku
                item.product_category = product.category
                fixed_count += 1
    
    db.session.commit()
    flash(f'Fixed {fixed_count} order items!', 'success')
    return redirect(url_for('orders.order_list'))


# ==================== CREATE ORDER (Multi-Product) ====================
@orders.route('/ecommerce/order/create', methods=['GET', 'POST'])
@login_required
def create_order():
    """Create new order with multiple products"""
    if request.method == 'GET':
        # Show order creation form
        customers = Customer.query.filter_by(created_by=current_user.id, status='Active').all()
        products = Product.query.filter_by(created_by=current_user.id, status='Published').all()
        
        # Convert products to JSON-serializable format with Decimal handling
        products_data = []
        for product in products:
            # Get values and convert Decimal to float
            suggested_price = product.suggested_selling_price
            if suggested_price is not None and isinstance(suggested_price, decimal.Decimal):
                suggested_price = float(suggested_price)
            
            avg_price = product.get_average_purchase_price()
            if avg_price is not None and isinstance(avg_price, decimal.Decimal):
                avg_price = float(avg_price)
            
            current_stock = product.get_current_stock()
            if current_stock is not None and isinstance(current_stock, decimal.Decimal):
                current_stock = int(current_stock)
            
            products_data.append({
                'id': product.id,
                'title': product.title,
                'sku': product.sku or '',
                'category': product.category or '',
                'suggested_selling_price': suggested_price or 0,
                'current_stock': current_stock or 0,
                'avg_purchase_price': avg_price or 0
            })
        
        return render_template(
            'ecommerce/apps-ecommerce-create-order.html',
            customers=customers,
            products=products_data,
            edit_mode=False
        )
    
    # POST - Create order
    try:
        # Get customer
        customer_id = request.form.get('customer_id')
        customer = Customer.query.filter_by(id=customer_id, created_by=current_user.id).first()
        
        if not customer:
            flash('Please select a valid customer', 'danger')
            return redirect(url_for('orders.create_order'))
        
        # Get payment and status info
        payment_method = request.form.get('payment_method', 'Cash')
        payment_status = request.form.get('payment_status', 'Unpaid')
        status = request.form.get('status', 'Pending')
        shipping_charge = float(request.form.get('shipping_charge', 0))
        notes = request.form.get('notes', '')
        
        # Create order header
        order = Order(
            customer_id=customer.id,
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
            payment_method=payment_method,
            payment_status=payment_status,
            status=status,
            shipping_charge=shipping_charge,
            notes=notes,
            order_date=datetime.utcnow(),
            created_by=current_user.id
        )
        
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        # Process multiple products from form
        items_data = {}
        for key, value in request.form.items():
            if key.startswith('items['):
                import re
                match = re.match(r'items\[(\d+)\]\[(\w+)\]', key)
                if match:
                    index = match.group(1)
                    field = match.group(2)
                    
                    if index not in items_data:
                        items_data[index] = {}
                    items_data[index][field] = value
        
        if not items_data:
            db.session.rollback()
            flash('Please add at least one product to the order', 'danger')
            return redirect(url_for('orders.create_order'))
        
        item_count = 0
        for item_data in items_data.values():
            product_id = int(item_data.get('product_id'))
            quantity = int(item_data.get('quantity', 1))
            selling_price = float(item_data.get('selling_price', 0))
            discount = float(item_data.get('discount', 0))
            gst = float(item_data.get('gst', 18))
            
            # Verify product belongs to user
            product = Product.query.filter_by(id=product_id, created_by=current_user.id).first()
            
            if not product:
                continue
            
            # Check stock availability
            current_stock = product.get_current_stock()
            if current_stock < quantity:
                db.session.rollback()
                flash(f'Insufficient stock for {product.title}. Available: {current_stock}', 'danger')
                return redirect(url_for('orders.create_order'))
            
            # Get average purchase price for profit calculation
            purchase_price = product.get_average_purchase_price()
            
            # Create order item
            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                selling_price=selling_price,
                discount_percentage=discount,
                gst_percentage=gst,
                purchase_price=purchase_price,
                created_by=current_user.id
            )
            
            # Update product snapshot and calculate all values
            item.update_product_snapshot()
            item.calculate_item()
            
            db.session.add(item)
            
            # Create inventory movement (stock out)
            movement = InventoryMovement.create_movement(
                product=product,
                quantity_change=-quantity,
                movement_type='Sale',
                reference_id=order.order_id,
                created_by=current_user.id,
                notes=f"Order #{order.order_id}: {quantity} x {product.title}"
            )
            db.session.add(movement)
            
            item_count += 1
        
        # Calculate order totals from all items
        order.calculate_totals()
        
        db.session.commit()
        
        flash(f'Order {order.order_id} created successfully with {item_count} items! Total: ₹{order.final_amount}', 'success')
        return redirect(url_for('orders.order_details', id=order.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating order: {str(e)}', 'danger')
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('orders.create_order'))


# ==================== ORDER DETAILS ====================
@orders.route('/ecommerce/order/<int:id>')
@login_required
def order_details(id):
    """View single order details with all items"""
    order = Order.query.get_or_404(id)
    
    # User isolation check
    if order.created_by != current_user.id:
        flash('You do not have access to this order', 'danger')
        return redirect(url_for('orders.order_list'))
    
    items = order.items
    customer = Customer.query.filter_by(id=order.customer_id, created_by=current_user.id).first()
    profit_margin = (order.profit / order.final_amount * 100) if order.final_amount and order.final_amount > 0 else 0
    
    return render_template(
        'ecommerce/apps-ecommerce-order-details.html',
        order=order,
        items=items,
        customer=customer,
        profit_margin=profit_margin
    )


# ==================== EDIT ORDER (GET) - ENHANCED ====================
@orders.route('/ecommerce/order/edit/<int:id>', methods=['GET'])
@login_required
def edit_order(id):
    """Edit order form - pre-filled with existing data"""
    # Get the order
    order = Order.query.get_or_404(id)
    
    # User isolation check
    if order.created_by != current_user.id:
        flash('You do not have permission to edit this order', 'danger')
        return redirect(url_for('orders.order_list'))
    
    # Only allow editing of pending orders
    if order.status != 'Pending':
        flash('Only pending orders can be edited', 'danger')
        return redirect(url_for('orders.order_details', id=id))
    
    # Get all items for this order
    order_items = order.items
    
    # Get customers for dropdown
    customers = Customer.query.filter_by(created_by=current_user.id, status='Active').all()
    
    # Get products for dropdown (for adding new items)
    products = Product.query.filter_by(created_by=current_user.id, status='Published').all()
    
    # Convert products to JSON-serializable format
    products_data = []
    for product in products:
        products_data.append({
            'id': product.id,
            'title': product.title,
            'sku': product.sku or '',
            'category': product.category or '',
            'suggested_selling_price': float(product.suggested_selling_price or 0),
            'current_stock': product.get_current_stock(),
            'avg_purchase_price': float(product.get_average_purchase_price() or 0)
        })
    
    # Convert order items to JSON-serializable format
    items_data = []
    for item in order_items:
        items_data.append({
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name or (item.product.title if item.product else 'Unknown'),
            'product_sku': item.product_sku or (item.product.sku if item.product else ''),
            'product_category': item.product_category or (item.product.category if item.product else ''),
            'quantity': item.quantity,
            'selling_price': float(item.selling_price or 0),
            'discount_percentage': float(item.discount_percentage or 0),
            'gst_percentage': float(item.gst_percentage or 0),
            'subtotal': float(item.subtotal or 0),
            'total': float(item.total or 0),
            'profit': float(item.profit or 0),
            'purchase_price': float(item.purchase_price or 0)
        })
    
    return render_template(
        'ecommerce/apps-ecommerce-create-order.html',
        edit_mode=True,
        order=order,
        order_items=items_data,
        customers=customers,
        products=products_data
    )


# ==================== UPDATE ORDER (POST) - WITH FULL ITEM EDITING ====================
@orders.route('/ecommerce/order/update/<int:id>', methods=['POST'])
@login_required
def update_order(id):
    """Update order details including items (add, remove, modify)"""
    order = Order.query.get_or_404(id)
    
    # User isolation check
    if order.created_by != current_user.id:
        flash('You do not have permission to update this order', 'danger')
        return redirect(url_for('orders.order_list'))
    
    # Only allow editing of pending orders
    if order.status != 'Pending':
        flash('Only pending orders can be edited', 'danger')
        return redirect(url_for('orders.order_details', id=id))
    
    try:
        # Store old items for stock adjustment
        old_items = {item.id: item for item in order.items}
        processed_item_ids = set()
        
        # Update order header fields
        order.payment_method = request.form.get('payment_method', order.payment_method)
        order.payment_status = request.form.get('payment_status', order.payment_status)
        order.status = request.form.get('status', order.status)
        order.notes = request.form.get('notes', order.notes)
        
        # Process items from form
        items_data = {}
        for key, value in request.form.items():
            if key.startswith('items['):
                import re
                match = re.match(r'items\[(\d+)\]\[(\w+)\]', key)
                if match:
                    index = match.group(1)
                    field = match.group(2)
                    
                    if index not in items_data:
                        items_data[index] = {}
                    items_data[index][field] = value
        
        # Track which items we've processed
        current_item_ids = set()
        
        for item_data in items_data.values():
            item_id = item_data.get('id')
            product_id = int(item_data.get('product_id'))
            quantity = int(item_data.get('quantity', 1))
            selling_price = float(item_data.get('selling_price', 0))
            discount = float(item_data.get('discount', 0))
            gst = float(item_data.get('gst', 18))
            
            # Verify product belongs to user
            product = Product.query.filter_by(id=product_id, created_by=current_user.id).first()
            if not product:
                continue
            
            # Check stock availability
            current_stock = product.get_current_stock()
            
            if item_id and int(item_id) in old_items:
                # Existing item - update
                item = old_items[int(item_id)]
                processed_item_ids.add(int(item_id))
                
                # Calculate stock difference
                old_quantity = item.quantity
                quantity_difference = quantity - old_quantity
                
                if quantity_difference > 0:
                    # Increasing quantity - check stock
                    if current_stock < quantity_difference:
                        flash(f'Insufficient stock for {product.title}. Available: {current_stock}', 'danger')
                        return redirect(url_for('orders.edit_order', id=order.id))
                    
                    # Create inventory movement for additional stock out
                    movement = InventoryMovement.create_movement(
                        product=product,
                        quantity_change=-quantity_difference,
                        movement_type='Sale Adjustment',
                        reference_id=order.order_id,
                        created_by=current_user.id,
                        notes=f"Order #{order.order_id}: Increased quantity by {quantity_difference}"
                    )
                    db.session.add(movement)
                    
                elif quantity_difference < 0:
                    # Decreasing quantity - restore stock
                    movement = InventoryMovement.create_movement(
                        product=product,
                        quantity_change=-quantity_difference,  # Positive value
                        movement_type='Sale Adjustment',
                        reference_id=order.order_id,
                        created_by=current_user.id,
                        notes=f"Order #{order.order_id}: Decreased quantity by {-quantity_difference}"
                    )
                    db.session.add(movement)
                
                # Update item fields
                item.quantity = quantity
                item.selling_price = selling_price
                item.discount_percentage = discount
                item.gst_percentage = gst
                
                # Recalculate item
                item.calculate_item()
                
            else:
                # New item
                if current_stock < quantity:
                    flash(f'Insufficient stock for {product.title}. Available: {current_stock}', 'danger')
                    return redirect(url_for('orders.edit_order', id=order.id))
                
                # Get average purchase price
                purchase_price = product.get_average_purchase_price()
                
                # Create new order item
                item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    selling_price=selling_price,
                    discount_percentage=discount,
                    gst_percentage=gst,
                    purchase_price=purchase_price,
                    created_by=current_user.id
                )
                
                # Update product snapshot and calculate
                item.update_product_snapshot()
                item.calculate_item()
                
                db.session.add(item)
                
                # Create inventory movement for new item
                movement = InventoryMovement.create_movement(
                    product=product,
                    quantity_change=-quantity,
                    movement_type='Sale',
                    reference_id=order.order_id,
                    created_by=current_user.id,
                    notes=f"Order #{order.order_id}: Added {quantity} x {product.title}"
                )
                db.session.add(movement)
        
        # Remove items that were deleted
        for item_id, item in old_items.items():
            if item_id not in processed_item_ids:
                # Restore stock for deleted item
                product = Product.query.get(item.product_id)
                if product:
                    movement = InventoryMovement.create_movement(
                        product=product,
                        quantity_change=item.quantity,
                        movement_type='Sale Adjustment',
                        reference_id=order.order_id,
                        created_by=current_user.id,
                        notes=f"Order #{order.order_id}: Removed {item.quantity} x {item.product_name}"
                    )
                    db.session.add(movement)
                
                db.session.delete(item)
        
        # Recalculate order totals
        order.calculate_totals()
        
        db.session.commit()
        
        flash(f'Order {order.order_id} updated successfully!', 'success')
        return redirect(url_for('orders.order_details', id=order.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating order: {str(e)}', 'danger')
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('orders.edit_order', id=order.id))


# ==================== UPDATE ORDER STATUS ====================
@orders.route('/ecommerce/order/<int:id>/status', methods=['POST'])
@login_required
def update_order_status(id):
    """Quick update order status"""
    order = Order.query.get_or_404(id)
    
    # User isolation check
    if order.created_by != current_user.id:
        flash('You do not have permission to update this order', 'danger')
        return redirect(url_for('orders.order_list'))
    
    try:
        new_status = request.form.get('status')
        if new_status and new_status != order.status:
            old_status = order.status
            order.status = new_status
            
            # If order is cancelled, restore stock for all items
            if new_status == 'Cancelled' and old_status != 'Cancelled':
                for item in order.items:
                    product = Product.query.get(item.product_id)
                    if product:
                        current_stock = product.get_current_stock()
                        
                        # Create inventory movement for cancellation (stock in)
                        movement = InventoryMovement.create_movement(
                            product=product,
                            quantity_change=item.quantity,
                            movement_type='Return',
                            reference_id=order.order_id,
                            created_by=current_user.id,
                            notes=f"Order #{order.order_id} cancelled, {item.quantity} x {item.product_name} returned"
                        )
                        db.session.add(movement)
            
            db.session.commit()
            flash(f'Order status updated to {new_status}', 'success')
        else:
            flash('No status change', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating status: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('orders.order_details', id=id))


# ==================== DELETE ORDER ====================
@orders.route('/ecommerce/order/delete/<int:id>', methods=['POST'])
@login_required
def delete_order(id):
    """Delete an order and restore stock"""
    order = Order.query.get_or_404(id)
    
    # User isolation check
    if order.created_by != current_user.id:
        flash('You do not have permission to delete this order', 'danger')
        return redirect(url_for('orders.order_list'))
    
    # Only allow deletion of pending orders
    if order.status != "Pending":
        flash('Only pending orders can be deleted', 'danger')
        return redirect(url_for('orders.order_details', id=id))
    
    try:
        # Restore product stock for all items
        for item in order.items:
            product = Product.query.get(item.product_id)
            if product:
                current_stock = product.get_current_stock()
                
                # Create inventory movement for deletion (stock in)
                movement = InventoryMovement.create_movement(
                    product=product,
                    quantity_change=item.quantity,
                    movement_type='Adjustment',
                    reference_id=order.order_id,
                    created_by=current_user.id,
                    notes=f"Order #{order.order_id} deleted, {item.quantity} x {item.product_name} restored"
                )
                db.session.add(movement)
        
        # Delete order (cascade will delete order items)
        order_id_display = order.order_id
        db.session.delete(order)
        db.session.commit()
        
        flash(f'Order {order_id_display} deleted successfully! Stock restored.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting order: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('orders.order_list'))


# ==================== API: GET PRODUCT DETAILS FOR ORDER FORM ====================
@orders.route('/api/order/product/<int:id>')
@login_required
def get_product_for_order(id):
    """API endpoint to get product details for order form"""
    product = Product.query.filter_by(id=id, created_by=current_user.id).first()
    
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'id': product.id,
        'title': product.title,
        'sku': product.sku,
        'suggested_price': float(product.suggested_selling_price or 0),
        'current_stock': product.get_current_stock(),
        'avg_purchase_price': float(product.get_average_purchase_price() or 0),
        'is_low_stock': product.is_low_stock()
    })


# ==================== API: CALCULATE ORDER ITEM ====================
@orders.route('/api/order/calculate-item', methods=['POST'])
@login_required
def calculate_order_item():
    """API endpoint to calculate order item values"""
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        selling_price = float(data.get('selling_price', 0))
        discount = float(data.get('discount', 0))
        gst = float(data.get('gst', 18))
        
        product = Product.query.filter_by(id=product_id, created_by=current_user.id).first()
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Check stock
        available_stock = product.get_current_stock()
        if available_stock < quantity:
            return jsonify({
                'error': f'Only {available_stock} items available',
                'available_stock': available_stock,
                'can_order': False
            }), 400
        
        # Get average purchase price
        purchase_price = product.get_average_purchase_price()
        
        # Calculate
        subtotal = quantity * selling_price
        discount_amount = subtotal * (discount / 100)
        after_discount = subtotal - discount_amount
        gst_amount = after_discount * (gst / 100)
        total = after_discount + gst_amount
        profit = (selling_price - purchase_price) * quantity
        
        return jsonify({
            'product_id': product.id,
            'product_name': product.title,
            'quantity': quantity,
            'selling_price': selling_price,
            'subtotal': round(subtotal, 2),
            'discount_percentage': discount,
            'discount_amount': round(discount_amount, 2),
            'after_discount': round(after_discount, 2),
            'gst_percentage': gst,
            'gst_amount': round(gst_amount, 2),
            'total': round(total, 2),
            'profit': round(profit, 2),
            'available_stock': available_stock,
            'can_order': available_stock >= quantity
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== API: ORDER STATISTICS ====================
@orders.route('/api/order-stats')
@login_required
def order_stats():
    """API endpoint for order statistics"""
    
    # Overall stats for current user
    orders_query = Order.query.filter_by(created_by=current_user.id)
    
    total_orders = orders_query.count()
    total_revenue = orders_query.with_entities(func.sum(Order.final_amount)).scalar() or 0
    total_profit = orders_query.with_entities(func.sum(Order.profit)).scalar() or 0
    
    # Today's stats
    today = datetime.now().date()
    today_orders = orders_query.filter(func.date(Order.order_date) == today).count()
    today_revenue = orders_query.filter(func.date(Order.order_date) == today)\
                                 .with_entities(func.sum(Order.final_amount)).scalar() or 0
    
    # Monthly stats
    first_day_month = datetime.now().replace(day=1).date()
    monthly_orders = orders_query.filter(Order.order_date >= first_day_month).count()
    monthly_revenue = orders_query.filter(Order.order_date >= first_day_month)\
                                   .with_entities(func.sum(Order.final_amount)).scalar() or 0
    
    # Status counts
    status_counts = {}
    for status in ['Pending', 'Processing', 'Delivered', 'Cancelled']:
        status_counts[status.lower()] = orders_query.filter_by(status=status).count()
    
    return jsonify({
        'overall': {
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'total_profit': float(total_profit)
        },
        'today': {
            'orders': today_orders,
            'revenue': float(today_revenue)
        },
        'monthly': {
            'orders': monthly_orders,
            'revenue': float(monthly_revenue)
        },
        'by_status': status_counts
    })


# ==================== API: RECENT ORDERS ====================
@orders.route('/api/recent-orders')
@login_required
def recent_orders():
    """API endpoint for recent orders"""
    
    recent = Order.query.filter_by(created_by=current_user.id)\
                        .order_by(Order.order_date.desc())\
                        .limit(10)\
                        .all()
    
    orders_data = []
    for order in recent:
        orders_data.append({
            'id': order.id,
            'order_id': order.order_id,
            'customer': order.customer_name,
            'item_count': order.get_item_count(),
            'total_quantity': order.get_total_quantity(),
            'amount': float(order.final_amount or 0),
            'profit': float(order.profit or 0),
            'status': order.status,
            'date': order.order_date.strftime('%d %b %Y %H:%M') if order.order_date else None
        })
    
    return jsonify(orders_data)


# ==================== API: CHECK STOCK BEFORE ORDER ====================
@orders.route('/api/check-stock/<int:product_id>/<int:quantity>')
@login_required
def check_stock(product_id, quantity):
    """Check if product has sufficient stock"""
    
    product = Product.query.filter_by(id=product_id, created_by=current_user.id).first()
    
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    current_stock = product.get_current_stock()
    
    return jsonify({
        'product_id': product_id,
        'product_name': product.title,
        'available_stock': current_stock,
        'requested_quantity': quantity,
        'sufficient': current_stock >= quantity,
        'avg_purchase_price': float(product.get_average_purchase_price() or 0)
    })


# ==================== ORDER INVOICE ====================
@orders.route('/ecommerce/order/<int:id>/invoice')
@login_required
def order_invoice(id):
    """Generate invoice for order"""
    order = Order.query.get_or_404(id)
    
    # User isolation check
    if order.created_by != current_user.id:
        flash('You do not have access to this order', 'danger')
        return redirect(url_for('orders.order_list'))
    
    items = order.items
    customer = Customer.query.filter_by(id=order.customer_id, created_by=current_user.id).first()
    
    return render_template(
        'ecommerce/apps-ecommerce-invoice.html',
        order=order,
        items=items,
        customer=customer
    )
@orders.route('/ecommerce/orders/repair-product-names', methods=['GET'])
@login_required
def repair_product_names():
    """Repair all order items to show correct product names"""
    if current_user.role != 'super_admin':
        flash('Access denied', 'danger')
        return redirect(url_for('orders.order_list'))
    
    fixed_count = 0
    items = OrderItem.query.all()
    
    for item in items:
        if not item.product_name or item.product_name == 'None':
            product = Product.query.get(item.product_id)
            if product:
                item.product_name = product.title
                item.product_sku = product.sku or ''
                item.product_category = product.category or ''
                fixed_count += 1
    
    db.session.commit()
    flash(f'Fixed {fixed_count} order items!', 'success')
    return redirect(url_for('orders.order_list'))