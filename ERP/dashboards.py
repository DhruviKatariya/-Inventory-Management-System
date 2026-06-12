from flask import Blueprint, render_template, jsonify, request, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import decimal
import random
from collections import defaultdict
from . import db
from .models import Order, OrderItem, Customer, Product, Purchase, Seller

dashboards = Blueprint('dashboards', __name__, template_folder='templates', static_folder='static')

def to_float(value):
    """Convert Decimal to float safely"""
    if value is None:
        return 0.0
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0

def format_indian_number(num):
    """Convert number to Indian format (lakhs, thousands)"""
    if num >= 10000000:  # crore
        return f"{num/10000000:.1f} Cr"
    elif num >= 100000:   # lakh
        return f"{num/100000:.1f} L"
    elif num >= 1000:     # thousand
        return f"{num/1000:.1f} k"
    else:
        return str(int(num))

@dashboards.route('/')
@dashboards.route('/dashboard')
@login_required
def index():
    """Main dashboard with all statistics"""
    now = datetime.now()
    today = now.date()
    first_day_month = datetime(now.year, now.month, 1)
    last_month_start = datetime(now.year, now.month-1, 1) if now.month > 1 else datetime(now.year-1, 12, 1)
    
    # ===== ORDER STATISTICS =====
    current_month_orders = Order.query.filter(
        Order.created_by == current_user.id,
        Order.order_date >= first_day_month
    ).count()
    
    last_month_orders = Order.query.filter(
        Order.created_by == current_user.id,
        Order.order_date >= last_month_start,
        Order.order_date < first_day_month
    ).count()
    
    total_orders = Order.query.filter_by(created_by=current_user.id).count()
    order_change = ((current_month_orders - last_month_orders) / last_month_orders * 100) if last_month_orders > 0 else 100
    
    # ===== REVENUE STATISTICS =====
    current_month_revenue_raw = db.session.query(func.sum(Order.final_amount))\
        .filter(Order.created_by == current_user.id, Order.order_date >= first_day_month)\
        .scalar() or 0
    current_month_revenue = to_float(current_month_revenue_raw)
    
    last_month_revenue_raw = db.session.query(func.sum(Order.final_amount))\
        .filter(
            Order.created_by == current_user.id,
            Order.order_date >= last_month_start,
            Order.order_date < first_day_month
        ).scalar() or 0
    last_month_revenue = to_float(last_month_revenue_raw)
    
    total_revenue_raw = db.session.query(func.sum(Order.final_amount))\
        .filter(Order.created_by == current_user.id).scalar() or 0
    total_revenue = to_float(total_revenue_raw)
    
    revenue_change = ((current_month_revenue - last_month_revenue) / last_month_revenue * 100) if last_month_revenue > 0 else 100
    
    # ===== PROFIT STATISTICS =====
    current_month_profit_raw = db.session.query(func.sum(Order.profit))\
        .filter(Order.created_by == current_user.id, Order.order_date >= first_day_month)\
        .scalar() or 0
    current_month_profit = to_float(current_month_profit_raw)
    
    last_month_profit_raw = db.session.query(func.sum(Order.profit))\
        .filter(
            Order.created_by == current_user.id,
            Order.order_date >= last_month_start,
            Order.order_date < first_day_month
        ).scalar() or 0
    last_month_profit = to_float(last_month_profit_raw)
    
    total_profit_raw = db.session.query(func.sum(Order.profit))\
        .filter(Order.created_by == current_user.id).scalar() or 0
    total_profit = to_float(total_profit_raw)
    
    profit_change = ((current_month_profit - last_month_profit) / last_month_profit * 100) if last_month_profit > 0 else 100
    
    # ===== CUSTOMER STATISTICS =====
    total_customers = Customer.query.filter_by(created_by=current_user.id).count()
    
    new_customers = Customer.query.filter(
        Customer.created_by == current_user.id,
        Customer.created_at >= first_day_month
    ).count()
    
    last_month_customers = Customer.query.filter(
        Customer.created_by == current_user.id,
        Customer.created_at >= last_month_start,
        Customer.created_at < first_day_month
    ).count()
    
    customer_change = ((new_customers - last_month_customers) / last_month_customers * 100) if last_month_customers > 0 else 100
    
    # ===== REFUND COUNT =====
    refund_count = Order.query.filter(
        Order.created_by == current_user.id,
        Order.status == 'Cancelled'
    ).count()
    
    # ===== LOW STOCK PRODUCTS =====
    products = Product.query.filter_by(created_by=current_user.id).all()
    low_stock_products = []
    low_stock_count = 0
    
    for product in products:
        stock = product.get_current_stock()
        if stock <= product.low_stock_threshold:
            low_stock_count += 1
            low_stock_products.append({
                'id': product.id,
                'title': product.title,
                'stock': stock,
                'threshold': product.low_stock_threshold
            })
    
    # ===== CHART DATA (Last 7 days – calendar days) =====
    days = 7
    chart_labels, chart_revenue, chart_profit = [], [], []
    chart_totals = {'orders': 0, 'revenue': 0, 'profit': 0}
    
    for i in range(days-1, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        day_orders = Order.query.filter(
            Order.created_by == current_user.id,
            Order.order_date >= day_start,
            Order.order_date <= day_end
        ).count()
        
        day_revenue_raw = db.session.query(func.sum(Order.final_amount))\
            .filter(
                Order.created_by == current_user.id,
                Order.order_date >= day_start,
                Order.order_date <= day_end
            ).scalar() or 0
        day_revenue = to_float(day_revenue_raw)
        
        day_profit_raw = db.session.query(func.sum(Order.profit))\
            .filter(
                Order.created_by == current_user.id,
                Order.order_date >= day_start,
                Order.order_date <= day_end
            ).scalar() or 0
        day_profit = to_float(day_profit_raw)
        
        chart_labels.append(day.strftime('%d %b'))
        chart_revenue.append(day_revenue)
        chart_profit.append(day_profit)
        
        chart_totals['orders'] += day_orders
        chart_totals['revenue'] += day_revenue
        chart_totals['profit'] += day_profit
    
    # ===== DELIVERY STATUS STATISTICS =====
    pending_count = Order.query.filter_by(created_by=current_user.id, status='Pending').count()
    processing_count = Order.query.filter_by(created_by=current_user.id, status='Processing').count()
    delivered_count = Order.query.filter_by(created_by=current_user.id, status='Delivered').count()
    cancelled_count = Order.query.filter_by(created_by=current_user.id, status='Cancelled').count()
    
    total_status_orders = pending_count + processing_count + delivered_count + cancelled_count
    
    if total_status_orders > 0:
        pending_percent = round((pending_count / total_status_orders) * 100, 1)
        processing_percent = round((processing_count / total_status_orders) * 100, 1)
        delivered_percent = round((delivered_count / total_status_orders) * 100, 1)
        cancelled_percent = round((cancelled_count / total_status_orders) * 100, 1)
        
        # Adjust to ensure total is 100%
        total_percent = pending_percent + processing_percent + delivered_percent + cancelled_percent
        if total_percent != 100:
            diff = 100 - total_percent
            max_percent = max(pending_percent, processing_percent, delivered_percent, cancelled_percent)
            if max_percent == pending_percent:
                pending_percent += diff
            elif max_percent == processing_percent:
                processing_percent += diff
            elif max_percent == delivered_percent:
                delivered_percent += diff
            else:
                cancelled_percent += diff
    else:
        pending_percent = processing_percent = delivered_percent = cancelled_percent = 0
    
    delivery_stats = {
        'pending': pending_percent,
        'processing': processing_percent,
        'delivered': delivered_percent,
        'cancelled': cancelled_percent,
        'pending_count': pending_count,
        'processing_count': processing_count,
        'delivered_count': delivered_count,
        'cancelled_count': cancelled_count
    }
    
    delivery_series = [pending_percent, processing_percent, delivered_percent, cancelled_percent]
    delivery_labels = ['Pending', 'Processing', 'Delivered', 'Cancelled']
    
    # ===== TOP PRODUCTS =====
    product_data = []
    top_products_query = db.session.query(
        Product.id,
        Product.title,
        Product.category,
        Product.image,
        Product.manufacturer_brand,
        Product.suggested_selling_price,
        func.count(OrderItem.id).label('orders_count'),
        func.sum(OrderItem.quantity).label('total_sold'),
        func.sum(OrderItem.total).label('revenue')
    ).join(OrderItem, OrderItem.product_id == Product.id)\
     .join(Order, Order.id == OrderItem.order_id)\
     .filter(Order.created_by == current_user.id)\
     .group_by(Product.id, Product.title, Product.category, Product.image, 
              Product.manufacturer_brand, Product.suggested_selling_price)\
     .order_by(func.sum(OrderItem.total).desc())\
     .limit(5).all()
    
    for p in top_products_query:
        product = Product.query.get(p.id)
        current_stock = product.get_current_stock() if product else 0
        total_sold = int(p.total_sold) if p.total_sold else 0
        revenue = to_float(p.revenue or 0)
        
        product_data.append({
            'id': p.id,
            'title': p.title,
            'category': p.category,
            'image': p.image,
            'brand': p.manufacturer_brand,
            'price': to_float(p.suggested_selling_price or 0),
            'total_sold': total_sold,
            'orders_count': p.orders_count,
            'revenue': revenue,
            'stock': current_stock
        })
    
    # ===== SELLERS DATA =====
    sellers = Seller.query.filter_by(created_by=current_user.id).limit(5).all()
    sellers_data = []
    for seller in sellers:
        products_count = db.session.query(func.count(Product.id))\
            .join(Purchase, Purchase.product_id == Product.id)\
            .filter(Purchase.seller_id == seller.id).scalar() or 0
        
        total_spent = seller.get_total_spent()
        total_spent_float = to_float(total_spent)
        
        sellers_data.append({
            'id': seller.id,
            'name': seller.company_name or seller.get_full_name(),
            'owner': seller.get_full_name(),
            'logo': seller.company_logo,
            'products_count': products_count,
            'amount': total_spent_float,
            'progress': min(100, int((total_spent_float / 500000) * 100)) if total_spent_float else random.randint(30, 90)
        })
    
    # ===== RECENT ORDERS =====
    recent_orders_list = Order.query.filter_by(created_by=current_user.id)\
                                     .order_by(Order.order_date.desc())\
                                     .limit(5).all()
    recent_orders = []
    for order in recent_orders_list:
        recent_orders.append({
            'id': order.id,
            'order_id': order.order_id,
            'customer_name': order.customer_name,
            'amount': to_float(order.final_amount or 0),
            'status': order.status
        })
    
    # ===== RECENT CUSTOMERS =====
    recent_customers_list = Customer.query.filter_by(created_by=current_user.id)\
                                         .order_by(Customer.created_at.desc())\
                                         .limit(5).all()
    recent_customers_data = []
    for customer in recent_customers_list:
        orders_count = len(customer.orders)
        spent = sum(to_float(o.final_amount or 0) for o in customer.orders)
        recent_customers_data.append({
            'id': customer.id,
            'name': customer.name,
            'email': customer.email,
            'orders_count': orders_count,
            'spent': spent,
            'status': customer.status
        })
    
    # ===== RECENT ACTIVITIES =====
    recent_orders_act = Order.query.filter_by(created_by=current_user.id)\
                                   .order_by(Order.order_date.desc())\
                                   .limit(3).all()
    
    recent_purchases = Purchase.query.filter_by(created_by=current_user.id)\
                                     .order_by(Purchase.purchase_date.desc())\
                                     .limit(3).all()
    
    recent_customers_act = Customer.query.filter_by(created_by=current_user.id)\
                                         .order_by(Customer.created_at.desc())\
                                         .limit(3).all()
    
    activities = []
    
    for order in recent_orders_act:
        activities.append({
            'type': 'order',
            'icon': 'shopping-cart-line',
            'title': f'Order #{order.order_id}',
            'time': order.order_date.strftime('%d %b %H:%M') if order.order_date else 'N/A',
            'amount': to_float(order.final_amount or 0),
            'url': url_for('orders.order_details', id=order.id)
        })
    
    for purchase in recent_purchases:
        seller_name = purchase.seller.get_full_name() if purchase.seller else "Unknown"
        activities.append({
            'type': 'purchase',
            'icon': 'truck-line',
            'title': f'Purchase from {seller_name}',
            'time': purchase.purchase_date.strftime('%d %b %H:%M') if purchase.purchase_date else 'N/A',
            'amount': to_float(purchase.total_cost or 0),
            'url': url_for('purchases.edit_purchase', id=purchase.id) if purchase.id else '#'
        })
    
    for customer in recent_customers_act:
        activities.append({
            'type': 'customer',
            'icon': 'user-add-line',
            'title': f'New customer: {customer.name}',
            'time': customer.created_at.strftime('%d %b %H:%M') if customer.created_at else 'N/A',
            'amount': None,
            'url': url_for('customers.customer_details', id=customer.id)
        })
    
    activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = activities[:7]
    
    # Format numbers for display
    formatted_numbers = {
        'total_revenue': format_indian_number(total_revenue),
        'total_profit': format_indian_number(total_profit),
        'total_customers': total_customers,
        'total_orders': total_orders,
        'chart_totals_revenue': format_indian_number(chart_totals['revenue']),
        'chart_totals_profit': format_indian_number(chart_totals['profit'])
    }
    
    return render_template(
        'dashboards/index.html',
        now=lambda: datetime.now(),
        # Stats
        total_orders=total_orders,
        order_change=order_change,
        total_revenue=total_revenue,
        revenue_change=revenue_change,
        total_profit=total_profit,
        profit_change=profit_change,
        total_customers=total_customers,
        customer_change=customer_change,
        refund_count=refund_count,
        # Low Stock
        low_stock_count=low_stock_count,
        low_stock_products=low_stock_products,
        # Chart Data
        chart_labels=chart_labels,
        chart_revenue=chart_revenue,
        chart_profit=chart_profit,
        chart_totals=chart_totals,
        # Delivery Status Data
        delivery_stats=delivery_stats,
        delivery_series=delivery_series,
        delivery_labels=delivery_labels,
        # Data Tables
        top_products=product_data,
        sellers_data=sellers_data,
        recent_orders=recent_orders,
        recent_customers_data=recent_customers_data,
        recent_activities=recent_activities,
        # Pie Chart Data
        pie_data=delivery_stats,
        pie_series=delivery_series,
        pie_labels=delivery_labels,
        # Formatted numbers
        formatted_numbers=formatted_numbers
    )

@dashboards.route('/api/dashboard/chart-data')
@login_required
def chart_data():
    """API endpoint for chart data with period filter and aggregation"""
    period = request.args.get('period', '7')
    days = int(period)
    now = datetime.now()
    today = now.date()
    
    # Determine start date (calendar day)
    start_date = today - timedelta(days=days-1)
    start_datetime = datetime.combine(start_date, datetime.min.time())
    
    # Fetch all orders within the range
    orders = Order.query.filter(
        Order.created_by == current_user.id,
        Order.order_date >= start_datetime
    ).order_by(Order.order_date).all()
    
    # Group based on period length
    if days <= 31:
        # Daily grouping
        groups = defaultdict(lambda: {'orders': 0, 'revenue': 0.0, 'profit': 0.0})
        for order in orders:
            day_key = order.order_date.date()
            groups[day_key]['orders'] += 1
            groups[day_key]['revenue'] += to_float(order.final_amount or 0)
            groups[day_key]['profit'] += to_float(order.profit or 0)
        
        # Generate labels for all days in range
        labels = []
        revenue_data = []
        profit_data = []
        totals = {'orders': 0, 'revenue': 0.0, 'profit': 0.0}
        
        for i in range(days):
            day = start_date + timedelta(days=i)
            data = groups.get(day, {'orders': 0, 'revenue': 0.0, 'profit': 0.0})
            labels.append(day.strftime('%d %b'))
            revenue_data.append(data['revenue'])
            profit_data.append(data['profit'])
            totals['orders'] += data['orders']
            totals['revenue'] += data['revenue']
            totals['profit'] += data['profit']
    
    elif days <= 90:
        # Weekly grouping
        groups = defaultdict(lambda: {'orders': 0, 'revenue': 0.0, 'profit': 0.0})
        for order in orders:
            # Use ISO week: year + week number
            week_key = order.order_date.strftime('%Y-W%W')
            groups[week_key]['orders'] += 1
            groups[week_key]['revenue'] += to_float(order.final_amount or 0)
            groups[week_key]['profit'] += to_float(order.profit or 0)
        
        # Collect sorted weeks
        sorted_weeks = sorted(groups.keys())
        labels = []
        revenue_data = []
        profit_data = []
        totals = {'orders': 0, 'revenue': 0.0, 'profit': 0.0}
        
        for week in sorted_weeks:
            # Parse week to get a representative date (Monday of that week)
            year, weeknum = week.split('-W')
            # Approximate date (first day of that week) – just for label
            first_day = datetime.strptime(f'{year}-{weeknum}-1', '%Y-%W-%w').date()
            labels.append(first_day.strftime('%d %b'))
            data = groups[week]
            revenue_data.append(data['revenue'])
            profit_data.append(data['profit'])
            totals['orders'] += data['orders']
            totals['revenue'] += data['revenue']
            totals['profit'] += data['profit']
    
    else:
        # Monthly grouping
        groups = defaultdict(lambda: {'orders': 0, 'revenue': 0.0, 'profit': 0.0})
        for order in orders:
            month_key = order.order_date.strftime('%Y-%m')
            groups[month_key]['orders'] += 1
            groups[month_key]['revenue'] += to_float(order.final_amount or 0)
            groups[month_key]['profit'] += to_float(order.profit or 0)
        
        sorted_months = sorted(groups.keys())
        labels = []
        revenue_data = []
        profit_data = []
        totals = {'orders': 0, 'revenue': 0.0, 'profit': 0.0}
        
        for month in sorted_months:
            # Convert to date (first of month)
            year, month_num = month.split('-')
            first_day = datetime(int(year), int(month_num), 1).date()
            labels.append(first_day.strftime('%b %Y'))
            data = groups[month]
            revenue_data.append(data['revenue'])
            profit_data.append(data['profit'])
            totals['orders'] += data['orders']
            totals['revenue'] += data['revenue']
            totals['profit'] += data['profit']
    
    return jsonify({
        'labels': labels,
        'revenue': revenue_data,
        'profit': profit_data,
        'totals': totals
    })

# Other API endpoints remain unchanged
@dashboards.route('/api/dashboard/delivery-stats')
@login_required
def delivery_stats_api():
    # ... (unchanged)
    pass

@dashboards.route('/api/dashboard/low-stock')
@login_required
def low_stock_api():
    # ... (unchanged)
    pass