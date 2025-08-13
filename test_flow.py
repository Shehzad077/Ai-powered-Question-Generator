from app import app, db, User, Plan
from werkzeug.security import check_password_hash

def test_complete_flow():
    with app.test_client() as client:
        print("🧪 Testing Complete Application Flow")
        print("=" * 50)
        
        # Test 1: Home page
        print("1. Testing Home Page...")
        response = client.get('/')
        if response.status_code == 200:
            print("   ✅ Home page loads")
        else:
            print(f"   ❌ Home page failed: {response.status_code}")
        
        # Test 2: Pricing page
        print("2. Testing Pricing Page...")
        response = client.get('/pricing')
        if response.status_code == 200:
            print("   ✅ Pricing page loads")
            # Check if plans are in the response
            if b'Free' in response.data and b'500' in response.data:
                print("   ✅ Plans are displayed correctly")
            else:
                print("   ❌ Plans not found in response")
        else:
            print(f"   ❌ Pricing page failed: {response.status_code}")
        
        # Test 3: Login page
        print("3. Testing Login Page...")
        response = client.get('/login')
        if response.status_code == 200:
            print("   ✅ Login page loads")
        else:
            print(f"   ❌ Login page failed: {response.status_code}")
        
        # Test 4: Admin login
        print("4. Testing Admin Login...")
        response = client.post('/login', data={
            'email': 'admin@mcq.com',
            'password': 'admin123'
        }, follow_redirects=True)
        if response.status_code == 200:
            print("   ✅ Admin login successful")
        else:
            print(f"   ❌ Admin login failed: {response.status_code}")
        
        # Test 5: Admin dashboard (after login)
        print("5. Testing Admin Dashboard...")
        response = client.get('/admin')
        if response.status_code == 200:
            print("   ✅ Admin dashboard accessible")
        else:
            print(f"   ❌ Admin dashboard failed: {response.status_code}")
        
        print("\n🎉 Testing Complete!")
        print("\n📋 Manual Testing Steps:")
        print("1. Open: http://127.0.0.1:5000")
        print("2. Click 'View Pricing' or go to: http://127.0.0.1:5000/pricing")
        print("3. Click 'Login' or go to: http://127.0.0.1:5000/login")
        print("4. Login with admin@mcq.com / admin123")
        print("5. Go to: http://127.0.0.1:5000/admin")

if __name__ == "__main__":
    test_complete_flow() 