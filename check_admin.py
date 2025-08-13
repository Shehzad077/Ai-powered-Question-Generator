from app import app, db, User
from werkzeug.security import generate_password_hash

def check_admin():
    with app.app_context():
        admin = User.query.filter_by(email='admin@gmail.com').first()
        if admin:
            print(f"Admin exists: {admin.name}")
            print(f"Admin is_admin: {admin.is_admin}")
        else:
            print("Admin user not found. Creating...")
            admin_user = User(
                name="Admin",
                email="admin@gmail.com",
                password_hash=generate_password_hash("admin123"),
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created successfully!")
            print("Email: admin@mcq.com")
            print("Password: admin123")

if __name__ == "__main__":
    check_admin() 
