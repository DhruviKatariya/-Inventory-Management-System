# Inventory Management System

 Inventory Management System built using Flask and MySQL.

## Features
- Product Management
- Inventory Tracking
- Customer Management
- Order Management
- Seller Management
- Dashboard Analytics

## Technologies Used
- Python
- Flask
- MySQL
- HTML, CSS, JavaScript
- Bootstrap




# Inventory Management System  – Complete Business Management Suite

Inventory Management System is a full‑featured web application built with **Flask, MySQL, and Bootstrap** that helps businesses manage products, customers, sellers, purchase orders, sales orders, inventory, and financial reports – all with **multi‑user data isolation**.

## About this project

Recommendation systems are cool, but every business needs a solid **Inventory Management System** to run daily operations. This system provides an easy‑to‑use dashboard for:

- Managing products, stock levels, and low‑stock alerts  
- Tracking customers and their order history  
- Handling sellers, purchases, and inventory movement  
- Creating multi‑product sales orders with automatic tax/discount/profit calculation  
- Generating PDF invoices  

The entire application uses **user isolation** – each user sees only their own data, making it safe for multi‑tenant use.

## Demo

## Dashboard

![Dashboard](screenshots/dashbord.png)



![Dashboard](screenshots/dashbord2.png)
You can run the system locally after following the setup steps below.  
A live demo is not hosted, but you can try it on your own machine.

## Dataset has been used

This Inventory Management System does not rely on an external dataset. Instead, **you create your own data**:

- Products (title, category, price, stock)  
- Customers (name, email, phone, address)  
- Sellers (company, GST, bank details)  
- Purchase and sales orders  

All data is stored in a **MySQL database** that you set up. The database schema is automatically created when you run the application for the first time (thanks to Flask‑SQLAlchemy).

## Concept used to build the system

The core logic is built on:

- **Flask** – lightweight web framework for routing and templating  
- **Flask‑SQLAlchemy** – ORM to interact with MySQL  
- **Flask‑Login** – user authentication and session management  
- **Jinja2** – dynamic HTML templates  
- **Bootstrap 5** – responsive UI  
- **ApexCharts** – interactive dashboard charts  
- **CKEditor** – rich text product descriptions  

### Inventory & Profit Calculation

- **Stock movement** is tracked via `InventoryMovement` records.  
- Each purchase **increases** stock; each sale **decreases** stock.  
- Profit per order = (selling price – average purchase price) × quantity.  
- Low‑stock alerts appear when stock ≤ threshold (default 5).

### Cosine Similarity?

Not used here – this is an , not a recommendation engine. But the idea is similar: we match **products to purchases** and **customers to orders** using database relationships.

## How to run

### STEPS

1. Prerequisites
Make sure you have installed:

Python 3.10 or higher – Download Python

MySQL Server – Download MySQL

Git (optional, to clone the repo) – Download Git

2. Clone or Download the Project
If you have the code on GitHub:

bash
git clone https://github.com/DhruviKatariya/-Inventory-Management-System.git
cd your-erp-system
If you have the files locally, just navigate into that folder.

3. Create a Virtual Environment
Windows (Command Prompt or PowerShell)
bash
python -m venv venv
venv\Scripts\activate
macOS / Linux
bash
python3 -m venv venv
source venv/bin/activate
After activation, you should see (venv) at the beginning of your terminal prompt.

4. Install Required Libraries
Create a file named requirements.txt in the project root with the following content:

text
Flask==2.3.3
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.2
PyMySQL==1.1.0
Werkzeug==2.3.7
Then install all dependencies:

bash
pip install -r requirements.txt
Alternative: install one by one:

bash
pip install Flask Flask-SQLAlchemy Flask-Login PyMySQL Werkzeug
5. Set Up MySQL Database
5.1 Start MySQL Server
On Windows: MySQL usually starts as a service. You can start it via “Services” or run net start MySQL in Administrator CMD.

On macOS/Linux: sudo systemctl start mysql or sudo service mysql start.

5.2 Create a Database
Open MySQL command line (or use a GUI like phpMyAdmin, DBeaver, or MySQL Workbench) and run:

sql
CREATE DATABASE erp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
5.3 Configure Database Connection in the Project
Open the file __init__.py and locate the line:

python
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://rootuser:pass@localhost:3306/erp"
Replace root and user:pass with your MySQL username and password.
If your password contains special characters like @, you need to URL‑encode them. For example, user:pass becomes user:pass.
If your password has no special characters, just write it normally.

Example for a simple password mypass:

python
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:mypass@localhost:3306/erp"
Note: The database name is erp (as created above).

6. Run the Application
Make sure your virtual environment is still activated.

From the project root directory (the folder that contains __init__.py), run:

bash
flask run
If that doesn’t work, try:

bash
python -m flask run
Or if you have a run.py file:

bash
python run.py
You should see output like:

text
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
Now open your browser and go to http://127.0.0.1:5000.

7. First-Time Setup (Create Tables)
The first time you run the app, it will automatically create all the database tables (db.create_all() is called inside create_app).
You do not need to run any separate migration command.

8. Register and Login
Click on Sign Up to create a new account.

After registration, log in with your email and password.

The first user becomes the admin.

You can now start adding products, sellers, customers, and purchases.


