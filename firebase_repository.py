from firebase_admin import db
from database_interface import DatabaseInterface
from split_logic import update_group_graph
import traceback
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
    def create_item_atomically(self, item_data):
        try:
            # 1. Generate unique ID
            item_ref = db.reference("items").push()
            item_id = item_ref.key
            item_data["itemId"] = item_id

            group_id = item_data["itemGroupId"]
            group_ref = db.reference(f"groups/{group_id}")

            def create_transaction(current_group):
                if current_group is None: return None
                
                # Fetch the denormalized name map from the group
                name_map = current_group.get("memberNames", {})
                
                # 🔥 DENORMALIZE PAYER NAMES
                payer_ids = item_data.get("itemPayer", [])
                item_data["itemPayerNames"] = [name_map.get(uid, "Unknown") for uid in payer_ids]
                
                # 🔥 DENORMALIZE SPLITTER NAMES
                splitter_ids = item_data.get("itemSpliter", [])
                item_data["itemSpliterNames"] = [name_map.get(uid, "Unknown") for uid in splitter_ids]

                # Standard logic: Add to history
                current_group.setdefault("groupItems", []).append(item_id)
                
                # Update split graph math
                from split_logic import update_group_graph
                p_id = payer_ids[0]
                values = item_data.get("itemSpliterValue", [])
                for i in range(len(splitter_ids)):
                    update_group_graph(current_group, p_id, splitter_ids[i], values[i])
                
                return current_group

            group_ref.transaction(create_transaction)
            
            # Save the fully denormalized item
            db.reference(f"items/{item_id}").set(item_data)
            return True, "item created"

        except Exception as e:
            return False, str(e)

    def delete_item_atomically(self, item_id):
        # 1. We must get the item data first to know what to reverse
        item_data = db.reference(f"items/{item_id}").get()
        if not item_data: return False, "Not found"

        group_id = item_data["itemGroupId"]
        group_ref = db.reference(f"groups/{group_id}")

        def delete_transaction(current_data):
            if current_data is None: return None
            
            # Remove from items history
            if "groupItems" in current_data:
                current_data["groupItems"] = [i for i in current_data["groupItems"] if i != item_id]

            # 🔥 REVERSE THE MATH
            # To delete: Payer becomes Receiver, Splitter becomes Payer
            payer_id = item_data["itemPayer"][0]
            for i, splitter_id in enumerate(item_data["itemSpliter"]):
                amount = item_data["itemSpliterValue"][i]
                # Notice the IDs are swapped: splitter_id is now the 'payer'
                update_group_graph(current_data, splitter_id, payer_id, amount)
            
            return current_data

        try:
            group_ref.transaction(delete_transaction)
            db.reference(f"items/{item_id}").delete()
            return True, "Deleted"
        except Exception as e:
            return False, str(e)
        
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
        
    # Inside FirebaseRepository class

    def delete_item_and_update_graph(self, item_id):
        # 1. Fetch Item details
        item = self.get_item(item_id)
        if not item:
            return False, "Item not found"

        group_id = item.get("itemGroupId")
        group_data = self.get_group(group_id)
        
        if group_data:
            # 2. Logic to REVERSE the graph
            # When deleting, the Splitters 'pay back' the Payer
            payer_id = item["itemPayer"][0]
            spliters = item.get("itemSpliter", [])
            values = item.get("itemSpliterValue", [])

            from split_logic import update_group_graph
            for i in range(len(spliters)):
                receiver_id = spliters[i]
                amt = float(values[i])
                # 🔥 REVERSE: Receiver becomes payer, Payer becomes receiver
                update_group_graph(group_data, receiver_id, payer_id, amt)

            # 3. Remove item from group's history list
            if "groupItems" in group_data and item_id in group_data["groupItems"]:
                group_data["groupItems"].remove(item_id)

            # 4. Save updated group state
            self.update_group(group_id, group_data)

        # 5. Finally delete the item record
        self.delete_item(item_id)
        return True, "Item deleted"