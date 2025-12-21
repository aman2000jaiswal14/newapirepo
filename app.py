import firebase_admin
from firebase_admin import credentials, auth
from flask import Flask, request, jsonify
from firebase_repository import FirebaseRepository
from split_logic import update_group_graph
import traceback, os

# Initialize
cred_path = os.path.join("/etc/secrets/", "firebase.json") # production
# cred_path = os.path.join(os.path.dirname(file), "firebase.json") # development
# cred_path = os.path.join("C:\\Users\\aman2\\Desktop\\Payplit\\host\\apirepo", "firebase.json") # development
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred, {"databaseURL": "https://myproject-b3962-default-rtdb.firebaseio.com/"})

app = Flask(__name__)
repo = FirebaseRepository()

def safe_res(status, msg, data=None, code=200):
    return jsonify({"status": status, "message": msg, "data": data or {}}), code


@app.route("/", methods=["GET"])
def check():
    return safe_res("success", "API running OK")

@app.route("/v1/users/login", methods=["POST"])
def login():
    try:
        email = request.get_json().get("email")
        user = auth.get_user_by_email(email)
        user_data = repo.get_user(user.uid)
        return safe_res("success", "Login successful", user_data)
    except: return safe_res("error", "Invalid User", code=404)

@app.route("/v1/users/create", methods=["POST"])
def create_user():
    try:
        data = request.get_json()
        user_rec = auth.create_user(email=data['email'], password=data['password'], display_name=data['name'])
        data['userId'] = user_rec.uid
        del data['password'] # Don't store password in DB
        repo.create_user(user_rec.uid, data)
        return safe_res("success", "Created", {"userId": user_rec.uid}, 201)
    except Exception as e: return safe_res("error", str(e), code=500)

@app.route("/v1/groups/create", methods=["POST"])
def create_group():
    data = repo.create_group(request.get_json())
    for uid in data['groupMembers']:
        user = repo.get_user(uid)
        if user:
            user.setdefault("groupIds", []).append(data['groupId'])
            repo.update_user(uid, user)
    return safe_res("success", "Group Created", {"group": data}, 201)

@app.route("/v1/groups/items", methods=["POST"])
def get_group_items():
    req = request.get_json()
    group = repo.get_group(req.get("groupId"))
    if not group or "groupItems" not in group: return jsonify([]), 200
    items = repo.get_paginated_items(group["groupItems"], req.get("limit", 10), req.get("offset", 0))
    return jsonify(items), 200

@app.route("/v1/items/create", methods=["POST"])
def add_item():
    data = request.get_json()
    item = repo.create_item(data)
    group = repo.get_group(item["itemGroupId"])
    if group:
        group.setdefault("groupItems", []).append(item["itemId"])
        payer_id = item["itemPayer"][0]
        for i, receiver_id in enumerate(item["itemSpliter"]):
            update_group_graph(group, payer_id, receiver_id, item["itemSpliterValue"][i])
        repo.update_group(item["itemGroupId"], group)
        return "item created", 201
    return "Group not found", 404

@app.route("/v1/groups/addMember", methods=["PUT"])
def add_member():
    data = request.get_json()
    email_key = data['memberEmail'].replace('.', '_dot_').replace('@', '_at_')
    lookup = db.reference(f'usersAsEmailKey/{email_key}').get()
    if not lookup: return safe_res("error", "User not found", code=404)
    
    mid = lookup['userId']
    group = repo.get_group(data['groupId'])
    if mid not in group.get("groupMembers", []):
        group.setdefault("groupMembers", []).append(mid)
        group.setdefault("memberNames", {})[mid] = repo.get_user(mid).get("name")
        # Init graph for new member
        group.setdefault("groupGraph", {}).setdefault(mid, {})
        for m in group["groupMembers"]:
            group["groupGraph"].setdefault(m, {})[mid] = 0
            group["groupGraph"][mid][m] = 0
        repo.update_group(data['groupId'], group)
        
        user = repo.get_user(mid)
        user.setdefault("groupIds", []).append(data['groupId'])
        repo.update_user(mid, user)
    return safe_res("success", "Member added")

@app.route("/v1/groups", methods=["DELETE"])
def delete_group():
    gid = request.get_json().get("groupId")
    group = repo.get_group(gid)
    if not group: return safe_res("error", "Not found", 404)
    for iid in group.get("groupItems", []): repo.delete_item(iid)
    for uid in group.get("groupMembers", []):
        u = repo.get_user(uid)
        if u:
            u["groupIds"] = [g for g in u.get("groupIds", []) if g != gid]
            repo.update_user(uid, u)
    repo.delete_group(gid)
    return safe_res("success", "Deleted")

@app.route("/v1/groups/expenseDetail", methods=["POST"])
def get_global_detail():
    gid = request.get_json().get("groupId")
    group = repo.get_group(gid)
    if not group or "groupGraph" not in group: return jsonify({"expenseDetail": []})
    lines = []
    for p_id, recs in group["groupGraph"].items():
        p_name = group["memberNames"].get(p_id, p_id)
        for r_id, amt in recs.items():
            if amt > 0: lines.append(f"{p_name} get back from {group['memberNames'].get(r_id, r_id)}: ₹{amt}")
    return jsonify({"expenseDetail": lines})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7000))
    app.run(host="0.0.0.0", port=port, debug=True)