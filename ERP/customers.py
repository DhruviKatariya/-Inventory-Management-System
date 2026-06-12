from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func, or_
from . import db
from .models import Customer, Order, OrderItem, Product

customers = Blueprint('customers', __name__, template_folder='templates', static_folder='static')


# ==================== LIST CUSTOMERS ====================
@customers.route('/ecommerce/customer')
@login_required
def customer_list():
    """List all customers - filtered by current user"""
    # Get filter parameters
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    city_filter = request.args.get('city', '')
    
    # Start with base query - USER ISOLATION
    query = Customer.query.filter_by(created_by=current_user.id)\
                          .order_by(Customer.created_at.desc())
    
    # Apply search filter
    if search:
        query = query.filter(
            or_(
                Customer.name.ilike(f'%{search}%'),
                Customer.email.ilike(f'%{search}%'),
                Customer.phone.ilike(f'{search}%'),
                Customer.city.ilike(f'%{search}%'),
                Customer.address.ilike(f'%{search}%')
            )
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter(Customer.status == status_filter)
    
    # Apply city filter
    if city_filter:
        query = query.filter(Customer.city.ilike(f'%{city_filter}%'))
    
    # Apply date range filter
    if date_from:
        try:
            query = query.filter(Customer.join_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        except:
            pass
    
    if date_to:
        try:
            query = query.filter(Customer.join_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        except:
            pass
    
    customers_data = query.all()
    
    # Calculate statistics for each customer
    for customer in customers_data:
        # Get orders count (using relationship)
        customer.order_count = len(customer.orders)
        
        # Calculate total spent using final_amount
        total = 0
        for order in customer.orders:
            if order.final_amount:
                total += order.final_amount
        customer.total_spent = total
        
        # Get last order date
        if customer.orders:
            # Sort orders by date (newest first)
            sorted_orders = sorted(customer.orders, key=lambda x: x.order_date or datetime.min, reverse=True)
            customer.last_order_date = sorted_orders[0].order_date
        else:
            customer.last_order_date = None
    
    # Get unique cities for filter dropdown
    cities = db.session.query(Customer.city)\
        .filter(Customer.created_by == current_user.id)\
        .filter(Customer.city.isnot(None))\
        .filter(Customer.city != '')\
        .distinct().order_by(Customer.city).all()
    cities = [city[0] for city in cities]
    
    # Calculate overall statistics for current user only
    total_customers = Customer.query.filter_by(created_by=current_user.id).count()
    active_customers = Customer.query.filter_by(created_by=current_user.id, status='Active').count()
    
    total_revenue = db.session.query(func.sum(Order.final_amount))\
                              .filter(Order.created_by == current_user.id)\
                              .scalar() or 0
    
    # Calculate new customers this month
    today = datetime.now()
    first_day_of_month = datetime(today.year, today.month, 1).date()
    new_customers_this_month = 0
    for customer in customers_data:
        if customer.join_date and customer.join_date >= first_day_of_month:
            new_customers_this_month += 1
    
    # Get low stock products for alert
    products = Product.query.filter_by(created_by=current_user.id).all()
    low_stock_count = sum(1 for p in products if p.is_low_stock())
    
    return render_template(
        'ecommerce/apps-ecommerce_customer.html',
        customers=customers_data,
        total_customers=total_customers,
        active_customers=active_customers,
        total_revenue=total_revenue,
        new_customers_this_month=new_customers_this_month,
        low_stock_count=low_stock_count,
        cities=cities,
        search=search,
        status_filter=status_filter,
        city_filter=city_filter,
        date_from=date_from,
        date_to=date_to
    )


# ==================== CUSTOMER DETAILS ====================
@customers.route('/ecommerce/customer/<int:id>')
@login_required
def customer_details(id):
    """View customer details with access check"""
    customer = Customer.query.get_or_404(id)
    
    # User isolation check
    if customer.created_by != current_user.id:
        flash('You do not have access to this customer', 'danger')
        return redirect(url_for('customers.customer_list'))
    
    # Get all orders for this customer
    orders = customer.orders.order_by(Order.order_date.desc()).all()
    
    # Calculate statistics
    total_orders = len(orders)
    total_spent = 0
    for order in orders:
        if order.final_amount:
            total_spent += order.final_amount
    
    avg_order_value = total_spent / total_orders if total_orders > 0 else 0
    
    # Get monthly spending for current year
    current_year = datetime.now().year
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Initialize monthly data
    monthly_spending = []
    for month_num in range(1, 13):
        month_total = 0
        month_count = 0
        for order in orders:
            if order.order_date and order.order_date.year == current_year and order.order_date.month == month_num:
                month_count += 1
                if order.final_amount:
                    month_total += order.final_amount
        
        if month_count > 0:
            monthly_spending.append({
                'month': month_names[month_num - 1],
                'orders': month_count,
                'total': float(month_total)
            })
    
    # Get favorite products (most ordered) - using OrderItem
    product_counts = {}
    for order in orders:
        for item in order.items:
            if item.product_id:
                if item.product_id not in product_counts:
                    product_counts[item.product_id] = {
                        'count': 0,
                        'quantity': 0
                    }
                product_counts[item.product_id]['count'] += 1
                product_counts[item.product_id]['quantity'] += item.quantity
    
    # Sort by count and get top 5
    favorite_products_data = []
    sorted_products = sorted(product_counts.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
    
    for product_id, stats in sorted_products:
        product = Product.query.get(product_id)
        if product:
            favorite_products_data.append({
                'name': product.title,
                'orders': stats['count'],
                'quantity': stats['quantity']
            })
    
    return render_template(
        'ecommerce/apps-ecommerce-customer-details.html',
        customer=customer,
        orders=orders,
        total_orders=total_orders,
        total_spent=total_spent,
        avg_order_value=avg_order_value,
        monthly_spending=monthly_spending,
        favorite_products=favorite_products_data
    )


# ==================== ADD CUSTOMER ====================
@customers.route('/ecommerce/customer/add', methods=['POST'])
@login_required
def add_customer():
    """Add new customer - assigned to current user"""
    try:
        # Get form data - including all fields
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        join_date_str = request.form.get('join_date')
        status = request.form.get('status', 'Active')
        
        # Validate required fields
        if not name:
            flash('Customer name is required!', 'danger')
            return redirect(url_for('customers.customer_list'))
        
        if not email:
            flash('Email is required!', 'danger')
            return redirect(url_for('customers.customer_list'))
        
        # Check if email already exists for this user
        existing = Customer.query.filter_by(email=email, created_by=current_user.id).first()
        if existing:
            flash('Email already exists! Please use a different email.', 'danger')
            return redirect(url_for('customers.customer_list'))
        
        # Parse join date
        join_date = None
        if join_date_str:
            try:
                join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date()
            except:
                flash('Invalid date format', 'warning')
        
        # Create customer with all fields
        customer = Customer(
            name=name,
            email=email,
            phone=phone,
            address=address,
            city=city,
            state=state,
            join_date=join_date,
            status=status,
            created_by=current_user.id
        )
        
        db.session.add(customer)
        db.session.commit()
        
        flash(f'Customer {customer.name} added successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding customer: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('customers.customer_list'))


# ==================== UPDATE CUSTOMER ====================
@customers.route('/ecommerce/customer/update/<int:id>', methods=['POST'])
@login_required
def update_customer(id):
    """Update customer with access check"""
    customer = Customer.query.get_or_404(id)
    
    # User isolation check
    if customer.created_by != current_user.id:
        flash('You do not have permission to update this customer', 'danger')
        return redirect(url_for('customers.customer_list'))
    
    try:
        # Get form data - including all fields
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        join_date_str = request.form.get('join_date')
        status = request.form.get('status', 'Active')
        
        # Validate required fields
        if not name:
            flash('Customer name is required!', 'danger')
            return redirect(url_for('customers.customer_list'))
        
        if not email:
            flash('Email is required!', 'danger')
            return redirect(url_for('customers.customer_list'))
        
        # Check if email already exists (if changed)
        if email != customer.email:
            existing = Customer.query.filter_by(email=email, created_by=current_user.id).first()
            if existing:
                flash('Email already exists! Please use a different email.', 'danger')
                return redirect(url_for('customers.customer_list'))
        
        # Parse join date
        join_date = None
        if join_date_str:
            try:
                join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date()
            except:
                flash('Invalid date format', 'warning')
        
        # Update customer - all fields
        customer.name = name
        customer.email = email
        customer.phone = phone
        customer.address = address
        customer.city = city
        customer.state = state
        customer.join_date = join_date
        customer.status = status
        
        db.session.commit()
        
        flash(f'Customer {customer.name} updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating customer: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('customers.customer_list'))


# ==================== DELETE CUSTOMER ====================
@customers.route('/ecommerce/customer/delete/<int:id>', methods=['POST'])
@login_required
def delete_customer(id):
    """Delete customer with access check"""
    customer = Customer.query.get_or_404(id)
    
    # User isolation check
    if customer.created_by != current_user.id:
        flash('You do not have permission to delete this customer', 'danger')
        return redirect(url_for('customers.customer_list'))
    
    try:
        # Check if customer has orders
        order_count = len(customer.orders)
        if order_count > 0:
            flash(f'Cannot delete customer {customer.name} because they have {order_count} order records!', 'danger')
            return redirect(url_for('customers.customer_list'))
        
        customer_name = customer.name
        db.session.delete(customer)
        db.session.commit()
        
        flash(f'Customer {customer_name} deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting customer: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('customers.customer_list'))


# ==================== API ENDPOINTS ====================

@customers.route('/api/customer/<int:id>')
@login_required
def get_customer_api(id):
    """API endpoint to get customer details - with access check"""
    customer = Customer.query.get_or_404(id)
    
    # User isolation check
    if customer.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    total_orders = len(customer.orders)
    
    total_spent = 0
    for order in customer.orders:
        if order.final_amount:
            total_spent += order.final_amount
    
    return jsonify({
        'id': customer.id,
        'name': customer.name,
        'email': customer.email,
        'phone': customer.phone,
        'address': customer.address,
        'city': customer.city,
        'state': customer.state,
        'join_date': customer.join_date.strftime('%Y-%m-%d') if customer.join_date else None,
        'status': customer.status,
        'total_orders': total_orders,
        'total_spent': float(total_spent),
        'created_at': customer.created_at.strftime('%Y-%m-%d %H:%M:%S') if customer.created_at else None
    })


@customers.route('/api/customer-stats')
@login_required
def customer_stats():
    """API endpoint for customer statistics - filtered by user"""
    
    # Overall stats for current user only
    customers_query = Customer.query.filter_by(created_by=current_user.id)
    
    total_customers = customers_query.count()
    active_customers = customers_query.filter_by(status='Active').count()
    inactive_customers = customers_query.filter_by(status='Inactive').count()
    
    # City-wise distribution
    city_stats = db.session.query(
        Customer.city, 
        func.count(Customer.id).label('count')
    ).filter(
        Customer.created_by == current_user.id,
        Customer.city.isnot(None),
        Customer.city != ''
    ).group_by(Customer.city).order_by(func.count(Customer.id).desc()).limit(5).all()
    
    city_distribution = [{'city': city, 'count': count} for city, count in city_stats]
    
    # New customers this month
    today = datetime.now()
    first_day = datetime(today.year, today.month, 1)
    new_customers = 0
    for customer in customers_query.all():
        if customer.created_at and customer.created_at >= first_day:
            new_customers += 1
    
    # Top customers by spending
    customer_spending = []
    for customer in customers_query.all():
        total_spent = 0
        for order in customer.orders:
            if order.final_amount:
                total_spent += order.final_amount
        total_orders = len(customer.orders)
        
        if total_orders > 0:
            customer_spending.append({
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'city': customer.city,
                'orders': total_orders,
                'total_spent': float(total_spent)
            })
    
    # Sort by total spent
    customer_spending.sort(key=lambda x: x['total_spent'], reverse=True)
    top_customers = customer_spending[:5]
    
    return jsonify({
        'overall': {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'inactive_customers': inactive_customers,
            'new_customers_this_month': new_customers
        },
        'city_distribution': city_distribution,
        'top_customers': top_customers
    })


@customers.route('/api/customer/<int:id>/orders')
@login_required
def customer_orders_api(id):
    """API endpoint to get customer order history - with access check"""
    customer = Customer.query.get_or_404(id)
    
    # User isolation check
    if customer.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    orders = customer.orders.order_by(Order.order_date.desc()).all()
    
    orders_data = []
    for order in orders:
        # Get product names from order items
        products = []
        for item in order.items:
            products.append({
                'name': item.product_name,
                'quantity': item.quantity,
                'price': item.selling_price
            })
        
        orders_data.append({
            'id': order.id,
            'order_id': order.order_id,
            'date': order.order_date.strftime('%d %b %Y') if order.order_date else None,
            'products': products,
            'total_items': len(order.items),
            'total_quantity': sum(item.quantity for item in order.items),
            'amount': float(order.final_amount or 0),
            'profit': float(order.profit or 0),
            'status': order.status,
            'payment_method': order.payment_method
        })
    
    return jsonify({
        'customer_id': customer.id,
        'customer_name': customer.name,
        'total_orders': len(orders_data),
        'total_spent': float(sum(o['amount'] for o in orders_data)),
        'orders': orders_data
    })


# ==================== BULK CUSTOMER IMPORT ====================
@customers.route('/ecommerce/customer/bulk-import', methods=['POST'])
@login_required
def bulk_import():
    """Bulk import customers from CSV"""
    if 'csv_file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('customers.customer_list'))
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('customers.customer_list'))
    
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file', 'danger')
        return redirect(url_for('customers.customer_list'))
    
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
                if not row.get('name') or not row.get('email'):
                    errors.append(f"Row {row_num}: Missing name or email")
                    error_count += 1
                    continue
                
                # Check if email already exists for this user
                existing = Customer.query.filter_by(
                    email=row.get('email'), 
                    created_by=current_user.id
                ).first()
                
                if existing:
                    errors.append(f"Row {row_num}: Email {row.get('email')} already exists")
                    error_count += 1
                    continue
                
                # Parse join date
                join_date = None
                date_value = row.get('join_date')

                if date_value:
                    try:
                        join_date = datetime.strptime(date_value.strip(), '%Y-%m-%d').date()
                    except:
                        try:
                            join_date = datetime.strptime(date_value.strip(), '%d-%m-%Y').date()
                        except:
                            try:
                                join_date = datetime.strptime(date_value.strip(), '%d/%m/%Y').date()
                            except:
                                join_date = None
                
                # Create customer - all fields
                customer = Customer(
                    name=row.get('name', '').strip(),
                    email=row.get('email', '').strip(),
                    phone=row.get('phone', '').strip(),
                    address=row.get('address', '').strip(),
                    city=row.get('city', '').strip(),
                    state=row.get('state', '').strip(),
                    join_date=join_date,
                    status=row.get('status', 'Active'),
                    created_by=current_user.id
                )
                
                db.session.add(customer)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        db.session.commit()
        
        if errors:
            for error in errors[:5]:
                flash(error, 'warning')
        
        flash(f'Bulk import completed: {success_count} customers added, {error_count} errors', 
              'success' if success_count > 0 else 'danger')
        
    except Exception as e:
        flash(f'Error processing CSV: {str(e)}', 'danger')
    
    return redirect(url_for('customers.customer_list'))


# ==================== CUSTOMER SEARCH ====================
@customers.route('/api/customer-search')
@login_required
def customer_search():
    """API endpoint for customer search"""
    search_term = request.args.get('q', '')
    
    if not search_term or len(search_term) < 2:
        return jsonify([])
    
    customers = Customer.query.filter(
        Customer.created_by == current_user.id,
        or_(
            Customer.name.ilike(f'%{search_term}%'),
            Customer.email.ilike(f'%{search_term}%'),
            Customer.phone.ilike(f'%{search_term}%'),
            Customer.city.ilike(f'%{search_term}%')
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'email': c.email,
        'phone': c.phone,
        'city': c.city
    } for c in customers])


# ==================== GET CITIES ====================
@customers.route('/api/cities')
@login_required
def get_cities():
    """API endpoint to get unique cities for filter"""
    cities = db.session.query(Customer.city)\
        .filter(Customer.created_by == current_user.id)\
        .filter(Customer.city.isnot(None))\
        .filter(Customer.city != '')\
        .distinct().order_by(Customer.city).all()
    
    return jsonify([city[0] for city in cities])