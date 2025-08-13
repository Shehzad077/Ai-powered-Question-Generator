from app import app, db, User, Plan
from werkzeug.security import check_password_hash

def test_admin_login():
    with app.app_context():
        # Test admin user
        admin = User.query.filter_by(email='admin@mcq.com').first()
        if admin:
            print(f"✅ Admin user found: {admin.name}")
            print(f"✅ Admin is_admin: {admin.is_admin}")
            
            # Test password
            if check_password_hash(admin.password_hash, 'admin123'):
                print("✅ Admin password is correct")
            else:
                print("❌ Admin password is incorrect")
        else:
            print("❌ Admin user not found")

def test_plans():
    with app.app_context():
        plans = Plan.query.filter_by(is_active=True).all()
        print(f"✅ Found {len(plans)} active plans:")
        for plan in plans:
            print(f"  - {plan.name}: ₨{plan.price_pkr}")

def test_pricing_route():
    with app.test_client() as client:
        response = client.get('/pricing')
        if response.status_code == 200:
            print("✅ Pricing page loads successfully")
        else:
            print(f"❌ Pricing page failed: {response.status_code}")

if __name__ == "__main__":
    print("Testing Admin Login:")
    test_admin_login()
    print("\nTesting Plans:")
    test_plans()
    print("\nTesting Pricing Route:")
    test_pricing_route() 