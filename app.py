import firebase_admin
from firebase_admin import credentials, auth, db
from flask import Flask, request, jsonify
from firebase_repository import FirebaseRepository
from split_logic import update_group_graph
import traceback,os




# Initialize
cred_path = os.path.join("/etc/secrets/", "firebase.json") # production
# cred_path = os.path.join(os.path.dirname(file), "firebase.json") # development
# cred_path = os.path.join("C:\\Users\\aman2\\Desktop\\Payplit\\host\\apirepo", "firebase.json") # development
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred, {"databaseURL": "https://myproject-b3962-default-rtdb.firebaseio.com/"})

app = Flask(__name__)
repo = FirebaseRepository()

def safe_res(status, msg, data=None, code=200):
    if data is None: data = {}
    return jsonify({"status": status, "message": msg, "data": data}), code


@app.route("/", methods=["GET"])
def check():
    return safe_res("success", "API running OK")

# ================================
# 👤 USERS SECTION
# ================================

@app.route("/v1/users/create", methods=["POST"])
def create_user():
    try:
        data = request.get_json(force=True)
        user_rec = auth.create_user(email=data['email'], password=data['password'], display_name=data['name'])
        uid = user_rec.uid
        user_data = {
            "userId": uid,
            "name": data['name'],
            "email": data['email'],
            "mobileNo": data.get('mobileNo', ""),
            "groupIds": []
        }
        repo.create_user(uid, user_data)
        return safe_res("success", "User created", {"userId": uid}, 201)
    except Exception as e:
        return safe_res("error", str(e), code=500)

@app.route("/v1/users/login", methods=["POST"])
def login():
    try:
        data = request.get_json(force=True)
        user = auth.get_user_by_email(data.get("email"))
        user_data = repo.get_user(user.uid)
        return safe_res("success", "Login successful", user_data)
    except:
        return safe_res("error", "User not found", code=404)

@app.route("/v1/users/groups", methods=["POST"])
def get_user_group_ids():
    """🔥 FIXED: This was the missing 404 route"""
    try:
        data = request.get_json(force=True)
        uid = data.get("userId")
        group_ids = repo.get_user_groups(uid)
        return safe_res("success", "Fetched", {"groups": group_ids})
    except:
        return safe_res("error", "Fail", code=500)

@app.route("/v1/users/<userId>", methods=["GET"])
def get_user_by_id(userId):
    user = repo.get_user(userId)
    return safe_res("success", "Fetched", {"user": user}) if user else safe_res("error", "Not found", code=404)


# ================================
# 👥 GROUPS SECTION
# ================================

@app.route("/v1/groups/create", methods=["POST"])
def create_group():
    try:
        data = request.get_json(force=True)
        group = repo.create_group(data)
        # Link group to all members
        for uid in group['groupMembers']:
            user = repo.get_user(uid)
            if user:
                user.setdefault("groupIds", [])
                if group['groupId'] not in user["groupIds"]:
                    user["groupIds"].append(group['groupId'])
                    repo.update_user(uid, user)
        return safe_res("success", "Group created", {"group": group}, 201)
    except:
        return safe_res("error", "Fail", code=500)

@app.route("/v1/groups/getGroup", methods=["POST"])
def get_group_by_id():
    """🔥 FIXED: Required for parallel fetching in Android"""
    try:
        data = request.get_json(force=True)
        gid = data.get("groupId")
        group = repo.get_group(gid)
        return safe_res("success", "Fetched", {"group": group}) if group else safe_res("error", "Not found", code=404)
    except:
        return safe_res("error", "Fail", code=500)

@app.route("/v1/groups/addMember", methods=["PUT"])
def add_member():
    try:
        data = request.get_json(force=True)
        email_key = data['memberEmail'].replace('.', '_dot_').replace('@', '_at_')
        lookup = repo.get_user_by_email_key(email_key)
        if not lookup: return safe_res("error", "User not found", code=404)
        
        mid = lookup['userId']
        gid = data['groupId']
        group = repo.get_group(gid)
        
        if mid not in group.get("groupMembers", []):
            group.setdefault("groupMembers", []).append(mid)
            # Denormalize name
            group.setdefault("memberNames", {})[mid] = repo.get_user(mid).get("name", "Unknown")
            # Init Graph
            group.setdefault("groupGraph", {}).setdefault(mid, {})
            for m in group["groupMembers"]:
                group["groupGraph"].setdefault(m, {})[mid] = 0
                group["groupGraph"][mid][m] = 0
            repo.update_group(gid, group)
            # Update user node
            user = repo.get_user(mid)
            user.setdefault("groupIds", []).append(gid)
            repo.update_user(mid, user)
            
        return safe_res("success", "Member added")
    except:
        return safe_res("error", "Fail", code=500)

@app.route("/v1/groups", methods=["DELETE"])
def delete_group():
    try:
        gid = request.get_json(force=True).get("groupId")
        group = repo.get_group(gid)
        if not group: return safe_res("error", "Not found", 404)
        # Cleanup Items
        for iid in group.get("groupItems", []): repo.delete_item(iid)
        # Cleanup Users
        for uid in group.get("groupMembers", []):
            u = repo.get_user(uid)
            if u:
                u["groupIds"] = [g for g in u.get("groupIds", []) if g != gid]
                repo.update_user(uid, u)
        repo.delete_group(gid)
        return safe_res("success", "Group deleted")
    except:
        return safe_res("error", "Fail", code=500)

@app.route("/v1/groups/membersDetail", methods=["POST"])
def get_members_detail():
    try:
        gid = request.get_json(force=True) # Expects raw groupId string
        group = repo.get_group(gid)
        if not group: return jsonify([]), 404
        users = [repo.get_user(uid) for uid in group.get("groupMembers", [])]
        return jsonify(users), 200
    except:
        return jsonify([]), 500


# ================================
# 💸 ITEMS SECTION
# ================================

@app.route("/v1/items/create", methods=["POST"])
def add_item():
    try:
        data = request.get_json(force=True)
        item = repo.create_item(data)
        group = repo.get_group(item["itemGroupId"])
        if group:
            group.setdefault("groupItems", []).append(item["itemId"])
            p_id = item["itemPayer"][0]
            for i, r_id in enumerate(item["itemSpliter"]):
                update_group_graph(group, p_id, r_id, item["itemSpliterValue"][i])
            repo.update_group(item["itemGroupId"], group)
            return "item created", 201
        return "Group not found", 404
    except:
        return "Error", 500

@app.route("/v1/groups/items", methods=["POST"])
def get_paginated_items():
    try:
        req = request.get_json(force=True)
        group = repo.get_group(req.get("groupId"))
        if not group or "groupItems" not in group: return jsonify([]), 200
        items = repo.get_paginated_items(group["groupItems"], req.get("limit", 10), req.get("offset", 0))
        return jsonify(items), 200
    except:
        return jsonify([]), 500

@app.route("/v1/items", methods=["DELETE"])
def delete_item():
    try:
        iid = request.args.get("itemId")
        # Logic to reverse graph should be here (optional for MVP)
        repo.delete_item(iid)
        return safe_res("success", "Deleted")
    except:
        return safe_res("error", "Fail", code=500)


# ================================
# 📊 SETTLEMENTS SECTION
# ================================

@app.route("/v1/groups/expenseDetail", methods=["POST"])
def get_global_settlement():
    try:
        gid = request.get_data(as_text=True).strip('"') # Matches your original string handling
        group = repo.get_group(gid)
        if not group or "groupGraph" not in group: return jsonify({"expenseDetail": []})
        lines = []
        for p_id, recs in group["groupGraph"].items():
            p_name = group["memberNames"].get(p_id, p_id)
            for r_id, amt in recs.items():
                if amt > 0:
                    r_name = group["memberNames"].get(r_id, r_id)
                    lines.append(f"{p_name} get back from {r_name}: ₹{amt}")
        return jsonify({"expenseDetail": lines}), 200
    except:
        return jsonify({"expenseDetail": []}), 500

@app.route("/v1/groups/expenseDetailbyCurrentUser", methods=["POST"])
def get_personal_settlement():
    try:
        data = request.get_json(force=True)
        gid = data.get("groupId")
        curr_id = data.get("currentUserId")
        group = repo.get_group(gid)
        if not group or "groupGraph" not in group: return jsonify({"expenseDetail": []})
        
        graph = group["groupGraph"]
        lines = []
        # Money you are owed
        if curr_id in graph:
            for r_id, amt in graph[curr_id].items():
                if amt > 0:
                    r_name = group["memberNames"].get(r_id, r_id)
                    lines.append(f"You get back from {r_name}: ₹{amt}")
        # Money you owe
        for p_id, recs in graph.items():
            if p_id != curr_id and curr_id in recs and recs[curr_id] > 0:
                p_name = group["memberNames"].get(p_id, p_id)
                lines.append(f"You owe {p_name}: ₹{recs[curr_id]}")
        return jsonify({"expenseDetail": lines}), 200
    except:
        return jsonify({"expenseDetail": []}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7000))
    app.run(host="0.0.0.0", port=port, debug=True)
