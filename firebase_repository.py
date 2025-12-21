from firebase_admin import db
from database_interface import DatabaseInterface

class FirebaseRepository(DatabaseInterface):
    # --- USER LOGIC ---
    def create_user(self, uid, data):
        db.reference(f"users/{uid}").set(data)
        email_key = data['email'].replace(".", "_dot_").replace("@", "_at_")
        db.reference(f"usersAsEmailKey/{email_key}").set({"userId": uid})

    def get_user(self, uid):
        return db.reference(f"users/{uid}").get()

    def get_all_users(self):
        return db.reference("users").get() or {}

    def get_user_by_email(self, email):
        email_key = email.replace(".", "_dot_").replace("@", "_at_")
        lookup = db.reference(f"usersAsEmailKey/{email_key}").get()
        return self.get_user(lookup['userId']) if lookup else None

    def update_user(self, uid, data):
        db.reference(f"users/{uid}").update(data)
        
    # Inside FirebaseRepository class

    def get_user_groups(self, uid):
        user = self.get_user(uid)
        return user.get("groupIds", []) if user else []

    def get_user_by_email_key(self, email_key):
        return db.reference(f"usersAsEmailKey/{email_key}").get()        

    # --- GROUP LOGIC ---
    def create_group(self, data):
        # 🔥 DENORMALIZATION
        member_names = {}
        for uid in data.get("groupMembers", []):
            user = self.get_user(uid)
            member_names[uid] = user.get("name", "Unknown") if user else "Unknown"
        data["memberNames"] = member_names
        
        ref = db.reference("groups").push()
        data["groupId"] = ref.key
        ref.set(data)
        return data

    def get_group(self, group_id):
        return db.reference(f"groups/{group_id}").get()

    def get_all_groups(self, limit, start_at):
        query = db.reference("groups").order_by_key()
        if start_at: query = query.start_at(start_at)
        return query.limit_to_first(limit).get() or {}

    def update_group(self, group_id, data):
        db.reference(f"groups/{group_id}").update(data)

    def delete_group(self, group_id):
        db.reference(f"groups/{group_id}").delete()

    # --- ITEM LOGIC ---
    def create_item(self, data):
        # 🔥 DENORMALIZATION
        payer_id = data["itemPayer"][0]
        user = self.get_user(payer_id)
        data["payerName"] = user.get("name", "Unknown") if user else "Unknown"
        
        ref = db.reference("items").push()
        data["itemId"] = ref.key
        ref.set(data)
        return data

    def get_item(self, item_id):
        return db.reference(f"items/{item_id}").get()

    def get_all_items(self):
        return db.reference("items").get() or {}

    def get_paginated_items(self, item_ids, limit, offset):
        # 🔥 PAGINATION (Newest first)
        reversed_ids = item_ids[::-1]
        paginated_ids = reversed_ids[offset : offset + limit]
        items = []
        for iid in paginated_ids:
            item_data = self.get_item(iid)
            if item_data: items.append(item_data)
        return items

    def delete_item(self, item_id):
        db.reference(f"items/{item_id}").delete()