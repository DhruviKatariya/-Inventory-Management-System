import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func, extract
from . import db
from .models import Seller, Purchase, Product, InventoryMovement

sellers = Blueprint('sellers', __name__, template_folder='templates', static_folder='static')


# ==================== LIST SELLERS ====================
@sellers.route('/ecommerce/sellers')
@login_required
def seller_list():
    """List all sellers - filtered by current user"""
    # User isolation - only show sellers created by current user
    sellers_data = Seller.query.filter_by(created_by=current_user.id)\
                               .order_by(Seller.created_at.desc())\
                               .all()
    
    # Calculate statistics for each seller
    for seller in sellers_data:
        # Get purchases using relationship
        purchases = seller.purchases
        
        # Calculate total purchases count
        seller.total_purchases_count = purchases.count()
        
        # Calculate total quantity purchased
        seller.total_quantity = purchases.with_entities(func.sum(Purchase.quantity)).scalar() or 0
        
        # Calculate total amount spent
        total_spent = purchases.with_entities(func.sum(Purchase.total_cost)).scalar()
        seller.total_spent = float(total_spent) if total_spent is not None else 0
        
        # Get unique products supplied
        seller.products_supplied = purchases.distinct(Purchase.product_id).count()
        
        # Get full name for display
        seller.full_name = seller.get_full_name()
    
    # Get low stock products for alert
    products = Product.query.filter_by(created_by=current_user.id).all()
    low_stock_count = sum(1 for p in products if p.is_low_stock())
    
    return render_template(
        'ecommerce/apps-ecommerce_sellers.html',
        sellers=sellers_data,
        low_stock_count=low_stock_count
    )


# ==================== SELLER DETAILS ====================
@sellers.route('/ecommerce/seller/<int:id>')
@login_required
def seller_details(id):
    """View seller details with access check"""
    seller = Seller.query.get_or_404(id)
    
    # User isolation check
    if seller.created_by != current_user.id:
        flash('You do not have access to this seller', 'danger')
        return redirect(url_for('sellers.seller_list'))
    
    # Get all purchases from this seller (with product info)
    purchases = seller.purchases.order_by(Purchase.purchase_date.desc()).all()
    
    # Calculate comprehensive statistics
    total_purchases = seller.purchases.count()
    
    total_quantity_val = seller.purchases.with_entities(func.sum(Purchase.quantity)).scalar()
    total_quantity = int(total_quantity_val) if total_quantity_val is not None else 0
    
    total_spent_val = seller.purchases.with_entities(func.sum(Purchase.total_cost)).scalar()
    total_spent = float(total_spent_val) if total_spent_val is not None else 0
    
    # Get unique products supplied
    unique_products = db.session.query(Product).join(
        Purchase, Purchase.product_id == Product.id
    ).filter(
        Purchase.seller_id == id,
        Product.created_by == current_user.id  # User isolation
    ).distinct().all()
    
    # Get product IDs for this seller
    product_ids = [p.id for p in unique_products]
    
    # Calculate average purchase price
    avg_price = float(total_spent / total_quantity) if total_quantity > 0 else 0
    
    # Get purchase history by product
    purchases_by_product_raw = db.session.query(
        Product.id,
        Product.title,
        func.count(Purchase.id).label('purchase_count'),
        func.sum(Purchase.quantity).label('total_quantity'),
        func.sum(Purchase.total_cost).label('total_spent'),
        func.avg(Purchase.purchase_price).label('avg_price')
    ).join(Purchase, Purchase.product_id == Product.id)\
     .filter(
         Purchase.seller_id == id,
         Product.created_by == current_user.id  # User isolation
     )\
     .group_by(Product.id, Product.title)\
     .all()
    
    # Convert to proper types
    purchases_by_product = []
    for p in purchases_by_product_raw:
        purchases_by_product.append({
            'id': p.id,
            'title': p.title,
            'purchase_count': p.purchase_count,
            'total_quantity': int(p.total_quantity) if p.total_quantity else 0,
            'total_spent': float(p.total_spent) if p.total_spent else 0,
            'avg_price': float(p.avg_price) if p.avg_price else 0
        })
    
    # Get recent purchases (last 10)
    recent_purchases = seller.purchases.order_by(Purchase.purchase_date.desc()).limit(10).all()
    
    return render_template(
        'ecommerce/apps-ecommerce-sellers_details.html',
        seller=seller,
        purchases=purchases,
        total_purchases=total_purchases,
        total_quantity=total_quantity,
        total_spent=total_spent,
        avg_price=avg_price,
        unique_products=unique_products,
        purchases_by_product=purchases_by_product,
        recent_purchases=recent_purchases,
        product_ids=product_ids
    )


# ==================== ADD SELLER ====================
@sellers.route('/ecommerce/add_seller', methods=['POST'])
@login_required
def add_seller():
    """Add new seller - assigned to current user"""
    try:
        # Company Logo Upload
        logo_filename = None
        if 'company_logo' in request.files and request.files['company_logo'].filename:
            logo = request.files['company_logo']
            if logo.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                logo_filename = secure_filename(logo.filename)
                logo.save(os.path.join(current_app.config['UPLOAD_FOLDER'], logo_filename))
            else:
                flash('Invalid image format. Please upload PNG, JPG, JPEG, or GIF', 'warning')

        # Generate seller code
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        company_name = request.form.get('company_name', '').strip()
        
        # Create seller code (e.g., SEL-ABC-001)
        import random
        import string
        prefix = 'SEL'
        name_code = (company_name[:3] if company_name else first_name[:2] + last_name[:1]).upper()
        random_num = ''.join(random.choices(string.digits, k=3))
        seller_code = f"{prefix}-{name_code}-{random_num}"

        # Create seller with user isolation
        seller = Seller(
            first_name=first_name,
            last_name=last_name,
            contact_number=request.form.get('contact_number', '').strip(),
            email=request.form.get('email', '').strip(),
            city=request.form.get('city', '').strip(),
            country=request.form.get('country', '').strip(),
            company_name=company_name,
            company_email=request.form.get('company_email', '').strip(),
            work_number=request.form.get('work_number', '').strip(),
            company_logo=logo_filename,
            gst_number=request.form.get('gst_number', '').strip().upper(),
            seller_code=seller_code,  # Add seller code
            bank_name=request.form.get('bank_name', '').strip(),
            account_holder_name=request.form.get('account_holder_name', '').strip(),
            account_number=request.form.get('account_number', '').strip(),
            ifsc=request.form.get('ifsc', '').strip().upper(),
            created_by=current_user.id  # User isolation
        )

        # Validate required fields
        if not seller.first_name or not seller.last_name:
            flash('First name and last name are required!', 'danger')
            return redirect(url_for('sellers.seller_list'))

        db.session.add(seller)
        db.session.commit()

        flash(f'Seller {seller.get_full_name()} (Code: {seller_code}) added successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding seller: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('sellers.seller_list'))


# ==================== UPDATE SELLER ====================
@sellers.route('/ecommerce/seller/update/<int:id>', methods=['POST'])
@login_required
def update_seller(id):
    """Update seller with access check"""
    seller = Seller.query.get_or_404(id)
    
    # User isolation check
    if seller.created_by != current_user.id:
        flash('You do not have permission to update this seller', 'danger')
        return redirect(url_for('sellers.seller_list'))
    
    try:
        # Check if email already exists (if changed)
        new_email = request.form.get('email', '').strip()
        if new_email and new_email != seller.email:
            existing = Seller.query.filter_by(email=new_email).first()
            if existing and existing.id != seller.id:
                flash('Email already exists! Please use a different email.', 'danger')
                return redirect(url_for('sellers.seller_list'))
        
        # Update fields
        seller.first_name = request.form.get('first_name', seller.first_name).strip()
        seller.last_name = request.form.get('last_name', seller.last_name).strip()
        seller.contact_number = request.form.get('contact_number', seller.contact_number).strip()
        seller.email = new_email
        seller.city = request.form.get('city', seller.city).strip()
        seller.country = request.form.get('country', seller.country).strip()
        seller.company_name = request.form.get('company_name', seller.company_name).strip()
        seller.company_email = request.form.get('company_email', seller.company_email).strip()
        seller.work_number = request.form.get('work_number', seller.work_number).strip()
        seller.gst_number = request.form.get('gst_number', seller.gst_number).strip().upper()
        seller.bank_name = request.form.get('bank_name', seller.bank_name).strip()
        seller.account_holder_name = request.form.get('account_holder_name', seller.account_holder_name).strip()
        seller.account_number = request.form.get('account_number', seller.account_number).strip()
        seller.ifsc = request.form.get('ifsc', seller.ifsc).strip().upper()

        # Update Logo if new one uploaded
        if 'company_logo' in request.files and request.files['company_logo'].filename:
            logo = request.files['company_logo']
            if logo.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                filename = secure_filename(logo.filename)
                logo.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                
                # Delete old logo if exists
                if seller.company_logo:
                    old_logo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], seller.company_logo)
                    if os.path.exists(old_logo_path):
                        os.remove(old_logo_path)
                
                seller.company_logo = filename
            else:
                flash('Invalid image format. Logo not updated.', 'warning')

        db.session.commit()
        flash(f'Seller {seller.get_full_name()} updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating seller: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('sellers.seller_list'))


# ==================== DELETE SELLER ====================
@sellers.route('/ecommerce/seller/delete/<int:id>', methods=['POST'])
@login_required
def delete_seller(id):
    """Delete seller with access check"""
    seller = Seller.query.get_or_404(id)
    
    # User isolation check
    if seller.created_by != current_user.id:
        flash('You do not have permission to delete this seller', 'danger')
        return redirect(url_for('sellers.seller_list'))
    
    try:
        # Check if seller has any purchases
        if seller.purchases.count() > 0:
            flash(f'Cannot delete seller {seller.get_full_name()} because they have {seller.purchases.count()} purchase records!', 'warning')
            return redirect(url_for('sellers.seller_list'))
        
        # Delete company logo if exists
        if seller.company_logo:
            logo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], seller.company_logo)
            if os.path.exists(logo_path):
                os.remove(logo_path)
        
        seller_name = seller.get_full_name()
        db.session.delete(seller)
        db.session.commit()
        
        flash(f'Seller {seller_name} deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting seller: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('sellers.seller_list'))


# ==================== API ENDPOINTS ====================

@sellers.route('/api/seller/<int:id>')
@login_required
def get_seller_api(id):
    """API endpoint to get seller details - with access check"""
    seller = Seller.query.get_or_404(id)
    
    # User isolation check
    if seller.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get statistics
    purchases = seller.purchases
    total_purchases = purchases.count()
    total_quantity = purchases.with_entities(func.sum(Purchase.quantity)).scalar() or 0
    total_spent_val = purchases.with_entities(func.sum(Purchase.total_cost)).scalar()
    total_spent = float(total_spent_val) if total_spent_val is not None else 0
    
    # Get products supplied
    products = db.session.query(Product).distinct().join(
        Purchase, Purchase.product_id == Product.id
    ).filter(
        Purchase.seller_id == id,
        Product.created_by == current_user.id
    ).all()
    
    return jsonify({
        'id': seller.id,
        'first_name': seller.first_name,
        'last_name': seller.last_name,
        'full_name': seller.get_full_name(),
        'company_name': seller.company_name,
        'seller_code': seller.seller_code,
        'email': seller.email,
        'phone': seller.contact_number,
        'gst_number': seller.gst_number,
        'total_purchases': total_purchases,
        'total_quantity': int(total_quantity),
        'total_spent': total_spent,
        'products_supplied': len(products),
        'city': seller.city,
        'country': seller.country
    })


@sellers.route('/api/seller-stats')
@login_required
def seller_stats():
    """API endpoint for seller statistics - filtered by user"""
    sellers = Seller.query.filter_by(created_by=current_user.id).all()
    
    stats = []
    for seller in sellers:
        purchases = seller.purchases
        
        total_purchases = purchases.count()
        total_quantity_val = purchases.with_entities(func.sum(Purchase.quantity)).scalar()
        total_quantity = int(total_quantity_val) if total_quantity_val is not None else 0
        
        total_spent_val = purchases.with_entities(func.sum(Purchase.total_cost)).scalar()
        total_spent = float(total_spent_val) if total_spent_val is not None else 0
        
        avg_price = float(total_spent / total_quantity) if total_quantity > 0 else 0
        
        stats.append({
            'id': seller.id,
            'name': seller.get_full_name(),
            'company': seller.company_name,
            'code': seller.seller_code,
            'purchases': total_purchases,
            'quantity': total_quantity,
            'spent': total_spent,
            'avg_price': avg_price
        })
    
    # Sort by total spent (highest first)
    stats.sort(key=lambda x: x['spent'], reverse=True)
    
    return jsonify({
        'total_sellers': len(sellers),
        'top_sellers': stats[:5],
        'all_sellers': stats
    })


@sellers.route('/api/seller/<int:id>/purchases')
@login_required
def seller_purchases_api(id):
    """API endpoint to get all purchases from a seller"""
    seller = Seller.query.get_or_404(id)
    
    # User isolation check
    if seller.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    purchases = seller.purchases.order_by(Purchase.purchase_date.desc()).all()
    
    purchases_data = []
    for p in purchases:
        purchases_data.append({
            'id': p.id,
            'purchase_id': p.purchase_id,
            'date': p.purchase_date.strftime('%d %b %Y'),
            'product': p.product.title if p.product else 'Unknown',
            'product_id': p.product_id,
            'quantity': p.quantity,
            'price': float(p.purchase_price),
            'total_cost': float(p.total_cost)
        })
    
    total_spent_val = seller.purchases.with_entities(func.sum(Purchase.total_cost)).scalar()
    total_spent = float(total_spent_val) if total_spent_val is not None else 0
    
    return jsonify({
        'seller_id': seller.id,
        'seller_name': seller.get_full_name(),
        'total_purchases': len(purchases_data),
        'total_spent': total_spent,
        'purchases': purchases_data
    })


@sellers.route('/api/seller/<int:id>/products')
@login_required
def seller_products_api(id):
    """API endpoint to get all products supplied by a seller"""
    seller = Seller.query.get_or_404(id)
    
    # User isolation check
    if seller.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get unique products
    products = db.session.query(Product).distinct().join(
        Purchase, Purchase.product_id == Product.id
    ).filter(
        Purchase.seller_id == id,
        Product.created_by == current_user.id
    ).all()
    
    products_data = []
    for product in products:
        # Get purchase stats for this product from this seller
        purchases = Purchase.query.filter_by(
            seller_id=id, 
            product_id=product.id
        ).all()
        
        total_purchased = sum(p.quantity for p in purchases)
        total_spent = sum(float(p.total_cost) for p in purchases)
        avg_price = float(total_spent / total_purchased) if total_purchased > 0 else 0
        
        products_data.append({
            'id': product.id,
            'title': product.title,
            'sku': product.sku,
            'category': product.category,
            'total_purchased': total_purchased,
            'total_spent': total_spent,
            'avg_price': avg_price,
            'current_stock': product.get_current_stock(),
            'is_low_stock': product.is_low_stock()
        })
    
    return jsonify({
        'seller_id': seller.id,
        'seller_name': seller.get_full_name(),
        'total_products': len(products_data),
        'products': products_data
    })


# ==================== SELLER PURCHASE SUMMARY ====================
@sellers.route('/seller/<int:id>/purchase-summary')
@login_required
def purchase_summary(id):
    """Get purchase summary for a seller (monthly/quarterly)"""
    seller = Seller.query.get_or_404(id)
    
    # User isolation check
    if seller.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    current_year = datetime.now().year
    
    # Monthly summary for current year
    monthly_data = db.session.query(
        extract('month', Purchase.purchase_date).label('month'),
        func.count(Purchase.id).label('count'),
        func.sum(Purchase.quantity).label('quantity'),
        func.sum(Purchase.total_cost).label('total')
    ).filter(
        Purchase.seller_id == id,
        extract('year', Purchase.purchase_date) == current_year
    ).group_by(
        extract('month', Purchase.purchase_date)
    ).order_by(
        extract('month', Purchase.purchase_date)
    ).all()
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    summary = []
    for month in monthly_data:
        month_idx = int(month.month) - 1
        summary.append({
            'month': month_names[month_idx],
            'purchases': month.count,
            'quantity': int(month.quantity or 0),
            'total': float(month.total or 0)
        })
    
    # Yearly summary
    yearly_data = db.session.query(
        extract('year', Purchase.purchase_date).label('year'),
        func.count(Purchase.id).label('count'),
        func.sum(Purchase.quantity).label('quantity'),
        func.sum(Purchase.total_cost).label('total')
    ).filter(
        Purchase.seller_id == id
    ).group_by(
        extract('year', Purchase.purchase_date)
    ).order_by(
        extract('year', Purchase.purchase_date).desc()
    ).all()
    
    yearly_summary = []
    for year in yearly_data:
        yearly_summary.append({
            'year': int(year.year),
            'purchases': year.count,
            'quantity': int(year.quantity or 0),
            'total': float(year.total or 0)
        })
    
    return jsonify({
        'seller': seller.get_full_name(),
        'seller_code': seller.seller_code,
        'current_year': current_year,
        'monthly_summary': summary,
        'yearly_summary': yearly_summary
    })


# ==================== BULK SELLER IMPORT ====================
@sellers.route('/ecommerce/seller/bulk-import', methods=['POST'])
@login_required
def bulk_import():
    """Bulk import sellers from CSV"""
    if 'csv_file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('sellers.seller_list'))
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('sellers.seller_list'))
    
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file', 'danger')
        return redirect(url_for('sellers.seller_list'))
    
    import csv
    import io
    
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        success_count = 0
        error_count = 0
        
        for row in csv_input:
            try:
                # Generate seller code
                import random
                import string
                prefix = 'SEL'
                name_code = (row.get('company_name', '')[:3] if row.get('company_name') else 
                            row.get('first_name', '')[:2] + row.get('last_name', '')[:1]).upper()
                random_num = ''.join(random.choices(string.digits, k=3))
                seller_code = f"{prefix}-{name_code}-{random_num}"
                
                seller = Seller(
                    first_name=row.get('first_name', '').strip(),
                    last_name=row.get('last_name', '').strip(),
                    contact_number=row.get('contact_number', '').strip(),
                    email=row.get('email', '').strip(),
                    city=row.get('city', '').strip(),
                    country=row.get('country', '').strip(),
                    company_name=row.get('company_name', '').strip(),
                    company_email=row.get('company_email', '').strip(),
                    work_number=row.get('work_number', '').strip(),
                    gst_number=row.get('gst_number', '').strip().upper(),
                    seller_code=seller_code,
                    bank_name=row.get('bank_name', '').strip(),
                    account_holder_name=row.get('account_holder_name', '').strip(),
                    account_number=row.get('account_number', '').strip(),
                    ifsc=row.get('ifsc', '').strip().upper(),
                    created_by=current_user.id
                )
                
                db.session.add(seller)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"Error importing row: {e}")
        
        db.session.commit()
        flash(f'Bulk import completed: {success_count} sellers added, {error_count} errors', 'success')
        
    except Exception as e:
        flash(f'Error processing CSV: {str(e)}', 'danger')
    
    return redirect(url_for('sellers.seller_list'))


# ==================== SELLER PERFORMANCE ====================
@sellers.route('/api/seller-performance')
@login_required
def seller_performance():
    """Get seller performance metrics"""
    sellers = Seller.query.filter_by(created_by=current_user.id).all()
    
    performance_data = []
    for seller in sellers:
        purchases = seller.purchases
        
        total_purchases = purchases.count()
        if total_purchases == 0:
            continue
            
        total_quantity = purchases.with_entities(func.sum(Purchase.quantity)).scalar() or 0
        total_spent = purchases.with_entities(func.sum(Purchase.total_cost)).scalar() or 0
        
        # Get last purchase date
        last_purchase = purchases.order_by(Purchase.purchase_date.desc()).first()
        last_purchase_date = last_purchase.purchase_date.strftime('%Y-%m-%d') if last_purchase else None
        
        # Get unique products
        unique_products = purchases.distinct(Purchase.product_id).count()
        
        performance_data.append({
            'id': seller.id,
            'name': seller.get_full_name(),
            'company': seller.company_name,
            'code': seller.seller_code,
            'total_purchases': total_purchases,
            'total_quantity': int(total_quantity),
            'total_spent': float(total_spent),
            'unique_products': unique_products,
            'last_purchase': last_purchase_date,
            'avg_purchase_value': float(total_spent / total_purchases) if total_purchases > 0 else 0
        })
    
    # Sort by total spent
    performance_data.sort(key=lambda x: x['total_spent'], reverse=True)
    
    return jsonify({
        'total_sellers': len(performance_data),
        'performance': performance_data
    })