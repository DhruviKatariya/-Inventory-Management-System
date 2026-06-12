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

1. **Clone the repository**

```bash
git clone https://github.com/DhruviKatariya/-Inventory-Management-System.git
