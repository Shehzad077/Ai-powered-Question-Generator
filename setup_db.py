from app import app, db, User, Plan
from werkzeug.security import generate_password_hash
from datetime import datetime

def setup_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
        
        # Create default plans if they don't exist
        if not Plan.query.first():
            default_plans = [
                Plan(name='Free', price_pkr=0, duration_days=30, mcq_limit=10, short_limit=5, long_limit=2),
                Plan(name='Basic', price_pkr=500, duration_days=30, mcq_limit=50, short_limit=25, long_limit=10),
                Plan(name='Pro', price_pkr=1000, duration_days=30, mcq_limit=100, short_limit=50, long_limit=25),
                Plan(name='Enterprise', price_pkr=2000, duration_days=30, mcq_limit=-1, short_limit=-1, long_limit=-1)
            ]
            db.session.add_all(default_plans)
            db.session.commit()
            print("Default plans created successfully!")
        
        # Create admin user if it doesn't exist
        admin_email = "admin@mcq.com"
        if not User.query.filter_by(email=admin_email).first():
            admin_user = User(
                name="Admin",
                email=admin_email,
                password_hash=generate_password_hash("admin123"),
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created successfully!")
            print("Email: admin@mcq.com")
            print("Password: admin123")
        
        print("Database setup completed!")

if __name__ == "__main__":
    setup_database() 