from app import db, User, app
from werkzeug.security import generate_password_hash

# Change these values as needed
admin_name = "Admin"
admin_email = "admin@gmail.com"
admin_password = "admin123"

with app.app_context():
    # Check if admin already exists
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        if not existing.is_admin:
            existing.is_admin = True
            db.session.commit()
            print("Admin privileges updated for existing user!")
        else:
            print("Admin already exists!")
    else:
        admin = User(
            name=admin_name,
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!") 
