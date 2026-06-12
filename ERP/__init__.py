from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret-key'


    app.config['SQLALCHEMY_DATABASE_URI'] = (
        "mysql+pymysql://root:user:pass@localhost:3306/erp"
 
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

    

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    login_manager = LoginManager()
    login_manager.login_view = 'account.login'
    login_manager.init_app(app)

    db.init_app(app)

    from .models import users 
    with app.app_context():
        db.create_all()

    @login_manager.user_loader
    def load_user(user_id):
        return users.query.get(int(user_id))
    


    # Add this function to convert numbers to words
    def wordize(number):
        """Convert number to words (for invoice amount)"""
        ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
        teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 
                'Seventeen', 'Eighteen', 'Nineteen']
        tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
        
        def convert(n):
            if n == 0:
                return ''
            elif n < 10:
                return ones[n]
            elif n < 20:
                return teens[n - 10]
            elif n < 100:
                return tens[n // 10] + ' ' + convert(n % 10)
            elif n < 1000:
                return ones[n // 100] + ' Hundred ' + convert(n % 100)
            else:
                return str(n) + ' (Number too large)'
        
        return convert(number)

    # Register the filter with Jinja2
    app.jinja_env.filters['wordize'] = wordize

    from .dashboards import dashboards
    from .apps import apps
    from .layouts import layouts
    from .account import account
    from .components import components
    from .products import products   # 👈 make sure this line has NO indent
    from .customers import customers
    from .sellers import sellers
    from .orders import orders
    from .purchase import purchases



    app.register_blueprint(dashboards)
    app.register_blueprint(apps)
    app.register_blueprint(layouts)
    app.register_blueprint(account)
    app.register_blueprint(components)
    app.register_blueprint(products)
    app.register_blueprint(customers)
    app.register_blueprint(sellers)
    app.register_blueprint(orders)
    app.register_blueprint(purchases)

    return app