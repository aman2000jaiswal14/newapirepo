def update_group_graph(group_data, payer_id, receiver_id, amount):
    if receiver_id == payer_id: return
    amount = float(amount) + group_data['groupGraph'][payer_id].get(receiver_id, 0)
    group_data['groupGraph'][payer_id][receiver_id] = 0
    if amount == 0: return

    for member_id in group_data.get('groupMembers', []):
        if amount > 0 and member_id != receiver_id:
            extra = group_data['groupGraph'].get(receiver_id, {}).get(member_id, 0)
            flow = min(amount, extra)
            group_data['groupGraph'][receiver_id][member_id] -= flow
            if member_id != payer_id:
                group_data['groupGraph'][payer_id][member_id] = group_data['groupGraph'].get(payer_id, {}).get(member_id, 0) + flow
            amount -= flow
    if amount > 0:
        group_data['groupGraph'][payer_id][receiver_id] = group_data['groupGraph'].get(payer_id, {}).get(receiver_id, 0) + amount