from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from datetime import datetime
import random

from . import db
from .models import Order   # make sure Order model exists


apps = Blueprint(
    'ecommerce',
    __name__,
    template_folder='templates',
    static_folder='static'
)



#Ecommerce Pages

#@apps.route('/ecommerce/products')
#@login_required
#def ecommerce_products():
 #   return render_template('ecommerce/apps-ecommerce-products.html')  

#@apps.route('/ecommerce/product_details')
#@login_required
#def ecommerce_product_details():
 #   return render_template('ecommerce/apps-ecommerce-product_details.html')    

#@apps.route('/ecommerce/add_product')
#@login_required
#def ecommerce_add_product():
 #   return render_template('ecommerce/apps-ecommerce-add_product.html') 

#@apps.route('/ecommerce/orders')
#@login_required
#def ecommerce_orders():
 #   return render_template('ecommerce/apps-ecommerce-orders.html')   

@apps.route('/ecommerce/order_details')
@login_required
def ecommerce_order_details():
    return render_template('ecommerce/apps-ecommerce-order_details.html')       

#@apps.route('/ecommerce/customer')
#@login_required
#def ecommerce_customer():
 #   return render_template('ecommerce/apps-ecommerce_customer.html')       

@apps.route('/ecommerce/cart')
@login_required
def ecommerce_cart():
    return render_template('ecommerce/apps-ecommerce_cart.html')   

@apps.route('/ecommerce/checkout')
@login_required
def ecommerce_checkout():
    return render_template('ecommerce/apps-ecommerce_checkout.html')  

#@apps.route('/ecommerce/sellers')
#@login_required
#def ecommerce_sellers():
 #   return render_template('ecommerce/apps-ecommerce_sellers.html')   

@apps.route('/ecommerce/seller_details')
@login_required
def ecommerce_seller_details():
    return render_template('ecommerce/apps-ecommerce-sellers_details.html')         





