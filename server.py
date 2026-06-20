import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

MONGODB_URI = os.getenv("MONGODB_URI")
PORT = int(os.getenv("PORT", 8080))

client = MongoClient(MONGODB_URI)
db = client['mall_shopping_system']

# --- SEED DATA ---
initial_shops = []
initial_deliveries = []

initial_settings = {
    "key": "global_config",
    "totalCouriersPool": 10,
    "baseDeliveryFee": 30.00,
    "perKmDeliveryFee": 10.00,
    "tieredCommissionRules": {
        "enabled": False,
        "tier1Limit": 5,
        "tier1Rate": 10,
        "tier2Limit": 10,
        "tier2Rate": 15,
        "tier3Rate": 20
    },
    "dailyCommissions": {}
}


# --- DATABASE SEEDING ---
def seed_database():
    try:
        if db.shops.count_documents({}) == 0:
            db.shops.insert_many(initial_shops)
            print("Seeded default shops into database.")
            
        if db.deliveries.count_documents({}) == 0:
            db.deliveries.insert_many(initial_deliveries)
            print("Seeded default deliveries into database.")
            
        if db.settings.count_documents({}) == 0:
            db.settings.insert_one(initial_settings)
            print("Seeded default settings into database.")
    except Exception as e:
        print("Database seeding error:", e)


# Run Seeding
seed_database()


# --- HELPER FUNCTIONS ---
def serialize_mongo(doc):
    if doc is None:
        return None
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc

def serialize_mongo_list(docs):
    return [serialize_mongo(doc) for doc in docs]


# --- API ROUTES ---

@app.route('/api/state', methods=['GET'])
def get_state():
    try:
        shops = list(db.shops.find({}))
        deliveries = list(db.deliveries.find({}))
        offers = list(db.offers.find({}))
        settings = db.settings.find_one({"key": "global_config"})
        if not settings:
            settings = initial_settings.copy()
            db.settings.insert_one(settings)
            
        return jsonify({
            "shops": serialize_mongo_list(shops),
            "deliveries": serialize_mongo_list(deliveries),
            "offers": serialize_mongo_list(offers),
            "settings": serialize_mongo(settings)
        })
    except Exception as e:
        print("Error fetching state:", e)
        return jsonify({"error": "Failed to fetch state"}), 500


@app.route('/api/state', methods=['POST'])
def update_state():
    try:
        data = request.json
        shops = data.get('shops')
        deliveries = data.get('deliveries')
        offers = data.get('offers')
        totalCouriersPool = data.get('totalCouriersPool', 10)
        baseDeliveryFee = data.get('baseDeliveryFee', 30.00)
        perKmDeliveryFee = data.get('perKmDeliveryFee', 10.00)
        dailyCommissions = data.get('dailyCommissions', {})
        tieredCommissionRules = data.get('tieredCommissionRules')

        # Sync Shops
        if isinstance(shops, list):
            db.shops.delete_many({})
            if shops:
                # Remove _id key to let MongoDB recreate them uniquely
                for s in shops:
                    s.pop('_id', None)
                db.shops.insert_many(shops)

        # Sync Deliveries
        if isinstance(deliveries, list):
            db.deliveries.delete_many({})
            if deliveries:
                # Remove _id key to let MongoDB recreate them uniquely
                for d in deliveries:
                    d.pop('_id', None)
                db.deliveries.insert_many(deliveries)

        # Sync Offers
        if isinstance(offers, list):
            db.offers.delete_many({})
            if offers:
                for o in offers:
                    o.pop('_id', None)
                db.offers.insert_many(offers)

        # Sync Settings
        db.settings.update_one(
            {"key": "global_config"},
            {"$set": {
                "totalCouriersPool": totalCouriersPool,
                "baseDeliveryFee": baseDeliveryFee,
                "perKmDeliveryFee": perKmDeliveryFee,
                "dailyCommissions": dailyCommissions,
                "tieredCommissionRules": tieredCommissionRules or initial_settings["tieredCommissionRules"]
            }},
            upsert=True
        )

        return jsonify({"success": True, "message": "Database state updated successfully."})
    except Exception as e:
        print("Error updating state:", e)
        return jsonify({"error": "Failed to sync state to database"}), 500


# --- STATIC FILE SERVING ---

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)


if __name__ == '__main__':
    print(f"Flask server is running on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=True)
