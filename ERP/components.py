from flask import Blueprint,render_template
from flask_login import login_required


components = Blueprint('components',__name__,template_folder='templates',
    static_folder='static',)
    
#Charts pages
@components.route('/components/apexcharts/charts-apex-line')
@login_required
def charts_apex_line():
    return render_template('components/apexcharts/charts-apex-line.html')

@components.route('/components/apexcharts/charts-apex-area')
@login_required
def charts_apex_area():
    return render_template('components/apexcharts/charts-apex-area.html')  

@components.route('/components/apexcharts/charts-apex-column')
@login_required
def charts_apex_column():
    return render_template('components/apexcharts/charts-apex-column.html')       

@components.route('/components/apexcharts/charts-apex-bar')
@login_required
def charts_apex_bar():
    return render_template('components/apexcharts/charts-apex-bar.html')

@components.route('/components/apexcharts/charts-apex-candlestick')
@login_required
def charts_apex_candlestick():
    return render_template('components/apexcharts/charts-apex-candlestick.html')                  

@components.route('/components/apexcharts/charts-apex-treemap')
@login_required
def charts_apex_treemap():
    return render_template('components/apexcharts/charts-apex-treemap.html') 

@components.route('/components/charts-chartjs')
@login_required
def charts_chartjs():
    return render_template('components/charts-chartjs.html')    
