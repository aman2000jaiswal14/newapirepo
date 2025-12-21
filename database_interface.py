from abc import ABC, abstractmethod

class DatabaseInterface(ABC):
    @abstractmethod
    def create_user(self, uid, data): pass
    @abstractmethod
    def get_user(self, uid): pass
    @abstractmethod
    def get_all_users(self): pass
    @abstractmethod
    def get_user_by_email(self, email): pass
    @abstractmethod
    def update_user(self, uid, data): pass

    @abstractmethod
    def create_group(self, data): pass
    @abstractmethod
    def get_group(self, group_id): pass
    @abstractmethod
    def get_all_groups(self, limit, start_at): pass
    @abstractmethod
    def update_group(self, group_id, data): pass
    @abstractmethod
    def delete_group(self, group_id): pass

    @abstractmethod
    def create_item(self, data): pass
    @abstractmethod
    def get_item(self, item_id): pass
    @abstractmethod
    def get_all_items(self): pass
    @abstractmethod
    def get_paginated_items(self, item_ids, limit, offset): pass
    @abstractmethod
    def delete_item(self, item_id): pass