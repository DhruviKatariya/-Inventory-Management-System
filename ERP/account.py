from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from .models import users  # Changed from User to users (matches your model)
from . import db

account = Blueprint('account', __name__, template_folder='templates', static_folder='static')

# Actual Auth pages (working)
@account.route('/account/login')
def login():
    return render_template('account/login.html')

@account.route('/account/login', methods=['POST'])
def login_post():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        # Find user by email
        user = users.query.filter_by(email=email).first()

        # FIXED: Use the check_password method from the model
        if not user or not user.check_password(password):  # ← Changed this line
            flash("Invalid Credentials", "danger")
            return redirect(url_for('account.login'))

        login_user(user, remember=remember)
        
        # Update last login time
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        flash(f"Welcome back, {user.full_name or user.username}!", "success")
        return redirect(url_for('dashboards.index'))

@account.route('/account/signup')
def signup():
    return render_template('account/signup.html')

@account.route('/account/signup', methods=['POST'])
def signup_post():
    email = request.form.get('email')
    username = request.form.get('username')
    password = request.form.get('password')
    full_name = request.form.get('full_name', username)

    # Check if user exists
    user_email = users.query.filter_by(email=email).first()
    user_username = users.query.filter_by(username=username).first()

    if user_email:
        flash("User email already exists", "danger")
        return redirect(url_for('account.signup'))
    if user_username:
        flash("Username already exists", "danger")
        return redirect(url_for('account.signup'))

    # FIXED: Use the model's set_password method
    new_user = users(
        email=email,
        username=username,
        full_name=full_name,
        role='admin',
        is_active=True,
        created_at=datetime.utcnow()
    )
    new_user.set_password(password)  # ← Changed this line

    db.session.add(new_user)
    db.session.commit()

    flash("Registration successful! Please login.", "success")
    return redirect(url_for('account.login'))

@account.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('account.login'))

# Optional: Profile page
@account.route('/account/profile')
@login_required
def profile():
    return render_template('account/profile.html', user=current_user)

# Optional: Change password
@account.route('/account/forgot-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Check current password
    if not current_user.check_password(current_password):
        flash("Current password is incorrect", "danger")
        return redirect(url_for('account.profile'))

    if new_password != confirm_password:
        flash("New passwords do not match", "danger")
        return redirect(url_for('account.profile'))

    if len(new_password) < 6:
        flash("Password must be at least 6 characters", "danger")
        return redirect(url_for('account.profile'))

    # Set new password
    current_user.set_password(new_password)
    db.session.commit()

    flash("Password changed successfully!", "success")
    return redirect(url_for('account.profile'))