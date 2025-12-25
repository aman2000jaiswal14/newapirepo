from decimal import Decimal

def update_group_balances(group_data, payer_id, receiver_id, amount, is_reversal=False):
    # Use the ledger to keep track of absolute debt
    balances = group_data.setdefault('groupBalance', {})
    
    # Initialize if missing (using strings for Decimal safety)
    p_bal = Decimal(str(balances.get(payer_id, 0)))
    r_bal = Decimal(str(balances.get(receiver_id, 0)))
    amt = Decimal(str(amount))

    if not is_reversal:
        balances[payer_id] = float(p_bal + amt)
        balances[receiver_id] = float(r_bal - amt)
    else:
        balances[payer_id] = float(p_bal - amt)
        balances[receiver_id] = float(r_bal + amt)

def optimal_account_balance(group_data):
    group_balance_list = group_data.get('groupBalance', {})
    
    pos_accounts = []
    neg_accounts = []
    
    for uid, balance in group_balance_list.items():
        val = Decimal(str(balance))
        if val > 0:
            pos_accounts.append([val, uid])
        elif val < 0:
            neg_accounts.append([abs(val), uid])

    # Greedy Sort
    pos_accounts.sort(key=lambda x: x[0], reverse=True)
    neg_accounts.sort(key=lambda x: x[0], reverse=True)

    # 🔥 FIX: Use a Dictionary structure to match Android DTO
    # Current Android DTO expects: { "userId": { "otherUserId": amount } }
    new_graph = {uid: {} for uid in group_data.get('groupMembers', [])}
    
    i = 0 # positive index
    j = 0 # negative index

    while i < len(pos_accounts) and j < len(neg_accounts):
        pos_val, pos_uid = pos_accounts[i]
        neg_val, neg_uid = neg_accounts[j]
        
        settle_amt = min(pos_val, neg_val)
        
        if settle_amt > 0:
            # Map structure: Payer (Positive) gets back from Receiver (Negative)
            # This matches your Android DTO: Map<String, Map<String, Double>>
            new_graph[pos_uid][neg_uid] = float(settle_amt)
        
        pos_accounts[i][0] -= settle_amt
        neg_accounts[j][0] -= settle_amt
        
        if pos_accounts[i][0] == 0: i += 1
        if neg_accounts[j][0] == 0: j += 1

    group_data['groupGraph'] = new_graph