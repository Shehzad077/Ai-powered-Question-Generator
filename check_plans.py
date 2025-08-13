from app import app, db, Plan

def check_plans():
    with app.app_context():
        plans = Plan.query.all()
        print(f"Found {len(plans)} plans:")
        for plan in plans:
            print(f"- {plan.name}: ₨{plan.price_pkr} (MCQ: {plan.mcq_limit}, Short: {plan.short_limit}, Long: {plan.long_limit})")

if __name__ == "__main__":
    check_plans() 