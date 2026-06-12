from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func, extract, or_
from . import db
from .models import Purchase, Product, Seller, InventoryMovement

# Blueprint name is 'purchases' (consistent with all url_for calls)
purchases = Blueprint('purchases', __name__, template_folder='templates', static_folder='static')


# ==================== LIST PURCHASES ====================
@purchases.route('/ecommerce/purchases')
@login_required
def purchase_list():
    """List all purchases - filtered by current user"""
    # Get filter parameters
    search = request.args.get('search', '')
    seller_id = request.args.get('seller_id', '')
    product_id = request.args.get('product_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Start with base query - USER ISOLATION
    query = Purchase.query.filter_by(created_by=current_user.id)\
                          .order_by(Purchase.purchase_date.desc())
    
    # Apply filters
    if search:
        query = query.join(Product).filter(
            or_(
                Product.title.ilike(f'%{search}%'),
                Purchase.purchase_id.ilike(f'%{search}%')
            )
        )
    
    if seller_id and seller_id.isdigit():
        query = query.filter(Purchase.seller_id == int(seller_id))
    
    if product_id and product_id.isdigit():
        query = query.filter(Purchase.product_id == int(product_id))
    
    if date_from:
        try:
            query = query.filter(Purchase.purchase_date >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    
    if date_to:
        try:
            query = query.filter(Purchase.purchase_date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            pass
    
    purchases = query.all()
    
    # Calculate statistics
    total_purchases = len(purchases)
    total_quantity = sum(p.quantity for p in purchases)
    total_cost = sum(p.total_cost for p in purchases)
    
    # Get all sellers and products for filters - USER ISOLATION
    sellers = Seller.query.filter_by(created_by=current_user.id).all()
    products = Product.query.filter_by(created_by=current_user.id).all()
    
    # Get low stock products for alert
    low_stock_products = [p for p in products if p.is_low_stock()]
    low_stock_count = len(low_stock_products)
    
    return render_template(
        'ecommerce/apps-ecommerce-purchases.html',
        purchases=purchases,
        sellers=sellers,
        products=products,
        total_purchases=total_purchases,
        total_quantity=total_quantity,
        total_cost=total_cost,
        low_stock_count=low_stock_count,
        low_stock_products=low_stock_products,
        search=search,
        seller_id=int(seller_id) if seller_id and seller_id.isdigit() else None,
        product_id=int(product_id) if product_id and product_id.isdigit() else None,
        date_from=date_from,
        date_to=date_to
    )


# ==================== ADD PURCHASE ====================
@purchases.route('/ecommerce/purchase/add', methods=['GET', 'POST'])
@login_required
def add_purchase():
    """Add new purchase - increases stock"""
    if request.method == 'POST':
        try:
            # DEBUG: Print form data to see what's being received
            print("=" * 50)
            print("ADD PURCHASE FORM DATA:")
            for key, value in request.form.items():
                print(f"{key}: {value}")
            print("=" * 50)
            
            seller_id = request.form.get('seller_id')
            product_id = request.form.get('product_id')
            
            if not seller_id or not product_id:
                flash('Please select both seller and product', 'danger')
                return redirect(url_for('purchases.add_purchase'))
            
            seller_id = int(seller_id)
            product_id = int(product_id)
            
            quantity = int(request.form.get('quantity', 0))
            purchase_price = float(request.form.get('purchase_price', 0))
            
            # Validate inputs
            if quantity <= 0:
                flash('Quantity must be greater than zero', 'danger')
                return redirect(url_for('purchases.add_purchase'))
            
            if purchase_price <= 0:
                flash('Purchase price must be greater than zero', 'danger')
                return redirect(url_for('purchases.add_purchase'))
            
            # Get seller and product with user isolation check
            seller = Seller.query.filter_by(id=seller_id, created_by=current_user.id).first()
            product = Product.query.filter_by(id=product_id, created_by=current_user.id).first()
            
            if not seller:
                flash('Seller not found or access denied', 'danger')
                return redirect(url_for('purchases.add_purchase'))
            
            if not product:
                flash('Product not found or access denied', 'danger')
                return redirect(url_for('purchases.add_purchase'))
            
            # Calculate total cost
            total_cost = quantity * purchase_price
            
            # Create purchase record with user isolation
            purchase = Purchase(
                seller_id=seller_id,
                product_id=product_id,
                quantity=quantity,
                purchase_price=purchase_price,
                total_cost=total_cost,
                purchase_date=datetime.utcnow(),
                created_by=current_user.id  # CRITICAL: Add user isolation
            )
            
            # The purchase_id will be auto-generated by the model's __init__
            
            db.session.add(purchase)
            db.session.flush()  # Get purchase ID to use in reference
            
            # Get current stock before update
            old_stock = product.get_current_stock() - quantity  # Before this purchase
            new_stock = product.get_current_stock()  # After this purchase
            
            # Create inventory movement (stock IN)
            movement = InventoryMovement(
                product_id=product_id,
                quantity_change=quantity,
                previous_stock=old_stock,
                new_stock=new_stock,
                movement_type='purchase',
                reference_id=purchase.purchase_id,  # Use the generated purchase_id
                created_by=current_user.id,  # Add user isolation
                notes=f"Purchase from {seller.get_full_name()}"
            )
            db.session.add(movement)
            
            db.session.commit()
            
            # Get updated stock
            new_stock = product.get_current_stock()
            
            flash(f'Purchase {purchase.purchase_id} added successfully! Stock increased by {quantity}. New stock: {new_stock}', 'success')
            return redirect(url_for('purchases.purchase_list'))
            
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
            return redirect(url_for('purchases.add_purchase'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding purchase: {str(e)}', 'danger')
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    # GET request - show form
    pre_selected_product = request.args.get('product_id')
    pre_selected_seller = request.args.get('seller_id')
    
    # User isolation for dropdowns
    sellers = Seller.query.filter_by(created_by=current_user.id).all()
    products = Product.query.filter_by(created_by=current_user.id).all()
    
    return render_template(
        'ecommerce/apps-ecommerce-add-purchase.html',
        sellers=sellers,
        products=products,
        pre_selected_product=int(pre_selected_product) if pre_selected_product and pre_selected_product.isdigit() else None,
        pre_selected_seller=int(pre_selected_seller) if pre_selected_seller and pre_selected_seller.isdigit() else None,
        edit_mode=False
    )


# ==================== EDIT PURCHASE ====================
@purchases.route('/ecommerce/purchase/edit/<int:id>', methods=['GET'])
@login_required
def edit_purchase(id):
    """Edit purchase form with access check"""
    purchase = Purchase.query.get_or_404(id)
    
    # User isolation check
    if purchase.created_by != current_user.id:
        flash('You do not have permission to edit this purchase', 'danger')
        return redirect(url_for('purchases.purchase_list'))
    
    if not purchase.product:
        flash('Product not found for this purchase', 'danger')
        return redirect(url_for('purchases.purchase_list'))
    
    if not purchase.seller:
        flash('Seller not found for this purchase', 'danger')
        return redirect(url_for('purchases.purchase_list'))
    
    # User isolation for dropdowns
    sellers = Seller.query.filter_by(created_by=current_user.id).all()
    products = Product.query.filter_by(created_by=current_user.id).all()
    
    return render_template(
        'ecommerce/apps-ecommerce-add-purchase.html',
        purchase=purchase,
        sellers=sellers,
        products=products,
        edit_mode=True
    )


# ==================== UPDATE PURCHASE ====================
@purchases.route('/ecommerce/purchase/update/<int:id>', methods=['POST'])
@login_required
def update_purchase(id):
    """Update purchase with stock adjustment"""
    purchase = Purchase.query.get_or_404(id)
    
    # User isolation check
    if purchase.created_by != current_user.id:
        flash('You do not have permission to update this purchase', 'danger')
        return redirect(url_for('purchases.purchase_list'))
    
    try:
        product = Product.query.filter_by(id=purchase.product_id, created_by=current_user.id).first()
        if not product:
            flash('Product not found or access denied', 'danger')
            return redirect(url_for('purchases.purchase_list'))
        
        old_quantity = purchase.quantity
        old_price = purchase.purchase_price
        
        quantity = int(request.form.get('quantity', old_quantity))
        purchase_price = float(request.form.get('purchase_price', old_price))
        
        if quantity <= 0:
            flash('Quantity must be greater than zero', 'danger')
            return redirect(url_for('purchases.edit_purchase', id=id))
        
        if purchase_price <= 0:
            flash('Purchase price must be greater than zero', 'danger')
            return redirect(url_for('purchases.edit_purchase', id=id))
        
        new_total_cost = quantity * purchase_price
        quantity_difference = quantity - old_quantity
        
        # Update purchase
        purchase.quantity = quantity
        purchase.purchase_price = purchase_price
        purchase.total_cost = new_total_cost
        
        # Get stock before update
        old_stock = product.get_current_stock() - quantity_difference  # Before adjustment
        new_stock = product.get_current_stock()  # After adjustment
        
        # Create inventory movement for adjustment
        movement = InventoryMovement(
            product_id=product.id,
            quantity_change=quantity_difference,
            previous_stock=old_stock,
            new_stock=new_stock,
            movement_type='purchase_adjustment',
            reference_id=f'PUR-ADJ-{purchase.purchase_id}',
            created_by=current_user.id,
            notes=f"Purchase #{purchase.purchase_id} updated: quantity changed from {old_quantity} to {quantity}"
        )
        db.session.add(movement)
        
        db.session.commit()
        
        flash(f'Purchase updated successfully! Stock adjusted by {quantity_difference:+d}. New stock: {new_stock}', 'success')
        
    except ValueError as e:
        flash(f'Invalid input: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating purchase: {str(e)}', 'danger')
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('purchases.purchase_list'))


# ==================== DELETE PURCHASE ====================
@purchases.route('/ecommerce/purchase/delete/<int:id>', methods=['POST'])
@login_required
def delete_purchase(id):
    """Delete purchase with stock adjustment"""
    purchase = Purchase.query.get_or_404(id)
    
    # User isolation check
    if purchase.created_by != current_user.id:
        flash('You do not have permission to delete this purchase', 'danger')
        return redirect(url_for('purchases.purchase_list'))
    
    try:
        product = Product.query.filter_by(id=purchase.product_id, created_by=current_user.id).first()
        if not product:
            flash('Product associated with this purchase not found', 'danger')
            return redirect(url_for('purchases.purchase_list'))
        
        current_stock = product.get_current_stock()
        if current_stock < purchase.quantity:
            flash(f'Cannot delete purchase: Current stock ({current_stock}) is less than purchase quantity ({purchase.quantity}). Stock mismatch detected.', 'danger')
            return redirect(url_for('purchases.purchase_list'))
        
        # Get stock before deletion
        old_stock = current_stock
        new_stock = old_stock - purchase.quantity
        
        # Create inventory movement for deletion (stock out)
        movement = InventoryMovement(
            product_id=product.id,
            quantity_change=-purchase.quantity,
            previous_stock=old_stock,
            new_stock=new_stock,
            movement_type='purchase_deleted',
            reference_id=f'PUR-DEL-{purchase.purchase_id}',
            created_by=current_user.id,
            notes=f"Purchase #{purchase.purchase_id} deleted, stock decreased by {purchase.quantity}"
        )
        db.session.add(movement)
        
        # Delete purchase
        purchase_id_display = purchase.purchase_id
        db.session.delete(purchase)
        db.session.commit()
        
        flash(f'Purchase {purchase_id_display} deleted successfully! Stock decreased by {purchase.quantity}. New stock: {new_stock}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting purchase: {str(e)}', 'danger')
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('purchases.purchase_list'))


# ==================== API: GET PURCHASE DETAILS ====================
@purchases.route('/api/purchase/<int:id>')
@login_required
def get_purchase_api(id):
    """API endpoint to get purchase details"""
    purchase = Purchase.query.get_or_404(id)
    
    # User isolation check
    if purchase.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'id': purchase.id,
        'purchase_id': purchase.purchase_id,
        'seller_id': purchase.seller_id,
        'seller_name': purchase.seller.get_full_name() if purchase.seller else 'Unknown',
        'product_id': purchase.product_id,
        'product_name': purchase.product.title if purchase.product else 'Unknown',
        'quantity': purchase.quantity,
        'purchase_price': purchase.purchase_price,
        'total_cost': purchase.total_cost,
        'purchase_date': purchase.purchase_date.strftime('%Y-%m-%d') if purchase.purchase_date else None
    })


# ==================== API: PURCHASE STATISTICS ====================
@purchases.route('/api/purchase-stats')
@login_required
def purchase_stats():
    """API endpoint for purchase statistics - filtered by user"""
    
    # Overall statistics
    purchases_query = Purchase.query.filter_by(created_by=current_user.id)
    
    total_purchases = purchases_query.count()
    total_quantity = purchases_query.with_entities(func.sum(Purchase.quantity)).scalar() or 0
    total_cost = purchases_query.with_entities(func.sum(Purchase.total_cost)).scalar() or 0
    
    # Monthly statistics for current year
    current_year = datetime.now().year
    
    monthly_stats = db.session.query(
        extract('month', Purchase.purchase_date).label('month'),
        func.count(Purchase.id).label('count'),
        func.sum(Purchase.quantity).label('quantity'),
        func.sum(Purchase.total_cost).label('cost')
    ).filter(
        Purchase.created_by == current_user.id,
        extract('year', Purchase.purchase_date) == current_year
    ).group_by(
        extract('month', Purchase.purchase_date)
    ).order_by(
        extract('month', Purchase.purchase_date)
    ).all()
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    monthly_data = []
    for stat in monthly_stats:
        month_idx = int(stat.month) - 1
        monthly_data.append({
            'month': month_names[month_idx],
            'purchases': stat.count,
            'quantity': int(stat.quantity or 0),
            'cost': float(stat.cost or 0)
        })
    
    # Top sellers by purchase volume
    top_sellers = db.session.query(
        Seller.id,
        Seller.first_name,
        Seller.last_name,
        Seller.company_name,
        func.count(Purchase.id).label('purchase_count'),
        func.sum(Purchase.quantity).label('total_quantity'),
        func.sum(Purchase.total_cost).label('total_spent')
    ).join(Purchase, Purchase.seller_id == Seller.id)\
     .filter(Purchase.created_by == current_user.id)\
     .group_by(Seller.id, Seller.first_name, Seller.last_name, Seller.company_name)\
     .order_by(func.sum(Purchase.total_cost).desc())\
     .limit(5)\
     .all()
    
    seller_data = []
    for seller in top_sellers:
        seller_data.append({
            'id': seller.id,
            'name': seller.company_name or f"{seller.first_name} {seller.last_name}",
            'purchases': seller.purchase_count,
            'quantity': int(seller.total_quantity or 0),
            'total_spent': float(seller.total_spent or 0)
        })
    
    return jsonify({
        'overall': {
            'total_purchases': total_purchases,
            'total_quantity': int(total_quantity),
            'total_cost': float(total_cost)
        },
        'monthly': monthly_data,
        'top_sellers': seller_data
    })


# ==================== API: CHECK STOCK BEFORE PURCHASE DELETE ====================
@purchases.route('/api/check-purchase-delete/<int:id>')
@login_required
def check_purchase_delete(id):
    """Check if purchase can be safely deleted"""
    purchase = Purchase.query.get_or_404(id)
    
    # User isolation check
    if purchase.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    product = Product.query.get(purchase.product_id)
    if not product:
        return jsonify({'can_delete': False, 'reason': 'Product not found'})
    
    current_stock = product.get_current_stock()
    
    if current_stock < purchase.quantity:
        return jsonify({
            'can_delete': False,
            'reason': f'Current stock ({current_stock}) is less than purchase quantity ({purchase.quantity})',
            'current_stock': current_stock,
            'purchase_quantity': purchase.quantity
        })
    
    return jsonify({
        'can_delete': True,
        'current_stock': current_stock,
        'new_stock': current_stock - purchase.quantity,
        'purchase_quantity': purchase.quantity
    })


# ==================== BULK PURCHASE IMPORT ====================
@purchases.route('/ecommerce/purchase/bulk-import', methods=['POST'])
@login_required
def bulk_import():
    """Bulk import purchases from CSV"""
    if 'csv_file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('purchases.purchase_list'))
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('purchases.purchase_list'))
    
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file', 'danger')
        return redirect(url_for('purchases.purchase_list'))
    
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
                if not row.get('seller_id') or not row.get('product_id'):
                    errors.append(f"Row {row_num}: Missing seller_id or product_id")
                    error_count += 1
                    continue
                
                seller_id = int(row.get('seller_id'))
                product_id = int(row.get('product_id'))
                quantity = int(row.get('quantity', 0))
                purchase_price = float(row.get('purchase_price', 0))
                
                # Check if seller and product exist and belong to user
                seller = Seller.query.filter_by(id=seller_id, created_by=current_user.id).first()
                product = Product.query.filter_by(id=product_id, created_by=current_user.id).first()
                
                if not seller:
                    errors.append(f"Row {row_num}: Seller ID {seller_id} not found or access denied")
                    error_count += 1
                    continue
                
                if not product:
                    errors.append(f"Row {row_num}: Product ID {product_id} not found or access denied")
                    error_count += 1
                    continue
                
                if quantity <= 0:
                    errors.append(f"Row {row_num}: Quantity must be positive")
                    error_count += 1
                    continue
                
                if purchase_price <= 0:
                    errors.append(f"Row {row_num}: Purchase price must be positive")
                    error_count += 1
                    continue
                
                total_cost = quantity * purchase_price
                
                # Parse date if provided
                purchase_date = datetime.utcnow()
                if row.get('purchase_date'):
                    try:
                        purchase_date = datetime.strptime(row.get('purchase_date'), '%Y-%m-%d')
                    except:
                        pass
                
                # Create purchase
                purchase = Purchase(
                    seller_id=seller_id,
                    product_id=product_id,
                    quantity=quantity,
                    purchase_price=purchase_price,
                    total_cost=total_cost,
                    purchase_date=purchase_date,
                    created_by=current_user.id
                )
                
                db.session.add(purchase)
                db.session.flush()
                
                # Create inventory movement
                movement = InventoryMovement(
                    product_id=product_id,
                    quantity_change=quantity,
                    previous_stock=product.get_current_stock() - quantity,
                    new_stock=product.get_current_stock(),
                    movement_type='purchase',
                    reference_id=purchase.purchase_id,
                    created_by=current_user.id,
                    notes=f"Bulk import purchase from {seller.get_full_name()}"
                )
                db.session.add(movement)
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        db.session.commit()
        
        if errors:
            for error in errors[:5]:
                flash(error, 'warning')
        
        flash(f'Bulk import completed: {success_count} purchases added, {error_count} errors', 
              'success' if success_count > 0 else 'danger')
        
    except Exception as e:
        flash(f'Error processing CSV: {str(e)}', 'danger')
    
    return redirect(url_for('purchases.purchase_list'))